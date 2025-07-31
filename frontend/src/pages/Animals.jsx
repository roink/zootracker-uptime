import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';

// Browse all animals with category filters and search

export default function AnimalsPage({ token, userId }) {
  const navigate = useNavigate();
  const [animals, setAnimals] = useState([]);
  const [seenAnimals, setSeenAnimals] = useState([]);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('All');
  const authFetch = useAuthFetch();

  // load animal list and fetch details for scientific name and category
  useEffect(() => {
    fetch(`${API}/animals`)
      .then((r) => r.json())
      .then(async (list) => {
        const detailed = await Promise.all(
          list.map(async (a) => {
            const resp = await fetch(`${API}/animals/${a.id}`);
            if (resp.ok) {
              const info = await resp.json();
              return { ...a, ...info };
            }
            return a;
          })
        );
        setAnimals(detailed);
      });
  }, []);

  // load animals seen by the current user
  useEffect(() => {
    if (!token || !userId) return;
    authFetch(`${API}/users/${userId}/animals`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then(setSeenAnimals)
      .catch(() => setSeenAnimals([]));
  }, [token, userId]);

  const seenIds = useMemo(() => new Set(seenAnimals.map((a) => a.id)), [seenAnimals]);
  const categories = useMemo(() => {
    const set = new Set(animals.map((a) => a.category).filter(Boolean));
    return ['All', ...Array.from(set)];
  }, [animals]);

  const filtered = animals
    .filter((a) => a.common_name.toLowerCase().includes(query.toLowerCase()))
    .filter((a) => (category === 'All' ? true : a.category === category));

  return (
    <div className="page-container">
      <div className="spaced-bottom">
        <input
          placeholder="Search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="spaced-bottom">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={`filter-button${category === cat ? ' active' : ''}`}
          >
            {cat}
          </button>
        ))}
      </div>
      <div className="d-flex flex-wrap gap-2">
        {filtered.map((a) => (
          <button
            key={a.id}
            type="button"
            className="animal-card"
            onClick={() => navigate(`/animals/${a.id}`)}
          >
            <img
              src={a.default_image_url || 'https://via.placeholder.com/150'}
              alt={a.common_name}
              className="card-img"
            />
            <div className="fw-bold">{a.common_name}</div>
            {a.scientific_name && (
              <div className="fst-italic small">{a.scientific_name}</div>
            )}
            {seenIds.has(a.id) && (
              <span className="seen-badge">
                Seen
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

