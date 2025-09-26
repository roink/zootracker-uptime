import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  Link,
  useSearchParams,
  useParams,
  useNavigate,
  useLocation,
} from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import Seo from '../components/Seo';
import { useAuth } from '../auth/AuthContext.jsx';
import ZoosMap from '../components/ZoosMap.jsx';
import { normalizeCoordinates } from '../utils/coordinates.js';
import { getZooDisplayName } from '../utils/zooDisplayName.js';

const LOCATION_STORAGE_KEY = 'userLocation';

function mapViewsEqual(a, b) {
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
function readStoredLocation() {
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
  } catch (error) {
    // Ignore storage errors (e.g. private browsing) and treat as unset.
  }
  return null;
}

// Attempt to persist the latest location while tolerating storage errors.
function writeStoredLocation(value) {
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
  } catch (error) {
    // Ignore storage errors silently so the UI keeps working.
  }
}

// Listing page showing all zoos with search, region filters and visit status.

export default function ZoosPage() {
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSearch = searchParams.get('q') || '';
  const initialContinent = searchParams.get('continent') || '';
  const initialCountry = searchParams.get('country') || '';
  const initialVisit = searchParams.get('visit');
  const initialView = searchParams.get('view') === 'map' ? 'map' : 'list';

  const [zoos, setZoos] = useState([]);
  const [visitedIds, setVisitedIds] = useState([]);
  const [search, setSearch] = useState(initialSearch);
  const [query, setQuery] = useState(initialSearch);
  const [continents, setContinents] = useState([]);
  const [countries, setCountries] = useState([]);
  const [continentId, setContinentId] = useState(initialContinent);
  const [countryId, setCountryId] = useState(initialCountry);
  const [visitFilter, setVisitFilter] = useState(() =>
    initialVisit === 'visited' || initialVisit === 'not' ? initialVisit : 'all'
  ); // all | visited | not
  const [visitedLoading, setVisitedLoading] = useState(true);
  const [estimatedLocation, setEstimatedLocation] = useState(null);
  const [location, setLocation] = useState(() => readStoredLocation());
  const authFetch = useAuthFetch();
  const { isAuthenticated } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const locationState = useLocation();
  const mapViewRef = useRef(locationState.state?.mapView ?? null);
  const [mapView, setMapView] = useState(() => mapViewRef.current);
  const [viewMode, setViewMode] = useState(initialView);
  const [mapResizeToken, setMapResizeToken] = useState(0);
  const estimateAttemptedRef = useRef(false);

  useEffect(() => {
    const nextView = locationState.state?.mapView ?? null;
    if (!mapViewsEqual(nextView, mapViewRef.current)) {
      mapViewRef.current = nextView;
      setMapView(nextView);
    }
  }, [locationState.state]);

  useEffect(() => {
    mapViewRef.current = mapView;
  }, [mapView]);

  const updateMapView = useCallback(
    (view) => {
      if (!view || !Array.isArray(view.center)) {
        if (mapViewRef.current) {
          mapViewRef.current = null;
          setMapView(null);
          const baseState = locationState.state ? { ...locationState.state } : {};
          delete baseState.mapView;
          navigate(
            { pathname: locationState.pathname, search: locationState.search },
            { replace: true, state: baseState }
          );
        }
        return;
      }

      if (mapViewsEqual(view, mapViewRef.current)) {
        return;
      }

      mapViewRef.current = view;
      setMapView(view);
      const baseState = locationState.state ? { ...locationState.state } : {};
      baseState.mapView = view;
      navigate(
        { pathname: locationState.pathname, search: locationState.search },
        { replace: true, state: baseState }
      );
    },
    [locationState.pathname, locationState.search, locationState.state, navigate]
  );

  // Keep local state in sync with URL (supports browser back/forward)
  useEffect(() => {
    const spQ = searchParams.get('q') || '';
    const spCont = searchParams.get('continent') || '';
    const spCountry = searchParams.get('country') || '';
    const spVisit = searchParams.get('visit');
    const spVisitNorm =
      spVisit === 'visited' || spVisit === 'not' ? spVisit : 'all';
    const spView = searchParams.get('view') === 'map' ? 'map' : 'list';

    if (spQ !== search) setSearch(spQ);
    if (spQ !== query) setQuery(spQ);
    if (spCont !== continentId) setContinentId(spCont);
    if (spCountry !== countryId) setCountryId(spCountry);
    if (spVisitNorm !== visitFilter) setVisitFilter(spVisitNorm);
    if (spView !== viewMode) setViewMode(spView);
  }, [searchParams]);

  useEffect(() => {
    // State ➜ URL, but only if different (avoid loops & history spam)
    const next = new URLSearchParams();
    if (query) next.set('q', query);
    if (continentId) next.set('continent', continentId);
    if (countryId) next.set('country', countryId);
    if (visitFilter !== 'all') next.set('visit', visitFilter);
    if (viewMode === 'map') next.set('view', 'map');

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true });
    }
  }, [
    query,
    continentId,
    countryId,
    visitFilter,
    viewMode,
    searchParams,
    setSearchParams,
  ]);

  useEffect(() => {
    if (viewMode === 'map') {
      setMapResizeToken((token) => token + 1);
    }
  }, [viewMode]);

  useEffect(() => {
    fetch(`${API}/zoos/continents`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setContinents)
      .catch(() => setContinents([]));
  }, []);

  useEffect(() => {
    if (!continentId) {
      setCountries([]);
      setCountryId('');
      return;
    }
    fetch(`${API}/zoos/countries?continent_id=${continentId}`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setCountries)
      .catch(() => setCountries([]));
  }, [continentId]);


  useEffect(() => {
    const id = setTimeout(() => setQuery(search), 500);
    return () => clearTimeout(id);
  }, [search]);

  const activeLocation = useMemo(
    () => location || estimatedLocation,
    [location, estimatedLocation]
  );

  useEffect(() => {
    const params = new URLSearchParams();
    if (activeLocation) {
      params.set('latitude', activeLocation.lat);
      params.set('longitude', activeLocation.lon);
    }
    if (query) params.set('q', query);
    if (continentId) params.set('continent_id', continentId);
    if (countryId) params.set('country_id', countryId);
    fetch(`${API}/zoos${params.toString() ? `?${params.toString()}` : ''}`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setZoos)
      .catch(() => setZoos([]));
  }, [
    activeLocation?.lat,
    activeLocation?.lon,
    query,
    continentId,
    countryId,
  ]);

  useEffect(() => {
    if (estimateAttemptedRef.current) return;
    estimateAttemptedRef.current = true;

    let cancelled = false;
    fetch(`${API}/location/estimate`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled) return;
        const lat = Number(data?.latitude);
        const lon = Number(data?.longitude);
        if (Number.isFinite(lat) && Number.isFinite(lon)) {
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
    } catch (error) {
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
      .then((r) => (r.ok ? r.json() : []))
      .then(setVisitedIds)
      .catch(() => setVisitedIds([]))
      .finally(() => setVisitedLoading(false));
  }, [isAuthenticated, authFetch]);

  const visitedSet = useMemo(() => new Set(visitedIds.map(String)), [visitedIds]);

  const updateVisitFilter = (v) => {
    setVisitFilter(v);
  };

  const filtered = useMemo(() => {
    return zoos.filter((z) => {
      if (visitFilter === 'visited') return visitedSet.has(String(z.id));
      if (visitFilter === 'not') return !visitedSet.has(String(z.id));
      return true;
    });
  }, [zoos, visitFilter, visitedSet]);

  const zoosWithCoordinates = useMemo(
    () =>
      filtered
        .map((zoo) => {
          const coords = normalizeCoordinates(zoo);
          if (!coords) {
            return null;
          }
          return { ...zoo, ...coords };
        })
        .filter(Boolean),
    [filtered]
  );

  useEffect(() => {
    if (import.meta.env.DEV && filtered.length > 0 && zoosWithCoordinates.length === 0) {
      // eslint-disable-next-line no-console
      console.warn(
        'ZoosPage: no coordinate fields found on items. Example keys:',
        Object.keys(filtered[0] || {})
      );
    }
  }, [filtered, zoosWithCoordinates]);

  const localizedName = (item) =>
    lang === 'de' ? item.name_de || item.name_en : item.name_en || item.name_de;

  const localizedCountry = (item) =>
    lang === 'de'
      ? item.country_name_de || item.country_name_en
      : item.country_name_en || item.country_name_de;

  const handleViewChange = (mode) => {
    setViewMode(mode);
  };

  const handleSelectZoo = (zoo, view) => {
    if (view) {
      updateMapView(view);
    }
    navigate(`${prefix}/zoos/${zoo.slug || zoo.id}`);
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
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="col-md-4 mb-2">
          <select
            className="form-select"
            aria-label={t('zoo.continent')}
            value={continentId}
            onChange={(e) => {
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
            onChange={(e) => setCountryId(e.target.value)}
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
        <div className="col-md-4 mb-2">
          <fieldset
            className="btn-group w-100"
            role="group"
            aria-label="Visit filter"
          >
            <legend className="visually-hidden">Visit filter</legend>
            <input
              type="radio"
              className="btn-check"
              name="visit-filter"
              id="visit-all"
              autoComplete="off"
              checked={visitFilter === 'all'}
              onChange={() => updateVisitFilter('all')}
              disabled={visitedLoading}
            />
            <label className="btn btn-outline-primary" htmlFor="visit-all">
              {t('zoo.all')}
            </label>

            <input
              type="radio"
              className="btn-check"
              name="visit-filter"
              id="visit-visited"
              autoComplete="off"
              checked={visitFilter === 'visited'}
              onChange={() => updateVisitFilter('visited')}
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
              onChange={() => updateVisitFilter('not')}
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
        </div>
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
            onChange={() => handleViewChange('list')}
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
            onChange={() => handleViewChange('map')}
          />
          <label className="btn btn-outline-primary" htmlFor="zoo-view-map">
            {t('zoo.viewMap')}
          </label>
        </fieldset>
      </div>
      {viewMode === 'list' ? (
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
                    <div className="fw-bold">
                      {getZooDisplayName(z)}
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
          {filtered.length === 0 && (
            <div className="list-group-item text-muted" role="status">
              {t('zoo.noResults')}
            </div>
          )}
        </div>
      ) : filtered.length === 0 ? (
        <div className="alert alert-info" role="status">
          {t('zoo.noResults')}
        </div>
      ) : zoosWithCoordinates.length > 0 ? (
        <ZoosMap
          zoos={zoosWithCoordinates}
          center={activeLocation}
          onSelect={handleSelectZoo}
          initialView={mapView}
          onViewChange={updateMapView}
          resizeToken={mapResizeToken}
        />
      ) : (
        <div className="alert alert-info" role="status">
          {t('zoo.noMapResults')}
        </div>
      )}
    </div>
  );
}

