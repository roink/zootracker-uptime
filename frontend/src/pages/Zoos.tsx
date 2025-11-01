import type { ChangeEvent } from 'react';
import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useTranslation, Trans } from 'react-i18next';
import {
  Link,
  useSearchParams,
  useParams,
  useNavigate,
  useLocation,
} from 'react-router-dom';

import { API } from '../api';
import { useAuth } from '../auth/AuthContext';
import FavoriteBadge from '../components/FavoriteBadge';
import Seo from '../components/Seo';
import ZoosMap from '../components/ZoosMap';
import useAuthFetch from '../hooks/useAuthFetch';
import type {
  CameraState,
  CameraViewChange,
  ListFilters,
  LocationEstimate,
  MapFilters,
  MapZooFeature,
  PaginatedZooPage,
  RegionOption,
  RequestConfig,
  ZooListItem,
} from '../types/zoos';
import { normalizeCoordinates } from '../utils/coordinates';
import { getZooDisplayName } from '../utils/zooDisplayName';

interface ZoosPageProps {
  token?: string;
}

const LOCATION_STORAGE_KEY = 'userLocation';
const PAGE_SIZE = 20;

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null;
}

function toStringId(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) {
    return value;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  return null;
}

function toOptionalString(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null;
}

function toOptionalNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function toOptionalBoolean(value: unknown): boolean | null {
  if (typeof value === 'boolean') {
    return value;
  }
  if (typeof value === 'number') {
    return value !== 0;
  }
  return null;
}

function toZooListItem(value: unknown): ZooListItem | null {
  if (!isRecord(value)) {
    return null;
  }
  const id = toStringId(value.id);
  if (!id) {
    return null;
  }
  const latitude = toOptionalNumber(value.latitude);
  const longitude = toOptionalNumber(value.longitude);
  const location = isRecord(value.location) ? (value.location) : null;
  return {
    id,
    slug: toOptionalString(value.slug),
    name: toOptionalString(value.name),
    name_en: toOptionalString(value.name_en),
    name_de: toOptionalString(value.name_de),
    city: toOptionalString(value.city),
    country_name_en: toOptionalString(value.country_name_en),
    country_name_de: toOptionalString(value.country_name_de),
    latitude,
    longitude,
    distance_km: toOptionalNumber(value.distance_km),
    is_favorite: toOptionalBoolean(value.is_favorite),
    location,
  };
}

function normalizeZooItems(source: unknown): ZooListItem[] {
  if (!Array.isArray(source)) {
    return [];
  }
  return source
    .map((item) => toZooListItem(item))
    .filter((item): item is ZooListItem => item !== null);
}

function normalizeZooPage(payload: unknown, fallbackOffset = 0): PaginatedZooPage {
  if (isRecord(payload) && Array.isArray(payload.items)) {
    const items = normalizeZooItems(payload.items);
    const total = toOptionalNumber(payload.total) ?? items.length;
    const offset = toOptionalNumber(payload.offset) ?? fallbackOffset;
    const limit = toOptionalNumber(payload.limit) ?? items.length;
    return { items, total, offset, limit };
  }
  if (Array.isArray(payload)) {
    const items = normalizeZooItems(payload);
    return {
      items,
      total: items.length,
      offset: fallbackOffset,
      limit: items.length,
    };
  }
  return { items: [], total: 0, offset: fallbackOffset, limit: 0 };
}

function sanitizeCameraState(value: unknown): CameraState | null {
  if (!isRecord(value)) {
    return null;
  }
  const centerValue = value.center;
  if (!Array.isArray(centerValue) || centerValue.length < 2) {
    return null;
  }
  const lon = toOptionalNumber(centerValue[0]);
  const lat = toOptionalNumber(centerValue[1]);
  if (lon === null || lat === null) {
    return null;
  }
  const zoom = toOptionalNumber(value.zoom ?? null) ?? undefined;
  const bearing = toOptionalNumber(value.bearing ?? null) ?? undefined;
  const pitch = toOptionalNumber(value.pitch ?? null) ?? undefined;
  return {
    center: [lon, lat],
    ...(zoom !== undefined ? { zoom } : {}),
    ...(bearing !== undefined ? { bearing } : {}),
    ...(pitch !== undefined ? { pitch } : {}),
  };
}

function normalizeRegions(source: unknown): RegionOption[] {
  if (!Array.isArray(source)) {
    return [];
  }
  return source
    .map((item) => {
      if (!isRecord(item)) {
        return null;
      }
      const id = toStringId(item.id);
      if (!id) {
        return null;
      }
      const region: RegionOption = {
        id,
        name_en: toOptionalString(item.name_en),
        name_de: toOptionalString(item.name_de),
      };
      return region;
    })
    .filter((value): value is RegionOption => value !== null);
}

/**
 * @typedef {Object} CameraState
 * @property {[number, number]} center Longitude and latitude pair used to restore the viewport.
 * @property {number} zoom Zoom level applied when persisting and restoring camera state.
 * @property {number} bearing Map bearing in degrees.
 * @property {number} pitch Map pitch in degrees.
 * @description Shared camera schema used by ZoosMap and Zoos.jsx when persisting map position.
 */

