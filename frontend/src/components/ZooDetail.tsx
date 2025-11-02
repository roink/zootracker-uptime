import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import { API } from '../api';
import LazyMap from './LazyMap';
import SightingHistoryList from './SightingHistoryList';
import SightingModal from './SightingModal';
import { useAuth } from '../auth/AuthContext';
import useAuthFetch from '../hooks/useAuthFetch';
import type { AnimalSummary, Sighting, ZooSummary } from '../types/domain';
import { formatSightingDayLabel } from '../utils/sightingHistory';
import { getZooDisplayName } from '../utils/zooDisplayName';

type HeadingLevel = 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';

export interface ZooDetailData extends Omit<ZooSummary, 'slug' | 'is_favorite'> {
  slug?: string | null;
  description_en?: string | null;
  description_de?: string | null;
  address?: string | null;
  country?: string | null;
  seo_description_en?: string | null;
  seo_description_de?: string | null;
  is_favorite?: boolean | null;
}

type ZooAnimal = AnimalSummary & {
  slug?: string | null;
  scientific_name?: string | null;
  is_favorite?: boolean | null;
};

interface ModalState {
  zooId: string;
  zooName: string;
  animalId: string;
  animalName: string;
}

interface ZooDetailProps {
  zoo: ZooDetailData;
  displayName?: string;
  headingLevel?: HeadingLevel;
  refresh?: number;
  onLogged?: () => void;
  onFavoriteChange?: (nextFavorite: boolean) => void;
}

