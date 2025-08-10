import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import SightingModal from './SightingModal';
import LazyMap from './LazyMap';

// Detailed view for a single zoo with a list of resident animals.
// Used by the ZooDetailPage component.
export default function ZooDetail({ zoo, token, userId, refresh, onLogged }) {
  const [animals, setAnimals] = useState([]);
  const [visits, setVisits] = useState([]);
  const [seenAnimals, setSeenAnimals] = useState([]);
  const [modalData, setModalData] = useState(null);
  const navigate = useNavigate();
  const authFetch = useAuthFetch(token);

  // Load animals in this zoo
  useEffect(() => {
    fetch(`${API}/zoos/${zoo.id}/animals`)
      .then((r) => r.json())
      .then(setAnimals)
      .catch(() => setAnimals([]));
  }, [zoo, refresh]);

  // Load user's visit history
  useEffect(() => {
    if (!token) return;
    authFetch(`${API}/visits`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then(setVisits)
      .catch(() => setVisits([]));
  }, [token, authFetch, refresh]);

  // Load animals the user has seen
  useEffect(() => {
    if (!token || !userId) return;
    authFetch(`${API}/users/${userId}/animals`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then(setSeenAnimals)
      .catch(() => setSeenAnimals([]));
  }, [token, userId, authFetch, refresh]);

  const visited = visits.some((v) => v.zoo_id === zoo.id);
  const seenIds = new Set(seenAnimals.map((a) => a.id));

  return (
    <div className="p-3">
      {zoo.image_url && (
        <img
          src={zoo.image_url}
          alt={zoo.name}
          className="img-fluid mb-2 cover-image"
        />
      )}
      <h3>{zoo.name}</h3>
      {zoo.address && <div className="text-muted">📍 {zoo.address}</div>}
      {Number.isFinite(zoo.latitude) && Number.isFinite(zoo.longitude) && (
        <div className="mt-1">
          <LazyMap latitude={zoo.latitude} longitude={zoo.longitude} />
        </div>
      )}
      {zoo.description && (
        <p className="mt-2 pre-wrap">
          {zoo.description}
        </p>
      )}
      <div className="mt-2">Visited? {visited ? '☑️ Yes' : '✘ No'}</div>
      {/* visit logging removed - visits are created automatically from sightings */}
      <h4 className="mt-3">Animals</h4>
      <table className="table">
        <thead>
          <tr>
            <th align="left">Name</th>
            <th className="text-center">Seen?</th>
            <th className="text-center"></th>
          </tr>
        </thead>
        <tbody>
          {animals.map((a) => (
            <tr
              key={a.id}
              className="pointer-row"
              onClick={() => navigate(`/animals/${a.id}`)}
              tabIndex="0"
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  navigate(`/animals/${a.id}`);
                }
              }}
            >
              <td>{a.common_name}</td>
              <td className="text-center">{seenIds.has(a.id) ? '✔️' : '—'}</td>
              <td className="text-center">
                <button
                  className="btn btn-sm btn-outline-secondary"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!token) {
                      navigate('/login');
                      return;
                    }
                    setModalData({
                      zooId: zoo.id,
                      zooName: zoo.name,
                      animalId: a.id,
                      animalName: a.common_name,
                    });
                  }}
                >
                  ➕
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {modalData && (
          <SightingModal
            token={token}
            animals={animals}
            defaultZooId={modalData.zooId}
            defaultAnimalId={modalData.animalId}
            defaultZooName={modalData.zooName}
            defaultAnimalName={modalData.animalName}
            onLogged={() => {
              onLogged && onLogged();
              fetch(`${API}/zoos/${zoo.id}/animals`)
                .then((r) => r.json())
                .then(setAnimals)
                .catch(() => setAnimals([]));
              if (token) {
                authFetch(`${API}/visits`, {
                  headers: { Authorization: `Bearer ${token}` },
                })
                  .then((r) => (r.ok ? r.json() : []))
                  .then(setVisits)
                  .catch(() => setVisits([]));
                if (userId) {
                  authFetch(`${API}/users/${userId}/animals`, {
                    headers: { Authorization: `Bearer ${token}` },
                  })
                    .then((r) => (r.ok ? r.json() : []))
                    .then(setSeenAnimals)
                    .catch(() => setSeenAnimals([]));
                }
              }
            }}
            onClose={() => setModalData(null)}
          />
        )}
      </div>
    );
  }