function mapViewsEqual(
  a: CameraState | null | undefined,
  b: CameraState | null | undefined
): boolean {
  if (!a && !b) return true;
  if (!a || !b) return false;
  if (!Array.isArray(a.center) || !Array.isArray(b.center)) return false;
  const [aLon, aLat] = a.center;
  const [bLon, bLat] = b.center;
  const centerMatch =
    Math.abs((aLon || 0) - (bLon || 0)) < 1e-6 &&
    Math.abs((aLat || 0) - (bLat || 0)) < 1e-6;
  if (!centerMatch) return false;
  const zoomMatch = Math.abs((a.zoom || 0) - (b.zoom || 0)) < 1e-4;
  const bearingMatch = Math.abs((a.bearing || 0) - (b.bearing || 0)) < 1e-2;
  const pitchMatch = Math.abs((a.pitch || 0) - (b.pitch || 0)) < 1e-2;
  return zoomMatch && bearingMatch && pitchMatch;
}

// Safely read a previously stored location from sessionStorage.
function readStoredLocation(): LocationEstimate | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = window.sessionStorage?.getItem(LOCATION_STORAGE_KEY);
    if (!stored) return null;
    const parsed = JSON.parse(stored);
    const lat = Number(parsed?.lat);
    const lon = Number(parsed?.lon);
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      return { lat, lon };
    }
  } catch (_error) {
    // Ignore storage errors (e.g. private browsing) and treat as unset.
  }
  return null;
}

// Attempt to persist the latest location while tolerating storage errors.
function writeStoredLocation(value: LocationEstimate | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (
      value &&
      Number.isFinite(value.lat) &&
      Number.isFinite(value.lon)
    ) {
      window.sessionStorage?.setItem(
        LOCATION_STORAGE_KEY,
        JSON.stringify({ lat: value.lat, lon: value.lon })
      );
    } else {
      window.sessionStorage?.removeItem(LOCATION_STORAGE_KEY);
    }
  } catch (_error) {
    // Ignore storage errors silently so the UI keeps working.
  }
}

// Listing page showing all zoos with search, region filters and visit status.

