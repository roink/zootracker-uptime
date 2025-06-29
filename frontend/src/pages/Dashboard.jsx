import React, { useState, useEffect, useMemo } from 'react';
import { LogVisit, LogSighting } from '../components/logForms';
import { API } from '../api';

export default function Dashboard({ token, userId, zoos, animals, refresh, onUpdate }) {
  const [visits, setVisits] = useState([]);
  const [seenAnimals, setSeenAnimals] = useState([]);
  const [sightings, setSightings] = useState([]);
  const [badges, setBadges] = useState([]);
  const [showVisitForm, setShowVisitForm] = useState(false);
  const [showSightingForm, setShowSightingForm] = useState(false);

  useEffect(() => {
    fetch(`${API}/visits`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then(setVisits);
    fetch(`${API}/users/${userId}/animals`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then(setSeenAnimals);
    fetch(`${API}/sightings`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then(setSightings);
    fetch(`${API}/users/${userId}/achievements`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then(setBadges)
      .catch(() => setBadges([]));
  }, [token, userId, refresh]);

  const feedItems = useMemo(() => {
    const v = visits.map((x) => ({ type: 'visit', date: x.visit_date, item: x }));
    const s = sightings.map((x) => ({ type: 'sighting', date: x.sighting_datetime, item: x }));
    return [...v, ...s].sort((a, b) => new Date(b.date) - new Date(a.date));
  }, [visits, sightings]);

  const zooName = (id) => zoos.find((z) => z.id === id)?.name || id;
  const animalName = (id) => animals.find((a) => a.id === id)?.common_name || id;

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-around', marginBottom: '20px' }}>
        <div>Zoos Visited: {new Set(visits.map((v) => v.zoo_id)).size}</div>
        <div>Animals Seen: {seenAnimals.length}</div>
        <div>Badges: {badges.length}</div>
      </div>
      <h3>Activity Feed</h3>
      <ul>
        {feedItems.map((f, idx) => (
          <li key={idx}>
            {f.type === 'visit'
              ? `Visited ${zooName(f.item.zoo_id)} on ${f.item.visit_date}`
              : `Saw ${animalName(f.item.animal_id)} at ${zooName(f.item.zoo_id)}`}
          </li>
        ))}
      </ul>
      <h3>Recent Badges</h3>
      <div style={{ display: 'flex', overflowX: 'auto', marginBottom: '20px' }}>
        {badges.length === 0 && <div style={{ padding: '10px' }}>No badges yet</div>}
        {badges.map((b) => (
          <div key={b.id} style={{ marginRight: '10px' }}>{b.name}</div>
        ))}
      </div>
      <div style={{ marginTop: '10px' }}>
        <button onClick={() => setShowSightingForm((s) => !s)} style={{ marginRight: '10px' }}>
          Log Sighting
        </button>
        <button onClick={() => setShowVisitForm((v) => !v)}>Log Visit</button>
      </div>
      {showVisitForm && (
        <div style={{ marginTop: '20px' }}>
          <LogVisit
            token={token}
            userId={userId}
            zoos={zoos}
            onLogged={() => {
              onUpdate && onUpdate();
              setShowVisitForm(false);
            }}
          />
        </div>
      )}
      {showSightingForm && (
        <div style={{ marginTop: '20px' }}>
          <LogSighting
            token={token}
            userId={userId}
            animals={animals}
            zoos={zoos}
            onLogged={() => {
              onUpdate && onUpdate();
              setShowSightingForm(false);
            }}
          />
        </div>
      )}
    </div>
  );
}
