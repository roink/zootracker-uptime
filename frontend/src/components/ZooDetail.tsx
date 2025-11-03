import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

// Media query hook for responsive layout
function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mql = window.matchMedia(query);
    const handler = (e: MediaQueryListEvent) => { setMatches(e.matches); };
    setMatches(mql.matches);
    mql.addEventListener('change', handler);
    return () => { mql.removeEventListener('change', handler); };
  }, [query]);

  return matches;
}

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
import '../styles/zoo-detail.css';

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
  
  // Tab/Accordion state
  const [activeSection, setActiveSection] = useState('overview');
  const [openSections, setOpenSections] = useState(new Set(['overview']));
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  
  const navigate = useNavigate();
  const { lang: langParam } = useParams();
  const prefix = langParam ? `/${langParam}` : '';
  const { t } = useTranslation();
  const authFetch = useAuthFetch();
  const { isAuthenticated } = useAuth();
  const zooSlug = zoo.slug ?? null;
  const locale = langParam === 'de' ? 'de-DE' : 'en-US';
  const limit = 50;
  const isDesktop = useMediaQuery('(min-width: 992px)');

  // Toggle accordion section (mobile)
  const toggleAccordion = useCallback((sectionId: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionId)) {
        next.delete(sectionId);
      } else {
        next.add(sectionId);
      }
      return next;
    });
  }, []);

  // Handle tab keyboard navigation (desktop)
  const handleTabKeyDown = useCallback(
    (event: React.KeyboardEvent, index: number) => {
      const { key } = event;
      let nextIndex = index;
      if (key === 'ArrowLeft' || key === 'ArrowUp') {
        event.preventDefault();
        nextIndex = index > 0 ? index - 1 : tabRefs.current.length - 1;
      } else if (key === 'ArrowRight' || key === 'ArrowDown') {
        event.preventDefault();
        nextIndex = index < tabRefs.current.length - 1 ? index + 1 : 0;
      } else if (key === 'Home') {
        event.preventDefault();
        nextIndex = 0;
      } else if (key === 'End') {
        event.preventDefault();
        nextIndex = tabRefs.current.length - 1;
      }
      tabRefs.current[nextIndex]?.focus();
    },
    []
  );

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

  // Build sections array
  const sections = useMemo(() => {
    const result = [
      {
        id: 'overview',
        label: t('zoo.overviewTab'),
        render: () => (
          <>
            {zoo.address && (
              <div className="text-muted mb-3">
                📍 {zoo.address}
              </div>
            )}
            {zooDescription && (
              <div>
                {needsCollapse ? (
                  <>
                    {!descExpanded && (
                      <p className="pre-wrap">
                        {zooDescription.slice(0, MAX_DESC)}…
                      </p>
                    )}
                    <p
                      id="zoo-desc-full"
                      className={`pre-wrap collapse ${descExpanded ? 'show' : ''}`}
                    >
                      {zooDescription}
                    </p>
                    <button
                      className="btn btn-link p-0"
                      type="button"
                      onClick={() => { setDescExpanded((v) => !v); }}
                      aria-expanded={descExpanded}
                      aria-controls="zoo-desc-full"
                    >
                      {descExpanded ? t('zoo.showLess') : t('zoo.showMore')}
                    </button>
                  </>
                ) : (
                  <p className="pre-wrap">{zooDescription}</p>
                )}
              </div>
            )}
            <div className="mt-3">
              <span className="me-3">
                {t('zoo.visited')} {visited ? `☑️ ${t('zoo.yes')}` : `✘ ${t('zoo.no')}`}
              </span>
            </div>
          </>
        ),
      },
      {
        id: 'animals',
        label: t('zoo.animalsTab'),
        render: () => (
          <>
            <div className="animals-section-filters">
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
            <div className="animals-grid" aria-busy={animalsLoading}>
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

          </>
        ),
      },
      {
        id: 'visits',
        label: t('zoo.visitsTab'),
        render: () => (
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
        ),
      },
    ];
    return result;
  }, [
    t,
    zoo.address,
    zooDescription,
    needsCollapse,
    descExpanded,
    visited,
    filters,
    facets,
    isAuthenticated,
    langParam,
    authMessage,
    setAuthMessage,
    animalsError,
    animalsLoading,
    animals,
    prefix,
    tileLang,
    navigate,
    zoo.id,
    zooDisplayName,
    getAnimalName,
    sentinelRef,
    history,
    locale,
    historyLoading,
    historyError,
    formatHistoryDay,
    renderHistoryItem,
  ]);

  // Map section - only shown on desktop in the right column when overview tab is active
  const showDesktopMap = isDesktop && activeSection === 'overview' && Number.isFinite(zoo.latitude) && Number.isFinite(zoo.longitude);
  const mapSection = showDesktopMap ? (
    <div className="zoo-map-container">
      <LazyMap latitude={zoo.latitude} longitude={zoo.longitude} />
    </div>
  ) : null;

  return (
    <div className="zoo-detail-container">
      <div className="zoo-header">
        <HeadingTag>
          {zoo.city && <span className="city-prefix">{zoo.city}: </span>}
          {zoo.name}
          {favorite && (
            <span className="text-warning" role="img" aria-label={t('zoo.favoriteBadge')}>
              ★
            </span>
          )}
        </HeadingTag>
        <div className="d-flex flex-wrap gap-2 align-items-center mt-2">
          <button
            type="button"
            className={`btn btn-sm favorite-toggle ${favorite ? 'btn-warning' : 'btn-outline-secondary'}`}
            onClick={handleFavoriteToggle}
            disabled={favoritePending}
            aria-pressed={favorite}
          >
            <span className="favorite-icon" aria-hidden="true">★</span>
            <span>{favorite ? t('zoo.removeFavorite') : t('zoo.addFavorite')}</span>
          </button>
        </div>
        {favoriteError && (
          <div className="text-danger small mt-2" role="status">
            {favoriteError}
          </div>
        )}
      </div>

      {/* Mobile: Map always visible below header, above accordion */}
      {!isDesktop && Number.isFinite(zoo.latitude) && Number.isFinite(zoo.longitude) && (
        <div className="zoo-map-mobile mb-3">
          <LazyMap latitude={zoo.latitude} longitude={zoo.longitude} />
        </div>
      )}

      {/* Desktop: Tabs + content grid with sticky map */}
      {isDesktop ? (
        <div
          className="zoo-desktop-sections mt-3"
          role="region"
          aria-label="Zoo sections"
        >
          <div className="nav nav-tabs w-100" role="tablist">
            {sections.map((section, index) => (
              <button
                key={section.id}
                type="button"
                role="tab"
                className={`nav-link ${activeSection === section.id ? 'active' : ''}`}
                id={`${section.id}-tab`}
                aria-controls={`${section.id}-panel`}
                aria-selected={activeSection === section.id}
                onClick={() => { setActiveSection(section.id); }}
                onKeyDown={(event) => { handleTabKeyDown(event, index); }}
                ref={(node) => {
                  tabRefs.current[index] = node;
                }}
              >
                {section.label}
              </button>
            ))}
          </div>
          <div className="row g-4 g-lg-5 align-items-start mt-3">
            <div className={`col-12 ${mapSection ? 'col-lg-6 order-lg-1' : ''}`}>
              {sections.map((section) => (
                <div
                  key={section.id}
                  id={`${section.id}-panel`}
                  role="tabpanel"
                  aria-labelledby={`${section.id}-tab`}
                  className="zoo-tabpanel"
                  hidden={activeSection !== section.id}
                >
                  {section.render()}
                </div>
              ))}
            </div>
            {mapSection && (
              <div className="col-12 col-lg-6 order-lg-2">
                <div className="sticky-lg-top" style={{ top: '1rem' }}>
                  {mapSection}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Mobile: Accordion sections */
        <div className="accordion zoo-accordion" id="zoo-detail-sections">
          {sections.map((section) => {
            const open = openSections.has(section.id);
            return (
              <div className="accordion-item" key={section.id}>
                <h2 className="accordion-header" id={`${section.id}-heading`}>
                  <button
                    className={`accordion-button ${open ? '' : 'collapsed'}`}
                    type="button"
                    aria-expanded={open}
                    aria-controls={`${section.id}-collapse`}
                    onClick={() => { toggleAccordion(section.id); }}
                  >
                    {section.label}
                  </button>
                </h2>
                <div
                  id={`${section.id}-collapse`}
                  className={`accordion-collapse collapse ${open ? 'show' : ''}`}
                  aria-labelledby={`${section.id}-heading`}
                >
                  <div className="accordion-body">{section.render()}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Sighting Modal */}
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

// Old code to be removed starts here - will be cleaned up below
