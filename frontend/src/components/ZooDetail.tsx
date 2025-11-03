import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import { API } from '../api';
import AnimalFilters from './AnimalFilters';
import AnimalTile from './AnimalTile';
import LazyMap from './LazyMap';
import SightingHistoryList from './SightingHistoryList';
import SightingModal from './SightingModal';
import { useAuth } from '../auth/AuthContext';
import { useAnimalFilters } from '../hooks/useAnimalFilters';
import useAuthFetch from '../hooks/useAuthFetch';
import { useInfiniteScroll } from '../hooks/useInfiniteScroll';
import type {
  Sighting,
  ZooAnimalFacetOption,
  ZooAnimalListing,
  ZooAnimalTile,
  ZooSummary,
} from '../types/domain';
import { formatSightingDayLabel } from '../utils/sightingHistory';
import { getZooDisplayName } from '../utils/zooDisplayName';

type HeadingLevel = 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';

export interface ZooDetailData extends Omit<ZooSummary, 'slug' | 'is_favorite'> {
  slug?: string | null;
  description_en?: string | null;
  description_de?: string | null;
  address?: string | null;
  country?: string | null;
  seo_description_en?: string | null;
  seo_description_de?: string | null;
  is_favorite?: boolean | null;
}

interface ModalState {
  zooId: string;
  zooName: string;
  animalId: string;
  animalName: string;
}

interface ZooDetailProps {
  zoo: ZooDetailData;
  displayName?: string;
  headingLevel?: HeadingLevel;
  refresh?: number;
  onLogged?: () => void;
  onFavoriteChange?: (nextFavorite: boolean) => void;
}

type ZooAnimalFacetsState = {
  classes: ZooAnimalFacetOption[];
  orders: ZooAnimalFacetOption[];
  families: ZooAnimalFacetOption[];
};

