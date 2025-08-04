import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { API } from '../api';
import Seo from '../components/Seo';

// Global search results page

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
    fetch(`${API}/search?q=${encodeURIComponent(query)}&limit=50`)
      .then((r) => r.json())
      .then((res) => {
        setZoos(res.zoos);
        setAnimals(res.animals);
      });
  }, [query]);

  return (
    <div className="page-container">
      <Seo
        title="Search"
        description="Find zoos and animals on ZooTracker."
      />
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
