import { useState, useEffect, useMemo } from 'react';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import SightingModal from '../components/SightingModal';
import { useNavigate } from 'react-router-dom';
import Seo from '../components/Seo';

// User dashboard showing recent visits, sightings and badges. Includes
// buttons to open forms for logging additional activity.

export default function Dashboard({ token, userId, zoos, animals, refresh, onUpdate }) {
  const [visits, setVisits] = useState([]);
  // Number of unique animals the user has seen
  const [seenCount, setSeenCount] = useState(0);
  const [sightings, setSightings] = useState([]);
  const [badges, setBadges] = useState([]);
  const [modalData, setModalData] = useState(null);
  const navigate = useNavigate();
  const authFetch = useAuthFetch(token);

  useEffect(() => {
    const uid = userId || localStorage.getItem('userId');
    authFetch(`${API}/visits`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then(setVisits)
      .catch(() => setVisits([]));
    if (!uid) return;
    authFetch(`${API}/users/${uid}/animals/count`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : { count: 0 }))
      .then((d) => setSeenCount(d.count ?? 0))
      .catch(() => setSeenCount(0));
    authFetch(`${API}/sightings`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then(setSightings)
      .catch(() => setSightings([]));
    authFetch(`${API}/users/${uid}/achievements`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then(setBadges)
      .catch(() => setBadges([]));
  }, [token, userId, refresh, authFetch]);

  // Combine visits and sightings into a single chronologically sorted feed.
  const feedItems = useMemo(() => {
    const v = visits.map((x) => ({ type: 'visit', date: x.visit_date, item: x }));
    const s = sightings.map((x) => ({ type: 'sighting', date: x.sighting_datetime, item: x }));
    return [...v, ...s].sort((a, b) => new Date(b.date) - new Date(a.date));
  }, [visits, sightings]);

  // Distinct zoo count, derived from visits and sightings in case visit sync is missing.
  const visitedZooCount = useMemo(() => {
    const ids = new Set([
      ...visits.map((v) => v.zoo_id),
      ...sightings.map((s) => s.zoo_id),
    ]);
    return ids.size;
  }, [visits, sightings]);

  const zooName = (id) => zoos.find((z) => z.id === id)?.name || id;
  const animalName = (id) => animals.find((a) => a.id === id)?.common_name || id;

  return (
    <div className="container">
      <Seo
        title="Dashboard"
        description="View your zoo visits, animal sightings and badges."
      />
      <div className="row text-center mb-3">
        <div className="col">Zoos Visited: {visitedZooCount}</div>
        <div className="col">Animals Seen: {seenCount}</div>
        <div className="col">Badges: {badges.length}</div>
      </div>
      <h3>Activity Feed</h3>
      <ul className="list-group mb-3">
        {feedItems.map((f, idx) => (
          <li
            key={idx}
            className="list-group-item d-flex justify-content-between align-items-center"
          >
            <span>
              {f.type === 'visit'
                ? `Visited ${zooName(f.item.zoo_id)} on ${f.item.visit_date}`
                : `Saw ${animalName(f.item.animal_id)} at ${zooName(f.item.zoo_id)} on ${f.item.sighting_datetime.slice(0, 10)}`}
            </span>
            {f.type === 'sighting' && (
              <button
                className="btn btn-sm btn-outline-secondary"
                onClick={() =>
                  setModalData({
                    sightingId: f.item.id,
                    zooId: f.item.zoo_id,
                    zooName: zooName(f.item.zoo_id),
                    animalId: f.item.animal_id,
                    animalName: animalName(f.item.animal_id),
                  })
                }
              >
                Edit
              </button>
            )}
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
        <button
          className="btn btn-secondary me-2"
          onClick={() => {
            if (!token) {
              navigate('/login');
              return;
            }
            setModalData({});
          }}
        >
          Log Sighting
        </button>
      </div>
      {modalData && (
        <SightingModal
          token={token}
          zoos={zoos}
          animals={animals}
          sightingId={modalData.sightingId}
          defaultZooId={modalData.zooId}
          defaultAnimalId={modalData.animalId}
          defaultZooName={modalData.zooName}
          defaultAnimalName={modalData.animalName}
          onLogged={() => {
            onUpdate && onUpdate();
          }}
          onUpdated={() => {
            onUpdate && onUpdate();
          }}
          onClose={() => setModalData(null)}
        />
      )}
    </div>
  );
}
