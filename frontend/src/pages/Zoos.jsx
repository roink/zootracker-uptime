import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams, useParams } from 'react-router-dom';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import Seo from '../components/Seo';
import { useAuth } from '../auth/AuthContext.jsx';

// Listing page showing all zoos with filters for region, search query and visit status.

export default function ZoosPage() {
  const navigate = useNavigate();
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const [zoos, setZoos] = useState([]);
  const [visitedIds, setVisitedIds] = useState([]);
  const [query, setQuery] = useState('');
  const [region, setRegion] = useState('All');
  const [searchParams, setSearchParams] = useSearchParams();
  const [visitFilter, setVisitFilter] = useState(() => {
    const v = searchParams.get('visit');
    return v === 'visited' || v === 'not' ? v : 'all';
  }); // all | visited | not
  const [visitedLoading, setVisitedLoading] = useState(true);
  // Persist user location so zoos remain sorted by distance across navigation
  const [location, setLocation] = useState(() => {
    const stored = sessionStorage.getItem('userLocation');
    return stored ? JSON.parse(stored) : null;
  });
  const authFetch = useAuthFetch();
  const { isAuthenticated } = useAuth();

  // Fetch zoos sorted by distance when location is available
  useEffect(() => {
    const params = [];
    if (location) {
      params.push(`latitude=${location.lat}`);
      params.push(`longitude=${location.lon}`);
    }
    fetch(`${API}/zoos${params.length ? `?${params.join('&')}` : ''}`)
      .then((r) => r.json())
      .then(setZoos);
  }, [location]);

  // Determine the current location of the user and cache it
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

  const visitedSet = useMemo(
    () => new Set(visitedIds.map(String)),
    [visitedIds]
  );

  useEffect(() => {
    const v = searchParams.get('visit');
    if (v === 'visited' || v === 'not') {
      setVisitFilter(v);
    } else {
      setVisitFilter('all');
    }
  }, [searchParams]);

  const updateVisitFilter = (v) => {
    setVisitFilter(v);
    const params = new URLSearchParams(searchParams);
    if (v === 'all') params.delete('visit');
    else params.set('visit', v);
    setSearchParams(params);
  };

  // Apply search, visit status and region filters in sequence.
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const r = region.toLowerCase();
    return zoos
      .filter(
        (z) =>
          z.name.toLowerCase().includes(q) ||
          (z.city || '').toLowerCase().includes(q)
      )
      .filter((z) => {
        // Keep zoos based on the selected visit status
        if (visitFilter === 'visited') return visitedSet.has(String(z.id));
        if (visitFilter === 'not') return !visitedSet.has(String(z.id));
        return true;
      })
      .filter((z) =>
        region === 'All'
          ? true
          : (z.address || '').toLowerCase().includes(r)
      );
  }, [zoos, query, region, visitFilter, visitedSet]);

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
            placeholder="Search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="col-md-4 mb-2">
          <select
            className="form-select"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
          >
            <option value="All">All Regions</option>
            <option value="Europe">Europe</option>
            <option value="Asia">Asia</option>
            <option value="Africa">Africa</option>
            <option value="Americas">Americas</option>
            <option value="Oceania">Oceania</option>
          </select>
        </div>
        <div className="col-md-4 mb-2">
          {
            // Visit filter: show all, only visited, or only not visited zoos
          }
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
            <label className="btn btn-outline-primary" htmlFor="visit-all">All</label>

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
            <label className="btn btn-outline-primary" htmlFor="visit-visited">Visited</label>

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
            <label className="btn btn-outline-primary" htmlFor="visit-not">Not visited</label>
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
                <div className="text-muted">
                  📍 {z.address}
                </div>
              </div>
              <div className="text-end">
                {z.distance_km != null && (
                  <div className="small text-muted">
                    {z.distance_km.toFixed(1)} km
                  </div>
                )}
                {visitedSet.has(String(z.id)) && (
                  <span className="badge bg-success mt-1">Visited</span>
                )}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
