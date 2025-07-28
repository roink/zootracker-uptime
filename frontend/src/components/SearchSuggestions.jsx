import React from 'react';

// Dropdown list showing search suggestions below the header search field.
// Buttons use `onPointerDown` so the selection fires before the input field
// loses focus which keeps taps and clicks reliable on all devices.
export default function SearchSuggestions({ results, onSelect }) {
  const handleDown = (type, id) => onSelect(type, id);

  return (
    <ul className="list-group position-absolute top-100 start-0 search-suggestions">
      {results.zoos.map((z) => (
        <li key={`z-${z.id}`} className="list-group-item">
          <button
            type="button"
            className="btn btn-link p-0"
            onPointerDown={() => handleDown('zoo', z.id)}
          >
            {z.name}
          </button>
        </li>
      ))}
      {results.animals.map((a) => (
        <li key={`a-${a.id}`} className="list-group-item">
          <button
            type="button"
            className="btn btn-link p-0"
            onPointerDown={() => handleDown('animal', a.id)}
          >
            {a.common_name}
          </button>
        </li>
      ))}
    </ul>
  );
}
