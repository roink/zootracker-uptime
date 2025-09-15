import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import { useTranslation } from 'react-i18next';
import Seo from '../components/Seo';
import { useAuth } from '../auth/AuthContext.jsx';

// Browse all animals with hierarchical taxonomy filters and pagination
export default function AnimalsPage() {
  const navigate = useNavigate();
  const { lang } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const prefix = `/${lang}`;
  const [animals, setAnimals] = useState([]);
  const [seenAnimals, setSeenAnimals] = useState([]);
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [classes, setClasses] = useState([]);
  const [orders, setOrders] = useState([]);
  const [families, setFamilies] = useState([]);
  const [classId, setClassId] = useState(searchParams.get('class') || '');
  const [orderId, setOrderId] = useState(searchParams.get('order') || '');
  const [familyId, setFamilyId] = useState(searchParams.get('family') || '');
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const authFetch = useAuthFetch();
  const { isAuthenticated, user } = useAuth();
  const uid = user?.id;
  const limit = 20; // number of animals per page
  const { t } = useTranslation();

  // Persist filter selections in the URL so they survive navigation
  useEffect(() => {
    const params = {};
    if (classId) params.class = classId;
    if (orderId) params.order = orderId;
    if (familyId) params.family = familyId;
    setSearchParams(params);
  }, [classId, orderId, familyId, setSearchParams]);

  // Fetch list of classes on mount
  useEffect(() => {
    fetch(`${API}/animals/classes`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setClasses)
      .catch(() => setClasses([]));
  }, []);

  // Fetch orders whenever class changes
  useEffect(() => {
    if (!classId) {
      setOrders([]);
      setFamilies([]);
      return;
    }
    setOrders([]);
    fetch(`${API}/animals/orders?class_id=${classId}`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setOrders)
      .catch(() => setOrders([]));
  }, [classId]);

  // Fetch families whenever order changes
  useEffect(() => {
    if (!orderId) {
      setFamilies([]);
      return;
    }
    setFamilies([]);
    fetch(`${API}/animals/families?order_id=${orderId}`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setFamilies)
      .catch(() => setFamilies([]));
  }, [orderId]);

  // Debounce the search input to avoid fetching on every keystroke
  useEffect(() => {
    const id = setTimeout(() => {
      setQuery(search);
    }, 500);
    return () => clearTimeout(id);
  }, [search]);

  // Fetch a page of animals from the API
  const loadAnimals = (reset = false) => {
    const currentOffset = reset ? 0 : offset;
    if (reset) setHasMore(false); // hide button until the first page loads
    setLoading(true);
    setError('');
    const params = new URLSearchParams({
      limit,
      offset: currentOffset,
      q: query,
    });
    if (classId) params.append('class_id', classId);
    if (orderId) params.append('order_id', orderId);
    if (familyId) params.append('family_id', familyId);
    fetch(`${API}/animals?${params.toString()}`)
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load');
        return r.json();
      })
      .then((data) => {
        setAnimals((prev) => (reset ? data : [...prev, ...data]));
        setOffset(currentOffset + data.length);
        setHasMore(data.length === limit);
      })
      .catch(() => setError('Failed to load animals'))
      .finally(() => setLoading(false));
  };

  // Initial load and reset when search or filters change
  useEffect(() => {
    loadAnimals(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, classId, orderId, familyId]);

  // load animals seen by the current user
  useEffect(() => {
    if (!isAuthenticated || !uid) return;
    authFetch(`${API}/users/${uid}/animals`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setSeenAnimals)
      .catch(() => setSeenAnimals([]));
  }, [isAuthenticated, uid, authFetch]);

  const seenIds = useMemo(() => new Set(seenAnimals.map((a) => a.id)), [seenAnimals]);

  const localizedName = (item) =>
    lang === 'de' ? item.name_de || item.name_en : item.name_en || item.name_de;

  return (
    <div className="container">
      <Seo
        title="Animals"
        description="Browse animals and track the ones you've seen."
      />
      <div className="row mb-3">
        <div className="col-md-3 mb-2">
          <input
            className="form-control"
            placeholder={t('nav.search')}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setAnimals([]);
              setOffset(0);
              setHasMore(false);
            }}
          />
        </div>
        <div className="col-md-3 mb-2">
          <select
            className="form-select"
            value={classId}
            onChange={(e) => {
              setClassId(e.target.value);
              setOrderId('');
              setFamilyId('');
            }}
          >
            <option value="">{t('animal.allClasses')}</option>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {localizedName(c)}
              </option>
            ))}
          </select>
        </div>
        <div className="col-md-3 mb-2">
          <select
            className="form-select"
            value={orderId}
            onChange={(e) => {
              setOrderId(e.target.value);
              setFamilyId('');
            }}
            disabled={!classId}
          >
            <option value="">{t('animal.allOrders')}</option>
            {orders.map((o) => (
              <option key={o.id} value={o.id}>
                {localizedName(o)}
              </option>
            ))}
          </select>
        </div>
        <div className="col-md-3 mb-2">
          <select
            className="form-select"
            value={familyId}
            onChange={(e) => setFamilyId(e.target.value)}
            disabled={!orderId}
          >
            <option value="">{t('animal.allFamilies')}</option>
            {families.map((f) => (
              <option key={f.id} value={f.id}>
                {localizedName(f)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {error && (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      )}
      <div className="d-flex flex-wrap gap-2">
        {animals.map((a) => (
          <button
            key={a.id}
            type="button"
            className="animal-card"
            onClick={() => navigate(`${prefix}/animals/${a.id}`)}
          >
            {a.default_image_url && (
              <img
                src={a.default_image_url}
                alt={lang === 'de' ? a.name_de || a.name_en : a.name_en || a.name_de}
                className="card-img"
              />
            )}
            {/* Always show the localized name in bold */}
            <div className="fw-bold">
              {lang === 'de' ? a.name_de || a.name_en : a.name_en || a.name_de}
            </div>
            {a.scientific_name && (
              <div className="fst-italic small">{a.scientific_name}</div>
            )}
            {seenIds.has(a.id) && (
              <span className="seen-badge">{t('animal.seen')}</span>
            )}
          </button>
        ))}
      </div>
      {hasMore && (
        <div className="text-center my-3">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => loadAnimals(false)}
            disabled={loading}
          >
            {loading ? t('actions.loading') : t('actions.loadMore')}
          </button>
        </div>
      )}
    </div>
  );
}
