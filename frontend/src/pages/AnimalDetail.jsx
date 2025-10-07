import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  useParams,
  useNavigate,
  useLocation,
  Link,
  createSearchParams,
} from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { API } from '../api';
import { getZooDisplayName } from '../utils/zooDisplayName.js';
import { normalizeCoordinates } from '../utils/coordinates.js';
import useAuthFetch from '../hooks/useAuthFetch';
import SightingModal from '../components/SightingModal';
import SightingHistoryList from '../components/SightingHistoryList.jsx';
import Seo from '../components/Seo';
import { useAuth } from '../auth/AuthContext.jsx';
import ZoosMap from '../components/ZoosMap.jsx';
import FavoriteBadge from '../components/FavoriteBadge.jsx';
import '../styles/animal-detail.css';
import { formatSightingDayLabel } from '../utils/sightingHistory.js';

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

// Normalize map camera view snapshots stored in navigation state
function sanitizeCameraView(view) {
  if (!view) return null;
  const center = Array.isArray(view.center) ? view.center : null;
  if (!center || center.length !== 2) return null;
  const [lon, lat] = center;
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
  const safeView = {
    center: [Number(lon), Number(lat)],
  };
  if (Number.isFinite(view.zoom)) safeView.zoom = Number(view.zoom);
  if (Number.isFinite(view.bearing)) safeView.bearing = Number(view.bearing);
  if (Number.isFinite(view.pitch)) safeView.pitch = Number(view.pitch);
  return safeView;
}

function cameraViewsEqual(a, b) {
  const left = sanitizeCameraView(a);
  const right = sanitizeCameraView(b);
  if (!left && !right) return true;
  if (!left || !right) return false;
  const [lonA, latA] = left.center;
  const [lonB, latB] = right.center;
  if (lonA !== lonB || latA !== latB) return false;
  const zoomA = Number.isFinite(left.zoom) ? left.zoom : null;
  const zoomB = Number.isFinite(right.zoom) ? right.zoom : null;
  if (zoomA !== zoomB) return false;
  const bearingA = Number.isFinite(left.bearing) ? left.bearing : null;
  const bearingB = Number.isFinite(right.bearing) ? right.bearing : null;
  if (bearingA !== bearingB) return false;
  const pitchA = Number.isFinite(left.pitch) ? left.pitch : null;
  const pitchB = Number.isFinite(right.pitch) ? right.pitch : null;
  return pitchA === pitchB;
}

// Detailed page showing an animal along with nearby zoos and user sightings

