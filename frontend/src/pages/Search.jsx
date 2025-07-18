import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { API } from '../api';

function useQuery() {
  return new URLSearchParams(useLocation().search);
}

export default function SearchPage() {
  const navigate = useNavigate();
  const query = useQuery().get('q') || '';
  const [zoos, setZoos] = useState([]);
  const [animals, setAnimals] = useState([]);

  useEffect(() => {
    if (!query) return;
    fetch(`${API}/zoos?q=${encodeURIComponent(query)}`)
      .then((r) => r.json())
      .then(setZoos);
    fetch(`${API}/animals?q=${encodeURIComponent(query)}`)
      .then((r) => r.json())
      .then(setAnimals);
  }, [query]);

  return (
    <div style={{ padding: '20px' }}>
      <h2>Search Results for "{query}"</h2>
      <h3>Zoos</h3>
      <ul>
        {zoos.map((z) => (
          <li key={z.id}>
            <button onClick={() => navigate(`/zoos/${z.id}`)}>{z.name}</button>
          </li>
        ))}
      </ul>
      <h3>Animals</h3>
      <ul>
        {animals.map((a) => (
          <li key={a.id}>
            <button onClick={() => navigate(`/animals/${a.id}`)}>
              {a.common_name}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