// Detailed view for a single zoo with a list of resident animals.
// Used by the ZooDetailPage component.
export default function ZooDetail({
  zoo,
  displayName,
  headingLevel = 'h2',
  refresh = 0,
  onLogged,
  onFavoriteChange,
}: ZooDetailProps) {
  const [animals, setAnimals] = useState<ZooAnimal[]>([]);
  const [visited, setVisited] = useState(false);
  const [seenIds, setSeenIds] = useState<Set<string>>(new Set());
  const [history, setHistory] = useState<Sighting[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(false);
  const [modalData, setModalData] = useState<ModalState | null>(null);
  const navigate = useNavigate();
  const { lang: langParam } = useParams();
  const prefix = langParam ? `/${langParam}` : '';
  const { t } = useTranslation();
  const authFetch = useAuthFetch();
  const { isAuthenticated, user } = useAuth();
  const userId = user?.id;
  const zooSlug = zoo.slug ?? null;
  const locale = langParam === 'de' ? 'de-DE' : 'en-US';
  const [descExpanded, setDescExpanded] = useState(false); // track full description visibility
  const [favorite, setFavorite] = useState(false);
  const [favoritePending, setFavoritePending] = useState(false);
  const [favoriteError, setFavoriteError] = useState('');
  // Helper: pick animal name in current language
  const getAnimalName = useCallback(
    (animal: ZooAnimal) =>
      langParam === 'de'
        ? animal.name_de || animal.name_en || ''
        : animal.name_en || animal.name_de || '',
    [langParam]
  );

  const getSightingAnimalName = useCallback(
    (sighting: Sighting) =>
      langParam === 'de'
        ? sighting.animal_name_de || sighting.animal_name_en || ''
        : sighting.animal_name_en || sighting.animal_name_de || '',
    [langParam]
  );

  const formatHistoryDay = useCallback(
    (day: string) =>
      formatSightingDayLabel(day, locale, {
        today: t('dashboard.today'),
        yesterday: t('dashboard.yesterday'),
      }),
    [locale, t]
  );

  const renderHistoryItem = useCallback(
    (sighting: Sighting, helpers: { formatTime: (value: string) => string | null }) => {
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
    if (!zooSlug) return;
    if (!isAuthenticated) {
      void navigate(`${prefix}/login`);
      return;
    }
    setFavoritePending(true);
    setFavoriteError('');
    try {
      const response = await authFetch(`${API}/zoos/${zooSlug}/favorite`, {
        method: favorite ? 'DELETE' : 'PUT',
      });
      if (!response.ok) {
        throw new Error('Failed to toggle favorite');
      }
      const payload = await response.json();
      const nextFavorite = Boolean((payload as { favorite?: unknown }).favorite);
      setFavorite(nextFavorite);
      onFavoriteChange?.(nextFavorite);
    } catch (_err) {
      setFavoriteError(t('zoo.favoriteError'));
    } finally {
      setFavoritePending(false);
    }
  }, [authFetch, favorite, isAuthenticated, navigate, onFavoriteChange, prefix, t, zooSlug]);

  const loadAnimals = useCallback(async () => {
    if (!zooSlug) {
      setAnimals([]);
      return;
    }
    try {
      const response = await authFetch(`${API}/zoos/${zooSlug}/animals`);
      if (!response.ok) {
        setAnimals([]);
        return;
      }
      const data = (await response.json()) as unknown;
      setAnimals(Array.isArray(data) ? (data as ZooAnimal[]) : []);
    } catch {
      setAnimals([]);
    }
  }, [authFetch, zooSlug]);

  const loadVisited = useCallback(async () => {
    if (!isAuthenticated || !zooSlug) {
      setVisited(false);
      return;
    }
    try {
      const response = await authFetch(`${API}/zoos/${zooSlug}/visited`);
      if (!response.ok) {
        setVisited(false);
        return;
      }
      const result = (await response.json()) as { visited?: unknown };
      setVisited(Boolean(result.visited));
    } catch {
      setVisited(false);
    }
  }, [authFetch, isAuthenticated, zooSlug]);

  const loadSeenIds = useCallback(async () => {
    if (!isAuthenticated || !userId) {
      setSeenIds(new Set());
      return;
    }
    try {
      const response = await authFetch(`${API}/users/${userId}/animals/ids`);
      if (!response.ok) {
        setSeenIds(new Set());
        return;
      }
      const ids = (await response.json()) as unknown;
      const normalized = Array.isArray(ids)
        ? ids.filter((value): value is string => typeof value === 'string')
        : [];
      setSeenIds(new Set(normalized));
    } catch {
      setSeenIds(new Set());
    }
  }, [authFetch, isAuthenticated, userId]);

  const fetchHistory = useCallback(
    async ({ signal, limit, offset }: { signal?: AbortSignal; limit?: number; offset?: number } = {}): Promise<Sighting[]> => {
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
      const response = await authFetch(url, signal ? { signal } : {});
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = (await response.json()) as unknown;
      if (data && typeof data === 'object' && Array.isArray((data as { items?: unknown }).items)) {
        return (data as { items: Sighting[] }).items.map((item) => item);
      }
      if (Array.isArray(data)) {
        return data as Sighting[];
      }
      return [];
    },
    [authFetch, zooSlug]
  );

  const loadHistory = useCallback(
    async ({ signal }: { signal?: AbortSignal } = {}) => {
      if (!isAuthenticated || !zooSlug) {
        setHistory([]);
        setHistoryError(false);
        setHistoryLoading(false);
        return;
      }
      setHistoryLoading(true);
      setHistoryError(false);
      try {
        const items = await fetchHistory(signal ? { signal } : {});
        setHistory(items);
        setHistoryError(false);
      } catch (err) {
        if (
          typeof err === 'object' &&
          err !== null &&
          'name' in err &&
          (err as { name?: unknown }).name === 'AbortError'
        ) {
          return;
        }
        setHistory([]);
        setHistoryError(true);
      } finally {
        if (!signal || !signal.aborted) {
          setHistoryLoading(false);
        }
      }
    },
    [fetchHistory, isAuthenticated, zooSlug]
  );

  const reloadLocalData = useCallback(() => {
    void loadAnimals();
    void loadVisited();
    void loadSeenIds();
    void loadHistory();
  }, [loadAnimals, loadVisited, loadSeenIds, loadHistory]);

  // Load animals in this zoo (server already returns popularity order;
  // keep client-side sort as a fallback for robustness)
  useEffect(() => {
    void loadAnimals();
  }, [loadAnimals, refresh]);

    useEffect(() => {
      setFavorite(Boolean(zoo.is_favorite));
      setFavoriteError('');
    }, [zoo.is_favorite]);

  // Load whether user has visited this zoo
  useEffect(() => {
    void loadVisited();
  }, [loadVisited, refresh]);

  // Load IDs of animals the user has seen
  useEffect(() => {
    void loadSeenIds();
  }, [loadSeenIds, refresh]);

  useEffect(() => {
    const controller = new AbortController();
    void loadHistory({ signal: controller.signal });
    return () => { controller.abort(); };
  }, [loadHistory, refresh]);

  // pick description based on current language with fallback to generic text
  const zooDescription =
    langParam === 'de' ? zoo.description_de : zoo.description_en;
  const MAX_DESC = 400; // collapse threshold
  const needsCollapse = zooDescription && zooDescription.length > MAX_DESC;

  // Build the heading text by prefixing the city when available
  const zooDisplayName = displayName || getZooDisplayName(zoo);
  const allowedHeadingLevels: HeadingLevel[] = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'];
  const HeadingTag: HeadingLevel = allowedHeadingLevels.includes(headingLevel)
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
                  onClick={() => { setDescExpanded((v) => !v); }}
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
          onLogin={() => void navigate(`${prefix}/login`)}
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
              onClick={() => void navigate(`${prefix}/animals/${a.slug || a.id}`)}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  void navigate(`${prefix}/animals/${a.slug || a.id}`);
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
                      void navigate(`${prefix}/login`);
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
            onLogged?.();
            reloadLocalData();
          }}
          onClose={() => { setModalData(null); }}
        />
      )}
      </div>
    );
  }