export default function AnimalDetailPage({ refresh, onLogged }) {
  const { slug, lang } = useParams();
  const navigate = useNavigate();
  const routerLocation = useLocation();
  const prefix = `/${lang}`;
  const { t } = useTranslation();
  const authFetch = useAuthFetch();
  const { isAuthenticated } = useAuth();
  const initialViewMode =
    routerLocation.state?.animalViewMode === 'map' ? 'map' : 'list';
  const initialMapView = sanitizeCameraView(routerLocation.state?.animalMapView);
  const [animal, setAnimal] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(false);
  const [userLocation, setUserLocation] = useState(null);
  const [zoos, setZoos] = useState([]);
  const [modalData, setModalData] = useState(null);
  const [zooFilter, setZooFilter] = useState('');
  const [sortBy, setSortBy] = useState('name'); // 'name' | 'distance'
  const [descOpen, setDescOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [viewMode, setViewMode] = useState(initialViewMode);
  const [mapView, setMapView] = useState(initialMapView);
  const [mapResizeToken, setMapResizeToken] = useState(() =>
    initialViewMode === 'map' ? 1 : 0
  );
  const persistedViewRef = useRef({
    viewMode: initialViewMode,
    mapView: initialMapView,
  });
  const [favorite, setFavorite] = useState(false);
  const [favoritePending, setFavoritePending] = useState(false);
  const [favoriteError, setFavoriteError] = useState('');

  // Choose localized name for current language
  const animalName = useMemo(() => {
    if (!animal) return '';
    return lang === 'de' ? animal.name_de || animal.name_en : animal.name_en || animal.name_de;
  }, [animal, lang]);

  // Choose description in the active language with fallback
  const animalDesc = useMemo(() => {
    if (!animal) return '';
    return lang === 'de'
      ? animal.description_de
      : animal.description_en || animal.description_de;
  }, [animal, lang]);

  const className = useMemo(() => {
    if (!animal) return null;
    return lang === 'de'
      ? animal.class_name_de || animal.class_name_en
      : animal.class_name_en || animal.class_name_de;
  }, [animal, lang]);

  const orderName = useMemo(() => {
    if (!animal) return null;
    return lang === 'de'
      ? animal.order_name_de || animal.order_name_en
      : animal.order_name_en || animal.order_name_de;
  }, [animal, lang]);

  const familyName = useMemo(() => {
    if (!animal) return null;
    return lang === 'de'
      ? animal.family_name_de || animal.family_name_en
      : animal.family_name_en || animal.family_name_de;
  }, [animal, lang]);

  const classificationLinks = useMemo(() => {
    if (!animal) {
      return { class: null, order: null, family: null };
    }

    const makeLink = ({ classId, orderId, familyId }) => {
      const filtered = [
        ['class', classId],
        ['order', orderId],
        ['family', familyId],
      ].filter(([, value]) => value != null && value !== '');
      const params = createSearchParams(
        filtered.map(([key, value]) => [key, String(value)])
      );
      const query = params.toString();
      return `${prefix}/animals${query ? `?${query}` : ''}`;
    };

    return {
      class: animal.class_id ? makeLink({ classId: animal.class_id }) : null,
      order:
        animal.class_id && animal.order_id
          ? makeLink({ classId: animal.class_id, orderId: animal.order_id })
          : null,
      family:
        animal.class_id && animal.order_id && animal.family_id
          ? makeLink({
              classId: animal.class_id,
              orderId: animal.order_id,
              familyId: animal.family_id,
            })
          : null,
    };
  }, [animal, prefix]);

  useEffect(() => {
    const params = [];
    if (userLocation) {
      params.push(`latitude=${userLocation.lat}`);
      params.push(`longitude=${userLocation.lon}`);
    }
    const controller = new AbortController();
    setLoading(true);
    setError(false);
    setFavoriteError('');
    // fetch animal details and associated zoos (with distance when available)
    (async () => {
      try {
        const response = await authFetch(
          `${API}/animals/${slug}${params.length ? `?${params.join('&')}` : ''}`,
          { signal: controller.signal }
        );
        if (!response.ok) {
          throw new Error('Failed to load');
        }
        const data = await response.json();
        setAnimal(data);
        setZoos(data.zoos || []);
        setLoading(false);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(true);
          setLoading(false);
          setAnimal(null);
          setZoos([]);
        }
      }
    })();

    return () => controller.abort();
  }, [slug, userLocation, authFetch]);

  const fetchHistory = useCallback(
    async ({ signal, limit, offset } = {}) => {
      if (!slug) {
        return [];
      }
      const params = new URLSearchParams();
      if (typeof limit === 'number') {
        params.set('limit', String(limit));
      }
      if (typeof offset === 'number' && offset > 0) {
        params.set('offset', String(offset));
      }
      const baseUrl = `${API}/animals/${slug}/sightings`;
      const url = params.size ? `${baseUrl}?${params.toString()}` : baseUrl;
      const response = await authFetch(url, { signal });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      if (data && Array.isArray(data.items)) {
        return data.items;
      }
      return Array.isArray(data) ? data : [];
    },
    [authFetch, slug]
  );

  const loadHistory = useCallback(
    ({ signal } = {}) => {
      if (!isAuthenticated || !slug) {
        setHistory([]);
        setHistoryError(false);
        setHistoryLoading(false);
        return Promise.resolve();
      }
      setHistoryLoading(true);
      setHistoryError(false);
      return fetchHistory({ signal })
        .then((items) => {
          setHistory(items);
          setHistoryError(false);
        })
        .catch((err) => {
          if (err?.name === 'AbortError') {
            return;
          }
          setHistory([]);
          setHistoryError(true);
        })
        .finally(() => {
          if (!signal || !signal.aborted) {
            setHistoryLoading(false);
          }
        });
    },
    [fetchHistory, isAuthenticated, slug]
  );

  useEffect(() => {
    const controller = new AbortController();
    loadHistory({ signal: controller.signal });
    return () => controller.abort();
  }, [loadHistory, refresh]);

  useEffect(() => {
    setFavorite(Boolean(animal?.is_favorite));
    setFavoriteError('');
  }, [animal?.is_favorite]);

  useEffect(() => {
    const navState = routerLocation.state || {};
    const nextMode = navState.animalViewMode === 'map' ? 'map' : 'list';
    const nextView = sanitizeCameraView(navState.animalMapView);
    setViewMode(nextMode);
    setMapView(nextView);
    setMapResizeToken(nextMode === 'map' ? 1 : 0);
    persistedViewRef.current = {
      viewMode: nextMode,
      mapView: nextView,
    };
  }, [slug]);

  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) =>
          setUserLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => setUserLocation(null),
        { enableHighAccuracy: false, timeout: 3000, maximumAge: 600000 }
      );
    }
  }, []);

  // Keep sort default in sync with location availability
  useEffect(() => {
    if (userLocation) setSortBy('distance');
  }, [userLocation]);

  const filteredZoos = useMemo(() => {
    const q = zooFilter.trim().toLowerCase();
    let list = [...zoos];
    if (q) {
      list = list.filter((z) =>
        [z.city, z.name].filter(Boolean).join(' ').toLowerCase().includes(q)
      );
    }
    list.sort((a, b) => {
      if (sortBy === 'distance' && userLocation) {
        const da = a.distance_km ?? Number.POSITIVE_INFINITY;
        const db = b.distance_km ?? Number.POSITIVE_INFINITY;
        return da - db;
      }
      const an = getZooDisplayName(a) || '';
      const bn = getZooDisplayName(b) || '';
      return an.localeCompare(bn);
    });
    return list;
  }, [zoos, zooFilter, sortBy, userLocation]);

  const zoosWithCoordinates = useMemo(
    () => filteredZoos.filter((zoo) => normalizeCoordinates(zoo)),
    [filteredZoos]
  );

  const persistViewState = useCallback(
    (nextMode, nextView) => {
      const desiredMode = nextMode || viewMode;
      const sanitizedView = sanitizeCameraView(nextView);
      const previous = persistedViewRef.current;
      if (
        previous.viewMode === desiredMode &&
        cameraViewsEqual(previous.mapView, sanitizedView)
      ) {
        return;
      }
      persistedViewRef.current = {
        viewMode: desiredMode,
        mapView: sanitizedView,
      };
      const state = routerLocation.state || {};
      navigate(`${routerLocation.pathname}${routerLocation.search}`, {
        replace: true,
        state: {
          ...state,
          animalViewMode: desiredMode,
          animalMapView: sanitizedView,
        },
      });
    },
    [
      navigate,
      routerLocation.pathname,
      routerLocation.search,
      routerLocation.state,
      viewMode,
    ]
  );

  const handleMapSelect = useCallback(
    (zoo, view) => {
      const sanitizedView = sanitizeCameraView(view) ?? mapView;
      setMapView(sanitizedView);
      persistViewState('map', sanitizedView);
      navigate(`${prefix}/zoos/${zoo.slug || zoo.id}`, {
        state: {
          animalViewMode: 'map',
          animalMapView: sanitizedView,
        },
      });
    },
    [mapView, navigate, persistViewState, prefix]
  );

  const handleViewModeChange = useCallback(
    (mode) => {
      setViewMode(mode);
      if (mode === 'map') {
        setMapResizeToken((token) => token + 1);
      }
      persistViewState(mode, mapView);
    },
    [mapView, persistViewState]
  );

  const handleMapViewChange = useCallback(
    (view) => {
      const sanitizedView = sanitizeCameraView(view) ?? mapView;
      setMapView(sanitizedView);
      persistViewState(viewMode, sanitizedView);
    },
    [mapView, persistViewState, viewMode]
  );

  const handleFavoriteToggle = useCallback(async () => {
    if (!animal) return;
    if (!isAuthenticated) {
      navigate(`${prefix}/login`, {
        state: { redirectTo: routerLocation.pathname },
      });
      return;
    }
    setFavoritePending(true);
    setFavoriteError('');
    try {
      const response = await authFetch(
        `${API}/animals/${animal.slug}/favorite`,
        { method: favorite ? 'DELETE' : 'PUT' }
      );
      if (!response.ok) {
        throw new Error('Failed to toggle favorite');
      }
      const payload = await response.json();
      const nextFavorite = Boolean(payload.favorite);
      setFavorite(nextFavorite);
      setAnimal((prev) => (prev ? { ...prev, is_favorite: nextFavorite } : prev));
    } catch (err) {
      setFavoriteError(t('animal.favoriteError'));
    } finally {
      setFavoritePending(false);
    }
  }, [animal, authFetch, favorite, isAuthenticated, navigate, prefix, routerLocation.pathname, t]);

  const handleLoginRedirect = useCallback(() => {
    navigate(`${prefix}/login`, {
      state: { redirectTo: routerLocation.pathname },
    });
  }, [navigate, prefix, routerLocation.pathname]);

  const formatHistoryDay = useCallback(
    (day) =>
      formatSightingDayLabel(day, locale, {
        today: t('dashboard.today'),
        yesterday: t('dashboard.yesterday'),
      }),
    [locale, t]
  );

  const renderHistoryItem = useCallback(
    (sighting, helpers) => {
      const zooName = sighting.zoo_name || sighting.zoo_id;
      const timeLabel = helpers.formatTime(sighting.sighting_datetime);
      const message = timeLabel
        ? t('animal.sightingHistoryItemWithTime', {
            animal: animalName,
            zoo: zooName,
            time: timeLabel,
          })
        : t('animal.sightingHistoryItem', {
            animal: animalName,
            zoo: zooName,
          });
      return (
        <>
          <div>{message}</div>
          {sighting.notes && (
            <div className="small text-muted mt-1">{sighting.notes}</div>
          )}
        </>
      );
    },
    [animalName, t]
  );

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

  const userSightings = Array.isArray(history) ? history : [];
  const seen = userSightings.length > 0;
  const firstSeen = seen
    ? new Date(
        userSightings
          .map((s) => s.sighting_datetime)
          .sort()[0]
      ).toLocaleDateString()
    : null;
  const gallery = userSightings.filter((s) => s.photo_url);
  const hasGallery = animal.images && animal.images.length > 0;

  const closestZoo = filteredZoos[0] ?? zoos[0];

  const historyMessages = {
    login: t('animal.sightingHistoryLogin'),
    loginCta: t('nav.login'),
    loading: t('animal.sightingHistoryLoading'),
    error: t('animal.sightingHistoryError'),
    empty: t('animal.sightingHistoryEmpty'),
  };

  const unauthenticatedHistory = (
    <div className="alert alert-info mt-2" role="status" aria-live="polite">
      <p className="mb-2">{historyMessages.login}</p>
      <button
        type="button"
        className="btn btn-primary btn-sm"
        onClick={handleLoginRedirect}
      >
        {historyMessages.loginCta}
      </button>
    </div>
  );

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
          {hasGallery ? (
            <div className="animal-media" style={{ '--ar': aspect }}>
              {/* Render image gallery using Bootstrap carousel */}
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
                        aria-label={`Slide ${i + 1} of ${animal.images.length}`}
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
                            draggable="false"
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
            </div>
          ) : (
            animal.default_image_url && (
              <div className="animal-media" style={{ '--ar': aspect }}>
                <img
                  src={animal.default_image_url}
                  alt={animalName}
                  decoding="async"
                  loading="lazy"
                  draggable="false"
                />
              </div>
            )
          )}
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
          {(className || orderName || familyName) && (
            <dl className="small mt-2 mb-0">
              {className && (
                <>
                  <dt className="fw-semibold">{t('animal.class')}</dt>
                  <dd className="mb-0">
                    {classificationLinks.class ? (
                      <Link
                        className="link-underline link-underline-opacity-0 link-underline-opacity-75-hover"
                        to={classificationLinks.class}
                        aria-label={t('animal.filterByClass', {
                          classification: className,
                        })}
                      >
                        {className}
                      </Link>
                    ) : (
                      className
                    )}
                  </dd>
                </>
              )}
              {orderName && (
                <>
                  <dt className="fw-semibold">{t('animal.order')}</dt>
                  <dd className="mb-0">
                    {classificationLinks.order ? (
                      <Link
                        className="link-underline link-underline-opacity-0 link-underline-opacity-75-hover"
                        to={classificationLinks.order}
                        aria-label={t('animal.filterByOrder', {
                          classification: orderName,
                        })}
                      >
                        {orderName}
                      </Link>
                    ) : (
                      orderName
                    )}
                  </dd>
                </>
              )}
              {familyName && (
                <>
                  <dt className="fw-semibold">{t('animal.family')}</dt>
                  <dd className="mb-0">
                    {classificationLinks.family ? (
                      <Link
                        className="link-underline link-underline-opacity-0 link-underline-opacity-75-hover"
                        to={classificationLinks.family}
                        aria-label={t('animal.filterByFamily', {
                          classification: familyName,
                        })}
                      >
                        {familyName}
                      </Link>
                    ) : (
                      familyName
                    )}
                  </dd>
                </>
              )}
            </dl>
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
            <button
              type="button"
              className={`btn btn-sm ${favorite ? 'btn-warning' : 'btn-outline-secondary'}`}
              onClick={handleFavoriteToggle}
              disabled={favoritePending}
              aria-pressed={favorite}
            >
              {favorite ? t('animal.removeFavorite') : t('animal.addFavorite')}
            </button>
          </div>
          {favoriteError && (
            <div className="text-danger small mt-1" role="status">
              {favoriteError}
            </div>
          )}
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
          <div className="card mt-3">
            <div className="card-body">
              <h4 className="card-title mb-3">
                {t('animal.sightingHistoryHeading')}
              </h4>
              <SightingHistoryList
                sightings={history}
                locale={locale}
                isAuthenticated={isAuthenticated}
                loading={historyLoading}
                error={historyError}
                messages={historyMessages}
                onLogin={handleLoginRedirect}
                formatDay={formatHistoryDay}
                renderSighting={renderHistoryItem}
                unauthenticatedContent={unauthenticatedHistory}
              />
            </div>
          </div>
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
            {/* Sorting controls only apply to the table view */}
            {viewMode === 'list' && (
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
                  disabled={!userLocation}
                  title={!userLocation ? t('animal.enableLocationSort') : undefined}
                >
                  {t('actions.sortByDistance')}
                </button>
              </div>
            )}
          </div>
          <div className="d-flex justify-content-end flex-wrap gap-2 mt-3">
            <fieldset className="btn-group" role="group" aria-label={t('zoo.viewToggle')}>
              <legend className="visually-hidden">{t('zoo.viewToggle')}</legend>
              <input
                type="radio"
                className="btn-check"
                name="animal-zoo-view"
                id="animal-zoo-view-list"
                autoComplete="off"
                checked={viewMode === 'list'}
                onChange={() => handleViewModeChange('list')}
              />
              <label className="btn btn-outline-primary" htmlFor="animal-zoo-view-list">
                {t('zoo.viewList')}
              </label>
              <input
                type="radio"
                className="btn-check"
                name="animal-zoo-view"
                id="animal-zoo-view-map"
                autoComplete="off"
                checked={viewMode === 'map'}
                onChange={() => handleViewModeChange('map')}
              />
              <label className="btn btn-outline-primary" htmlFor="animal-zoo-view-map">
                {t('zoo.viewMap')}
              </label>
            </fieldset>
          </div>
          <div className="small text-muted mt-2" aria-live="polite">
            Showing {filteredZoos.length} of {zoos.length}
          </div>
        </div>
        {viewMode === 'list' ? (
          <div className="table-responsive">
            <table className="table table-hover align-middle mb-0">
              <thead className="table-light">
                <tr>
                  <th scope="col">Zoo</th>
                  {userLocation && (
                    <th scope="col" className="text-end">Distance (km)</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {filteredZoos.map((z) => {
                  const displayName = getZooDisplayName(z);
                  return (
                    <tr
                      key={z.id}
                      className="pointer-row"
                      role="link"
                      aria-label={`Open ${displayName}`}
                      onClick={() => navigate(`${prefix}/zoos/${z.slug || z.id}`)}
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          navigate(`${prefix}/zoos/${z.slug || z.id}`);
                        }
                      }}
                    >
                      <td>
                        <span className="d-inline-flex align-items-center gap-1">
                          {displayName}
                          {/* Highlight favorite zoos with a shared badge component. */}
                          <FavoriteBadge isFavorite={Boolean(z.is_favorite)} />
                        </span>
                      </td>
                      {userLocation && (
                        <td className="text-end">
                          {z.distance_km != null ? z.distance_km.toFixed(1) : ''}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="card-body pt-0">
            {zoosWithCoordinates.length > 0 ? (
              <ZoosMap
                zoos={zoosWithCoordinates}
                center={
                  userLocation
                    ? {
                        lat: userLocation.lat,
                        lon: userLocation.lon,
                      }
                    : null
                }
                onSelect={handleMapSelect}
                initialView={mapView}
                onViewChange={handleMapViewChange}
                resizeToken={mapResizeToken}
                ariaLabel={t('animal.mapAriaLabel', { animal: animalName })}
              />
            ) : (
              <div className="alert alert-info mb-0" role="status">
                {t('zoo.noMapResults')}
              </div>
            )}
          </div>
        )}
      </div>
      <button
        onClick={() => {
          if (!isAuthenticated) {
            navigate(`${prefix}/login`);
            return;
          }
          setModalData({
            animalId: animal.id,
            animalName: animalName,
            zooId: closestZoo ? closestZoo.id : undefined,
            zooName: closestZoo
              ? getZooDisplayName(closestZoo)
              : undefined,
          });
        }}
        className="spaced-top btn btn-primary"
      >
        {t('actions.logSighting')}
      </button>
      {modalData && (
        <SightingModal
          zoos={zoos}
          defaultZooId={modalData.zooId}
          defaultAnimalId={modalData.animalId}
          defaultZooName={modalData.zooName}
          defaultAnimalName={modalData.animalName}
          onLogged={() => {
            loadHistory();
            onLogged && onLogged();
          }}
          onClose={() => setModalData(null)}
        />
      )}
    </div>
  );
}
