import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { API } from '../api';

export default function AnimalDetailPage({ token, userId, refresh }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const routerLocation = useLocation();
  const [animal, setAnimal] = useState(null);
  const [sightings, setSightings] = useState([]);
  const [location, setLocation] = useState(null);
  const [zoos, setZoos] = useState([]);

  useEffect(() => {
    fetch(`${API}/animals/${id}`).then((r) => r.json()).then(setAnimal);
  }, [id]);

  useEffect(() => {
    const params = [];
    if (location) {
      params.push(`latitude=${location.lat}`);
      params.push(`longitude=${location.lon}`);
    }
    fetch(`${API}/animals/${id}/zoos${params.length ? `?${params.join('&')}` : ''}`)
      .then((r) => r.json())
      .then(setZoos);
  }, [id, location]);

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/sightings`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then(setSightings)
      .catch(() => setSightings([]));
  }, [token, refresh]);

  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) =>
          setLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => {}
      );
    }
  }, []);

  if (!animal) return <div>Loading...</div>;

  const userSightings = sightings.filter((s) => s.animal_id === animal.id);
  const seen = userSightings.length > 0;
  const firstSeen = seen
    ? new Date(
        userSightings
          .map((s) => s.sighting_datetime)
          .sort()[0]
      ).toLocaleDateString()
    : null;
  const gallery = userSightings.filter((s) => s.photo_url);

  const toRad = (v) => (v * Math.PI) / 180;
  const distanceKm = (z) => {
    if (!location || z.latitude == null || z.longitude == null) return null;
    const lat1 = location.lat;
    const lon1 = location.lon;
    const lat2 = parseFloat(z.latitude);
    const lon2 = parseFloat(z.longitude);
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(lat1)) *
        Math.cos(toRad(lat2)) *
        Math.sin(dLon / 2) ** 2;
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return 6371 * c;
  };

  const closestZoo = zoos[0];

  return (
    <div style={{ padding: '20px' }}>
      <button onClick={() => navigate(-1)} style={{ marginBottom: '10px' }}>
        Back
      </button>
      {animal.default_image_url && (
        <img
          src={animal.default_image_url}
          alt={animal.common_name}
          style={{ width: '100%', maxHeight: '200px', objectFit: 'cover' }}
        />
      )}
      <h3>{animal.common_name}</h3>
      {animal.scientific_name && (
        <div style={{ fontStyle: 'italic' }}>{animal.scientific_name}</div>
      )}
      {animal.category && (
        <span
          style={{
            display: 'inline-block',
            background: '#1976d2',
            color: 'white',
            padding: '2px 6px',
            borderRadius: '4px',
            fontSize: '12px',
            marginTop: '4px',
          }}
        >
          {animal.category}
        </span>
      )}
      <div style={{ marginTop: '10px' }}>
        {seen ? `Seen ✔️ (first on ${firstSeen})` : 'Not seen 🚫'}
      </div>
      {gallery.length > 0 && (
        <div
          style={{
            display: 'flex',
            overflowX: 'auto',
            gap: '10px',
            marginTop: '10px',
          }}
        >
          {gallery.map((g, idx) => (
            <img
              key={idx}
              src={g.photo_url}
              alt='sighting'
              style={{ width: '150px', height: '100px', objectFit: 'cover' }}
            />
          ))}
        </div>
      )}
      <h4 style={{ marginTop: '20px' }}>Where to See</h4>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th align='left'>Zoo</th>
            {location && <th style={{ textAlign: 'right' }}>Distance (km)</th>}
          </tr>
        </thead>
        <tbody>
          {zoos.map((z) => (
            <tr
              key={z.id}
              style={{ borderTop: '1px solid #ccc', cursor: 'pointer' }}
              onClick={() => navigate(`/zoos/${z.id}`)}
            >
              <td>{z.name}</td>
              {location && (
                <td style={{ textAlign: 'right' }}>
                  {distanceKm(z)?.toFixed(1)}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <button
        onClick={() =>
          // Launch modal with the selected animal and closest zoo prefilled
          navigate('/sightings/new', {
            state: {
              animalId: animal.id,
              animalName: animal.common_name,
              zooId: closestZoo ? closestZoo.id : undefined,
              zooName: closestZoo ? closestZoo.name : undefined,
              backgroundLocation: routerLocation,

              from: `/animals/${animal.id}`,
            },
          })
        }
        style={{ marginTop: '10px' }}
      >
        Log Sighting
      </button>
    </div>
  );
}
