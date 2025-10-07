import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import SightingModal from './SightingModal';
import LazyMap from './LazyMap';
import SightingHistoryList from './SightingHistoryList.jsx';
import { useAuth } from '../auth/AuthContext.jsx';
import { getZooDisplayName } from '../utils/zooDisplayName.js';
import { formatSightingDayLabel } from '../utils/sightingHistory.js';

// Detailed view for a single zoo with a list of resident animals.
// Used by the ZooDetailPage component.
export default function ZooDetail({
  zoo,
  displayName,
  headingLevel = 'h2',
  refresh,
  onLogged,
  onFavoriteChange,
}) {
  const [animals, setAnimals] = useState([]);
  const [visited, setVisited] = useState(false);
  const [seenIds, setSeenIds] = useState(new Set());
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(false);
  const [modalData, setModalData] = useState(null);
  const navigate = useNavigate();
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const { t } = useTranslation();
  const authFetch = useAuthFetch();
  const { isAuthenticated, user } = useAuth();
  const userId = user?.id;
  const zooSlug = zoo?.slug;
  const locale = lang === 'de' ? 'de-DE' : 'en-US';
  const [descExpanded, setDescExpanded] = useState(false); // track full description visibility
  const [favorite, setFavorite] = useState(false);
  const [favoritePending, setFavoritePending] = useState(false);
  const [favoriteError, setFavoriteError] = useState('');
  // Helper: pick animal name in current language
  const getAnimalName = useCallback(
    (a) =>
      lang === 'de'
        ? a.name_de || a.name_en
        : a.name_en || a.name_de,
    [lang]
  );

  const getSightingAnimalName = useCallback(
    (s) =>
      lang === 'de'
        ? s.animal_name_de || s.animal_name_en
        : s.animal_name_en || s.animal_name_de,
    [lang]
  );

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
      const animalName = getSightingAnimalName(sighting);
      const timeLabel = helpers.formatTime(sighting.sighting_datetime);
      const message = timeLabel
        ? t('zoo.visitHistoryItemWithTime', {
            animal: animalName,
            time: timeLabel,
          })
        : t('zoo.visitHistoryItem', { animal: animalName });
      return (
        <>
          <div>{message}</div>
          {sighting.notes && (
            <div className="small text-muted mt-1">{sighting.notes}</div>
          )}
        </>
      );
    },
    [getSightingAnimalName, t]
  );

  const handleFavoriteToggle = useCallback(async () => {
    if (!zoo) return;
    if (!isAuthenticated) {
      navigate(`${prefix}/login`);
      return;
    }
    setFavoritePending(true);
    setFavoriteError('');
    try {
      const response = await authFetch(`${API}/zoos/${zoo.slug}/favorite`, {
        method: favorite ? 'DELETE' : 'PUT',
      });
      if (!response.ok) {
        throw new Error('Failed to toggle favorite');
      }
      const payload = await response.json();
      const nextFavorite = Boolean(payload.favorite);
      setFavorite(nextFavorite);
      onFavoriteChange?.(nextFavorite);
    } catch (err) {
      setFavoriteError(t('zoo.favoriteError'));
    } finally {
      setFavoritePending(false);
    }
  }, [authFetch, favorite, isAuthenticated, navigate, onFavoriteChange, prefix, t, zoo]);

  const loadAnimals = useCallback(() => {
    if (!zooSlug) {
      setAnimals([]);
      return Promise.resolve();
    }
    return authFetch(`${API}/zoos/${zooSlug}/animals`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        setAnimals(Array.isArray(data) ? data : []);
      })
      .catch(() => setAnimals([]));
  }, [authFetch, zooSlug]);

  const loadVisited = useCallback(() => {
    if (!isAuthenticated || !zooSlug) {
      setVisited(false);
      return Promise.resolve();
    }
    return authFetch(`${API}/zoos/${zooSlug}/visited`)
      .then((r) => (r.ok ? r.json() : { visited: false }))
      .then((d) => setVisited(Boolean(d.visited)))
      .catch(() => setVisited(false));
  }, [authFetch, isAuthenticated, zooSlug]);

  const loadSeenIds = useCallback(() => {
    if (!isAuthenticated || !userId) {
      setSeenIds(new Set());
      return Promise.resolve();
    }
    return authFetch(`${API}/users/${userId}/animals/ids`)
      .then((r) => (r.ok ? r.json() : []))
      .then((ids) => setSeenIds(new Set(ids)))
      .catch(() => setSeenIds(new Set()));
  }, [authFetch, isAuthenticated, userId]);

  const fetchHistory = useCallback(
    async ({ signal, limit, offset } = {}) => {
      if (!zooSlug) {
        return [];
      }
      const params = new URLSearchParams();
      if (typeof limit === 'number') {
        params.set('limit', String(limit));
      }
      if (typeof offset === 'number' && offset > 0) {
        params.set('offset', String(offset));
      }
      const baseUrl = `${API}/zoos/${zooSlug}/sightings`;
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
    [authFetch, zooSlug]
  );

  const loadHistory = useCallback(
    ({ signal } = {}) => {
      if (!isAuthenticated || !zooSlug) {
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
    [fetchHistory, isAuthenticated, zooSlug]
  );

  const reloadLocalData = useCallback(() => {
    loadAnimals();
    loadVisited();
    loadSeenIds();
    loadHistory();
  }, [loadAnimals, loadVisited, loadSeenIds, loadHistory]);

  // Load animals in this zoo (server already returns popularity order;
  // keep client-side sort as a fallback for robustness)
  useEffect(() => {
    loadAnimals();
  }, [loadAnimals, refresh]);

  useEffect(() => {
    setFavorite(Boolean(zoo?.is_favorite));
    setFavoriteError('');
  }, [zoo?.is_favorite]);

  // Load whether user has visited this zoo
  useEffect(() => {
    loadVisited();
  }, [loadVisited, refresh]);

  // Load IDs of animals the user has seen
  useEffect(() => {
    loadSeenIds();
  }, [loadSeenIds, refresh]);

  useEffect(() => {
    const controller = new AbortController();
    loadHistory({ signal: controller.signal });
    return () => controller.abort();
  }, [loadHistory, refresh]);

  // pick description based on current language with fallback to generic text
  const zooDescription =
    lang === 'de' ? zoo.description_de : zoo.description_en;
  const MAX_DESC = 400; // collapse threshold
  const needsCollapse = zooDescription && zooDescription.length > MAX_DESC;

  // Build the heading text by prefixing the city when available
  const zooDisplayName = displayName || getZooDisplayName(zoo);
  const allowedHeadingLevels = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'];
  const HeadingTag = allowedHeadingLevels.includes(headingLevel)
    ? headingLevel
    : 'h2';

  return (
    <div className="p-3">
      <HeadingTag className="h3 d-flex align-items-center gap-2">
        {zooDisplayName}
        {favorite && (
          <span className="text-warning" role="img" aria-label={t('zoo.favoriteBadge')}>
            ★
          </span>
        )}
      </HeadingTag>
      {zoo.address && <div className="text-muted">📍 {zoo.address}</div>}
      {Number.isFinite(zoo.latitude) && Number.isFinite(zoo.longitude) && (
        <div className="mt-1">
          <LazyMap latitude={zoo.latitude} longitude={zoo.longitude} />
        </div>
      )}
      {zooDescription && (
        <div className="card mt-3">
          <div className="card-body">
            <h5 className="card-title">{t('zoo.description')}</h5>
            {needsCollapse ? (
              <>
                {!descExpanded && (
                  <p className="card-text pre-wrap">
                    {zooDescription.slice(0, MAX_DESC)}…
                  </p>
                )}
                <p
                  id="zoo-desc-full"
                  className={`card-text pre-wrap collapse ${descExpanded ? 'show' : ''}`}
                >
                  {zooDescription}
                </p>
                <button
                  className="btn btn-link p-0"
                  type="button"
                  data-bs-toggle="collapse"
                  data-bs-target="#zoo-desc-full"
                  aria-expanded={descExpanded}
                  aria-controls="zoo-desc-full"
                  onClick={() => setDescExpanded((v) => !v)}
                >
                  {descExpanded ? t('zoo.showLess') : t('zoo.showMore')}
                </button>
              </>
            ) : (
              <p className="card-text pre-wrap">{zooDescription}</p>
            )}
          </div>
        </div>
      )}
      <div className="mt-2 d-flex flex-wrap gap-2 align-items-center">
        <span>
          {t('zoo.visited')} {visited ? `☑️ ${t('zoo.yes')}` : `✘ ${t('zoo.no')}`}
        </span>
        <button
          type="button"
          className={`btn btn-sm ${favorite ? 'btn-warning' : 'btn-outline-secondary'}`}
          onClick={handleFavoriteToggle}
          disabled={favoritePending}
          aria-pressed={favorite}
        >
          {favorite ? t('zoo.removeFavorite') : t('zoo.addFavorite')}
        </button>
      </div>
      {favoriteError && (
        <div className="text-danger small mt-1" role="status">
          {favoriteError}
        </div>
      )}
      <div className="mt-3">
        <h4>{t('zoo.visitHistoryHeading')}</h4>
        <SightingHistoryList
          sightings={history}
          locale={locale}
          isAuthenticated={isAuthenticated}
          loading={historyLoading}
          error={historyError}
          messages={{
            login: t('zoo.visitHistoryLogin'),
            loginCta: t('nav.login'),
            loading: t('zoo.visitHistoryLoading'),
            error: t('zoo.visitHistoryError'),
            empty: t('zoo.visitHistoryEmpty'),
          }}
          onLogin={() => navigate(`${prefix}/login`)}
          formatDay={formatHistoryDay}
          renderSighting={renderHistoryItem}
        />
      </div>
      {/* visit logging removed - visits are created automatically from sightings */}
      <h4 className="mt-3">{t('zoo.animals')}</h4>
      <table className="table">
        <thead>
          <tr>
            <th align="left">{t('zoo.name')}</th>
            <th className="text-center">{t('zoo.seen')}</th>
            <th className="text-center"></th>
          </tr>
        </thead>
        <tbody>
          {animals.map((a) => (
            <tr
              key={a.id}
              className="pointer-row"
              onClick={() => navigate(`${prefix}/animals/${a.slug || a.id}`)}
              tabIndex="0"
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  navigate(`${prefix}/animals/${a.slug || a.id}`);
                }
              }}
            >
              <td>
                <div className="d-flex align-items-center gap-1">
                  {getAnimalName(a)}
                  {a.is_favorite && (
                    <span
                      className="text-warning"
                      role="img"
                      aria-label={t('animal.favoriteBadge')}
                    >
                      ★
                    </span>
                  )}
                </div>
                {a.scientific_name && (
                  <div className="fst-italic small">{a.scientific_name}</div>
                )}
              </td>
              <td className="text-center">{seenIds.has(a.id) ? '✔️' : '—'}</td>
              <td className="text-center">
                <button
                  className="btn btn-sm btn-outline-secondary"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!isAuthenticated) {
                      navigate(`${prefix}/login`);
                      return;
                    }
                    setModalData({
                      zooId: zoo.id,
                      zooName: zooDisplayName,
                      animalId: a.id,
                      animalName: getAnimalName(a),
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
            animals={animals}
            defaultZooId={modalData.zooId}
            defaultAnimalId={modalData.animalId}
            defaultZooName={modalData.zooName}
            defaultAnimalName={modalData.animalName}
            onLogged={() => {
              onLogged && onLogged();
              reloadLocalData();
            }}
            onClose={() => setModalData(null)}
          />
        )}
      </div>
    );
  }
