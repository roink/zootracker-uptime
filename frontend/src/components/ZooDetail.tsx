import { useState, useEffect, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { API } from '../api';
import AnimalTile from './AnimalTile';
import LazyMap from './LazyMap';
import SightingHistoryList from './SightingHistoryList';
import SightingModal from './SightingModal';
import { useAuth } from '../auth/AuthContext';
import useAuthFetch from '../hooks/useAuthFetch';
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

// Normalize URL parameters so filter comparisons stay stable.
function parseNumericParams(values: string[]): number[] {
  return values
    .map((value) => Number.parseInt(value, 10))
    .filter((value) => !Number.isNaN(value));
}

function normalizeNumericList(values: number[]): number[] {
  return Array.from(new Set(values)).sort((a, b) => a - b);
}

function arraysEqual(a: number[], b: number[]): boolean {
  if (a.length !== b.length) {
    return false;
  }
  return a.every((value, index) => value === b[index]);
}

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
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || '';
  const initialClasses = normalizeNumericList(parseNumericParams(searchParams.getAll('class')));
  const initialOrders = normalizeNumericList(parseNumericParams(searchParams.getAll('order')));
  const initialFamilies = normalizeNumericList(parseNumericParams(searchParams.getAll('family')));
  const initialSeenOnly = searchParams.get('seen') === '1';
  const initialFavoritesOnly = searchParams.get('favorites') === '1';
  const [searchInput, setSearchInput] = useState(initialQuery);
  const [query, setQuery] = useState(initialQuery.trim());
  const [selectedClasses, setSelectedClasses] = useState<number[]>(initialClasses);
  const [selectedOrders, setSelectedOrders] = useState<number[]>(initialOrders);
  const [selectedFamilies, setSelectedFamilies] = useState<number[]>(initialFamilies);
  const [seenOnly, setSeenOnly] = useState(initialSeenOnly);
  const [favoritesOnly, setFavoritesOnly] = useState(initialFavoritesOnly);
  const [animals, setAnimals] = useState<ZooAnimalTile[]>([]);
  const [inventoryAnimals, setInventoryAnimals] = useState<ZooAnimalTile[]>([]);
  const [facets, setFacets] = useState<ZooAnimalFacetsState>({
    classes: [],
    orders: [],
    families: [],
  });
  const [animalsLoading, setAnimalsLoading] = useState(false);
  const [animalsError, setAnimalsError] = useState('');
  const [visited, setVisited] = useState(false);
  const [history, setHistory] = useState<Sighting[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(false);
  const [modalData, setModalData] = useState<ModalState | null>(null);
  const navigate = useNavigate();
  const { lang: langParam } = useParams();
  const prefix = langParam ? `/${langParam}` : '';
  const { t } = useTranslation();
  const authFetch = useAuthFetch();
  const { isAuthenticated } = useAuth();
  const zooSlug = zoo.slug ?? null;
  const locale = langParam === 'de' ? 'de-DE' : 'en-US';
  const [descExpanded, setDescExpanded] = useState(false); // track full description visibility
  const [favorite, setFavorite] = useState(false);
  const [favoritePending, setFavoritePending] = useState(false);
  const [favoriteError, setFavoriteError] = useState('');
  const searchParamsSnapshot = useMemo(() => searchParams.toString(), [searchParams]);

  useEffect(() => {
    const urlQuery = searchParams.get('q') || '';
    if (urlQuery !== searchInput) {
      setSearchInput(urlQuery);
    }
    const trimmedUrlQuery = urlQuery.trim();
    setQuery((prev) => (prev === trimmedUrlQuery ? prev : trimmedUrlQuery));

    const nextClasses = normalizeNumericList(parseNumericParams(searchParams.getAll('class')));
    if (!arraysEqual(nextClasses, selectedClasses)) {
      setSelectedClasses(nextClasses);
    }
    const nextOrders = normalizeNumericList(parseNumericParams(searchParams.getAll('order')));
    if (!arraysEqual(nextOrders, selectedOrders)) {
      setSelectedOrders(nextOrders);
    }
    const nextFamilies = normalizeNumericList(parseNumericParams(searchParams.getAll('family')));
    if (!arraysEqual(nextFamilies, selectedFamilies)) {
      setSelectedFamilies(nextFamilies);
    }
    const nextSeen = searchParams.get('seen') === '1';
    if (nextSeen !== seenOnly) {
      setSeenOnly(nextSeen);
    }
    const nextFavorites = searchParams.get('favorites') === '1';
    if (nextFavorites !== favoritesOnly) {
      setFavoritesOnly(nextFavorites);
    }
  }, [
    favoritesOnly,
    searchInput,
    searchParams,
    selectedClasses,
    selectedFamilies,
    selectedOrders,
    seenOnly,
  ]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const trimmed = searchInput.trim();
      setQuery((prev) => (prev === trimmed ? prev : trimmed));
    }, 250);
    return () => {
      window.clearTimeout(handle);
    };
  }, [searchInput]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (query) {
      params.set('q', query);
    }
    selectedClasses.forEach((value) => {
      params.append('class', String(value));
    });
    selectedOrders.forEach((value) => {
      params.append('order', String(value));
    });
    selectedFamilies.forEach((value) => {
      params.append('family', String(value));
    });
    if (seenOnly) {
      params.set('seen', '1');
    }
    if (favoritesOnly) {
      params.set('favorites', '1');
    }
    const next = params.toString();
    if (next !== searchParamsSnapshot) {
      setSearchParams(params, { replace: true });
    }
  }, [
    favoritesOnly,
    query,
    searchParamsSnapshot,
    selectedClasses,
    selectedFamilies,
    selectedOrders,
    seenOnly,
    setSearchParams,
  ]);

  useEffect(() => {
    if (!isAuthenticated && favoritesOnly) {
      setFavoritesOnly(false);
    }
  }, [favoritesOnly, isAuthenticated]);
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

  const formatFacetLabel = useCallback(
    (facet: ZooAnimalFacetOption) =>
      langParam === 'de'
        ? facet.name_de || facet.name_en || String(facet.id)
        : facet.name_en || facet.name_de || String(facet.id),
    [langParam],
  );

  const toggleClassFacet = useCallback((value: number) => {
    setSelectedClasses((prev) =>
      normalizeNumericList(prev.includes(value) ? prev.filter((id) => id !== value) : [...prev, value]),
    );
  }, []);

  const toggleOrderFacet = useCallback((value: number) => {
    setSelectedOrders((prev) =>
      normalizeNumericList(prev.includes(value) ? prev.filter((id) => id !== value) : [...prev, value]),
    );
  }, []);

  const toggleFamilyFacet = useCallback((value: number) => {
    setSelectedFamilies((prev) =>
      normalizeNumericList(prev.includes(value) ? prev.filter((id) => id !== value) : [...prev, value]),
    );
  }, []);

  const renderFacetGroup = (
    group: 'classes' | 'orders' | 'families',
    options: ZooAnimalFacetOption[],
    selected: number[],
    onToggle: (value: number) => void,
    title: string,
    ariaKey: string,
  ) => {
    if (options.length === 0) {
      return null;
    }
    return (
      <fieldset className="mb-0">
        <legend className="fs-6 mb-1">{title}</legend>
        <div className="d-flex flex-wrap gap-2">
          {options.map((facet) => {
            const label = formatFacetLabel(facet);
            const isSelected = selected.includes(facet.id);
            const controlId = `facet-${group}-${facet.id}`;
            return (
              <div className="form-check form-check-inline" key={controlId}>
                <input
                  className="form-check-input"
                  type="checkbox"
                  id={controlId}
                  checked={isSelected}
                  onChange={() => {
                    onToggle(facet.id);
                  }}
                  aria-label={t(ariaKey, { classification: label })}
                />
                <label className="form-check-label" htmlFor={controlId}>
                  {label}
                  <span className="ms-1 text-muted small">({facet.count})</span>
                </label>
              </div>
            );
          })}
        </div>
      </fieldset>
    );
  };

  const animalsStatus = animalsLoading
    ? t('actions.loading')
    : t('zoo.animalsCount', { count: animals.length });

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

  const fetchZooAnimals = useCallback(
    async ({ signal }: { signal?: AbortSignal } = {}) => {
      if (!zooSlug) {
        setAnimals([]);
        setInventoryAnimals([]);
        setFacets({ classes: [], orders: [], families: [] });
        setAnimalsError('');
        setAnimalsLoading(false);
        return;
      }
      setAnimalsLoading(true);
      setAnimalsError('');
      try {
        const params = new URLSearchParams();
        if (query) params.set('q', query);
        selectedClasses.forEach((value) => {
          params.append('class', String(value));
        });
        selectedOrders.forEach((value) => {
          params.append('order', String(value));
        });
        selectedFamilies.forEach((value) => {
          params.append('family', String(value));
        });
        if (seenOnly) params.set('seen', '1');
        if (favoritesOnly) params.set('favorites', '1');
        const baseUrl = `${API}/zoos/${zooSlug}/animals`;
        const url = params.size ? `${baseUrl}?${params.toString()}` : baseUrl;
        const response = await authFetch(url, signal ? { signal } : {});
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = (await response.json()) as ZooAnimalListing;
        const items = Array.isArray(payload.items) ? payload.items : [];
        const inventory = Array.isArray(payload.inventory) ? payload.inventory : [];
        setAnimals(items);
        setInventoryAnimals(inventory);
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
        setAnimalsError('');
      } catch (_err) {
        if (signal?.aborted) {
          return;
        }
        setAnimals([]);
        setInventoryAnimals([]);
        setFacets({ classes: [], orders: [], families: [] });
        setAnimalsError(t('zoo.animalsLoadError'));
      } finally {
        if (!signal?.aborted) {
          setAnimalsLoading(false);
        }
      }
    },
    [
      authFetch,
      favoritesOnly,
      query,
      selectedClasses,
      selectedFamilies,
      selectedOrders,
      seenOnly,
      t,
      zooSlug,
    ],
  );

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
    void fetchZooAnimals();
    void loadVisited();
    void loadHistory();
  }, [fetchZooAnimals, loadVisited, loadHistory]);

  // Load animals for this zoo whenever filters or refresh token change
  useEffect(() => {
    const controller = new AbortController();
    void fetchZooAnimals({ signal: controller.signal });
    return () => {
      controller.abort();
    };
  }, [fetchZooAnimals, refresh]);

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
        <div className="card mt-2">
          <div className="card-body">
            <div className="row g-3 align-items-end">
              <div className="col-12 col-lg-4">
                <label className="form-label" htmlFor="zoo-animal-search">
                  {t('zoo.animalSearchLabel')}
                </label>
                  <input
                    id="zoo-animal-search"
                    type="search"
                    className="form-control"
                    value={searchInput}
                    onChange={(event) => {
                      setSearchInput(event.target.value);
                    }}
                    placeholder={t('zoo.animalSearchPlaceholder')}
                    autoComplete="off"
                  />
              </div>
              <div className="col-6 col-md-4 col-xl-2">
                <div className="form-check mt-4">
                    <input
                      className="form-check-input"
                      type="checkbox"
                      id="zoo-animal-filter-seen"
                      checked={seenOnly}
                      onChange={(event) => {
                        setSeenOnly(event.target.checked);
                      }}
                    />
                  <label className="form-check-label" htmlFor="zoo-animal-filter-seen">
                    {t('zoo.filterSeen')}
                  </label>
                </div>
              </div>
              {isAuthenticated && (
                <div className="col-6 col-md-4 col-xl-2">
                  <div className="form-check mt-4">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        id="zoo-animal-filter-favorites"
                        checked={favoritesOnly}
                        onChange={(event) => {
                          setFavoritesOnly(event.target.checked);
                        }}
                      />
                    <label className="form-check-label" htmlFor="zoo-animal-filter-favorites">
                      {t('zoo.filterFavorites')}
                    </label>
                  </div>
                </div>
              )}
            </div>
            <div className="row g-3 mt-2">
              {facets.classes.length > 0 && (
                <div className="col-12 col-lg-4">
                  {renderFacetGroup(
                    'classes',
                    facets.classes,
                    selectedClasses,
                    toggleClassFacet,
                    t('zoo.filterClasses'),
                    'animal.filterByClass',
                  )}
                </div>
              )}
              {facets.orders.length > 0 && (
                <div className="col-12 col-lg-4">
                  {renderFacetGroup(
                    'orders',
                    facets.orders,
                    selectedOrders,
                    toggleOrderFacet,
                    t('zoo.filterOrders'),
                    'animal.filterByOrder',
                  )}
                </div>
              )}
              {facets.families.length > 0 && (
                <div className="col-12 col-lg-4">
                  {renderFacetGroup(
                    'families',
                    facets.families,
                    selectedFamilies,
                    toggleFamilyFacet,
                    t('zoo.filterFamilies'),
                    'animal.filterByFamily',
                  )}
                </div>
              )}
            </div>
            <p className="mt-3 mb-0 text-muted small">{animalsStatus}</p>
          </div>
        </div>
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
              <div className="mt-2 d-flex justify-content-end">
                <button
                  type="button"
                  className="btn btn-sm btn-outline-secondary"
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
              </div>
            </AnimalTile>
          ))}
        </div>
        <div
          id="zoo-animals-status"
          role="status"
          aria-live="polite"
          className="visually-hidden"
        >
          {animalsStatus}
        </div>
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
      </div>
      {modalData && (
        <SightingModal
          animals={inventoryAnimals.length > 0 ? inventoryAnimals : null}
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
