import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
  const { id, lang } = useParams();
  const navigate = useNavigate();
  const prefix = `/${lang}`;
  const { t } = useTranslation();
  const authFetch = useAuthFetch(token);
  const [animal, setAnimal] = useState(null);
  const [sightings, setSightings] = useState([]);
  const [location, setLocation] = useState(null);
  const [zoos, setZoos] = useState([]);
  const [modalData, setModalData] = useState(null);
  const [zooFilter, setZooFilter] = useState('');
  const [sortBy, setSortBy] = useState('name'); // 'name' | 'distance'
  const [descOpen, setDescOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // Choose localized name for current language
  const animalName = useMemo(() => {
    if (!animal) return '';
    return lang === 'de' ? animal.name_de || animal.common_name : animal.common_name;
  }, [animal, lang]);

  // Choose description in the active language with fallback
  const animalDesc = useMemo(() => {
    if (!animal) return '';
    return lang === 'de'
      ? animal.description_de
      : animal.description_en || animal.description_de;
  }, [animal, lang]);

  useEffect(() => {
    const params = [];
    if (location) {
      params.push(`latitude=${location.lat}`);
      params.push(`longitude=${location.lon}`);
    }
    const controller = new AbortController();
    setLoading(true);
    setError(false);
    // fetch animal details and associated zoos (with distance when available)
    fetch(
      `${API}/animals/${id}${params.length ? `?${params.join('&')}` : ''}`,
      { signal: controller.signal }
    )
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data) => {
        setAnimal(data);
        setZoos(data.zoos || []);
        setLoading(false);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setError(true);
          setLoading(false);
        }
        setAnimal(null);
        setZoos([]);
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

  // Keep sort default in sync with location availability
  useEffect(() => {
    if (location) setSortBy('distance');
  }, [location]);

  const filteredZoos = useMemo(() => {
    const q = zooFilter.trim().toLowerCase();
    let list = [...zoos];
    if (q) {
      list = list.filter((z) =>
        [z.city, z.name].filter(Boolean).join(' ').toLowerCase().includes(q)
      );
    }
    list.sort((a, b) => {
      if (sortBy === 'distance' && location) {
        const da = a.distance_km ?? Number.POSITIVE_INFINITY;
        const db = b.distance_km ?? Number.POSITIVE_INFINITY;
        return da - db;
      }
      const an = (a.city ? `${a.city}: ${a.name}` : a.name) || '';
      const bn = (b.city ? `${b.city}: ${b.name}` : b.name) || '';
      return an.localeCompare(bn);
    });
    return list;
  }, [zoos, zooFilter, sortBy, location]);

  if (loading) return <div className="page-container">Loading...</div>;
  if (error) return (
    <div className="page-container">
      <p className="text-danger">Unable to load animal.</p>
    </div>
  );
  if (!animal) return (
    <div className="page-container">
      <p>Animal not found.</p>
    </div>
  );

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
        title={animal ? animalName : 'Animal'}
        description={
          animal
            ? `Discover where to see ${animalName} and log your sightings.`
            : 'Animal details on ZooTracker.'
        }
      />
      {/* Image above on mobile, swapped to the right on large screens */}
      <div className="row g-3">
        <div className="col-12 col-lg-6 order-lg-2 sticky-lg-top" style={{ top: '1rem' }}>
          {/* Stable image stage: fixed aspect ratio, no jumping controls */}
          <div className="animal-media" style={{ '--ar': aspect }}>
            {animal.images && animal.images.length > 0 ? (
              // Render image gallery using Bootstrap carousel
              <div
                id="animalCarousel"
                className="carousel slide h-100"
                role="region"
                aria-roledescription="carousel"
                aria-label={`${animalName} image gallery`}
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
                    const sizes =
                      '(min-width: 1200px) 540px, (min-width: 992px) 50vw, 100vw'; // matches 2-col layout

                    // Each image links to its Commons description page
                    return (
                      <div
                        key={img.mid}
                        className={`carousel-item ${idx === 0 ? 'active' : ''}`}
                        aria-label={`Slide ${idx + 1} of ${animal.images.length}`}
                      >
                        {/* Clicking the image opens the attribution page */}
                        <Link
                          to={`${prefix}/images/${img.mid}`}
                          state={{ name: animalName }}
                          className="d-block"
                        >
                          <img
                            src={fallbackSrc}
                            srcSet={srcSet}
                            sizes={sizes}
                            decoding="async"
                            loading={loadingAttr}
                            fetchpriority={fetchPri}
                            alt={animalName}
                            className="img-fluid"
                          />
                        </Link>
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
                  alt={animalName}
                  className="img-fluid w-100"
                  loading="lazy"
                />
              )
            )}
          </div>
        </div>
        <div className="col-12 col-lg-6 order-lg-1">
          <h2 className="mb-1">{animalName}</h2>
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
          <div className="spaced-top d-flex flex-wrap gap-2 align-items-center">
            <span className={`badge ${seen ? 'bg-success' : 'bg-secondary'}`}>
              {seen
                ? t('animal.seenOn', { date: firstSeen })
                : t('animal.notSeen')}
            </span>
            {animal.iucn_conservation_status && (() => {
              const code = animal.iucn_conservation_status.toUpperCase();
              const meta = IUCN[code] || { label: code, badge: 'bg-secondary' };
              return (
                <span className={`badge ${meta.badge}`} title={meta.label}>
                  IUCN: {code}
                </span>
              );
            })()}
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
          {animalDesc && (
            <div className="card mt-3">
              <div className="card-body">
                <h5 className="card-title">{t('zoo.description')}</h5>
                <p
                  id="animal-description"
                  className={`card-text ${descOpen ? '' : 'line-clamp-6'}`}
                >
                  {animalDesc}
                </p>
                <button
                  className="btn btn-link p-0"
                  onClick={() => setDescOpen((v) => !v)}
                  aria-expanded={descOpen}
                  aria-controls="animal-description"
                >
                  {descOpen ? t('zoo.showLess') : t('zoo.showMore')}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="card spaced-top-lg">
        <div className="card-body pb-2">
          <div className="d-flex flex-wrap gap-2 align-items-center">
            <h4 className="mb-0 me-auto">{t('animal.whereToSee')}</h4>
            <div className="input-group input-group-sm" style={{ maxWidth: 280 }}>
              <span className="input-group-text">{t('actions.filter')}</span>
              <input
                type="search"
                className="form-control"
                placeholder={t('animal.filterPlaceholder')}
                value={zooFilter}
                onChange={(e) => setZooFilter(e.target.value)}
                aria-label={t('animal.filterAria')}
              />
            </div>
            <div className="btn-group btn-group-sm" role="group" aria-label="Sort zoos">
              <button
                className={`btn btn-outline-secondary ${sortBy === 'name' ? 'active' : ''}`}
                onClick={() => setSortBy('name')}
              >
                {t('actions.sortByName')}
              </button>
              <button
                className={`btn btn-outline-secondary ${sortBy === 'distance' ? 'active' : ''}`}
                onClick={() => setSortBy('distance')}
                disabled={!location}
                title={!location ? t('animal.enableLocationSort') : undefined}
              >
                {t('actions.sortByDistance')}
              </button>
            </div>
          </div>
          <div className="small text-muted mt-2" aria-live="polite">
            Showing {filteredZoos.length} of {zoos.length}
          </div>
        </div>
        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th scope="col">Zoo</th>
                {location && <th scope="col" className="text-end">Distance (km)</th>}
              </tr>
            </thead>
            <tbody>
              {filteredZoos.map((z) => (
                <tr
                  key={z.id}
                  className="pointer-row"
                  role="link"
                  aria-label={`Open ${z.city ? `${z.city}: ${z.name}` : z.name}`}
                  onClick={() => navigate(`${prefix}/zoos/${z.id}`)}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      navigate(`${prefix}/zoos/${z.id}`);
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
        </div>
      </div>
      <button
        onClick={() => {
          if (!token) {
            navigate(`${prefix}/login`);
            return;
          }
          setModalData({
            animalId: animal.id,
            animalName: animalName,
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
        {t('actions.logSighting')}
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
