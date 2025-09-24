import { useState, useEffect } from 'react';
import { API } from '../api';
import { getZooDisplayName } from '../utils/zooDisplayName.js';

// Simple search component used by the legacy zoos page
export default function ZooSearch({ onSelectZoo }) {
  const [query, setQuery] = useState('');
  const [zoos, setZoos] = useState([]);

  const search = () => {
    fetch(`${API}/zoos?q=${encodeURIComponent(query)}`)
      .then((r) => r.json())
      .then(setZoos);
  };

  // perform an initial search so the list isn't empty
  useEffect(search, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      <h2>Search Zoos</h2>
      <input
        className="form-control mb-2"
        placeholder="Search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <button className="btn btn-secondary mb-2" onClick={search}>
        Search
      </button>
      <ul className="list-group">
        {zoos.map((z) => (
          <li key={z.id} className="list-group-item">
            <button className="btn btn-link" onClick={() => onSelectZoo(z)}>
              {getZooDisplayName(z)}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
