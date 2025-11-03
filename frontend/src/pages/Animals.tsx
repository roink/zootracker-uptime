import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';

import { API } from '../api';
import { useAuth } from '../auth/AuthContext';
import AnimalFilters from '../components/AnimalFilters';
import AnimalTile from '../components/AnimalTile';
import Seo from '../components/Seo';
import { useAnimalFilters } from '../hooks/useAnimalFilters';
import useAuthFetch from '../hooks/useAuthFetch';
import { useInfiniteScroll } from '../hooks/useInfiniteScroll';

interface AnimalListItem {
  id: string;
  slug: string;
  name_en: string;
  name_de?: string | null;
  scientific_name?: string | null;
  default_image_url?: string | null;
  zoo_count: number;
  is_favorite: boolean;
}

interface AnimalSearchPage {
  items: AnimalListItem[];
  total: number;
  limit: number;
  offset: number;
}

interface TaxonName {
  id: number;
  name_de?: string | null;
  name_en?: string | null;
}

// Browse all animals with hierarchical taxonomy filters and pagination
export default function AnimalsPage() {
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const { t } = useTranslation();
  const authFetch = useAuthFetch();
  const { isAuthenticated, user } = useAuth();
  const filters = useAnimalFilters();

  const [animals, setAnimals] = useState<AnimalListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [authMessage, setAuthMessage] = useState('');
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [seenAnimals, setSeenAnimals] = useState<string[]>([]);
  const [classes, setClasses] = useState<TaxonName[]>([]);
  const [orders, setOrders] = useState<TaxonName[]>([]);
  const [families, setFamilies] = useState<TaxonName[]>([]);

  const limit = 50;
  const tileLang = lang === 'de' ? 'de' : 'en';

  // Reset authentication-required filters when not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      if (filters.favoritesOnly) {
        filters.setFavoritesOnly(false);
      }
      if (filters.seenOnly) {
        filters.setSeenOnly(false);
      }
    } else {
      // Clear auth message when user logs in
      setAuthMessage('');
    }
  }, [isAuthenticated, filters]);

  // Clear auth message when filters change
  useEffect(() => {
    setAuthMessage('');
  }, [
    filters.query,
    filters.selectedClass,
    filters.selectedOrder,
    filters.selectedFamily,
  ]);

  // Load taxonomy options
  useEffect(() => {
    void fetch(`${API}/animals/classes`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data: TaxonName[]) => { setClasses(data); return undefined; })
      .catch(() => { setClasses([]); });
  }, []);

  useEffect(() => {
    if (!filters.selectedClass) {
      setOrders([]);
      return;
    }
    void fetch(`${API}/animals/orders?class_id=${filters.selectedClass}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data: TaxonName[]) => { setOrders(data); return undefined; })
      .catch(() => { setOrders([]); });
  }, [filters.selectedClass]);

  useEffect(() => {
    if (!filters.selectedOrder) {
      setFamilies([]);
      return;
    }
    void fetch(`${API}/animals/families?order_id=${filters.selectedOrder}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data: TaxonName[]) => { setFamilies(data); return undefined; })
      .catch(() => { setFamilies([]); });
  }, [filters.selectedOrder]);

  // Load seen animals for current user
  useEffect(() => {
    if (!isAuthenticated || !user?.id) {
      setSeenAnimals([]);
      return;
    }
    void authFetch(`${API}/users/${user.id}/animals`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data: { id: string }[]) => { setSeenAnimals(data.map((a) => a.id)); return undefined; })
      .catch(() => { setSeenAnimals([]); });
  }, [isAuthenticated, user?.id, authFetch]);

  // Fetch animals with pagination
  const fetchAnimals = useCallback(
    async ({ reset = false, signal }: { reset?: boolean; signal?: AbortSignal } = {}) => {
      setLoading(true);
      setError('');

      try {
        const currentOffset = reset ? 0 : offset;
        const params = new URLSearchParams();
        params.set('limit', String(limit));
        params.set('offset', String(currentOffset));
        if (filters.query) params.set('q', filters.query);
        if (filters.selectedClass !== null) params.set('class_id', String(filters.selectedClass));
        if (filters.selectedOrder !== null) params.set('order_id', String(filters.selectedOrder));
        if (filters.selectedFamily !== null) params.set('family_id', String(filters.selectedFamily));
        if (filters.seenOnly) params.set('seen_only', 'true');
        if (filters.favoritesOnly) params.set('favorites_only', 'true');

        const url = `${API}/animals?${params.toString()}`;
        const response = await authFetch(url, signal ? { signal } : {});

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const payload = (await response.json()) as AnimalSearchPage;
        const items = Array.isArray(payload.items) ? payload.items : [];
        const responseTotal = payload.total || 0;

        if (reset) {
          setAnimals(items);
          setOffset(items.length);
        } else {
          setAnimals((prev) => [...prev, ...items]);
          setOffset((prev) => prev + items.length);
        }

        setHasMore(currentOffset + items.length < responseTotal);
        setError('');
      } catch (_err) {
        if (signal?.aborted) {
          return;
        }
        if (reset) {
          setAnimals([]);
        }
        setError(t('zoo.animalsLoadError'));
        setHasMore(false);
      } finally {
        if (!signal?.aborted) {
          setLoading(false);
        }
      }
    },
    [
      authFetch,
      filters.favoritesOnly,
      filters.query,
      filters.selectedClass,
      filters.selectedFamily,
      filters.selectedOrder,
      filters.seenOnly,
      limit,
      offset,
      t,
    ],
  );

  // Load more handler for infinite scroll
  const loadMore = useCallback(() => {
    if (!loading && hasMore) {
      void fetchAnimals({ reset: false });
    }
  }, [loading, fetchAnimals, hasMore]);

  // Use infinite scroll hook
  const sentinelRef = useInfiniteScroll({
    hasMore,
    loading,
    onLoadMore: loadMore,
  });

  // Reset and load animals when filters change
  useEffect(() => {
    const controller = new AbortController();
    void fetchAnimals({ reset: true, signal: controller.signal });
    return () => {
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    filters.query,
    filters.selectedClass,
    filters.selectedOrder,
    filters.selectedFamily,
    filters.seenOnly,
    filters.favoritesOnly,
  ]);

  const seenIds = new Set(seenAnimals);

  return (
    <div className="container">
      <Seo
        title={t('nav.animals')}
        description="Browse animals and track the ones you've seen."
      />
      
      <h1>{t('nav.animals')}</h1>
      
      <div className="mt-3">
        <AnimalFilters
          searchInput={filters.searchInput}
          onSearchChange={filters.setSearchInput}
          selectedClass={filters.selectedClass}
          onClassChange={filters.handleClassChange}
          selectedOrder={filters.selectedOrder}
          onOrderChange={filters.handleOrderChange}
          selectedFamily={filters.selectedFamily}
          onFamilyChange={filters.handleFamilyChange}
          seenOnly={filters.seenOnly}
          onSeenChange={filters.setSeenOnly}
          favoritesOnly={filters.favoritesOnly}
          onFavoritesChange={filters.setFavoritesOnly}
          classes={classes}
          orders={orders}
          families={families}
          hasActiveFilters={filters.hasActiveFilters}
          onClearFilters={filters.clearAllFilters}
          isAuthenticated={isAuthenticated}
          lang={lang || 'en'}
          showSeenFilter
          searchLabelKey="zoo.animalSearchLabelGlobal"
          onAuthRequired={setAuthMessage}
        />
      </div>

      {authMessage && (
        <div className="alert alert-info mt-3" role="status">
          {authMessage}
        </div>
      )}

      {error && (
        <div className="alert alert-danger mt-3" role="alert">
          {error}
        </div>
      )}

      <div className="animals-grid mt-3" aria-busy={loading}>
        {animals.map((animal) => (
          <AnimalTile
            key={animal.id}
            to={`${prefix}/animals/${animal.slug || animal.id}`}
            animal={animal}
            lang={tileLang}
            seen={seenIds.has(animal.id)}
          />
        ))}
      </div>

      {/* Infinite scroll sentinel */}
      <div ref={sentinelRef} className="infinite-scroll-sentinel" aria-hidden="true" />

      {loading && (
        <div className="text-center my-3">
          <div className="spinner-border" role="status" aria-hidden="true" />
          <span className="visually-hidden">{t('actions.loading')}</span>
        </div>
      )}

      {!loading && animals.length === 0 && !error && (
        <div className="alert alert-info mt-3" role="status">
          {t('zoo.noAnimalsMatch')}
        </div>
      )}

      {!loading && !hasMore && animals.length > 0 && (
        <div className="text-center my-3 text-muted small">
          {t('zoo.noMoreResults')}
        </div>
      )}
    </div>
  );
}
