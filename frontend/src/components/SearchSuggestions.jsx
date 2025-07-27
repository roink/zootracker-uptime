import React from 'react';

// Dropdown list showing search suggestions below the header search field.
export default function SearchSuggestions({ results, onSelect }) {
  return (
    <ul className="list-group position-absolute top-100 start-0 search-suggestions">
      {results.zoos.map((z) => (
        <li key={`z-${z.id}`} className="list-group-item">
          <button className="btn btn-link p-0" onClick={() => onSelect('zoo', z.id)}>
            {z.name}
          </button>
        </li>
      ))}
      {results.animals.map((a) => (
        <li key={`a-${a.id}`} className="list-group-item">
          <button className="btn btn-link p-0" onClick={() => onSelect('animal', a.id)}>
            {a.common_name}
          </button>
        </li>
      ))}
    </ul>
  );
}
