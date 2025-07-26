import React, { useState, useEffect, useMemo } from 'react';
import { LogVisit, LogSighting } from '../components/logForms';
import { API } from '../api';

// User dashboard showing recent visits, sightings and badges. Includes
// buttons to open forms for logging additional activity.

export default function Dashboard({ token, userId, zoos, animals, refresh, onUpdate }) {
  const [visits, setVisits] = useState([]);
  const [seenAnimals, setSeenAnimals] = useState([]);
  const [sightings, setSightings] = useState([]);
  const [badges, setBadges] = useState([]);
  const [showVisitForm, setShowVisitForm] = useState(false);
  const [showSightingForm, setShowSightingForm] = useState(false);

  useEffect(() => {
    const uid = userId || localStorage.getItem('userId');
    fetch(`${API}/visits`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then(setVisits);
    if (!uid) return;
    fetch(`${API}/users/${uid}/animals`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then(setSeenAnimals);
    fetch(`${API}/sightings`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then(setSightings);
    fetch(`${API}/users/${uid}/achievements`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then(setBadges)
      .catch(() => setBadges([]));
  }, [token, userId, refresh]);

  // Combine visits and sightings into a single chronologically sorted feed.
  const feedItems = useMemo(() => {
    const v = visits.map((x) => ({ type: 'visit', date: x.visit_date, item: x }));
    const s = sightings.map((x) => ({ type: 'sighting', date: x.sighting_datetime, item: x }));
    return [...v, ...s].sort((a, b) => new Date(b.date) - new Date(a.date));
  }, [visits, sightings]);

  const zooName = (id) => zoos.find((z) => z.id === id)?.name || id;
  const animalName = (id) => animals.find((a) => a.id === id)?.common_name || id;

  return (
    <div className="container">
      <div className="row text-center mb-3">
        <div className="col">Zoos Visited: {new Set(visits.map((v) => v.zoo_id)).size}</div>
        <div className="col">Animals Seen: {seenAnimals.length}</div>
        <div className="col">Badges: {badges.length}</div>
      </div>
      <h3>Activity Feed</h3>
      <ul className="list-group mb-3">
        {feedItems.map((f, idx) => (
          <li key={idx} className="list-group-item">
            {f.type === 'visit'
              ? `Visited ${zooName(f.item.zoo_id)} on ${f.item.visit_date}`
              : `Saw ${animalName(f.item.animal_id)} at ${zooName(f.item.zoo_id)}`}
          </li>
        ))}
      </ul>
      <h3>Recent Badges</h3>
      <div className="d-flex overflow-auto mb-3">
        {badges.length === 0 && <div className="p-2">No badges yet</div>}
        {badges.map((b) => (
          <div key={b.id} className="me-2">{b.name}</div>
        ))}
      </div>
      <div className="mt-2">
        <button className="btn btn-secondary me-2" onClick={() => setShowSightingForm((s) => !s)}>
          Log Sighting
        </button>
        <button className="btn btn-primary" onClick={() => setShowVisitForm((v) => !v)}>
          Log Visit
        </button>
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
