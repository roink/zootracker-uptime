import { useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { useState, useMemo, useEffect, Fragment, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import { API } from '../api';
import { useAuth } from '../auth/AuthContext';
import type { AnimalOption, ZooOption } from '../components/logForms';
import Seo from '../components/Seo';
import SightingModal from '../components/SightingModal';
import useAuthFetch from '../hooks/useAuthFetch';
import type { AnimalSummary, Sighting, Visit, ZooSummary } from '../types/domain';
import { fetchJson, isJsonObject, readJsonArray } from '../utils/fetchJson';
import { groupSightingsByDay, formatSightingDayLabel } from '../utils/sightingHistory';

interface DashboardProps {
  refresh?: number;
  onUpdate?: () => void;
}

type ZooMap = Record<string, ZooOption>;
type AnimalMap = Record<string, AnimalOption>;

type Achievement = {
  id: string;
  name?: string | null;
};

type ModalData = {
  sightingId?: string | null;
  zooId?: string | null;
  zooName?: string | null;
  animalId?: string | null;
  animalName?: string | null;
  note?: string | null;
};

// User dashboard showing recent visits, sightings and badges. Includes
// buttons to open forms for logging additional activity.
export default function Dashboard({ refresh, onUpdate }: DashboardProps) {
  const [modalData, setModalData] = useState<ModalData | null>(null);
  const navigate = useNavigate();
  const { lang = 'en' } = useParams<{ lang: string }>();
  const prefix = `/${lang}`;
  const authFetch = useAuthFetch();
  const queryClient = useQueryClient();
  const { isAuthenticated, user } = useAuth();
  const uid = user?.id ?? null;
  const { t } = useTranslation();

  // Refetch dashboard data when refresh counter changes
  useEffect(() => {
    if (!isAuthenticated || !uid) return;
    void queryClient.invalidateQueries({ queryKey: ['user', uid, 'visits'] });
    void queryClient.invalidateQueries({ queryKey: ['user', uid, 'animalsSeen'] });
    void queryClient.invalidateQueries({ queryKey: ['user', uid, 'sightings'] });
  }, [refresh, uid, isAuthenticated, queryClient]);

  const { data: zooMap = {}, isFetching: zoosFetching } = useQuery<unknown, Error, ZooMap>({
    queryKey: ['zoos'],
    queryFn: ({ signal }) => fetchJson(`${API}/zoos?limit=6000`, { signal }),
    staleTime: Infinity,
    gcTime: 30 * 60 * 1000,
    placeholderData: keepPreviousData,
    select: (payload) => {
      const zoos = readJsonArray<ZooOption>(payload);
      return Object.fromEntries(zoos.map((zoo) => [zoo.id, zoo] as const)) as ZooMap;
    },
  });

  const { data: animalMap = {}, isFetching: animalsFetching } = useQuery<
    unknown,
    Error,
    AnimalMap
  >({
    queryKey: ['animals'],
    queryFn: ({ signal }) => fetchJson(`${API}/animals`, { signal }),
    staleTime: Infinity,
    gcTime: 30 * 60 * 1000,
    placeholderData: keepPreviousData,
    select: (payload) => {
      const animals = readJsonArray<AnimalOption>(payload);
      return Object.fromEntries(animals.map((animal) => [animal.id, animal] as const)) as AnimalMap;
    },
  });

  const {
    data: visits = [],
    isFetching: visitsFetching,
  } = useQuery<Visit[]>({
    queryKey: ['user', uid, 'visits'],
    queryFn: async ({ signal }) => {
      const payload = await fetchJson(`${API}/visits`, { signal }, authFetch);
      return Array.isArray(payload) ? (payload as Visit[]) : [];
    },
    enabled: isAuthenticated,
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  });

  const {
    data: seenCount = 0,
    isFetching: seenFetching,
  } = useQuery<number>({
    queryKey: ['user', uid, 'animalsSeen'],
    queryFn: async ({ signal }) => {
      const payload = await fetchJson(`${API}/users/${uid}/animals/count`, { signal }, authFetch);
      if (isJsonObject(payload) && typeof (payload as { count?: unknown }).count === 'number') {
        return (payload as { count: number }).count;
      }
      return 0;
    },
    enabled: isAuthenticated && !!uid,
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  });

  const {
    data: sightings = [],
    isFetching: sightingsFetching,
  } = useQuery<Sighting[]>({
    queryKey: ['user', uid, 'sightings'],
    queryFn: async ({ signal }) => {
      const payload = await fetchJson(`${API}/sightings`, { signal }, authFetch);
      return Array.isArray(payload) ? (payload as Sighting[]) : [];
    },
    enabled: isAuthenticated,
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  });

  const {
    data: badges = [],
    isFetching: badgesFetching,
  } = useQuery<Achievement[]>({
    queryKey: ['user', uid, 'achievements'],
    // Placeholder query: achievements endpoint is not yet available so we
    // avoid calling it and just return an empty list for now.
    queryFn: async () => [],
    enabled: false,
    initialData: [] as Achievement[],
    staleTime: Infinity,
  });

  const zoos = useMemo(() => Object.values(zooMap), [zooMap]);
  const animals = useMemo(() => Object.values(animalMap), [animalMap]);
  const displayAnimalName = (sighting: Sighting) =>
    lang === 'de'
      ? sighting.animal_name_de || sighting.animal_name_en || sighting.animal_id
      : sighting.animal_name_en || sighting.animal_name_de || sighting.animal_id;

  const refreshing =
    zoosFetching ||
    animalsFetching ||
    visitsFetching ||
    seenFetching ||
    sightingsFetching ||
    badgesFetching;

  // Group sightings by day and order by day descending then creation time
  const groupedSightings = useMemo(
    () => groupSightingsByDay(sightings),
    [sightings]
  );

  const formatDay = useCallback(
    (day: string) =>
      formatSightingDayLabel(day, lang === 'de' ? 'de-DE' : 'en-US', {
        today: t('dashboard.today'),
        yesterday: t('dashboard.yesterday'),
      }),
    [lang, t]
  );

  // Distinct zoo count, derived from visits and sightings in case visit sync is missing
  const visitedZooCount = useMemo(() => {
    const ids = new Set([
      ...visits.map((visit) => visit.zoo_id),
      ...sightings.map((sighting) => sighting.zoo_id),
    ]);
    return ids.size;
  }, [visits, sightings]);

  return (
    <div className="container">
      <Seo
        title={t('nav.dashboard')}
        description={t('dashboard.description')}
      />
      <div className={`row text-center mb-3 ${refreshing ? 'opacity-50' : ''}`}>
        <div className="col">
          {t('dashboard.zoosVisited', { count: visitedZooCount })}
        </div>
        <div className="col">
          {t('dashboard.animalsSeen', { count: seenCount })}
        </div>
        <div className="col">
          {t('dashboard.badges', { count: badges.length })}
        </div>
      </div>
      <h3>{t('dashboard.activityFeed')}</h3>
      <ul className="list-group mb-3">
        {groupedSightings.map((group) => (
          <Fragment key={group.day}>
            <li className="list-group-item active">{formatDay(group.day)}</li>
            {group.items.map((sighting) => (
              <li
                key={sighting.id}
                className="list-group-item d-flex justify-content-between align-items-start"
              >
                <div className="me-3">
                  <div>
                    {t('dashboard.sighting', {
                      animal: displayAnimalName(sighting),
                      zoo: sighting.zoo_name ?? sighting.zoo_id,
                      date: sighting.sighting_datetime.slice(0, 10),
                    })}
                  </div>
                  {sighting.notes && (
                    <div className="text-muted small mt-1">
                      {t('dashboard.note', { note: sighting.notes })}
                    </div>
                  )}
                </div>
                <button
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => {
                    setModalData({
                      sightingId: sighting.id,
                      zooId: sighting.zoo_id,
                      zooName: sighting.zoo_name ?? null,
                      animalId: sighting.animal_id,
                      animalName: displayAnimalName(sighting),
                      note: sighting.notes ?? null,
                    });
                  }}
                >
                  {t('actions.edit')}
                </button>
              </li>
            ))}
          </Fragment>
        ))}
      </ul>
      <h3>{t('dashboard.recentBadges')}</h3>
      <div className="d-flex overflow-auto mb-3">
        {badges.length === 0 && (
          <div className="p-2">{t('dashboard.noBadges')}</div>
        )}
        {badges.map((badge) => (
          <div key={badge.id} className="me-2">{badge.name ?? '—'}</div>
        ))}
      </div>
      <div className="mt-2">
        <button
          className="btn btn-secondary me-2"
          onClick={() => {
            if (!isAuthenticated) {
              void navigate(`${prefix}/login`);
              return;
            }
            setModalData({});
          }}
        >
          {t('actions.logSighting')}
        </button>
      </div>
      {modalData && (
        <SightingModal
          zoos={zoos}
          animals={animals}
          sightingId={modalData.sightingId ?? null}
          {...(modalData.zooId ? { defaultZooId: modalData.zooId } : {})}
          {...(modalData.animalId ? { defaultAnimalId: modalData.animalId } : {})}
          {...(modalData.zooName ? { defaultZooName: modalData.zooName } : {})}
          {...(modalData.animalName ? { defaultAnimalName: modalData.animalName } : {})}
          defaultNotes={modalData.note ?? ''}
          onLogged={() => {
            onUpdate?.();
          }}
          onUpdated={() => {
            onUpdate?.();
          }}
          onClose={() => {
            setModalData(null);
          }}
        />
      )}
    </div>
  );
}
