import { useState, useEffect, useMemo, Fragment } from 'react';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import SightingModal from '../components/SightingModal';
import { useNavigate } from 'react-router-dom';
import Seo from '../components/Seo';

// User dashboard showing recent visits, sightings and badges. Includes
// buttons to open forms for logging additional activity.

export default function Dashboard({ token, userId, refresh, onUpdate }) {
  const [visits, setVisits] = useState([]);
  // Number of unique animals the user has seen
  const [seenCount, setSeenCount] = useState(0);
  const [sightings, setSightings] = useState([]);
  const [badges, setBadges] = useState([]);
  const [zoos, setZoos] = useState([]);
  const [animals, setAnimals] = useState([]);
  const [modalData, setModalData] = useState(null);
  const navigate = useNavigate();
  const authFetch = useAuthFetch(token);

  // Load zoo and animal lists when the dashboard is viewed so we
  // don't fetch them on every app startup.
  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    (async () => {
      try {
        const [zRes, aRes] = await Promise.all([
          fetch(`${API}/zoos`, { signal: controller.signal }),
          fetch(`${API}/animals`, { signal: controller.signal }),
        ]);
        const zData = zRes.ok ? await zRes.json() : [];
        const aData = aRes.ok ? await aRes.json() : [];
        setZoos(zData);
        setAnimals(aData);
      } catch (e) {
        if (e.name !== 'AbortError') {
          setZoos([]);
          setAnimals([]);
        }
      }
    })();
    return () => controller.abort();
  }, [token]);

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

  // Group sightings by day and order by day descending then creation time.
  const groupedSightings = useMemo(() => {
    const sorted = [...sightings].sort((a, b) => {
      const dayA = new Date(a.sighting_datetime).toDateString();
      const dayB = new Date(b.sighting_datetime).toDateString();
      if (dayA === dayB) {
        return new Date(b.created_at) - new Date(a.created_at);
      }
      return new Date(b.sighting_datetime) - new Date(a.sighting_datetime);
    });
    const groups = [];
    sorted.forEach((s) => {
      const day = s.sighting_datetime.slice(0, 10);
      const last = groups[groups.length - 1];
      if (!last || last.day !== day) {
        groups.push({ day, items: [s] });
      } else {
        last.items.push(s);
      }
    });
    return groups;
  }, [sightings]);

  const formatDay = (day) => {
    const today = new Date().toISOString().slice(0, 10);
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const yDay = yesterday.toISOString().slice(0, 10);
    if (day === today) return 'Today';
    if (day === yDay) return 'Yesterday';
    return new Date(day).toLocaleDateString();
  };

  // Distinct zoo count, derived from visits and sightings in case visit sync is missing.
  const visitedZooCount = useMemo(() => {
    const ids = new Set([
      ...visits.map((v) => v.zoo_id),
      ...sightings.map((s) => s.zoo_id),
    ]);
    return ids.size;
  }, [visits, sightings]);

  const zooName = (id) => zoos.find((z) => z.id === id)?.name || id;
  const animalName = (id) =>
    animals.find((a) => a.id === id)?.common_name || id;

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
        {groupedSightings.map((g) => (
          <Fragment key={g.day}>
            <li className="list-group-item active">{formatDay(g.day)}</li>
            {g.items.map((s) => (
              <li
                key={s.id}
                className="list-group-item d-flex justify-content-between align-items-center"
              >
                <span>
                  {`Saw ${
                    s.animal_name_de ?? animalName(s.animal_id)
                  } at ${zooName(s.zoo_id)} on ${s.sighting_datetime.slice(0, 10)}`}
                </span>
                <button
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() =>
                    setModalData({
                      sightingId: s.id,
                      zooId: s.zoo_id,
                      zooName: zooName(s.zoo_id),
                      animalId: s.animal_id,
                      animalName: s.animal_name_de ?? animalName(s.animal_id),
                    })
                  }
                >
                  Edit
                </button>
              </li>
            ))}
          </Fragment>
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
