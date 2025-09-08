import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import SightingModal from '../components/SightingModal';
import Seo from '../components/Seo';
import '../styles/animal-detail.css';

// Map IUCN codes to labels and bootstrap badge classes
const IUCN = {
  EX: { label: 'Extinct', badge: 'bg-dark' },
  EW: { label: 'Extinct in the Wild', badge: 'bg-dark' },
  CR: { label: 'Critically Endangered', badge: 'bg-danger' },
  EN: { label: 'Endangered', badge: 'bg-danger' },
  VU: { label: 'Vulnerable', badge: 'bg-warning' },
  NT: { label: 'Near Threatened', badge: 'bg-info' },
  LC: { label: 'Least Concern', badge: 'bg-success' },
  DD: { label: 'Data Deficient', badge: 'bg-secondary' },
  NE: { label: 'Not Evaluated', badge: 'bg-secondary' },
};

// Detailed page showing an animal along with nearby zoos and user sightings

export default function AnimalDetailPage({ token, refresh, onLogged }) {
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

  const loadSightings = useCallback(() => {
    if (!token) return;
    authFetch(`${API}/sightings`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then(setSightings)
      .catch(() => setSightings([]));
  }, [token, authFetch]);

  useEffect(() => {
    loadSightings();
  }, [loadSightings, refresh]);

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

  // compute a stable aspect ratio from the first image (fallback 4/3)
  const computeAspect = (img) => {
    if (!img) return '4 / 3';
    const candidates = (img.variants && img.variants.length ? img.variants : []);
    const v = candidates[candidates.length - 1] || img; // prefer a larger variant if present
    const w = v?.width || img?.width;
    const h = v?.height || img?.height;
    return w && h ? `${w} / ${h}` : '4 / 3';
  };
  const aspect =
    animal.images && animal.images.length ? computeAspect(animal.images[0]) : '4 / 3';

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
      {/* Image above on mobile, swapped to the right on large screens */}
      <div className="row g-3">
        <div className="col-12 col-lg-6 order-lg-2">
          {/* Stable image stage: fixed aspect ratio, no jumping controls */}
          <div className="animal-media" style={{ '--ar': aspect }}>
            {animal.images && animal.images.length > 0 ? (
              // Render image gallery using Bootstrap carousel
              <div
                id="animalCarousel"
                className="carousel slide h-100"
                data-bs-ride="false"
                data-bs-interval="false"
                data-bs-touch="true"
              >
                {animal.images.length > 1 && (
                  <div className="carousel-indicators">
                    {animal.images.map((_, i) => (
                      <button
                        key={i}
                        type="button"
                        data-bs-target="#animalCarousel"
                        data-bs-slide-to={i}
                        className={i === 0 ? 'active' : ''}
                        aria-label={`Slide ${i + 1}`}
                      />
                    ))}
                  </div>
                )}
                <div className="carousel-inner h-100">
                  {animal.images.map((img, idx) => {
                    // Sort variants so the smallest width comes first
                    const sorted = [...(img.variants || [])].sort(
                      (a, b) => a.width - b.width
                    );
                    const fallback = sorted[0];
                    const fallbackSrc = fallback?.thumb_url || img.original_url;
                    // Deduplicate widths to keep srcset concise
                    const uniqueByWidth = [];
                    const seen = new Set();
                    for (const v of sorted) {
                      if (!seen.has(v.width)) {
                        uniqueByWidth.push(v);
                        seen.add(v.width);
                      }
                    }
                    const srcSet = uniqueByWidth
                      .map((v) => `${v.thumb_url} ${v.width}w`)
                      .join(', ');
                    // First slide is likely LCP: prioritize it; others can be lazy/low
                    const isFirst = idx === 0;
                    const loadingAttr = isFirst ? 'eager' : 'lazy';
                    const fetchPri = isFirst ? 'high' : 'low';

                    // Each image links to its Commons description page
                    return (
                      <div
                        key={img.mid}
                        className={`carousel-item ${idx === 0 ? 'active' : ''}`}
                      >
                        <a
                          href={img.commons_page_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="d-block"
                        >
                          <img
                            src={fallbackSrc}
                            srcSet={srcSet}
                            sizes="(min-width: 992px) 50vw, 100vw"
                            decoding="async"
                            loading={loadingAttr}
                            fetchPriority={fetchPri}
                            alt={
                              img.commons_title
                                ? `${animal.common_name} — ${img.commons_title}`
                                : `${animal.common_name} – Wikimedia Commons image`
                            }
                            className="img-fluid"
                          />
                        </a>
                      </div>
                    );
                  })}
                </div>
                {animal.images.length > 1 && (
                  <>
                    <button
                      className="carousel-control-prev"
                      type="button"
                      data-bs-target="#animalCarousel"
                      data-bs-slide="prev"
                    >
                      <span className="carousel-control-prev-icon" aria-hidden="true"></span>
                      <span className="visually-hidden">Previous</span>
                    </button>
                    <button
                      className="carousel-control-next"
                      type="button"
                      data-bs-target="#animalCarousel"
                      data-bs-slide="next"
                    >
                      <span className="carousel-control-next-icon" aria-hidden="true"></span>
                      <span className="visually-hidden">Next</span>
                    </button>
                  </>
                )}
              </div>
            ) : (
              animal.default_image_url && (
                <img
                  src={animal.default_image_url}
                  alt={`${animal.common_name} – Wikimedia Commons image`}
                  className="img-fluid"
                  loading="lazy"
                />
              )
            )}
          </div>
        </div>
        <div className="col-12 col-lg-6 order-lg-1">
          <h3>{animal.common_name}</h3>
          {animal.scientific_name && (
            <div className="fst-italic">{animal.scientific_name}</div>
          )}
          {animal.taxon_rank && (
            <div className="mt-1">
              <span className="badge bg-light text-muted border">{animal.taxon_rank}</span>
            </div>
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
                  alt="sighting"
                  className="gallery-img"
                />
              ))}
            </div>
          )}
          {(animal.description_de || animal.iucn_conservation_status) && (
            <div className="card mt-3">
              <div className="card-body">
                {animal.description_de && (
                  <>
                    <h5 className="card-title">Beschreibung</h5>
                    <p className="card-text">{animal.description_de}</p>
                  </>
                )}
                {animal.iucn_conservation_status && (() => {
                  const code = animal.iucn_conservation_status.toUpperCase();
                  const meta = IUCN[code] || { label: code, badge: 'bg-secondary' };
                  return (
                    <p className="card-text mb-0">
                      <strong>IUCN:</strong>{' '}
                      <span className={`badge ${meta.badge}`} title={meta.label}>{code}</span>{' '}
                      <span className="text-muted">({meta.label})</span>
                    </p>
                  );
                })()}
              </div>
            </div>
          )}
        </div>
      </div>
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
        className="spaced-top btn btn-primary"
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
