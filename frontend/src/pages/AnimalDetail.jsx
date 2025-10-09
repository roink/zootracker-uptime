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

function useMediaQuery(query) {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined') {
      return false;
    }
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined') {
      return () => {};
    }
    const mediaQueryList = window.matchMedia(query);
    const handleChange = (event) => setMatches(event.matches);
    handleChange(mediaQueryList);
    if (typeof mediaQueryList.addEventListener === 'function') {
      mediaQueryList.addEventListener('change', handleChange);
      return () => mediaQueryList.removeEventListener('change', handleChange);
    }
    mediaQueryList.addListener(handleChange);
    return () => mediaQueryList.removeListener(handleChange);
  }, [query]);

  return matches;
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
  const locale = lang === 'de' ? 'de-DE' : 'en-US';
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
  const isDesktop = useMediaQuery('(min-width: 992px)');
  const [activeSection, setActiveSection] = useState('overview');
  const [openSections, setOpenSections] = useState(() => new Set(['overview']));
  const tabRefs = useRef([]);
  const [taxonomyOpen, setTaxonomyOpen] = useState(false);

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

  const parentDetails = useMemo(() => {
    if (!animal?.parent) {
      return null;
    }
    const parent = animal.parent;
    const name =
      lang === 'de'
        ? parent.name_de || parent.name_en
        : parent.name_en || parent.name_de;
    return {
      slug: parent.slug,
      name: name || parent.scientific_name || parent.slug,
      scientific: parent.scientific_name || null,
    };
  }, [animal?.parent, lang]);

  const subspeciesLinks = useMemo(() => {
    const entries = Array.isArray(animal?.subspecies) ? animal.subspecies : [];
    return entries.map((entry) => {
      const name =
        lang === 'de'
          ? entry.name_de || entry.name_en
          : entry.name_en || entry.name_de;
      return {
        slug: entry.slug,
        name: name || entry.scientific_name || entry.slug,
        scientific: entry.scientific_name || null,
      };
    });
  }, [animal?.subspecies, lang]);

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
    setActiveSection('overview');
    setOpenSections(new Set(['overview']));
    setTaxonomyOpen(false);
  }, [slug]);

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
  const animalImages = Array.isArray(animal?.images) ? animal.images : [];
  const hasGallery = animalImages.length > 0;

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
  const aspect = hasGallery ? computeAspect(animalImages[0]) : '4 / 3';
  const mediaSection = hasGallery
    ? (
        <div className="animal-media" style={{ '--ar': aspect }}>
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
            {animalImages.length > 1 && (
              <div className="carousel-indicators">
                {animalImages.map((_, i) => (
                  <button
                    key={i}
                    type="button"
                    data-bs-target="#animalCarousel"
                    data-bs-slide-to={i}
                    className={i === 0 ? 'active' : ''}
                    aria-label={`Slide ${i + 1} of ${animalImages.length}`}
                  />
                ))}
              </div>
            )}
            <div className="carousel-inner h-100">
              {animalImages.map((img, idx) => {
                const sorted = [...(img.variants || [])].sort(
                  (a, b) => a.width - b.width
                );
                const fallback = sorted[0];
                const fallbackSrc = fallback?.thumb_url || img.original_url;
                const uniqueByWidth = [];
                const seenSet = new Set();
                for (const v of sorted) {
                  if (!seenSet.has(v.width)) {
                    uniqueByWidth.push(v);
                    seenSet.add(v.width);
                  }
                }
                const srcSet = uniqueByWidth
                  .map((v) => `${v.thumb_url} ${v.width}w`)
                  .join(', ');
                const isFirst = idx === 0;
                const loadingAttr = isFirst ? 'eager' : 'lazy';
                const fetchPri = isFirst ? 'high' : 'low';
                const sizes =
                  '(min-width: 1200px) 540px, (min-width: 992px) 50vw, 100vw';

                return (
                  <div
                    key={img.mid}
                    className={`carousel-item ${idx === 0 ? 'active' : ''}`}
                    aria-label={`Slide ${idx + 1} of ${animalImages.length}`}
                  >
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
            {animalImages.length > 1 && (
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
      )
    : animal?.default_image_url
    ? (
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
    : null;
  const taxonomyHasDetails = Boolean(
    className ||
      orderName ||
      familyName ||
      parentDetails ||
      subspeciesLinks.length > 0
  );
  const taxonomyContentId = 'animal-taxonomy-details';

  const renderOverviewPanel = () => (
    <div className="animal-section-panel card">
      <div className="card-body">
        {animalDesc && (
          <div>
            <h3 className="h5">{t('animal.aboutHeading')}</h3>
            <p
              id="animal-description"
              className={`mb-3 ${descOpen ? '' : 'line-clamp-6'}`}
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
        )}
        {taxonomyHasDetails && (
          <div className="taxonomy-disclosure mt-4">
            <button
              type="button"
              className="taxonomy-toggle btn btn-link p-0 text-start"
              onClick={() => setTaxonomyOpen((value) => !value)}
              aria-expanded={taxonomyOpen}
              aria-controls={taxonomyContentId}
            >
              <span className="fw-semibold d-block">
                {t('animal.taxonomyDisclosureLabel')}
              </span>
              <span className="small text-muted">
                {taxonomyOpen
                  ? t('animal.taxonomyDisclosureHide')
                  : t('animal.taxonomyDisclosureShow')}
              </span>
            </button>
            <div
              id={taxonomyContentId}
              className="taxonomy-content mt-3"
              hidden={!taxonomyOpen}
            >
              {(className || orderName || familyName) && (
                <dl className="small taxonomy-list mb-0">
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
              {(parentDetails || subspeciesLinks.length > 0) && (
                <div className="taxonomy-relations mt-3">
                  {parentDetails && (
                    <div className="taxonomy-parent">
                      <div className="relation-heading text-muted text-uppercase small mb-1">
                        {t('animal.parentSpecies')}
                      </div>
                      <Link
                        className="relation-link"
                        to={`${prefix}/animals/${parentDetails.slug}`}
                        aria-label={t('animal.viewParent', { name: parentDetails.name })}
                      >
                        {parentDetails.name}
                      </Link>
                      {parentDetails.scientific && (
                        <span className="relation-scientific">{parentDetails.scientific}</span>
                      )}
                    </div>
                  )}
                  {subspeciesLinks.length > 0 && (
                    <div className="taxonomy-subspecies">
                      <div className="relation-heading text-muted text-uppercase small mb-1">
                        {t('animal.subspeciesHeading')}
                      </div>
                      <ul className="subspecies-list">
                        {subspeciesLinks.map((entry) => (
                          <li key={entry.slug}>
                            <Link
                              className="relation-link"
                              to={`${prefix}/animals/${entry.slug}`}
                              aria-label={t('animal.viewSubspecies', { name: entry.name })}
                            >
                              {entry.name}
                            </Link>
                            {entry.scientific && (
                              <span className="relation-scientific">{entry.scientific}</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );

  const renderWherePanel = () => (
    <div className="animal-section-panel card">
      <div className="card-body pb-2">
        <div className="where-toolbar d-flex flex-column flex-lg-row gap-3 align-items-stretch align-items-lg-center">
          <div className="flex-grow-1">
            <div className="input-group input-group-sm">
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
          </div>
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
        {viewMode === 'list' && (
          <div className="d-flex flex-wrap gap-2 mt-3" role="group" aria-label={t('animal.sortZoos')}>
            <div className="btn-group btn-group-sm" role="group">
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
          </div>
        )}
        <div className="small text-muted mt-3" aria-live="polite">
          {t('animal.filteredCount', { count: filteredZoos.length, total: zoos.length })}
        </div>
      </div>
      {viewMode === 'list' ? (
        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th scope="col">Zoo</th>
                {userLocation && (
                  <th scope="col" className="text-end">
                    {t('animal.distanceColumnLabel')}
                  </th>
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
                    aria-label={t('animal.openZoo', { zoo: displayName })}
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
  );

  const renderSightingsPanel = () => (
    <div className="animal-section-panel card">
      <div className="card-body">
        {gallery.length > 0 && (
          <div className="sightings-gallery mb-4">
            <h3 className="h6 text-uppercase text-muted mb-2">
              {t('animal.sightingsGalleryHeading')}
            </h3>
            <div className="gallery">
              {gallery.map((g, idx) => (
                <img
                  key={idx}
                  src={g.photo_url}
                  alt={t('animal.sightingsGalleryAlt', { animal: animalName })}
                  className="gallery-img"
                />
              ))}
            </div>
          </div>
        )}
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
  );

  const sections = [
    { id: 'overview', label: t('animal.overviewTab'), render: renderOverviewPanel },
    { id: 'where', label: t('animal.whereToSee'), render: renderWherePanel },
    {
      id: 'sightings',
      label: t('animal.sightingHistoryHeading'),
      render: renderSightingsPanel,
    },
  ];

  useEffect(() => {
    if (!sections.length) {
      return;
    }
    const ids = sections.map((section) => section.id);
    if (!ids.includes(activeSection)) {
      setActiveSection(ids[0]);
    }
    setOpenSections((prev) => {
      const next = new Set();
      prev.forEach((id) => {
        if (ids.includes(id)) {
          next.add(id);
        }
      });
      if (prev.size > 0 && next.size === 0) {
        next.add(ids[0]);
      }
      if (next.size === prev.size && [...next].every((id) => prev.has(id))) {
        return prev;
      }
      return next;
    });
  }, [sections, activeSection]);

  const handleTabKeyDown = useCallback(
    (event, index) => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') {
        return;
      }
      event.preventDefault();
      const direction = event.key === 'ArrowRight' ? 1 : -1;
      const nextIndex = (index + direction + sections.length) % sections.length;
      const nextSection = sections[nextIndex];
      setActiveSection(nextSection.id);
      const node = tabRefs.current[nextIndex];
      if (node) {
        node.focus();
      }
    },
    [sections]
  );

  const toggleAccordion = useCallback((id) => {
    setOpenSections((prev) => {
      if (prev.has(id)) {
        return new Set();
      }
      return new Set([id]);
    });
  }, []);

  const animalId = animal?.id ?? null;

  const handleLogSightingClick = useCallback(() => {
    if (!animal) {
      return;
    }
    if (!isAuthenticated) {
      handleLoginRedirect();
      return;
    }
    const defaultZoo = closestZoo;
    setModalData({
      animalId: animalId,
      animalName: animalName,
      zooId: defaultZoo ? defaultZoo.id : undefined,
      zooName: defaultZoo ? getZooDisplayName(defaultZoo) : undefined,
    });
  }, [animal, animalId, animalName, closestZoo, handleLoginRedirect, isAuthenticated]);

  tabRefs.current = sections.map((_, index) => tabRefs.current[index] || null);

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

  return (
    <div className="page-container animal-detail-page">
      <Seo
        title={animal ? animalName : 'Animal'}
        description={
          animal
            ? `Discover where to see ${animalName} and log your sightings.`
            : 'Animal details on ZooTracker.'
        }
      />
      <header className="animal-header d-flex flex-column flex-lg-row gap-3 align-items-lg-start">
        <div className="flex-grow-1">
          <h1 className="mb-1">{animalName}</h1>
          {animal.scientific_name && (
            <div className="fst-italic text-muted">{animal.scientific_name}</div>
          )}
          {animal.taxon_rank && (
            <div className="mt-2">
              <span className="badge bg-light text-muted border">{animal.taxon_rank}</span>
            </div>
          )}
        </div>
        <button
          type="button"
          className="btn btn-primary btn-lg log-sighting-button"
          onClick={handleLogSightingClick}
        >
          {t('actions.logSighting')}
        </button>
      </header>
      <div className="animal-meta d-flex flex-wrap align-items-center gap-2 mt-3">
        <span className={`badge ${seen ? 'bg-success' : 'bg-secondary'}`}>
          {seen ? t('animal.seenOn', { date: firstSeen }) : t('animal.notSeen')}
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
          className={`btn btn-sm favorite-toggle ${favorite ? 'btn-warning text-dark' : 'btn-outline-secondary'}`}
          onClick={handleFavoriteToggle}
          disabled={favoritePending}
          aria-pressed={favorite}
        >
          <span aria-hidden="true" className="favorite-icon">★</span>
          <span className="ms-1">{t('animal.favoriteToggle')}</span>
          <span className="visually-hidden">
            {favorite
              ? t('animal.favoriteSelected')
              : t('animal.favoriteNotSelected')}
          </span>
        </button>
      </div>
      {favoriteError && (
        <div className="text-danger small mt-2" role="status">
          {favoriteError}
        </div>
      )}
      {isDesktop ? (
        <div
          className="animal-desktop-sections mt-3"
          role="region"
          aria-label={t('animal.sectionNavigationLabel')}
        >
          <div className="nav nav-tabs w-100" role="tablist">
            {sections.map((section, index) => (
              <button
                key={section.id}
                type="button"
                role="tab"
                className={`nav-link ${activeSection === section.id ? 'active' : ''}`}
                id={`${section.id}-tab`}
                aria-controls={`${section.id}-panel`}
                aria-selected={activeSection === section.id}
                onClick={() => setActiveSection(section.id)}
                onKeyDown={(event) => handleTabKeyDown(event, index)}
                ref={(node) => {
                  tabRefs.current[index] = node;
                }}
              >
                {section.label}
              </button>
            ))}
          </div>
          <div className="row g-4 g-lg-5 align-items-start mt-3">
            <div
              className={`col-12 ${mediaSection ? 'col-lg-6 order-lg-1' : ''}`}
            >
              {sections.map((section) => (
                <div
                  key={section.id}
                  id={`${section.id}-panel`}
                  role="tabpanel"
                  aria-labelledby={`${section.id}-tab`}
                  className="animal-tabpanel"
                  hidden={activeSection !== section.id}
                >
                  {section.render()}
                </div>
              ))}
            </div>
            {mediaSection && (
              <div className="col-12 col-lg-6 order-lg-2">
                <div className="sticky-lg-top" style={{ top: '1rem' }}>
                  {mediaSection}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <>
          {mediaSection && <div className="mt-3">{mediaSection}</div>}
          <div className="accordion animal-accordion mt-3" id="animal-detail-sections">
            {sections.map((section) => {
              const open = openSections.has(section.id);
              return (
                <div className="accordion-item" key={section.id}>
                  <h2 className="accordion-header" id={`${section.id}-heading`}>
                    <button
                      className={`accordion-button ${open ? '' : 'collapsed'}`}
                      type="button"
                      aria-expanded={open}
                      aria-controls={`${section.id}-collapse`}
                      onClick={() => toggleAccordion(section.id)}
                    >
                      {section.label}
                    </button>
                  </h2>
                  <div
                    id={`${section.id}-collapse`}
                    className={`accordion-collapse collapse ${open ? 'show' : ''}`}
                    aria-labelledby={`${section.id}-heading`}
                  >
                    <div className="accordion-body">{section.render()}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
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
