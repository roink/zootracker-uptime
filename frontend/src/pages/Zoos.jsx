import { useState, useEffect, useMemo } from 'react';
import { Link, useSearchParams, useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import Seo from '../components/Seo';
import { useAuth } from '../auth/AuthContext.jsx';
import ZoosMap from '../components/ZoosMap.jsx';

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
  const [location, setLocation] = useState(() => {
    const stored = sessionStorage.getItem('userLocation');
    return stored ? JSON.parse(stored) : null;
  });
  const authFetch = useAuthFetch();
  const { isAuthenticated } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [viewMode, setViewMode] = useState(initialView);

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
    let cancelled = false;
    fetch(`${API}/location/estimate`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled) return;
        if (
          data &&
          Number.isFinite(data.latitude) &&
          Number.isFinite(data.longitude)
        ) {
          setEstimatedLocation({ lat: data.latitude, lon: data.longitude });
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
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const loc = { lat: pos.coords.latitude, lon: pos.coords.longitude };
          setLocation(loc);
          sessionStorage.setItem('userLocation', JSON.stringify(loc));
        },
        () => {
          setLocation(null);
          sessionStorage.removeItem('userLocation');
        },
        { enableHighAccuracy: false, timeout: 3000, maximumAge: 600000 }
      );
    }
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

  const localizedName = (item) =>
    lang === 'de' ? item.name_de || item.name_en : item.name_en || item.name_de;

  const handleViewChange = (mode) => {
    setViewMode(mode);
  };

  const handleSelectZoo = (zoo) => {
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
        <div className="btn-group" role="group" aria-label={t('zoo.viewMode')}>
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
        </div>
      </div>
      {viewMode === 'list' ? (
        <div className="list-group">
          {filtered.map((z) => (
            <Link
              key={z.id}
              className="list-group-item list-group-item-action text-start w-100 text-decoration-none text-reset"
              to={`${prefix}/zoos/${z.slug || z.id}`}
            >
              <div className="d-flex justify-content-between">
                <div>
                  <div className="fw-bold">
                    {z.city ? `${z.city}: ${z.name}` : z.name}
                  </div>
                  <div className="text-muted">📍 {z.address}</div>
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
          ))}
          {filtered.length === 0 && (
            <div className="list-group-item text-muted" role="status">
              {t('zoo.noResults')}
            </div>
          )}
        </div>
      ) : filtered.length > 0 ? (
        <ZoosMap
          zoos={filtered}
          center={activeLocation}
          onSelect={handleSelectZoo}
        />
      ) : (
        <div className="alert alert-info" role="status">
          {t('zoo.noResults')}
        </div>
      )}
    </div>
  );
}

