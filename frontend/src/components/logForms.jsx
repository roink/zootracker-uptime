import React, { useState, useEffect, useRef } from 'react';
import { API } from '../api';
import searchCache from '../searchCache';

// Reusable forms for logging sightings and zoo visits. These components are used
// within the dashboard to submit data to the FastAPI backend.

// Form used to log a new animal sighting. When `animals` or `zoos` are not
// provided, they are fetched from the API. `defaultAnimalId` and
// `defaultZooId` pre‑select values but the user can search to change them.
export function LogSighting({
  token,
  userId,
  animals: propAnimals = null,
  zoos: propZoos = null,
  defaultAnimalId = '',
  defaultZooId = '',
  initialAnimalName = '',
  initialZooName = '',

  onLogged,
  onCancel,
}) {
  const [animals, setAnimals] = useState(propAnimals || []);
  const [zoos, setZoos] = useState(propZoos || []);
  const [animalId, setAnimalId] = useState(defaultAnimalId);
  const [zooId, setZooId] = useState(defaultZooId);
  // Inputs start with provided names so the form can show defaults
  const [animalInput, setAnimalInput] = useState(initialAnimalName);
  const [zooInput, setZooInput] = useState(initialZooName);
  const [zooSuggestions, setZooSuggestions] = useState([]);
  const [animalSuggestions, setAnimalSuggestions] = useState([]);
  const [zooFocused, setZooFocused] = useState(false);
  const [animalFocused, setAnimalFocused] = useState(false);
  const zooFetch = useRef(null);
  const animalFetch = useRef(null);
  // Date input defaults to today
  const [sightingDate, setSightingDate] = useState(
    () => new Date().toISOString().split('T')[0]
  );


  useEffect(() => {
    if (!propAnimals) {
      fetch(`${API}/animals`).then(r => r.json()).then(setAnimals);
    }
    if (!propZoos) {
      fetch(`${API}/zoos`).then(r => r.json()).then(setZoos);
    }
  }, [propAnimals, propZoos]);

  useEffect(() => {
    if (!zooFocused || !zooInput.trim()) {
      setZooSuggestions([]);
      if (zooFetch.current) zooFetch.current.abort();
      return;
    }
    const q = zooInput.trim().toLowerCase();
    const cached = searchCache[q];
    if (cached) {
      setZooSuggestions(cached.zoos);
      return;
    }
    const controller = new AbortController();
    zooFetch.current = controller;
    const t = setTimeout(() => {
      fetch(`${API}/search?q=${encodeURIComponent(q)}&limit=5`, {
        signal: controller.signal,
      })
        .then((r) => r.json())
        .then((res) => {
          searchCache[q] = res;
          if (!controller.signal.aborted) setZooSuggestions(res.zoos);
        })
        .catch(() => {
          if (!controller.signal.aborted) setZooSuggestions([]);
        });
    }, 500);
    return () => {
      clearTimeout(t);
      controller.abort();
    };
  }, [zooInput, zooFocused]);

  useEffect(() => {
    if (!animalFocused || !animalInput.trim()) {
      setAnimalSuggestions([]);
      if (animalFetch.current) animalFetch.current.abort();
      return;
    }
    const q = animalInput.trim().toLowerCase();
    const cached = searchCache[q];
    if (cached) {
      setAnimalSuggestions(cached.animals);
      return;
    }
    const controller = new AbortController();
    animalFetch.current = controller;
    const t = setTimeout(() => {
      fetch(`${API}/search?q=${encodeURIComponent(q)}&limit=5`, {
        signal: controller.signal,
      })
        .then((r) => r.json())
        .then((res) => {
          searchCache[q] = res;
          if (!controller.signal.aborted) setAnimalSuggestions(res.animals);
        })
        .catch(() => {
          if (!controller.signal.aborted) setAnimalSuggestions([]);
        });
    }, 500);
    return () => {
      clearTimeout(t);
      controller.abort();
    };
  }, [animalInput, animalFocused]);

  useEffect(() => {
    const a = animals.find(a => a.id === (animalId || defaultAnimalId));
    if (a) setAnimalInput(a.common_name);
  }, [animals, animalId, defaultAnimalId]);

  useEffect(() => {
    const z = zoos.find(z => z.id === (zooId || defaultZooId));
    if (z) setZooInput(z.name);
  }, [zoos, zooId, defaultZooId]);

  // Send a new sighting to the API for the selected animal and zoo.
  const submit = async (e) => {
    e.preventDefault();
    const uid = userId || localStorage.getItem('userId');
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
      user_id: uid,
      sighting_datetime: new Date(sightingDate).toISOString(),
    };
    const resp = await fetch(`${API}/sightings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(sighting)
    });
    if (resp.ok) {
      onLogged && onLogged();
    } else {
      alert('Failed to log sighting');
    }
  };

  return (
    <form onSubmit={submit} className="mb-3">
      <h3>New Sighting</h3>
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
                    setZooSuggestions([]);
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
                    setAnimalInput(a.common_name);
                    setAnimalSuggestions([]);
                    setAnimalFocused(false);
                  }}
                >
                  {a.common_name}
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
            className="btn btn-secondary me-2"
            onClick={onCancel}
          >
            Cancel
          </button>
        )}
        <button className="btn btn-primary" type="submit">
          Add Sighting
        </button>
      </div>
    </form>
  );
}

export function LogVisit({ token, userId, zoos, onLogged }) {
  const [zooId, setZooId] = useState(zoos[0]?.id || '');
  const [visitDate, setVisitDate] = useState('');

  useEffect(() => {
    if (!zooId && zoos.length > 0) {
      setZooId(zoos[0].id);
    }
  }, [zoos]);

  // Record a zoo visit for the chosen date.
  const submit = async (e) => {
    e.preventDefault();
    const uid = userId || localStorage.getItem('userId');
    if (!uid) {
      alert('User not available');
      return;
    }
    const visit = { zoo_id: zooId, visit_date: visitDate };
    const resp = await fetch(`${API}/users/${uid}/visits`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(visit)
    });
    if (resp.ok) {
      onLogged && onLogged();
      setVisitDate('');
    } else {
      alert('Failed to log visit');
    }
  };

  return (
    <form onSubmit={submit} className="mb-3">
      <h3>Log Visit</h3>
      <div className="mb-2">
        <select
          className="form-select"
          value={zooId}
          onChange={(e) => setZooId(e.target.value)}
        >
          {zoos.map((z) => (
            <option key={z.id} value={z.id}>{z.name}</option>
          ))}
        </select>
      </div>
      <div className="mb-2">
        <input
          className="form-control"
          type="date"
          value={visitDate}
          onChange={(e) => setVisitDate(e.target.value)}
        />
      </div>
      <button className="btn btn-primary" type="submit">Log Visit</button>
    </form>
  );
}
