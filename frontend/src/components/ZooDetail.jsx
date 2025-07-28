import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';

// Detailed view for a single zoo with a list of resident animals.
// Used by the ZooDetailPage component.
export default function ZooDetail({ zoo, token, userId, onBack, refresh }) {
  const [animals, setAnimals] = useState([]);
  const [visits, setVisits] = useState([]);
  const [seenAnimals, setSeenAnimals] = useState([]);
  const navigate = useNavigate();
  const location = useLocation();
  const authFetch = useAuthFetch();

  // Fetch animals in this zoo and user visit/sighting data
  const loadAnimals = () => {
    fetch(`${API}/zoos/${zoo.id}/animals`).then((r) => r.json()).then(setAnimals);
  };
  const loadVisits = () => {
    if (!token) return;
    authFetch(`${API}/visits`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then(setVisits)
      .catch(() => setVisits([]));
  };
  const loadSeen = () => {
    if (!token || !userId) return;
    authFetch(`${API}/users/${userId}/animals`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then(setSeenAnimals)
      .catch(() => setSeenAnimals([]));
  };

  useEffect(() => {
    loadAnimals();
    loadVisits();
    loadSeen();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoo, token, userId, refresh]);

  const visited = visits.some((v) => v.zoo_id === zoo.id);
  const seenIds = new Set(seenAnimals.map((a) => a.id));

  return (
    <div className="p-3">
      <button className="btn btn-link mb-2" onClick={onBack}>
        Back
      </button>
      {zoo.image_url && (
        <img
          src={zoo.image_url}
          alt={zoo.name}
          className="img-fluid mb-2"
          style={{ maxHeight: '200px', objectFit: 'cover' }}
        />
      )}
      <h3>{zoo.name}</h3>
      {zoo.address && <div className="text-muted">📍 {zoo.address}</div>}
      {zoo.latitude && zoo.longitude && (
        <iframe
          title="map"
          width="100%"
          height="200"
          className="border-0 mt-1"
          src={`https://maps.google.com/maps?q=${zoo.latitude},${zoo.longitude}&z=14&output=embed`}
        ></iframe>
      )}
      {zoo.description && (
        <p className="mt-2" style={{ whiteSpace: 'pre-wrap' }}>
          {zoo.description}
        </p>
      )}
      <div className="mt-2">Visited? {visited ? '☑️ Yes' : '✘ No'}</div>
      <button
        className="btn btn-primary btn-sm mt-2"
        onClick={() =>
          navigate('/visits/new', {
            state: { zooId: zoo.id, from: `/zoos/${zoo.id}` },
          })
        }
      >
        Log a Visit
      </button>
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
              style={{ cursor: 'pointer' }}
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
                    // Open the sighting form as a modal overlay with
                    // the current zoo and animal pre-filled.
                    navigate('/sightings/new', {
                      state: {
                        zooId: zoo.id,
                        zooName: zoo.name,
                        animalId: a.id,
                        animalName: a.common_name,
                        backgroundLocation: location,
                        from: `/zoos/${zoo.id}`,
                      },
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
    </div>
  );
}
