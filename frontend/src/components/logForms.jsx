import React, { useState, useEffect } from 'react';
import { API } from '../api';

// Reusable forms for logging sightings and zoo visits. These components are used
// within the dashboard to submit data to the FastAPI backend.

export function LogSighting({ token, userId, animals, zoos, onLogged }) {
  const [animalId, setAnimalId] = useState(animals[0]?.id || '');
  const [zooId, setZooId] = useState(zoos[0]?.id || '');

  // Send a new sighting to the API for the selected animal and zoo.
  const submit = async (e) => {
    e.preventDefault();
    const uid = userId || localStorage.getItem('userId');
    if (!uid) {
      alert('User not available');
      return;
    }
    const sighting = {
      zoo_id: zooId,
      animal_id: animalId,
      user_id: uid,
      sighting_datetime: new Date().toISOString(),
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
      <h3>Log Sighting</h3>
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
        <select
          className="form-select"
          value={animalId}
          onChange={(e) => setAnimalId(e.target.value)}
        >
          {animals.map((a) => (
            <option key={a.id} value={a.id}>{a.common_name}</option>
          ))}
        </select>
      </div>
      <button className="btn btn-primary" type="submit">Log</button>
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
