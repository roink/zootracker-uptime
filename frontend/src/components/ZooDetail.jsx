import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import SightingModal from './SightingModal';
import LazyMap from './LazyMap';
import { useAuth } from '../auth/AuthContext.jsx';

// Detailed view for a single zoo with a list of resident animals.
// Used by the ZooDetailPage component.
export default function ZooDetail({ zoo, refresh, onLogged }) {
  const [animals, setAnimals] = useState([]);
  const [visited, setVisited] = useState(false);
  const [seenIds, setSeenIds] = useState(new Set());
  const [modalData, setModalData] = useState(null);
  const navigate = useNavigate();
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const { t } = useTranslation();
  const authFetch = useAuthFetch();
  const { isAuthenticated, user } = useAuth();
  const userId = user?.id;
  const [descExpanded, setDescExpanded] = useState(false); // track full description visibility
  // Helper: pick animal name in current language
  const getAnimalName = useCallback(
    (a) =>
      lang === 'de'
        ? a.name_de || a.name_en
        : a.name_en || a.name_de,
    [lang]
  );

  // Load animals in this zoo (server already returns popularity order;
  // keep client-side sort as a fallback for robustness)
  useEffect(() => {
    fetch(`${API}/zoos/${zoo.id}/animals`)
      .then((r) => r.json())
      .then((data) => {
        setAnimals(
          Array.isArray(data) ? data : []
        );
      })
      .catch(() => setAnimals([]));
  }, [zoo, refresh]);

  // Load whether user has visited this zoo
  useEffect(() => {
    if (!isAuthenticated) return;
    authFetch(`${API}/zoos/${zoo.id}/visited`)
      .then((r) => (r.ok ? r.json() : { visited: false }))
      .then((d) => setVisited(Boolean(d.visited)))
      .catch(() => setVisited(false));
  }, [isAuthenticated, authFetch, zoo.id, refresh]);

  // Load IDs of animals the user has seen
  useEffect(() => {
    if (!isAuthenticated || !userId) return;
    authFetch(`${API}/users/${userId}/animals/ids`)
      .then((r) => (r.ok ? r.json() : []))
      .then((ids) => setSeenIds(new Set(ids)))
      .catch(() => setSeenIds(new Set()));
  }, [isAuthenticated, userId, authFetch, refresh]);
  // pick description based on current language with fallback to generic text
  const zooDescription =
    lang === 'de' ? zoo.description_de : zoo.description_en;
  const MAX_DESC = 400; // collapse threshold
  const needsCollapse = zooDescription && zooDescription.length > MAX_DESC;

  return (
    <div className="p-3">
      {zoo.image_url && (
        <img
          src={zoo.image_url}
          alt={zoo.name}
          className="img-fluid mb-2 cover-image"
        />
      )}
      <h3>{zoo.name}</h3>
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
      <div className="mt-2">
        {t('zoo.visited')} {visited ? `☑️ ${t('zoo.yes')}` : `✘ ${t('zoo.no')}`}
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
                <div>{getAnimalName(a)}</div>
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
                      zooName: zoo.name,
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
              fetch(`${API}/zoos/${zoo.id}/animals`)
                .then((r) => r.json())
                .then((data) => {
                  setAnimals(
                    Array.isArray(data) ? data : []
                  );
                })
                .catch(() => setAnimals([]));
              if (isAuthenticated) {
                authFetch(`${API}/zoos/${zoo.id}/visited`)
                  .then((r) => (r.ok ? r.json() : { visited: false }))
                  .then((d) => setVisited(Boolean(d.visited)))
                  .catch(() => setVisited(false));
                if (userId) {
                  authFetch(`${API}/users/${userId}/animals/ids`)
                    .then((r) => (r.ok ? r.json() : []))
                    .then((ids) => setSeenIds(new Set(ids)))
                    .catch(() => setSeenIds(new Set()));
                }
              }
            }}
            onClose={() => setModalData(null)}
          />
        )}
      </div>
    );
  }