export default function ZoosPage(_props: ZoosPageProps = {}) {
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSearch = searchParams.get('q') || '';
  const initialContinent = searchParams.get('continent') || '';
  const initialCountry = searchParams.get('country') || '';
  const initialVisit = searchParams.get('visit');
  const initialView = searchParams.get('view') === 'map' ? 'map' : 'list';
  const initialFavorites = searchParams.get('favorites') === '1';

  const [zoos, setZoos] = useState<ZooListItem[]>([]);
  const [mapZoos, setMapZoos] = useState<ZooListItem[]>([]);
  const [visitedIds, setVisitedIds] = useState<string[]>([]);
  const [search, setSearch] = useState(initialSearch);
  const [query, setQuery] = useState(initialSearch);
  const [continents, setContinents] = useState<RegionOption[]>([]);
  const [countries, setCountries] = useState<RegionOption[]>([]);
  const [continentId, setContinentId] = useState(initialContinent);
  const [countryId, setCountryId] = useState(initialCountry);
  const [visitFilter, setVisitFilter] = useState(() =>
    initialVisit === 'visited' || initialVisit === 'not' ? initialVisit : 'all'
  ); // all | visited | not
  const [favoritesOnly, setFavoritesOnly] = useState(initialFavorites);
  const [visitedLoading, setVisitedLoading] = useState(true);
  const [estimatedLocation, setEstimatedLocation] = useState<LocationEstimate | null>(null);
  const [location, setLocation] = useState(() => readStoredLocation());
  const authFetch = useAuthFetch();
  const { isAuthenticated, user } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const locationState = useLocation();
  const listRequestRef = useRef<AbortController | null>(null);
  const mapRequestRef = useRef<AbortController | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const zoosRef = useRef<ZooListItem[]>([]);
  const routerState = (locationState.state ?? null) as UnknownRecord | null;
  const initialRouterView = routerState && 'mapView' in routerState
    ? sanitizeCameraState(routerState.mapView)
    : null;
  const mapViewRef = useRef<CameraState | null>(initialRouterView);
  const [mapView, setMapView] = useState<CameraState | null>(() => mapViewRef.current);
  const [preferStoredView, setPreferStoredView] = useState<boolean>(
    () => Boolean(mapViewRef.current)
  );
  const [viewMode, setViewMode] = useState(initialView);
  const [mapResizeToken, setMapResizeToken] = useState(0);
  const estimateAttemptedRef = useRef(false);
  useEffect(() => () => {
    if (listRequestRef.current) {
      listRequestRef.current.abort();
    }
  }, []);
  useEffect(() => () => {
    if (mapRequestRef.current) {
      mapRequestRef.current.abort();
    }
  }, []);
  const [totalZoos, setTotalZoos] = useState(0);
  const [nextOffset, setNextOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [mapLoading, setMapLoading] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);

  useEffect(() => {
    zoosRef.current = zoos;
  }, [zoos]);

  useEffect(() => {
    // Only react when the router explicitly sends a camera update.
    const state = (locationState.state ?? null) as UnknownRecord | null;
    if (!state || !Object.prototype.hasOwnProperty.call(state, 'mapView')) {
      return;
    }
    const nextView = sanitizeCameraState(state.mapView);
    if (!mapViewsEqual(nextView, mapViewRef.current)) {
      mapViewRef.current = nextView;
      setMapView(nextView);
    }
    setPreferStoredView(Boolean(nextView));
  }, [locationState.state]);

  useEffect(() => {
    mapViewRef.current = mapView;
  }, [mapView]);

  const updateMapView = useCallback(
    (view: CameraViewChange | null | undefined) => {
      if (view?.isUserInteraction) {
        setPreferStoredView(true);
      }

      const sanitizedView = sanitizeCameraState(view);

      if (!sanitizedView) {
        setPreferStoredView(false);
        if (mapViewRef.current) {
          mapViewRef.current = null;
          setMapView(null);
        }
        const baseState: UnknownRecord = isRecord(locationState.state)
          ? { ...(locationState.state) }
          : {};
        baseState.mapView = null;
        void navigate(
          { pathname: locationState.pathname, search: locationState.search },
          { replace: true, state: baseState }
        );
        return;
      }

      if (mapViewsEqual(sanitizedView, mapViewRef.current)) {
        return;
      }

      mapViewRef.current = sanitizedView;
      setMapView(sanitizedView);
      const baseState: UnknownRecord = isRecord(locationState.state)
        ? { ...(locationState.state) }
        : {};
      baseState.mapView = sanitizedView;
        void navigate(
          { pathname: locationState.pathname, search: locationState.search },
          { replace: true, state: baseState }
        );
    },
    [
      locationState.pathname,
      locationState.search,
      locationState.state,
      navigate,
      setPreferStoredView,
    ]
  );

  const handleFavoritesToggle = useCallback(
    (checked: boolean) => {
      if (listRequestRef.current) {
        listRequestRef.current.abort();
        listRequestRef.current = null;
      }
      if (mapRequestRef.current) {
        mapRequestRef.current.abort();
        mapRequestRef.current = null;
      }
      zoosRef.current = [];
      setZoos([]);
      setMapZoos([]);
      setTotalZoos(0);
      setNextOffset(0);
      setHasMore(true);
      setListError(null);
      setMapError(null);
      setListLoading(true);
      setMapLoading(true);
      setFavoritesOnly(checked);
    },
    [
      setZoos,
      setMapZoos,
      setTotalZoos,
      setNextOffset,
      setHasMore,
      setListError,
      setMapError,
      setListLoading,
      setMapLoading,
    ]
  );

  useEffect(() => {
    if (!isAuthenticated && favoritesOnly) {
      handleFavoritesToggle(false);
    }
  }, [isAuthenticated, favoritesOnly, handleFavoritesToggle]);

  // Keep local state in sync with URL (supports browser back/forward)
  useEffect(() => {
    const spQ = searchParams.get('q') || '';
    const spCont = searchParams.get('continent') || '';
    const spCountry = searchParams.get('country') || '';
    const spVisit = searchParams.get('visit');
    const spVisitNorm =
      spVisit === 'visited' || spVisit === 'not' ? spVisit : 'all';
    const spView = searchParams.get('view') === 'map' ? 'map' : 'list';
    const spFavorites = searchParams.get('favorites') === '1';

    if (spQ !== search) setSearch(spQ);
    if (spQ !== query) setQuery(spQ);
    if (spCont !== continentId) setContinentId(spCont);
    if (spCountry !== countryId) setCountryId(spCountry);
    const effectiveVisit = !isAuthenticated ? 'all' : spVisitNorm;
    if (effectiveVisit !== visitFilter) setVisitFilter(effectiveVisit);
    if (spView !== viewMode) setViewMode(spView);
    if (spFavorites !== favoritesOnly) handleFavoritesToggle(spFavorites);
  }, [
    continentId,
    countryId,
    favoritesOnly,
    handleFavoritesToggle,
    isAuthenticated,
    query,
    search,
    searchParams,
    viewMode,
    visitFilter,
  ]);

  useEffect(() => {
    // State ➜ URL, but only if different (avoid loops & history spam)
    const next = new URLSearchParams();
    if (search) next.set('q', search);
    if (continentId) next.set('continent', continentId);
    if (countryId) next.set('country', countryId);
    if (visitFilter !== 'all') next.set('visit', visitFilter);
    if (viewMode === 'map') next.set('view', 'map');
    if (favoritesOnly) next.set('favorites', '1');

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true, state: locationState.state });
    }
  }, [
    search,
    continentId,
    countryId,
    visitFilter,
    viewMode,
    favoritesOnly,
    searchParams,
    setSearchParams,
    locationState.state,
  ]);

  useEffect(() => {
    if (viewMode === 'map') {
      setMapResizeToken((token) => token + 1);
    }
  }, [viewMode]);

  const mapFilters = useMemo<MapFilters>(
    () => ({
      q: query.trim(),
      continent: continentId || '',
      country: countryId || '',
      favoritesOnly,
    }),
    [query, continentId, countryId, favoritesOnly]
  );
  const mapFiltersKey = useMemo(
    () => JSON.stringify(mapFilters),
    [mapFilters]
  );

  const visitFilterActive = visitFilter === 'visited' || visitFilter === 'not';
  const visitSegment = visitFilter === 'visited' ? 'visited' : 'not-visited';
  const userId = user?.id ?? null;
  const isServerFilteredByVisit = isAuthenticated && visitFilterActive;

  const listRequestConfig = useMemo<RequestConfig>(() => {
    if (favoritesOnly) {
      if (!isAuthenticated) {
        return { url: null, requiresAuth: true, ready: false };
      }
      return {
        url: `${API}/zoos`,
        requiresAuth: true,
        ready: true,
      };
    }
    if (isAuthenticated && visitFilterActive) {
      if (!userId) {
        return {
          url: null,
          requiresAuth: true,
          ready: false,
        };
      }
      return {
        url: `${API}/users/${userId}/zoos/${visitSegment}`,
        requiresAuth: true,
        ready: true,
      };
    }
    return {
      url: `${API}/zoos`,
      requiresAuth: isAuthenticated,
      ready: true,
    };
  }, [favoritesOnly, isAuthenticated, visitFilterActive, userId, visitSegment]);

  const mapRequestConfig = useMemo<RequestConfig>(() => {
    if (favoritesOnly) {
      if (!isAuthenticated) {
        return { url: null, requiresAuth: true, ready: false };
      }
      return { url: `${API}/zoos/map`, requiresAuth: true, ready: true };
    }
    if (isAuthenticated && visitFilterActive) {
      if (!userId) {
        return { url: null, requiresAuth: true, ready: false };
      }
      return {
        url: `${API}/users/${userId}/zoos/${visitSegment}/map`,
        requiresAuth: true,
        ready: true,
      };
    }
    return { url: `${API}/zoos/map`, requiresAuth: false, ready: true };
  }, [favoritesOnly, isAuthenticated, visitFilterActive, userId, visitSegment]);

  useEffect(() => {
    if (mapRequestRef.current) {
      mapRequestRef.current.abort();
    }
    const controller = new AbortController();
    mapRequestRef.current = controller;
    setMapLoading(mapZoos.length === 0);
    setMapError(null);

    if (!mapRequestConfig.ready || !mapRequestConfig.url) {
      return () => {
        if (mapRequestRef.current === controller) {
          mapRequestRef.current = null;
        }
        controller.abort();
      };
    }

    const params = new URLSearchParams();
    if (mapFilters.q) params.set('q', mapFilters.q);
    if (mapFilters.continent) params.set('continent_id', mapFilters.continent);
    if (mapFilters.country) params.set('country_id', mapFilters.country);
    if (mapFilters.favoritesOnly) params.set('favorites_only', 'true');
    const paramsString = params.toString();
    const requestUrl = `${mapRequestConfig.url}${paramsString ? `?${paramsString}` : ''}`;
    const fetcher: typeof fetch = mapRequestConfig.requiresAuth ? authFetch : fetch;

    void (async () => {
      try {
        const response = await fetcher(requestUrl, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = (await response.json()) as unknown;
        if (!controller.signal.aborted) {
          setMapZoos(normalizeZooItems(data));
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setMapZoos([]);
          setMapError(error instanceof Error ? error.message : 'Failed to load map data');
        }
      } finally {
        if (!controller.signal.aborted) {
          setMapLoading(false);
        }
        if (mapRequestRef.current === controller) {
          mapRequestRef.current = null;
        }
      }
    })();

    return () => {
      if (mapRequestRef.current === controller) {
        mapRequestRef.current = null;
      }
      controller.abort();
    };
  }, [mapFiltersKey, mapFilters, mapRequestConfig, authFetch, mapZoos.length]);

  useEffect(() => {
    void fetch(`${API}/zoos/continents`)
      .then(async (r) => (r.ok ? ((await r.json()) as unknown) : []))
      .then((data) => { setContinents(normalizeRegions(data)); })
      .catch(() => { setContinents([]); });
  }, []);

  useEffect(() => {
    if (!continentId) {
      setCountries([]);
      setCountryId('');
      return;
    }
    void fetch(`${API}/zoos/countries?continent_id=${continentId}`)
      .then(async (r) => (r.ok ? ((await r.json()) as unknown) : []))
      .then((data) => { setCountries(normalizeRegions(data)); })
      .catch(() => { setCountries([]); });
  }, [continentId]);


  useEffect(() => {
    const id = setTimeout(() => { setQuery(search); }, 200);
    return () => { clearTimeout(id); };
  }, [search]);

  const activeLocation = useMemo<LocationEstimate | null>(
    () => location || estimatedLocation,
    [location, estimatedLocation]
  );

  const listFilters = useMemo<ListFilters>(
    () => ({
      q: query.trim(),
      continent: continentId || '',
      country: countryId || '',
      favoritesOnly,
      latitude:
        typeof activeLocation?.lat === 'number' && Number.isFinite(activeLocation.lat)
          ? activeLocation.lat
          : null,
      longitude:
        typeof activeLocation?.lon === 'number' && Number.isFinite(activeLocation.lon)
          ? activeLocation.lon
          : null,
    }),
    [
      query,
      continentId,
      countryId,
      favoritesOnly,
      activeLocation?.lat,
      activeLocation?.lon,
    ]
  );
  const listFiltersKey = useMemo(
    () => JSON.stringify(listFilters),
    [listFilters]
  );

  useEffect(() => {
    if (listRequestRef.current) {
      listRequestRef.current.abort();
      listRequestRef.current = null;
    }

    const controller = new AbortController();
    listRequestRef.current = controller;
    setListError(null);
    setHasMore(true);
    setNextOffset(0);
    setListLoading(zoosRef.current.length === 0);

    if (!listRequestConfig.ready || !listRequestConfig.url) {
      return () => {
        if (listRequestRef.current === controller) {
          listRequestRef.current = null;
        }
        controller.abort();
      };
    }

    const params = new URLSearchParams();
    if (listFilters.q) params.set('q', listFilters.q);
    if (listFilters.continent) params.set('continent_id', listFilters.continent);
    if (listFilters.country) params.set('country_id', listFilters.country);
    if (listFilters.favoritesOnly) params.set('favorites_only', 'true');
    if (listFilters.latitude !== null) {
      params.set('latitude', String(listFilters.latitude));
    }
    if (listFilters.longitude !== null) {
      params.set('longitude', String(listFilters.longitude));
    }
    params.set('limit', String(PAGE_SIZE));
    params.set('offset', '0');
    const paramsString = params.toString();
    const requestUrl = `${listRequestConfig.url}${paramsString ? `?${paramsString}` : ''}`;
    const fetcher: typeof fetch = listRequestConfig.requiresAuth ? authFetch : fetch;

    let active = true;

      void (async () => {
      try {
        const response = await fetcher(requestUrl, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = (await response.json()) as unknown;
        if (!active || controller.signal.aborted) {
          return;
        }
        const page = normalizeZooPage(data, 0);
        setZoos(page.items);
        const newOffset = page.offset + page.items.length;
        setNextOffset(newOffset);
        setTotalZoos(page.total);
        setHasMore(newOffset < page.total && page.items.length > 0);
      } catch (error) {
        if (!active || controller.signal.aborted) {
          return;
        }
        setListError(error instanceof Error ? error.message : 'Failed to load zoos');
      } finally {
        if (listRequestRef.current === controller) {
          listRequestRef.current = null;
        }
        if (!controller.signal.aborted && active) {
          setListLoading(false);
        }
      }
      })();

    return () => {
      active = false;
      if (listRequestRef.current === controller) {
        listRequestRef.current = null;
      }
      controller.abort();
    };
  }, [listFiltersKey, listFilters, listRequestConfig, authFetch]);

  const loadNextPage = useCallback(async () => {
    if (listRequestRef.current || listLoading || !hasMore) return;
    if (!listRequestConfig.ready || !listRequestConfig.url) return;

    const controller = new AbortController();
    listRequestRef.current = controller;
    setListLoading(true);
    setListError(null);

    const params = new URLSearchParams();
    if (listFilters.q) params.set('q', listFilters.q);
    if (listFilters.continent) params.set('continent_id', listFilters.continent);
    if (listFilters.country) params.set('country_id', listFilters.country);
    if (listFilters.favoritesOnly) params.set('favorites_only', 'true');
    if (listFilters.latitude !== null) {
      params.set('latitude', String(listFilters.latitude));
    }
    if (listFilters.longitude !== null) {
      params.set('longitude', String(listFilters.longitude));
    }
    params.set('limit', String(PAGE_SIZE));
    params.set('offset', String(nextOffset));
    const paramsString = params.toString();
    const requestUrl = `${listRequestConfig.url}${paramsString ? `?${paramsString}` : ''}`;
    const fetcher: typeof fetch = listRequestConfig.requiresAuth ? authFetch : fetch;

    try {
      const response = await fetcher(requestUrl, { signal: controller.signal });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = (await response.json()) as unknown;
      if (controller.signal.aborted) {
        return;
      }
      const page = normalizeZooPage(data, nextOffset);
      const newOffset = page.offset + page.items.length;
      setZoos((prev) => (page.offset === 0 ? page.items : [...prev, ...page.items]));
      setNextOffset(newOffset);
      setTotalZoos(page.total);
      setHasMore(newOffset < page.total && page.items.length > 0);
    } catch (error) {
      if (!controller.signal.aborted) {
        setListError(error instanceof Error ? error.message : 'Failed to load zoos');
      }
    } finally {
      if (listRequestRef.current === controller) {
        listRequestRef.current = null;
      }
      if (!controller.signal.aborted) {
        setListLoading(false);
      }
    }
  }, [
    listFilters,
    listLoading,
    hasMore,
    nextOffset,
    listRequestConfig,
    authFetch,
  ]);

  useEffect(() => {
    if (viewMode !== 'list') return undefined;
    if (typeof IntersectionObserver === 'undefined') return undefined;
    const node = sentinelRef.current;
    if (!node) return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
          if (entries.some((entry) => entry.isIntersecting)) {
            void loadNextPage();
          }
        },
      { root: null, rootMargin: '200px' }
    );
    observer.observe(node);
    return () => { observer.disconnect(); };
  }, [viewMode, loadNextPage]);

  useEffect(() => {
    if (estimateAttemptedRef.current) return;
    estimateAttemptedRef.current = true;

    let cancelled = false;
      void fetch(`${API}/location/estimate`)
        .then(async (r) => (r.ok ? ((await r.json()) as unknown) : null))
      .then((data) => {
        if (cancelled) return;
        const record = isRecord(data) ? data : null;
        const lat = record ? toOptionalNumber(record.latitude) : null;
        const lon = record ? toOptionalNumber(record.longitude) : null;
        if (lat !== null && lon !== null) {
          setEstimatedLocation({ lat, lon });
        } else {
          setEstimatedLocation(null);
        }
      })
      .catch(() => {
        if (!cancelled) setEstimatedLocation(null);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!navigator?.geolocation) return;

    let cancelled = false;
    try {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          if (cancelled) return;
          const lat = Number(pos.coords.latitude);
          const lon = Number(pos.coords.longitude);
          if (Number.isFinite(lat) && Number.isFinite(lon)) {
            const loc = { lat, lon };
            setLocation(loc);
            writeStoredLocation(loc);
          } else {
            setLocation(null);
            writeStoredLocation(null);
          }
        },
        () => {
          if (cancelled) return;
          setLocation(null);
          writeStoredLocation(null);
        },
        { enableHighAccuracy: false, timeout: 3000, maximumAge: 600000 }
      );
    } catch (_error) {
      setLocation(null);
      writeStoredLocation(null);
    }

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      setVisitedLoading(false);
      return;
    }
    setVisitedLoading(true);
    authFetch(`${API}/visits/ids`)
      .then(async (r) => {
        if (!r.ok) return [] as string[];
        const data = (await r.json()) as unknown;
        if (!Array.isArray(data)) return [] as string[];
        return data.map((value) => String(value));
      })
      .then(setVisitedIds)
      .catch(() => { setVisitedIds([]); })
      .finally(() => { setVisitedLoading(false); });
  }, [isAuthenticated, authFetch]);

  useEffect(() => {
    if (!isAuthenticated && (visitFilter === 'visited' || visitFilter === 'not')) {
      setVisitFilter('all');
    }
  }, [isAuthenticated, visitFilter]);


  useEffect(() => {
    if (favoritesOnly && visitFilter !== 'all') {
      setVisitFilter('all');
    }
  }, [favoritesOnly, visitFilter]);

  const visitedSet = useMemo(() => new Set(visitedIds), [visitedIds]);

  const updateVisitFilter = (v: 'all' | 'visited' | 'not') => {
    if ((v === 'visited' || v === 'not') && !isAuthenticated) {
      setVisitFilter('all');
      return;
    }
    if (v !== 'all' && favoritesOnly) {
      handleFavoritesToggle(false);
    }
    setVisitFilter(v);
  };

  const filtered = useMemo<ZooListItem[]>(() => {
    if (isServerFilteredByVisit) {
      return zoos;
    }
    return zoos.filter((z) => {
      if (visitFilter === 'visited') return visitedSet.has(String(z.id));
      if (visitFilter === 'not') return !visitedSet.has(String(z.id));
      return true;
    });
  }, [zoos, visitFilter, visitedSet, isServerFilteredByVisit]);

  const mapFiltered = useMemo<ZooListItem[]>(() => {
    if (isServerFilteredByVisit) {
      return mapZoos;
    }
    return mapZoos.filter((z) => {
      if (visitFilter === 'visited') return visitedSet.has(String(z.id));
      if (visitFilter === 'not') return !visitedSet.has(String(z.id));
      return true;
    });
  }, [mapZoos, visitFilter, visitedSet, isServerFilteredByVisit]);

  const mapZoosWithCoordinates = useMemo<MapZooFeature[]>(
    () =>
      mapFiltered
        .map((zoo) => {
          const coords = normalizeCoordinates(zoo);
          if (!coords) {
            return null;
          }
          return { ...zoo, latitude: coords.latitude, longitude: coords.longitude };
        })
        .filter((value): value is MapZooFeature => value !== null),
    [mapFiltered]
  );

  useEffect(() => {
    const importMetaEnv = typeof import.meta !== 'undefined' ? import.meta.env : undefined;
    const isVitest = importMetaEnv?.MODE === 'test';
    const isNodeTest = typeof process !== 'undefined' && process.env && process.env.NODE_ENV === 'test';
    if (
      importMetaEnv?.DEV &&
      !isVitest &&
      !isNodeTest &&
      mapFiltered.length > 0 &&
      mapZoosWithCoordinates.length === 0
    ) {
       
      console.warn(
        'ZoosPage: no coordinate fields found on items. Example keys:',
        Object.keys(mapFiltered[0] || {})
      );
    }
  }, [mapFiltered, mapZoosWithCoordinates]);

  const localizedName = (item: RegionOption): string =>
    lang === 'de' ? item.name_de || item.name_en || '' : item.name_en || item.name_de || '';

  const localizedCountry = (item: ZooListItem): string | null =>
    lang === 'de'
      ? item.country_name_de || item.country_name_en || null
      : item.country_name_en || item.country_name_de || null;

  const handleViewChange = (mode: 'list' | 'map') => {
    setViewMode(mode);
  };

    const handleSelectZoo = (zoo: ZooListItem, view?: CameraViewChange | null) => {
      if (view) {
        updateMapView(view);
      }
      void navigate(`${prefix}/zoos/${zoo.slug || zoo.id}`);
    };

  return (
    <div className="container">
      <Seo
        title="Zoos"
        description="Explore zoos around the world and log your visits."
      />
      <div className="row mb-3">
        <div className="col-md-4 mb-2">
          <input
            className="form-control"
            placeholder={t('nav.search')}
            value={search}
            onChange={(e: ChangeEvent<HTMLInputElement>) => { setSearch(e.target.value); }}
          />
        </div>
        <div className="col-md-4 mb-2">
          <select
            className="form-select"
            aria-label={t('zoo.continent')}
            value={continentId}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => {
              setContinentId(e.target.value);
              setCountryId('');
            }}
          >
            <option value="">{t('zoo.allContinents')}</option>
            {continents.map((c) => (
              <option key={c.id} value={c.id}>
                {localizedName(c)}
              </option>
            ))}
          </select>
        </div>
        <div className="col-md-4 mb-2">
          <select
            className="form-select"
            aria-label={t('zoo.country')}
            value={countryId}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => { setCountryId(e.target.value); }}
            disabled={!continentId}
          >
            <option value="">{t('zoo.allCountries')}</option>
            {countries.map((c) => (
              <option key={c.id} value={c.id}>
                {localizedName(c)}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="row mb-3">
        <div
          className={`${isAuthenticated ? 'col-12 col-md-4' : 'col-12'} mb-2`}
        >
          {isAuthenticated ? (
            <>
              <fieldset
                className="btn-group w-100"
                role="group"
                aria-label={t('zoo.visitFilterLabel')}
              >
                <legend className="visually-hidden">
                  {t('zoo.visitFilterLabel')}
                </legend>
                <input
                  type="radio"
                  className="btn-check"
                  name="visit-filter"
                  id="visit-all"
                  autoComplete="off"
                  checked={visitFilter === 'all'}
                  onChange={() => { updateVisitFilter('all'); }}
                  disabled={visitedLoading}
                />
                <label
                  className="btn btn-outline-primary"
                  htmlFor="visit-all"
                >
                  {t('zoo.all')}
                </label>

                <input
                  type="radio"
                  className="btn-check"
                  name="visit-filter"
                  id="visit-visited"
                  autoComplete="off"
                  checked={visitFilter === 'visited'}
                  onChange={() => { updateVisitFilter('visited'); }}
                  disabled={visitedLoading}
                />
                <label
                  className="btn btn-outline-primary"
                  htmlFor="visit-visited"
                >
                  {t('zoo.visitedOnly')}
                </label>

                <input
                  type="radio"
                  className="btn-check"
                  name="visit-filter"
                  id="visit-not"
                  autoComplete="off"
                  checked={visitFilter === 'not'}
                  onChange={() => { updateVisitFilter('not'); }}
                  disabled={visitedLoading}
                />
                <label className="btn btn-outline-primary" htmlFor="visit-not">
                  {t('zoo.notVisited')}
                </label>
              </fieldset>
              {visitFilter !== 'all' && visitedLoading && (
                <div
                  className="spinner-border spinner-border-sm text-primary ms-2"
                  role="status"
                  aria-label="Loading visited"
                />
              )}
            </>
          ) : (
            <div
              className="alert alert-info mb-0 w-100"
              role="status"
              aria-live="polite"
              aria-atomic="true"
            >
              <Trans
                i18nKey="zoo.visitFilterLoginPrompt"
                components={{
                  login: <Link className="alert-link" to={`${prefix}/login`} />,
                  signup: (
                    <Link
                      className="alert-link"
                      to={`${prefix}/login#signup`}
                    />
                  ),
                }}
              />
            </div>
          )}
        </div>
        {isAuthenticated && (
          <div className="col-md-4 mb-2">
            <div className="form-check mt-2">
              <input
                className="form-check-input"
                type="checkbox"
                id="zoos-favorites-only"
                checked={favoritesOnly}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  { handleFavoritesToggle(e.target.checked); }
                }
              />
              <label className="form-check-label" htmlFor="zoos-favorites-only">
                {t('zoo.favoritesOnly')}
              </label>
            </div>
          </div>
        )}
      </div>
      <div className="d-flex justify-content-end flex-wrap gap-2 mb-3">
        <fieldset className="btn-group" role="group" aria-label={t('zoo.viewToggle')}>
          <legend className="visually-hidden">{t('zoo.viewToggle')}</legend>
          <input
            type="radio"
            className="btn-check"
            name="zoo-view-mode"
            id="zoo-view-list"
            autoComplete="off"
            checked={viewMode === 'list'}
            onChange={() => { handleViewChange('list'); }}
          />
          <label className="btn btn-outline-primary" htmlFor="zoo-view-list">
            {t('zoo.viewList')}
          </label>

          <input
            type="radio"
            className="btn-check"
            name="zoo-view-mode"
            id="zoo-view-map"
            autoComplete="off"
            checked={viewMode === 'map'}
            onChange={() => { handleViewChange('map'); }}
          />
          <label className="btn btn-outline-primary" htmlFor="zoo-view-map">
            {t('zoo.viewMap')}
          </label>
        </fieldset>
      </div>
      {viewMode === 'list' ? (
        <>
          {filtered.length === 0 ? (
            <div className="my-4">
              {listLoading ? (
                <div
                  className="d-flex justify-content-center"
                  role="status"
                  aria-live="polite"
                >
                  <div className="spinner-border text-primary" aria-hidden="true" />
                  <span className="visually-hidden">{t('actions.loading')}</span>
                </div>
              ) : listError ? (
                <div className="alert alert-warning" role="status">
                  {t('zoo.loadingError')}
                </div>
              ) : !hasMore ? (
                <div className="alert alert-info" role="status">
                  {t('zoo.noResults')}
                </div>
              ) : null}
            </div>
          ) : (
            <>
              <div className="list-group">
                {filtered.map((z) => {
                  const countryName = localizedCountry(z);
                  return (
                    <Link
                      key={z.id}
                      className="list-group-item list-group-item-action text-start w-100 text-decoration-none text-reset"
                      to={`${prefix}/zoos/${z.slug || z.id}`}
                    >
                      <div className="d-flex justify-content-between">
                        <div>
                          <div className="fw-bold d-flex align-items-center gap-1">
                            {getZooDisplayName(z)}
                            <FavoriteBadge isFavorite={Boolean(z.is_favorite)} />
                          </div>
                          {countryName && (
                            <div className="text-muted">{countryName}</div>
                          )}
                        </div>
                        <div className="text-end">
                          {z.distance_km != null && (
                            <div className="small text-muted">
                              {z.distance_km.toFixed(1)} km
                            </div>
                          )}
                          {visitedSet.has(String(z.id)) && (
                            <span className="badge bg-success mt-1">
                              {t('zoo.visitedOnly')}
                            </span>
                          )}
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
              <div ref={sentinelRef} aria-hidden="true" style={{ height: '1px' }} />
              {listLoading && (
                <div
                  className="d-flex justify-content-center my-3"
                  role="status"
                  aria-live="polite"
                >
                  <div className="spinner-border text-primary" aria-hidden="true" />
                  <span className="visually-hidden">{t('zoo.loadingMore')}</span>
                </div>
              )}
              {listError && !listLoading && (
                <div className="alert alert-warning mt-3" role="status">
                  {t('zoo.loadingError')}
                </div>
              )}
              {!listLoading && !listError && !hasMore && totalZoos > 0 && (
                <div className="text-muted text-center my-3" role="status">
                  {t('zoo.noMoreResults')}
                </div>
              )}
            </>
          )}
        </>
      ) : (
        <div className="position-relative">
          <ZoosMap
            zoos={mapZoosWithCoordinates}
            center={preferStoredView ? null : activeLocation}
            onSelect={handleSelectZoo}
            initialView={mapViewRef.current}
            suppressAutoFit={Boolean(mapViewRef.current)}
            onViewChange={updateMapView}
            resizeToken={mapResizeToken}
          />
          {mapLoading && (
            <div
              className="position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center"
              style={{ pointerEvents: 'none' }}
              role="status"
              aria-live="polite"
            >
              <div className="spinner-border text-primary" aria-hidden="true" />
              <span className="visually-hidden">{t('zoo.mapLoading')}</span>
            </div>
          )}
          {!mapLoading && mapError && (
            <div className="position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center">
              <div className="alert alert-warning mb-0" role="status">
                {t('zoo.mapLoadingError')}
              </div>
            </div>
          )}
          {!mapLoading && !mapError && mapFiltered.length === 0 && (
            <div className="position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center">
              <div className="alert alert-info mb-0" role="status">
                {t('zoo.noResults')}
              </div>
            </div>
          )}
          {!mapLoading && !mapError && mapFiltered.length > 0 && mapZoosWithCoordinates.length === 0 && (
            <div className="position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center">
              <div className="alert alert-info mb-0" role="status">
                {t('zoo.noMapResults')}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

