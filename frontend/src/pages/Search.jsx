import { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { API } from '../api';
import Seo from '../components/Seo';

// Global search results page

function useQuery() {
  return new URLSearchParams(useLocation().search);
}

export default function SearchPage() {
  const navigate = useNavigate();
  const { lang } = useParams();
  const prefix = `/${lang}`;
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
      <h2>Search Results for &quot;{query}&quot;</h2>
      <h3>Zoos</h3>
      <ul>
        {zoos.map((z) => (
          <li key={z.slug || z.id}>
            <button onClick={() => navigate(`${prefix}/zoos/${z.slug || z.id}`)}>
              {z.city ? `${z.city}: ${z.name}` : z.name}
            </button>
          </li>
        ))}
      </ul>
      <h3>Animals</h3>
      <ul>
        {animals.map((a) => (
          <li key={a.slug || a.id}>
            <button onClick={() => navigate(`${prefix}/animals/${a.slug || a.id}`)}>
              {lang === 'de' ? a.name_de || a.name_en : a.name_en || a.name_de}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