// Detailed view for a single zoo with a list of resident animals.
// Used by the ZooDetailPage component.
export default function ZooDetail({
  zoo,
  displayName,
  headingLevel = 'h2',
  refresh = 0,
  onLogged,
  onFavoriteChange,
}: ZooDetailProps) {
  // Use shared filter hook
  const filters = useAnimalFilters();
  
  // Local state
  const [animals, setAnimals] = useState<ZooAnimalTile[]>([]);
  const [facets, setFacets] = useState<ZooAnimalFacetsState>({
    classes: [],
    orders: [],
    families: [],
  });
  const [animalsLoading, setAnimalsLoading] = useState(false);
  const [animalsError, setAnimalsError] = useState('');
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [_total, setTotal] = useState(0);
  
  const [visited, setVisited] = useState(false);
  const [history, setHistory] = useState<Sighting[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(false);
  const [modalData, setModalData] = useState<ModalState | null>(null);
  const [descExpanded, setDescExpanded] = useState(false);
  const [favorite, setFavorite] = useState(false);
  const [favoritePending, setFavoritePending] = useState(false);
  const [favoriteError, setFavoriteError] = useState('');
  const [authMessage, setAuthMessage] = useState('');
  
  const navigate = useNavigate();
  const { lang: langParam } = useParams();
  const prefix = langParam ? `/${langParam}` : '';
  const { t } = useTranslation();
  const authFetch = useAuthFetch();
  const { isAuthenticated } = useAuth();
  const zooSlug = zoo.slug ?? null;
  const locale = langParam === 'de' ? 'de-DE' : 'en-US';
  const limit = 50;

  // Reset authentication-required filters when not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      if (filters.favoritesOnly) {
        filters.setFavoritesOnly(false);
      }
      if (filters.seenOnly) {
        filters.setSeenOnly(false);
      }
    } else {
      // Clear auth message when user logs in
      setAuthMessage('');
    }
  }, [isAuthenticated, filters]);

  // Clear auth message when filters change
  useEffect(() => {
    setAuthMessage('');
  }, [
    filters.query,
    filters.selectedClass,
    filters.selectedOrder,
    filters.selectedFamily,
  ]);
  // Helper: pick animal name in current language
  const getAnimalName = useCallback(
    (animal: ZooAnimalTile) =>
      langParam === 'de'
        ? animal.name_de || animal.name_en || ''
        : animal.name_en || animal.name_de || '',
    [langParam]
  );

  const getSightingAnimalName = useCallback(
    (sighting: Sighting) =>
      langParam === 'de'
        ? sighting.animal_name_de || sighting.animal_name_en || ''
        : sighting.animal_name_en || sighting.animal_name_de || '',
    [langParam]
  );

  const formatHistoryDay = useCallback(
    (day: string) =>
      formatSightingDayLabel(day, locale, {
        today: t('dashboard.today'),
        yesterday: t('dashboard.yesterday'),
      }),
    [locale, t]
  );

  const renderHistoryItem = useCallback(
    (sighting: Sighting, helpers: { formatTime: (value: string) => string | null }) => {
      const animalName = getSightingAnimalName(sighting);
      const timeLabel = helpers.formatTime(sighting.sighting_datetime);
      const message = timeLabel
        ? t('zoo.visitHistoryItemWithTime', {
            animal: animalName,
            time: timeLabel,
          })
        : t('zoo.visitHistoryItem', { animal: animalName });
      return (
        <>
          <div>{message}</div>
          {sighting.notes && (
            <div className="small text-muted mt-1">{sighting.notes}</div>
          )}
        </>
      );
    },
    [getSightingAnimalName, t]
  );

  const tileLang = langParam === 'de' ? 'de' : 'en';

  const handleFavoriteToggle = useCallback(async () => {
    if (!zooSlug) return;
    if (!isAuthenticated) {
      void navigate(`${prefix}/login`);
      return;
    }
    setFavoritePending(true);
    setFavoriteError('');
    try {
      const response = await authFetch(`${API}/zoos/${zooSlug}/favorite`, {
        method: favorite ? 'DELETE' : 'PUT',
      });
      if (!response.ok) {
        throw new Error('Failed to toggle favorite');
      }
      const payload = await response.json();
      const nextFavorite = Boolean((payload as { favorite?: unknown }).favorite);
      setFavorite(nextFavorite);
      onFavoriteChange?.(nextFavorite);
    } catch (_err) {
      setFavoriteError(t('zoo.favoriteError'));
    } finally {
      setFavoritePending(false);
    }
  }, [authFetch, favorite, isAuthenticated, navigate, onFavoriteChange, prefix, t, zooSlug]);

  // Fetch animals with pagination support
  const fetchZooAnimals = useCallback(
    async ({ reset = false, signal }: { reset?: boolean; signal?: AbortSignal } = {}) => {
      if (!zooSlug) {
        setAnimals([]);
        setFacets({ classes: [], orders: [], families: [] });
        setAnimalsError('');
        setAnimalsLoading(false);
        setHasMore(false);
        return;
      }

      setAnimalsLoading(true);
      setAnimalsError('');

      try {
        const currentOffset = reset ? 0 : offset;
        const params = new URLSearchParams();
        params.set('limit', String(limit));
        params.set('offset', String(currentOffset));
        if (filters.query) params.set('q', filters.query);
        if (filters.selectedClass !== null) params.set('class', String(filters.selectedClass));
        if (filters.selectedOrder !== null) params.set('order', String(filters.selectedOrder));
        if (filters.selectedFamily !== null) params.set('family', String(filters.selectedFamily));
        if (filters.seenOnly) params.set('seen', '1');
        if (filters.favoritesOnly) params.set('favorites', '1');

        const url = `${API}/zoos/${zooSlug}/animals?${params.toString()}`;
        const response = await authFetch(url, signal ? { signal } : {});

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const payload = (await response.json()) as ZooAnimalListing;
        const items = Array.isArray(payload.items) ? payload.items : [];
        const responseTotal = payload.total || 0;

        if (reset) {
          setAnimals(items);
          setOffset(items.length);
        } else {
          setAnimals((prev) => [...prev, ...items]);
          setOffset((prev) => prev + items.length);
        }

        setTotal(responseTotal);
        setHasMore(currentOffset + items.length < responseTotal);

        // Update facets (only on reset/initial load)
        if (reset) {
          const rawFacets = (payload as { facets?: unknown }).facets;
          const safeFacets =
            rawFacets && typeof rawFacets === 'object'
              ? (rawFacets as Partial<Record<'classes' | 'orders' | 'families', unknown>>)
              : {};
          const nextFacets: ZooAnimalFacetsState = {
            classes: Array.isArray(safeFacets.classes)
              ? (safeFacets.classes as ZooAnimalFacetOption[])
              : [],
            orders: Array.isArray(safeFacets.orders)
              ? (safeFacets.orders as ZooAnimalFacetOption[])
              : [],
            families: Array.isArray(safeFacets.families)
              ? (safeFacets.families as ZooAnimalFacetOption[])
              : [],
          };
          setFacets(nextFacets);
        }

        setAnimalsError('');
      } catch (_err) {
        if (signal?.aborted) {
          return;
        }
        if (reset) {
          setAnimals([]);
          setFacets({ classes: [], orders: [], families: [] });
        }
        setAnimalsError(t('zoo.animalsLoadError'));
        setHasMore(false);
      } finally {
        if (!signal?.aborted) {
          setAnimalsLoading(false);
        }
      }
    },
    [
      authFetch,
      filters.favoritesOnly,
      filters.query,
      filters.selectedClass,
      filters.selectedFamily,
      filters.selectedOrder,
      filters.seenOnly,
      limit,
      offset,
      t,
      zooSlug,
    ],
  );

  // Load more handler for infinite scroll
  const loadMore = useCallback(() => {
    if (!animalsLoading && hasMore) {
      void fetchZooAnimals({ reset: false });
    }
  }, [animalsLoading, fetchZooAnimals, hasMore]);

  // Use infinite scroll hook
  const sentinelRef = useInfiniteScroll({
    hasMore,
    loading: animalsLoading,
    onLoadMore: loadMore,
  });

  const loadVisited = useCallback(async () => {
    if (!isAuthenticated || !zooSlug) {
      setVisited(false);
      return;
    }
    try {
      const response = await authFetch(`${API}/zoos/${zooSlug}/visited`);
      if (!response.ok) {
        setVisited(false);
        return;
      }
      const result = (await response.json()) as { visited?: unknown };
      setVisited(Boolean(result.visited));
    } catch {
      setVisited(false);
    }
  }, [authFetch, isAuthenticated, zooSlug]);

  const fetchHistory = useCallback(
    async ({ signal, limit, offset }: { signal?: AbortSignal; limit?: number; offset?: number } = {}): Promise<Sighting[]> => {
      if (!zooSlug) {
        return [];
      }
      const params = new URLSearchParams();
      if (typeof limit === 'number') {
        params.set('limit', String(limit));
      }
      if (typeof offset === 'number' && offset > 0) {
        params.set('offset', String(offset));
      }
      const baseUrl = `${API}/zoos/${zooSlug}/sightings`;
      const url = params.size ? `${baseUrl}?${params.toString()}` : baseUrl;
      const response = await authFetch(url, signal ? { signal } : {});
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = (await response.json()) as unknown;
      if (data && typeof data === 'object' && Array.isArray((data as { items?: unknown }).items)) {
        return (data as { items: Sighting[] }).items.map((item) => item);
      }
      if (Array.isArray(data)) {
        return data as Sighting[];
      }
      return [];
    },
    [authFetch, zooSlug]
  );

  const loadHistory = useCallback(
    async ({ signal }: { signal?: AbortSignal } = {}) => {
      if (!isAuthenticated || !zooSlug) {
        setHistory([]);
        setHistoryError(false);
        setHistoryLoading(false);
        return;
      }
      setHistoryLoading(true);
      setHistoryError(false);
      try {
        const items = await fetchHistory(signal ? { signal } : {});
        setHistory(items);
        setHistoryError(false);
      } catch (err) {
        if (
          typeof err === 'object' &&
          err !== null &&
          'name' in err &&
          (err as { name?: unknown }).name === 'AbortError'
        ) {
          return;
        }
        setHistory([]);
        setHistoryError(true);
      } finally {
        if (!signal || !signal.aborted) {
          setHistoryLoading(false);
        }
      }
    },
    [fetchHistory, isAuthenticated, zooSlug]
  );

  const reloadLocalData = useCallback(() => {
    void fetchZooAnimals({ reset: true });
    void loadVisited();
    void loadHistory();
  }, [fetchZooAnimals, loadVisited, loadHistory]);

  // Reset and load animals when filters change
  useEffect(() => {
    const controller = new AbortController();
    void fetchZooAnimals({ reset: true, signal: controller.signal });
    return () => {
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    filters.query,
    filters.selectedClass,
    filters.selectedOrder,
    filters.selectedFamily,
    filters.seenOnly,
    filters.favoritesOnly,
    zooSlug,
    refresh,
  ]);

  useEffect(() => {
    setFavorite(Boolean(zoo.is_favorite));
    setFavoriteError('');
  }, [zoo.is_favorite]);

  // Load whether user has visited this zoo
  useEffect(() => {
    void loadVisited();
  }, [loadVisited, refresh]);

  useEffect(() => {
    const controller = new AbortController();
    void loadHistory({ signal: controller.signal });
    return () => { controller.abort(); };
  }, [loadHistory, refresh]);

  // pick description based on current language with fallback to generic text
  const zooDescription =
    langParam === 'de' ? zoo.description_de : zoo.description_en;
  const MAX_DESC = 400; // collapse threshold
  const needsCollapse = zooDescription && zooDescription.length > MAX_DESC;

  // Build the heading text by prefixing the city when available
  const zooDisplayName = displayName || getZooDisplayName(zoo);
  const allowedHeadingLevels: HeadingLevel[] = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'];
  const HeadingTag: HeadingLevel = allowedHeadingLevels.includes(headingLevel)
    ? headingLevel
    : 'h2';

  return (
    <div className="p-3">
      <HeadingTag className="h3 d-flex align-items-center gap-2">
        {zooDisplayName}
        {favorite && (
          <span className="text-warning" role="img" aria-label={t('zoo.favoriteBadge')}>
            ★
          </span>
        )}
      </HeadingTag>
      {zoo.address && <div className="text-muted">📍 {zoo.address}</div>}
      {Number.isFinite(zoo.latitude) && Number.isFinite(zoo.longitude) && (
        <div className="mt-1">
          <LazyMap latitude={zoo.latitude} longitude={zoo.longitude} />
        </div>
      )}
      {zooDescription && (
        <div className="card mt-3">
          <div className="card-body">
            <h5 className="card-title">{t('zoo.description')}</h5>
            {needsCollapse ? (
              <>
                {!descExpanded && (
                  <p className="card-text pre-wrap">
                    {zooDescription.slice(0, MAX_DESC)}…
                  </p>
                )}
                <p
                  id="zoo-desc-full"
                  className={`card-text pre-wrap collapse ${descExpanded ? 'show' : ''}`}
                >
                  {zooDescription}
                </p>
                <button
                  className="btn btn-link p-0"
                  type="button"
                  data-bs-toggle="collapse"
                  data-bs-target="#zoo-desc-full"
                  aria-expanded={descExpanded}
                  aria-controls="zoo-desc-full"
                  onClick={() => { setDescExpanded((v) => !v); }}
                >
                  {descExpanded ? t('zoo.showLess') : t('zoo.showMore')}
                </button>
              </>
            ) : (
              <p className="card-text pre-wrap">{zooDescription}</p>
            )}
          </div>
        </div>
      )}
      <div className="mt-2 d-flex flex-wrap gap-2 align-items-center">
        <span>
          {t('zoo.visited')} {visited ? `☑️ ${t('zoo.yes')}` : `✘ ${t('zoo.no')}`}
        </span>
        <button
          type="button"
          className={`btn btn-sm ${favorite ? 'btn-warning' : 'btn-outline-secondary'}`}
          onClick={handleFavoriteToggle}
          disabled={favoritePending}
          aria-pressed={favorite}
        >
          {favorite ? t('zoo.removeFavorite') : t('zoo.addFavorite')}
        </button>
      </div>
      {favoriteError && (
        <div className="text-danger small mt-1" role="status">
          {favoriteError}
        </div>
      )}
      <div className="mt-3">
        <h4>{t('zoo.visitHistoryHeading')}</h4>
        <SightingHistoryList
          sightings={history}
          locale={locale}
          isAuthenticated={isAuthenticated}
          loading={historyLoading}
          error={historyError}
          messages={{
            login: t('zoo.visitHistoryLogin'),
            loginCta: t('nav.login'),
            loading: t('zoo.visitHistoryLoading'),
            error: t('zoo.visitHistoryError'),
            empty: t('zoo.visitHistoryEmpty'),
          }}
          onLogin={() => {
            void navigate(`${prefix}/login`);
          }}
          formatDay={formatHistoryDay}
          renderSighting={renderHistoryItem}
        />
      </div>
      {/* visit logging removed - visits are created automatically from sightings */}
      <div className="mt-3">
        <h4>{t('zoo.animals')}</h4>
        <div className="mt-2">
          <AnimalFilters
            searchInput={filters.searchInput}
            onSearchChange={filters.setSearchInput}
            selectedClass={filters.selectedClass}
            onClassChange={filters.handleClassChange}
            selectedOrder={filters.selectedOrder}
            onOrderChange={filters.handleOrderChange}
            selectedFamily={filters.selectedFamily}
            onFamilyChange={filters.handleFamilyChange}
            seenOnly={filters.seenOnly}
            onSeenChange={filters.setSeenOnly}
            favoritesOnly={filters.favoritesOnly}
            onFavoritesChange={filters.setFavoritesOnly}
            classes={facets.classes}
            orders={facets.orders}
            families={facets.families}
            hasActiveFilters={filters.hasActiveFilters}
            onClearFilters={filters.clearAllFilters}
            isAuthenticated={isAuthenticated}
            lang={langParam || 'en'}
            showSeenFilter
            searchLabelKey="zoo.animalSearchLabel"
            onAuthRequired={setAuthMessage}
          />
        </div>
        {authMessage && (
          <div className="alert alert-info mt-3" role="status">
            {authMessage}
          </div>
        )}
        {animalsError && (
          <div className="alert alert-danger mt-3" role="alert">
            {animalsError}
          </div>
        )}
        <div
          className="animals-grid mt-3"
          aria-busy={animalsLoading}
          aria-describedby="zoo-animals-status"
        >
          {animals.map((animal) => (
            <AnimalTile
              key={animal.id}
              to={`${prefix}/animals/${animal.slug || animal.id}`}
              animal={animal}
              lang={tileLang}
              seen={Boolean(animal.seen)}
            >
              <button
                type="button"
                className="btn btn-sm btn-outline-secondary action-button-bottom-right"
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  if (!isAuthenticated) {
                    void navigate(`${prefix}/login`);
                    return;
                  }
                  setModalData({
                    zooId: zoo.id,
                    zooName: zooDisplayName,
                    animalId: animal.id,
                    animalName: getAnimalName(animal),
                  });
                }}
                aria-label={t('actions.logSighting')}
              >
                ➕
              </button>
            </AnimalTile>
          ))}
        </div>
        
        {/* Infinite scroll sentinel */}
        <div ref={sentinelRef} className="infinite-scroll-sentinel" aria-hidden="true" />
        
        {animalsLoading && (
          <div className="text-center my-3">
            <div className="spinner-border" role="status" aria-hidden="true" />
            <span className="visually-hidden">{t('actions.loading')}</span>
          </div>
        )}
        {!animalsLoading && animals.length === 0 && !animalsError && (
          <div className="alert alert-info mt-3" role="status">
            {t('zoo.noAnimalsMatch')}
          </div>
        )}
        {!animalsLoading && !hasMore && animals.length > 0 && (
          <div className="text-center my-3 text-muted small">
            {t('zoo.noMoreResults')}
          </div>
        )}
      </div>
      {modalData && (
        <SightingModal
          animals={null}
          defaultZooId={modalData.zooId}
          defaultAnimalId={modalData.animalId}
          defaultZooName={modalData.zooName}
          defaultAnimalName={modalData.animalName}
          onLogged={() => {
            onLogged?.();
            reloadLocalData();
          }}
          onClose={() => { setModalData(null); }}
        />
      )}
      </div>
    );
  }
