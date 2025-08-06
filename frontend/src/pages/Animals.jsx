import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import Seo from '../components/Seo';

// Browse all animals with category filters, search and load-more pagination

export default function AnimalsPage({ token, userId }) {
  const navigate = useNavigate();
  const [animals, setAnimals] = useState([]);
  const [seenAnimals, setSeenAnimals] = useState([]);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('All');
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const authFetch = useAuthFetch(token);
  const limit = 20; // number of animals per page

  // Fetch a page of animals from the API
  const loadAnimals = (reset = false) => {
    const currentOffset = reset ? 0 : offset;
    if (reset) setHasMore(false); // hide button until the first page loads
    fetch(`${API}/animals?limit=${limit}&offset=${currentOffset}&q=${encodeURIComponent(query)}`)
      .then((r) => r.json())
      .then((data) => {
        setAnimals((prev) => (reset ? data : [...prev, ...data]));
        setOffset(currentOffset + data.length);
        setHasMore(data.length === limit);
      });
  };

  // Initial load and reset when the search query changes
  useEffect(() => {
    loadAnimals(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  // load animals seen by the current user
  useEffect(() => {
    if (!token || !userId) return;
    authFetch(`${API}/users/${userId}/animals`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setSeenAnimals)
      .catch(() => setSeenAnimals([]));
  }, [token, userId, authFetch]);

  const seenIds = useMemo(() => new Set(seenAnimals.map((a) => a.id)), [seenAnimals]);
  const categories = useMemo(() => {
    const set = new Set(animals.map((a) => a.category).filter(Boolean));
    return ['All', ...Array.from(set)];
  }, [animals]);

  // Apply category filter to the loaded animals
  const filtered = animals.filter((a) => (category === 'All' ? true : a.category === category));

  return (
    <div className="container">
      <Seo
        title="Animals"
        description="Browse animals and track the ones you've seen."
      />
      <div className="row mb-3">
        <div className="col-md-6 mb-2">
          <input
            className="form-control"
            placeholder="Search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOffset(0);
              setHasMore(false);
            }}
          />
        </div>
        <div className="col-md-6 mb-2">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategory(cat)}
              className={`btn btn-sm me-2 ${category === cat ? 'btn-primary' : 'btn-outline-primary'}`}
            >
              {cat}
            </button>
          ))}
        </div>
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
      {hasMore && (
        <div className="text-center my-3">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => loadAnimals(false)}
          >
            Load more
          </button>
        </div>
      )}
    </div>
  );
}

