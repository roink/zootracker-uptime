import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import SightingModal from '../components/SightingModal';
import Seo from '../components/Seo';

// Detailed page showing an animal along with nearby zoos and user sightings

export default function AnimalDetailPage({ token, userId, refresh, onLogged }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const authFetch = useAuthFetch(token);
  const [animal, setAnimal] = useState(null);
  const [sightings, setSightings] = useState([]);
  const [location, setLocation] = useState(null);
  const [zoos, setZoos] = useState([]);
  const [modalData, setModalData] = useState(null);

  useEffect(() => {
    const params = [];
    if (location) {
      params.push(`latitude=${location.lat}`);
      params.push(`longitude=${location.lon}`);
    }
    const controller = new AbortController();
    // fetch animal details and associated zoos (with distance when available)
    fetch(
      `${API}/animals/${id}${params.length ? `?${params.join('&')}` : ''}`,
      { signal: controller.signal }
    )
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data) => {
        setAnimal(data);
        setZoos(data.zoos || []);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setAnimal(null);
          setZoos([]);
        }
      });

    return () => controller.abort();
  }, [id, location]);

  const loadSightings = () => {
    if (!token) return;
    authFetch(`${API}/sightings`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then(setSightings)
      .catch(() => setSightings([]));
  };

  useEffect(() => {
    loadSightings();
  }, [token, refresh, authFetch]);

  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) =>
          setLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => setLocation(null),
        { enableHighAccuracy: false, timeout: 3000, maximumAge: 600000 }
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

  const closestZoo = zoos[0];

  return (
    <div className="page-container">
      <Seo
        title={animal ? animal.common_name : 'Animal'}
        description={
          animal
            ? `Discover where to see ${animal.common_name} and log your sightings.`
            : 'Animal details on ZooTracker.'
        }
      />
      {animal.default_image_url && (
        <img
          src={animal.default_image_url}
          alt={animal.common_name}
          className="cover-image"
        />
      )}
      <h3>{animal.common_name}</h3>
      {animal.scientific_name && (
        <div className="fst-italic">{animal.scientific_name}</div>
      )}
      {animal.category && (
        <span className="category-badge">
          {animal.category}
        </span>
      )}
      <div className="spaced-top">
        {seen ? `Seen ✔️ (first on ${firstSeen})` : 'Not seen 🚫'}
      </div>
      {gallery.length > 0 && (
        <div className="gallery">
          {gallery.map((g, idx) => (
            <img
              key={idx}
              src={g.photo_url}
              alt='sighting'
              className="gallery-img"
            />
          ))}
        </div>
      )}
      <h4 className="spaced-top-lg">Where to See</h4>
      <table className="table-full">
        <thead>
          <tr>
            <th align='left'>Zoo</th>
            {location && <th className="text-end">Distance (km)</th>}
          </tr>
        </thead>
        <tbody>
          {zoos.map((z) => (
            <tr
              key={z.id}
              className="pointer-row"
              onClick={() => navigate(`/zoos/${z.id}`)}
              tabIndex="0"
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  navigate(`/zoos/${z.id}`);
                }
              }}
            >
              <td>{z.city ? `${z.city}: ${z.name}` : z.name}</td>
              {location && (
                <td className="text-end">
                  {z.distance_km != null ? z.distance_km.toFixed(1) : ''}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <button
        onClick={() => {
          if (!token) {
            navigate('/login');
            return;
          }
          setModalData({
            animalId: animal.id,
            animalName: animal.common_name,
            zooId: closestZoo ? closestZoo.id : undefined,
            zooName: closestZoo
              ? closestZoo.city
                ? `${closestZoo.city}: ${closestZoo.name}`
                : closestZoo.name
              : undefined,
          });
        }}
        className="spaced-top"
      >
        Log Sighting
      </button>
      {modalData && (
        <SightingModal
          token={token}
          zoos={zoos}
          defaultZooId={modalData.zooId}
          defaultAnimalId={modalData.animalId}
          defaultZooName={modalData.zooName}
          defaultAnimalName={modalData.animalName}
          onLogged={() => {
            loadSightings();
            onLogged && onLogged();
          }}
          onClose={() => setModalData(null)}
        />
      )}
    </div>
  );
}
