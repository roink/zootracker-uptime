import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';
import { useTranslation } from 'react-i18next';
import Seo from '../components/Seo';
import { useAuth } from '../auth/AuthContext.jsx';

// Browse all animals with hierarchical taxonomy filters and pagination
export default function AnimalsPage() {
  const { lang } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const prefix = `/${lang}`;
  const [animals, setAnimals] = useState([]);
  const [seenAnimals, setSeenAnimals] = useState([]);
  const initialQ = searchParams.get('q') || '';
  const [search, setSearch] = useState(initialQ);
  const [query, setQuery] = useState(initialQ);
  const [classes, setClasses] = useState([]);
  const [orders, setOrders] = useState([]);
  const [families, setFamilies] = useState([]);
  const [classId, setClassId] = useState(searchParams.get('class') || '');
  const [orderId, setOrderId] = useState(searchParams.get('order') || '');
  const [familyId, setFamilyId] = useState(searchParams.get('family') || '');
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  // Track pagination state without triggering renders on every increment
  const offsetRef = useRef(0);
  const sentinelRef = useRef(null);
  const requestIdRef = useRef(0);
  const loadingRef = useRef(false);
  const controllerRef = useRef(null);
  const authFetch = useAuthFetch();
  const { isAuthenticated, user } = useAuth();
  const uid = user?.id;
  const limit = 20; // number of animals per page
  const [statusMessage, setStatusMessage] = useState('');
  const [prefersManualLoading, setPrefersManualLoading] = useState(false);
  const [supportsIntersectionObserver] = useState(
    () => typeof window !== 'undefined' && 'IntersectionObserver' in window
  );
  const autoLoadingEnabled = useMemo(
    () => supportsIntersectionObserver && !prefersManualLoading,
    [prefersManualLoading, supportsIntersectionObserver]
  );
  const { t } = useTranslation();

  // Hydrate local state from the URL whenever search params change
  useEffect(() => {
    const urlSearch = searchParams.get('q') || '';
    const urlClass = searchParams.get('class') || '';
    const urlOrder = searchParams.get('order') || '';
    const urlFamily = searchParams.get('family') || '';
    if (search !== urlSearch) {
      setSearch(urlSearch);
      setQuery(urlSearch);
    }
    if (classId !== urlClass) setClassId(urlClass);
    if (orderId !== urlOrder) setOrderId(urlOrder);
    if (familyId !== urlFamily) setFamilyId(urlFamily);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Persist search and filter selections in the URL
  useEffect(() => {
    const params = new URLSearchParams();
    if (query) params.set('q', query);
    if (classId) params.set('class', classId);
    if (orderId) params.set('order', orderId);
    if (familyId) params.set('family', familyId);
    const next = params.toString();
    if (next !== searchParams.toString()) {
      setSearchParams(params, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, classId, orderId, familyId]);

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

  // Fetch a page of animals from the API with deterministic pagination
  const loadAnimals = useCallback(
    (reset = false) => {
      if (loadingRef.current && !reset) {
        return controllerRef.current;
      }

      if (reset) {
        controllerRef.current?.abort();
      }

      const fetchId = requestIdRef.current + 1;
      requestIdRef.current = fetchId;
      const currentOffset = reset ? 0 : offsetRef.current;

      if (reset) {
        offsetRef.current = 0;
        setAnimals([]);
        setHasMore(false);
      }

      const controller = new AbortController();
      controllerRef.current = controller;

      loadingRef.current = true;
      setLoading(true);
      setError('');
      setStatusMessage(t('animal.loadingMore'));

      const params = new URLSearchParams({
        limit,
        offset: currentOffset,
        q: query,
      });
      if (classId) params.append('class_id', classId);
      if (orderId) params.append('order_id', orderId);
      if (familyId) params.append('family_id', familyId);

      const url = `${API}/animals?${params.toString()}`;

      (async () => {
        try {
          const response = await fetch(url, { signal: controller.signal });
          if (!response.ok) {
            throw new Error('Failed to load');
          }
          const data = await response.json();
          if (fetchId !== requestIdRef.current) {
            return;
          }
          setAnimals((prev) => (reset ? data : [...prev, ...data]));
          offsetRef.current = currentOffset + data.length;
          setHasMore(data.length === limit);
          if (data.length > 0) {
            const loadedText = t('animal.loadedMore', { count: data.length });
            if (data.length < limit) {
              setStatusMessage(
                `${loadedText} ${t('animal.noMoreAnimals')}`
              );
            } else {
              setStatusMessage(loadedText);
            }
          } else {
            setStatusMessage(t('animal.noMoreAnimals'));
          }
        } catch (err) {
          if (controller.signal.aborted || err.name === 'AbortError') {
            return;
          }
          if (fetchId === requestIdRef.current) {
            setError('Failed to load animals');
            setHasMore(false);
            setStatusMessage(t('animal.loadingError'));
          }
        } finally {
          if (fetchId === requestIdRef.current) {
            loadingRef.current = false;
            setLoading(false);
            if (controllerRef.current === controller) {
              controllerRef.current = null;
            }
          }
        }
      })();

      return controller;
    },
    [classId, familyId, limit, orderId, query, t]
  );

  // Initial load and reset when search or filters change
  useEffect(() => {
    const controller = loadAnimals(true);
    return () => {
      controller?.abort();
    };
  }, [loadAnimals]);

  useEffect(() => () => {
    controllerRef.current?.abort();
  }, []);

  // Observe when the user nears the end of the list and fetch the next page
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || !autoLoadingEnabled) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry.isIntersecting) {
          loadAnimals(false);
        }
      },
      { rootMargin: '200px' }
    );

    observer.observe(sentinel);

    return () => {
      observer.disconnect();
    };
  }, [autoLoadingEnabled, hasMore, loadAnimals]);

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
              offsetRef.current = 0;
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
      <div
        className="d-flex flex-wrap gap-2"
        aria-describedby="animals-status"
        aria-busy={loading}
      >
        {animals.map((a) => (
          <Link
            key={a.id}
            className="animal-card d-block text-decoration-none text-reset"
            to={`${prefix}/animals/${a.slug || a.id}`}
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
            {/* Display the number of zoos to explain the sort order */}
            <div className="small text-muted">
              {t('animal.keptInZoos', { count: a.zoo_count ?? 0 })}
            </div>
            {seenIds.has(a.id) && (
              <span className="seen-badge">{t('animal.seen')}</span>
            )}
          </Link>
        ))}
      </div>
      <div
        id="animals-status"
        role="status"
        aria-live="polite"
        className="visually-hidden"
      >
        {statusMessage}
      </div>
      <div
        ref={sentinelRef}
        className="infinite-scroll-sentinel"
        aria-hidden="true"
      />
      {hasMore && supportsIntersectionObserver && !prefersManualLoading && (
        <div className="text-center my-3">
          <button
            type="button"
            className="btn btn-link btn-sm"
            onClick={() => setPrefersManualLoading(true)}
          >
            {t('animal.useManualLoading')}
          </button>
        </div>
      )}
      {hasMore && (!supportsIntersectionObserver || prefersManualLoading) && (
        <div className="text-center my-3">
          <button
            type="button"
            className="btn btn-outline-primary"
            onClick={() => loadAnimals(false)}
            disabled={loading}
          >
            {loading ? t('actions.loading') : t('actions.loadMore')}
          </button>
        </div>
      )}
      {prefersManualLoading && supportsIntersectionObserver && (
        <div className="text-center mb-3">
          <button
            type="button"
            className="btn btn-link btn-sm"
            onClick={() => setPrefersManualLoading(false)}
            disabled={loading}
          >
            {t('animal.enableAutoLoading')}
          </button>
        </div>
      )}
      {loading && (
        <div className="text-center my-3">
          <div className="spinner-border" role="status" aria-hidden="true" />
          <span className="visually-hidden">{t('actions.loading')}</span>
        </div>
      )}
    </div>
  );
}
