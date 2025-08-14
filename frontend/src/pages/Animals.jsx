import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import Seo from '../components/Seo';

// Browse all animals with category filters, search and load-more pagination

export default function AnimalsPage({ token, userId }) {
  const navigate = useNavigate();
  const [animals, setAnimals] = useState([]);
  const [seenAnimals, setSeenAnimals] = useState([]);
  const [search, setSearch] = useState(''); // raw input value
  const [query, setQuery] = useState(''); // debounced search query
  const [category, setCategory] = useState('All');
  const [categories, setCategories] = useState(['All']);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const authFetch = useAuthFetch(token);
  const limit = 20; // number of animals per page

  // Map backend category names to German class labels
  // Explicit "Klasse N" keys are provided per client request while English
  // names serve as fallbacks when the backend uses them
  const classLabels = {
    'Klasse 1': 'S\u00e4ugetiere',
    'Klasse 2': 'V\u00f6gel',
    'Klasse 3': 'Reptilien',
    'Klasse 4': 'Amphibien',
    'Klasse 5': 'Fische',
    'Klasse 6': 'Haustiere',
    All: 'Alle',
    Mammal: 'S\u00e4ugetiere',
    Bird: 'V\u00f6gel',
    Reptile: 'Reptilien',
    Amphibian: 'Amphibien',
    Fish: 'Fische',
    Domestic: 'Haustiere',
  };

  // Fetch a page of animals from the API
  const loadAnimals = (reset = false) => {
    const currentOffset = reset ? 0 : offset;
    if (reset) setHasMore(false); // hide button until the first page loads
    setLoading(true);
    setError('');
    const catParam = category !== 'All' ? `&category=${encodeURIComponent(category)}` : '';
    fetch(`${API}/animals?limit=${limit}&offset=${currentOffset}&q=${encodeURIComponent(query)}${catParam}`)
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load');
        return r.json();
      })
      .then((data) => {
        setAnimals((prev) => (reset ? data : [...prev, ...data]));
        setOffset(currentOffset + data.length);
        setHasMore(data.length === limit);
        setCategories((prev) => {
          const set = new Set(prev);
          data.forEach((a) => a.category && set.add(a.category));
          return ['All', ...Array.from(set).filter((c) => c !== 'All')];
        });
      })
      .catch(() => setError('Failed to load animals'))
      .finally(() => setLoading(false));
  };

  // Debounce the search input to avoid fetching on every keystroke
  useEffect(() => {
    const id = setTimeout(() => {
      setQuery(search);
    }, 500);
    return () => clearTimeout(id);
  }, [search]);

  // Initial load and reset when the debounced query or category changes
  useEffect(() => {
    loadAnimals(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, category]);

  // load animals seen by the current user
  useEffect(() => {
    if (!token || !userId) return;
    authFetch(`${API}/users/${userId}/animals`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setSeenAnimals)
      .catch(() => setSeenAnimals([]));
  }, [token, userId, authFetch]);

  const seenIds = useMemo(() => new Set(seenAnimals.map((a) => a.id)), [seenAnimals]);

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
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setAnimals([]); // clear old cards while new results load
              setOffset(0);
              setHasMore(false);
            }}
          />
        </div>
        <div className="col-md-6 mb-2">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => {
                setCategory(cat);
                setAnimals([]); // remove stale cards immediately
                setOffset(0);
                setHasMore(false);
              }}
              className={`btn btn-sm me-2 ${category === cat ? 'btn-primary' : 'btn-outline-primary'}`}
            >
              {classLabels[cat] || cat}
            </button>
          ))}
        </div>
      </div>
      {error && (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      )}
      <div className="d-flex flex-wrap gap-2">
        {animals.map((a) => (
          <button
            key={a.id}
            type="button"
            className="animal-card"
            onClick={() => navigate(`/animals/${a.id}`)}
          >
            <img
              src={a.default_image_url || 'https://via.placeholder.com/150'}
              alt={a.scientific_name || a.common_name}
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
            disabled={loading}
          >
            {loading ? 'Loading...' : 'Load more'}
          </button>
        </div>
      )}
    </div>
  );
}

