import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import Seo from '../components/Seo';

// Listing page showing all zoos with search, region filters and visit status.

export default function ZoosPage({ token }) {
  const navigate = useNavigate();
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const [zoos, setZoos] = useState([]);
  const [visitedIds, setVisitedIds] = useState([]);
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [continents, setContinents] = useState([]);
  const [countries, setCountries] = useState([]);
  const [continentId, setContinentId] = useState('');
  const [countryId, setCountryId] = useState('');
  const [searchParams, setSearchParams] = useSearchParams();
  const [visitFilter, setVisitFilter] = useState(() => {
    const v = searchParams.get('visit');
    return v === 'visited' || v === 'not' ? v : 'all';
  }); // all | visited | not
  const [visitedLoading, setVisitedLoading] = useState(true);
  const [location, setLocation] = useState(() => {
    const stored = sessionStorage.getItem('userLocation');
    return stored ? JSON.parse(stored) : null;
  });
  const authFetch = useAuthFetch(token);
  const { t } = useTranslation();

  useEffect(() => {
    const c = searchParams.get('continent') || '';
    const co = searchParams.get('country') || '';
    const qParam = searchParams.get('q') || '';
    setContinentId(c);
    setCountryId(co);
    setSearch(qParam);
    setQuery(qParam);
  }, []);

  useEffect(() => {
    const params = {};
    if (query) params.q = query;
    if (continentId) params.continent = continentId;
    if (countryId) params.country = countryId;
    if (visitFilter !== 'all') params.visit = visitFilter;
    setSearchParams(params);
  }, [query, continentId, countryId, visitFilter, setSearchParams]);

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

  useEffect(() => {
    const params = new URLSearchParams();
    if (location) {
      params.set('latitude', location.lat);
      params.set('longitude', location.lon);
    }
    if (query) params.set('q', query);
    if (continentId) params.set('continent_id', continentId);
    if (countryId) params.set('country_id', countryId);
    fetch(`${API}/zoos${params.toString() ? `?${params.toString()}` : ''}`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setZoos)
      .catch(() => setZoos([]));
  }, [location, query, continentId, countryId]);

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
    if (!token) {
      setVisitedLoading(false);
      return;
    }
    setVisitedLoading(true);
    authFetch(`${API}/visits/ids`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setVisitedIds)
      .catch(() => setVisitedIds([]))
      .finally(() => setVisitedLoading(false));
  }, [token, authFetch]);

  const visitedSet = useMemo(() => new Set(visitedIds.map(String)), [visitedIds]);

  const updateVisitFilter = (v) => {
    setVisitFilter(v);
    const params = new URLSearchParams(searchParams);
    if (v === 'all') params.delete('visit');
    else params.set('visit', v);
    setSearchParams(params);
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
      <div className="list-group">
        {filtered.map((z) => (
          <button
            key={z.id}
            type="button"
            className="list-group-item list-group-item-action text-start w-100"
            onClick={() => navigate(`${prefix}/zoos/${z.id}`)}
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
          </button>
        ))}
      </div>
    </div>
  );
}

