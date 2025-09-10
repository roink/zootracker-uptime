import { useState, useMemo, useEffect, Fragment } from 'react';
import { useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import SightingModal from '../components/SightingModal';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Seo from '../components/Seo';

// User dashboard showing recent visits, sightings and badges. Includes
// buttons to open forms for logging additional activity.
export default function Dashboard({ token, userId, refresh, onUpdate }) {
  const [modalData, setModalData] = useState(null);
  const navigate = useNavigate();
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const authFetch = useAuthFetch(token);
  const queryClient = useQueryClient();
  const uid = userId || localStorage.getItem('userId');
  const { t } = useTranslation();

  // Refetch dashboard data when refresh counter changes
  useEffect(() => {
    if (!token) return;
    queryClient.invalidateQueries({ queryKey: ['user', uid, 'visits'] });
    queryClient.invalidateQueries({ queryKey: ['user', uid, 'animalsSeen'] });
    queryClient.invalidateQueries({ queryKey: ['user', uid, 'sightings'] });
    queryClient.invalidateQueries({ queryKey: ['user', uid, 'achievements'] });
  }, [refresh, uid, token, queryClient]);

  const { data: zooMap = {}, isFetching: zoosFetching } = useQuery({
    queryKey: ['zoos'],
    queryFn: async ({ signal }) => {
      const r = await fetch(`${API}/zoos`, { signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
    staleTime: 'static',
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
    staleTime: 'static',
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
    enabled: !!token,
    placeholderData: keepPreviousData,
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
    enabled: !!token && !!uid,
    placeholderData: keepPreviousData,
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
    enabled: !!token,
    placeholderData: keepPreviousData,
  });

  const {
    data: badges = [],
    isFetching: badgesFetching,
  } = useQuery({
    queryKey: ['user', uid, 'achievements'],
    queryFn: async ({ signal }) => {
      const r = await authFetch(`${API}/users/${uid}/achievements`, { signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
    enabled: !!token && !!uid,
    placeholderData: keepPreviousData,
  });

  const zoos = useMemo(() => Object.values(zooMap), [zooMap]);
  const animals = useMemo(() => Object.values(animalMap), [animalMap]);

  const zooName = (id) => zooMap[id]?.name || id;
  const animalName = (id) => {
    const a = animalMap[id];
    if (!a) return id;
    return lang === 'de' ? a.name_de || a.name_en : a.name_en || a.name_de;
  };

  const refreshing =
    zoosFetching ||
    animalsFetching ||
    visitsFetching ||
    seenFetching ||
    sightingsFetching ||
    badgesFetching;

  // Group sightings by day and order by day descending then creation time
  const groupedSightings = useMemo(() => {
    const sorted = [...sightings].sort((a, b) => {
      const dayA = new Date(a.sighting_datetime).toDateString();
      const dayB = new Date(b.sighting_datetime).toDateString();
      if (dayA === dayB) {
        return new Date(b.created_at) - new Date(a.created_at);
      }
      return new Date(b.sighting_datetime) - new Date(a.sighting_datetime);
    });
    const groups = [];
    sorted.forEach((s) => {
      const day = s.sighting_datetime.slice(0, 10);
      const last = groups[groups.length - 1];
      if (!last || last.day !== day) {
        groups.push({ day, items: [s] });
      } else {
        last.items.push(s);
      }
    });
    return groups;
  }, [sightings]);

  const formatDay = (day) => {
    const today = new Date().toISOString().slice(0, 10);
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const yDay = yesterday.toISOString().slice(0, 10);
    if (day === today) return 'Today';
    if (day === yDay) return 'Yesterday';
    return new Date(day).toLocaleDateString();
  };

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
        title="Dashboard"
        description="View your zoo visits, animal sightings and badges."
      />
      <div className={`row text-center mb-3 ${refreshing ? 'opacity-50' : ''}`}>
        <div className="col">Zoos Visited: {visitedZooCount}</div>
        <div className="col">Animals Seen: {seenCount}</div>
        <div className="col">Badges: {badges.length}</div>
      </div>
      <h3>Activity Feed</h3>
      <ul className="list-group mb-3">
        {groupedSightings.map((g) => (
          <Fragment key={g.day}>
            <li className="list-group-item active">{formatDay(g.day)}</li>
            {g.items.map((s) => (
              <li
                key={s.id}
                className="list-group-item d-flex justify-content-between align-items-center"
              >
                <span>
                  {`Saw ${
                    s.animal_name_de ?? animalName(s.animal_id)
                  } at ${zooName(s.zoo_id)} on ${s.sighting_datetime.slice(0, 10)}`}
                </span>
                <button
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() =>
                    setModalData({
                      sightingId: s.id,
                      zooId: s.zoo_id,
                      zooName: zooName(s.zoo_id),
                      animalId: s.animal_id,
                      animalName: s.animal_name_de ?? animalName(s.animal_id),
                    })
                  }
                >
                  Edit
                </button>
              </li>
            ))}
          </Fragment>
        ))}
      </ul>
      <h3>Recent Badges</h3>
      <div className="d-flex overflow-auto mb-3">
        {badges.length === 0 && <div className="p-2">No badges yet</div>}
        {badges.map((b) => (
          <div key={b.id} className="me-2">{b.name}</div>
        ))}
      </div>
      <div className="mt-2">
        <button
          className="btn btn-secondary me-2"
          onClick={() => {
            if (!token) {
              navigate(`${prefix}/login`);
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
          token={token}
          zoos={zoos}
          animals={animals}
          sightingId={modalData.sightingId}
          defaultZooId={modalData.zooId}
          defaultAnimalId={modalData.animalId}
          defaultZooName={modalData.zooName}
          defaultAnimalName={modalData.animalName}
          onLogged={() => {
            onUpdate && onUpdate();
          }}
          onUpdated={() => {
            onUpdate && onUpdate();
          }}
          onClose={() => setModalData(null)}
        />
      )}
    </div>
  );
}
