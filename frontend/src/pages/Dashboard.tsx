// @ts-nocheck
import { useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { useState, useMemo, useEffect, Fragment, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import { API } from '../api';
import { useAuth } from '../auth/AuthContext';
import Seo from '../components/Seo';
import SightingModal from '../components/SightingModal';
import useAuthFetch from '../hooks/useAuthFetch';
import { groupSightingsByDay, formatSightingDayLabel } from '../utils/sightingHistory';

// User dashboard showing recent visits, sightings and badges. Includes
// buttons to open forms for logging additional activity.
export default function Dashboard({ refresh, onUpdate }: any) {
  const [modalData, setModalData] = useState<any>(null);
  const navigate = useNavigate();
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const authFetch = useAuthFetch();
  const queryClient = useQueryClient();
  const { isAuthenticated, user } = useAuth();
  const uid = user?.id;
  const { t } = useTranslation();

  // Refetch dashboard data when refresh counter changes
  useEffect(() => {
    if (!isAuthenticated || !uid) return;
      void queryClient.invalidateQueries({ queryKey: ['user', uid, 'visits'] });
      void queryClient.invalidateQueries({ queryKey: ['user', uid, 'animalsSeen'] });
      void queryClient.invalidateQueries({ queryKey: ['user', uid, 'sightings'] });
  }, [refresh, uid, isAuthenticated, queryClient]);

  const { data: zooMap = {}, isFetching: zoosFetching } = useQuery({
    queryKey: ['zoos'],
    queryFn: async ({ signal }) => {
      const r = await fetch(`${API}/zoos?limit=6000`, { signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const payload = await r.json();
      if (Array.isArray(payload?.items)) return payload.items;
      if (Array.isArray(payload)) return payload;
      return [];
    },
    staleTime: Infinity,
    gcTime: 30 * 60 * 1000,
    placeholderData: keepPreviousData,
    select: (zoos) => Object.fromEntries(zoos.map((z) => [z.id, z])),
  });

  const { data: animalMap = {}, isFetching: animalsFetching } = useQuery({
    queryKey: ['animals'],
    queryFn: async ({ signal }) => {
      const r = await fetch(`${API}/animals`, { signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
    staleTime: Infinity,
    gcTime: 30 * 60 * 1000,
    placeholderData: keepPreviousData,
    select: (animals) => Object.fromEntries(animals.map((a) => [a.id, a])),
  });

  const {
    data: visits = [],
    isFetching: visitsFetching,
  } = useQuery({
    queryKey: ['user', uid, 'visits'],
    queryFn: async ({ signal }) => {
      const r = await authFetch(`${API}/visits`, { signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
    enabled: isAuthenticated,
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  });

  const {
    data: seenCount = 0,
    isFetching: seenFetching,
  } = useQuery({
    queryKey: ['user', uid, 'animalsSeen'],
    queryFn: async ({ signal }) => {
      const r = await authFetch(`${API}/users/${uid}/animals/count`, { signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      return d.count ?? 0;
    },
    enabled: isAuthenticated && !!uid,
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  });

  const {
    data: sightings = [],
    isFetching: sightingsFetching,
  } = useQuery({
    queryKey: ['user', uid, 'sightings'],
    queryFn: async ({ signal }) => {
      const r = await authFetch(`${API}/sightings`, { signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
    enabled: isAuthenticated,
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
  });

  const {
    data: badges = [],
    isFetching: badgesFetching,
  } = useQuery({
    queryKey: ['user', uid, 'achievements'],
    // Placeholder query: achievements endpoint is not yet available so we
    // avoid calling it and just return an empty list for now.
    queryFn: async () => [],
    enabled: false,
    initialData: [],
    staleTime: Infinity,
  });

  const zoos = useMemo(() => Object.values(zooMap), [zooMap]);
  const animals = useMemo(() => Object.values(animalMap), [animalMap]);
  const displayAnimalName = (s) =>
    lang === 'de'
      ? s.animal_name_de || s.animal_name_en
      : s.animal_name_en || s.animal_name_de;

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
    (day) =>
      formatSightingDayLabel(day, lang === 'de' ? 'de-DE' : 'en-US', {
        today: t('dashboard.today'),
        yesterday: t('dashboard.yesterday'),
      }),
    [lang, t]
  );

  // Distinct zoo count, derived from visits and sightings in case visit sync is missing
  const visitedZooCount = useMemo(() => {
    const ids = new Set([
      ...visits.map((v) => v.zoo_id),
      ...sightings.map((s) => s.zoo_id),
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
        {groupedSightings.map((g) => (
          <Fragment key={g.day}>
            <li className="list-group-item active">{formatDay(g.day)}</li>
            {g.items.map((s) => (
              <li
                key={s.id}
                className="list-group-item d-flex justify-content-between align-items-start"
              >
                <div className="me-3">
                  <div>
                    {t('dashboard.sighting', {
                      animal: displayAnimalName(s),
                      zoo: s.zoo_name ?? s.zoo_id,
                      date: s.sighting_datetime.slice(0, 10),
                    })}
                  </div>
                  {s.notes && (
                    <div className="text-muted small mt-1">
                      {t('dashboard.note', { note: s.notes })}
                    </div>
                  )}
                </div>
                <button
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() =>
                    { setModalData({
                      sightingId: s.id,
                      zooId: s.zoo_id,
                      zooName: s.zoo_name,
                      animalId: s.animal_id,
                      animalName: displayAnimalName(s),
                      note: s.notes ?? '',
                    }); }
                  }
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
        {badges.map((b) => (
          <div key={b.id} className="me-2">{b.name}</div>
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
          sightingId={modalData.sightingId}
          defaultZooId={modalData.zooId}
          defaultAnimalId={modalData.animalId}
          defaultZooName={modalData.zooName}
          defaultAnimalName={modalData.animalName}
          defaultNotes={modalData.note ?? ''}
          onLogged={() => {
            onUpdate && onUpdate();
          }}
          onUpdated={() => {
            onUpdate && onUpdate();
          }}
          onClose={() => { setModalData(null); }}
        />
      )}
    </div>
  );
}
