import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';

// Listing page showing all zoos with filters for region and search query.

export default function ZoosPage({ token }) {
  const navigate = useNavigate();
  const [zoos, setZoos] = useState([]);
  const [visits, setVisits] = useState([]);
  const [query, setQuery] = useState('');
  const [region, setRegion] = useState('All');
  const [visitedOnly, setVisitedOnly] = useState(false);
  const authFetch = useAuthFetch();

  useEffect(() => {
    fetch(`${API}/zoos`).then((r) => r.json()).then(setZoos);
  }, []);

  useEffect(() => {
    if (!token) return;
    authFetch(`${API}/visits`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then(setVisits)
      .catch(() => setVisits([]));
  }, [token]);

  const visitedIds = useMemo(() => visits.map((v) => v.zoo_id), [visits]);

  // Apply search, visited-only filter and region filter in sequence.
  const filtered = zoos
    .filter((z) => z.name.toLowerCase().includes(query.toLowerCase()))
    .filter((z) => (visitedOnly ? visitedIds.includes(z.id) : true))
    .filter((z) =>
      region === 'All' ? true : (z.address || '').toLowerCase().includes(region.toLowerCase())
    );

  return (
    <div className="container">
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
        <div className="col-md-4 d-flex align-items-center">
          <div className="form-check">
            <input
              className="form-check-input"
              id="visitedOnly"
              type="checkbox"
              checked={visitedOnly}
              onChange={(e) => setVisitedOnly(e.target.checked)}
            />
            <label className="form-check-label" htmlFor="visitedOnly">Visited</label>
          </div>
        </div>
      </div>
      <div className="list-group">
        {filtered.map((z) => (
          <div
            key={z.id}
            className="list-group-item list-group-item-action"
            onClick={() => navigate(`/zoos/${z.id}`)}
          >
            <div className="d-flex justify-content-between">
              <div>
                <div className="fw-bold">{z.name}</div>
                <div className="text-muted">📍 {z.address}</div>
              </div>
              {visitedIds.includes(z.id) && (
                <span className="badge bg-success align-self-center">Visited</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
