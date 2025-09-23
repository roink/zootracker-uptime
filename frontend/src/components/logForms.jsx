import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { API } from '../api';

import useAuthFetch from '../hooks/useAuthFetch';
import useSearchSuggestions from '../hooks/useSearchSuggestions';
import { useAuth } from '../auth/AuthContext.jsx';

// Reusable forms for logging sightings and zoo visits. These components are used
// within the dashboard to submit data to the FastAPI backend.

// Form used to log a new animal sighting. When `animals` or `zoos` are not
// provided, they are fetched from the API. `defaultAnimalId` and
// `defaultZooId` pre‑select values but the user can search to change them.
export function LogSighting({
  animals: propAnimals = null,
  zoos: propZoos = null,
  defaultAnimalId = '',
  defaultZooId = '',
  defaultDate = null,
  initialAnimalName = '',
  initialZooName = '',
  sightingId = null,

  onLogged,
  onCancel,
  onDeleted,
}) {
  const [animals, setAnimals] = useState(propAnimals || []);
  const [zoos, setZoos] = useState(propZoos || []);
  const [animalId, setAnimalId] = useState(defaultAnimalId);
  const [zooId, setZooId] = useState(defaultZooId);
  // Inputs start with provided names so the form can show defaults
  const [animalInput, setAnimalInput] = useState(initialAnimalName);
  const [zooInput, setZooInput] = useState(initialZooName);
  const [zooFocused, setZooFocused] = useState(false);
  const [animalFocused, setAnimalFocused] = useState(false);
  const { zoos: zooSuggestions } = useSearchSuggestions(zooInput, zooFocused);
  const { animals: animalSuggestions } = useSearchSuggestions(
    animalInput,
    animalFocused
  );
  // Wrapper for fetch that redirects to login on 401
  const authFetch = useAuthFetch();
  const { user } = useAuth();
  const { lang } = useParams();
  const getName = useCallback(
    (a) => (lang === 'de' ? a.name_de || a.name_en : a.name_en || a.name_de),
    [lang]
  );
  // Date input defaults to today
  const [sightingDate, setSightingDate] = useState(
    () => defaultDate || new Date().toISOString().split('T')[0]
  );

  // Update state if defaults change (e.g., after fetching an existing sighting)
  useEffect(() => {
    if (defaultAnimalId) setAnimalId(defaultAnimalId);
  }, [defaultAnimalId]);

  useEffect(() => {
    if (defaultZooId) setZooId(defaultZooId);
  }, [defaultZooId]);

  useEffect(() => {
    if (defaultDate) setSightingDate(defaultDate);
  }, [defaultDate]);


  useEffect(() => {
    if (!propAnimals) {
      fetch(`${API}/animals`).then(r => r.json()).then(setAnimals);
    }
    if (!propZoos) {
      fetch(`${API}/zoos`).then(r => r.json()).then(setZoos);
    }
  }, [propAnimals, propZoos]);


  useEffect(() => {
    const a = animals.find(a => a.id === (animalId || defaultAnimalId));
    if (a) setAnimalInput(getName(a));
  }, [animals, animalId, defaultAnimalId, getName]);

  useEffect(() => {
    const z = zoos.find(z => z.id === (zooId || defaultZooId));
    if (z) setZooInput(z.name);
  }, [zoos, zooId, defaultZooId]);

  // Send a new sighting to the API for the selected animal and zoo.
  const submit = async (e) => {
    e.preventDefault();
    const uid = user?.id;
    if (!uid) {
      alert('User not available');
      return;
    }
    if (!zooId || !animalId) {
      alert('Please choose a zoo and animal');
      return;
    }
    const sighting = {
      zoo_id: zooId,
      animal_id: animalId,
      sighting_datetime: new Date(sightingDate).toISOString(),
    };
    if (!sightingId) {
      // user_id is required only when creating a new sighting
      sighting.user_id = uid;
    }
    const url = sightingId ? `${API}/sightings/${sightingId}` : `${API}/sightings`;
    const method = sightingId ? 'PATCH' : 'POST';
    const resp = await authFetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(sighting)
    });
    if (resp.status === 401) return;
    if (resp.ok) {
      onLogged && onLogged();
    } else {
      alert('Failed to save sighting');
    }
  };

  const handleDelete = async () => {
    if (!sightingId) return;
    const resp = await authFetch(`${API}/sightings/${sightingId}`, {
      method: 'DELETE'
    });
    if (resp.status === 401) return;
    if (resp.ok) {
      onDeleted && onDeleted();
    } else {
      alert('Failed to delete sighting');
    }
  };

  return (
    <form onSubmit={submit} className="mb-3">
      <h3>{sightingId ? 'Edit Sighting' : 'New Sighting'}</h3>
      <div className="mb-2 position-relative">
        {/* Searchable zoo field */}
        <input
          className="form-control"
          placeholder="Zoo"
          value={zooInput}
          onChange={(e) => {
            const val = e.target.value;
            setZooInput(val);
            setZooId('');
          }}
          onFocus={() => setZooFocused(true)}
          onBlur={() => setTimeout(() => setZooFocused(false), 100)}
          required
        />
        {zooFocused && zooSuggestions.length > 0 && (
          <ul className="list-group position-absolute top-100 start-0 search-suggestions">
            {zooSuggestions.map((z) => (
              <li key={z.id} className="list-group-item">
                <button
                  type="button"
                  className="btn btn-link p-0"
                  onMouseDown={() => {
                    setZooId(z.id);
                    setZooInput(z.name);
                    setZooFocused(false);
                  }}
                >
                  {z.name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="mb-2 position-relative">
        {/* Searchable animal field */}
        <input
          className="form-control"
          placeholder="Animal"
          value={animalInput}
          onChange={(e) => {
            const val = e.target.value;
            setAnimalInput(val);
            setAnimalId('');
          }}
          onFocus={() => setAnimalFocused(true)}
          onBlur={() => setTimeout(() => setAnimalFocused(false), 100)}
          required
        />
        {animalFocused && animalSuggestions.length > 0 && (
          <ul className="list-group position-absolute top-100 start-0 search-suggestions">
            {animalSuggestions.map((a) => (
              <li key={a.id} className="list-group-item">
                <button
                  type="button"
                  className="btn btn-link p-0"
                  onMouseDown={() => {
                    setAnimalId(a.id);
                    setAnimalInput(getName(a));
                    setAnimalFocused(false);
                  }}
                >
                  {getName(a)}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="mb-2">
        <input
          className="form-control"
          type="date"
          value={sightingDate}
          onChange={(e) => setSightingDate(e.target.value)}
          required
        />
      </div>
      <div className="text-end">
        {onCancel && (
          <button
            type="button"
            className="btn btn-outline-danger me-2"
            onClick={onCancel}
          >
            Cancel
          </button>
        )}
        {sightingId && (
          <button
            type="button"
            className="btn btn-danger me-2"
            onClick={handleDelete}
          >
            Delete
          </button>
        )}
        <button className="btn btn-primary" type="submit">
          {sightingId ? 'Apply changes' : 'Add Sighting'}
        </button>
      </div>
    </form>
  );
}

