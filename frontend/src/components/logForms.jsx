import React, { useState, useEffect } from 'react';
import { API } from '../api';

export function LogSighting({ token, userId, animals, zoos, onLogged }) {
  const [animalId, setAnimalId] = useState(animals[0]?.id || '');
  const [zooId, setZooId] = useState(zoos[0]?.id || '');

  const submit = async (e) => {
    e.preventDefault();
    const sighting = {
      zoo_id: zooId,
      animal_id: animalId,
      user_id: userId,
      sighting_datetime: new Date().toISOString()
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
    <form onSubmit={submit}>
      <h3>Log Sighting</h3>
      <select value={zooId} onChange={(e) => setZooId(e.target.value)}>
        {zoos.map((z) => (
          <option key={z.id} value={z.id}>{z.name}</option>
        ))}
      </select>
      <select value={animalId} onChange={(e) => setAnimalId(e.target.value)}>
        {animals.map((a) => (
          <option key={a.id} value={a.id}>{a.common_name}</option>
        ))}
      </select>
      <button type="submit">Log</button>
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

  const submit = async (e) => {
    e.preventDefault();
    const visit = { zoo_id: zooId, visit_date: visitDate };
    const resp = await fetch(`${API}/users/${userId}/visits`, {
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
    <form onSubmit={submit}>
      <h3>Log Visit</h3>
      <select value={zooId} onChange={(e) => setZooId(e.target.value)}>
        {zoos.map((z) => (
          <option key={z.id} value={z.id}>{z.name}</option>
        ))}
      </select>
      <input
        type="date"
        value={visitDate}
        onChange={(e) => setVisitDate(e.target.value)}
      />
      <button type="submit">Log Visit</button>
    </form>
  );
}
