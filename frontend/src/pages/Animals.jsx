import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';

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
    <div style={{ padding: '20px' }}>
      <div style={{ marginBottom: '10px' }}>
        <input
          placeholder="Search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div style={{ marginBottom: '10px' }}>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            style={{
              marginRight: '5px',
              padding: '4px 8px',
              border: '1px solid #ccc',
              borderRadius: '16px',
              background: category === cat ? '#1976d2' : '#eee',
              color: category === cat ? 'white' : 'black',
              cursor: 'pointer',
            }}
          >
            {cat}
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
        {filtered.map((a) => (
          <div
            key={a.id}
            onClick={() => navigate(`/animals/${a.id}`)}
            style={{
              border: '1px solid #ccc',
              padding: '10px',
              width: '150px',
              cursor: 'pointer',
            }}
          >
            <img
              src={a.default_image_url || 'https://via.placeholder.com/150'}
              alt={a.common_name}
              style={{ width: '100%', height: '100px', objectFit: 'cover', marginBottom: '5px' }}
            />
            <div style={{ fontWeight: 'bold' }}>{a.common_name}</div>
            {a.scientific_name && (
              <div style={{ fontStyle: 'italic', fontSize: '0.9em' }}>{a.scientific_name}</div>
            )}
            {seenIds.has(a.id) && (
              <span
                style={{
                  display: 'inline-block',
                  marginTop: '4px',
                  background: '#4caf50',
                  color: 'white',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  fontSize: '12px',
                }}
              >
                Seen
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

