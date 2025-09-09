import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import Seo from '../components/Seo';

// Listing page showing all zoos with filters for region, search query and visit status.

export default function ZoosPage({ token }) {
  const navigate = useNavigate();
  const [zoos, setZoos] = useState([]);
  const [visitedIds, setVisitedIds] = useState([]);
  const [query, setQuery] = useState('');
  const [region, setRegion] = useState('All');
  const [visitFilter, setVisitFilter] = useState('all'); // all | visited | not
  // Persist user location so zoos remain sorted by distance across navigation
  const [location, setLocation] = useState(() => {
    const stored = sessionStorage.getItem('userLocation');
    return stored ? JSON.parse(stored) : null;
  });
  const authFetch = useAuthFetch(token);

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
    if (!token) return;
    authFetch(`${API}/visits/ids`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setVisitedIds)
      .catch(() => setVisitedIds([]));
  }, [token, authFetch]);

  const visitedSet = useMemo(() => new Set(visitedIds), [visitedIds]);

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
        if (visitFilter === 'visited') return visitedSet.has(z.id);
        if (visitFilter === 'not') return !visitedSet.has(z.id);
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
          {/* Visit filter: show all, only visited, or only not visited zoos */}
          <div className="btn-group w-100" role="group" aria-label="Visit filter">
            <input
              type="radio"
              className="btn-check"
              name="visit-filter"
              id="visit-all"
              autoComplete="off"
              checked={visitFilter === 'all'}
              onChange={() => setVisitFilter('all')}
            />
            <label className="btn btn-outline-primary" htmlFor="visit-all">All</label>

            <input
              type="radio"
              className="btn-check"
              name="visit-filter"
              id="visit-visited"
              autoComplete="off"
              checked={visitFilter === 'visited'}
              onChange={() => setVisitFilter('visited')}
            />
            <label className="btn btn-outline-primary" htmlFor="visit-visited">Visited</label>

            <input
              type="radio"
              className="btn-check"
              name="visit-filter"
              id="visit-not"
              autoComplete="off"
              checked={visitFilter === 'not'}
              onChange={() => setVisitFilter('not')}
            />
            <label className="btn btn-outline-primary" htmlFor="visit-not">Not visited</label>
          </div>
        </div>
      </div>
      <div className="list-group">
        {filtered.map((z) => (
          <button
            key={z.id}
            type="button"
            className="list-group-item list-group-item-action text-start w-100"
            onClick={() => navigate(`/zoos/${z.id}`)}
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
                {visitedSet.has(z.id) && (
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
