// @ts-nocheck
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams, useSearchParams } from 'react-router-dom';

import { API } from '../api';
import { useAuth } from '../auth/AuthContext';
import AnimalTile from '../components/AnimalTile';
import Seo from '../components/Seo';
import useAuthFetch from '../hooks/useAuthFetch';
import { getZooDisplayName } from '../utils/zooDisplayName';

export default function SearchPage() {
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const [searchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  const [zoos, setZoos] = useState<any[]>([]);
  const [animals, setAnimals] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const { t } = useTranslation();
  const authFetch = useAuthFetch();
  const { isAuthenticated, user } = useAuth();
  const uid = user?.id;
  const [seenAnimals, setSeenAnimals] = useState<any[]>([]);

  // Trim whitespace so empty queries don't trigger fetches
  const normalizedQuery = useMemo(() => query.trim(), [query]);
  const hasQuery = normalizedQuery.length > 0;

  useEffect(() => {
    if (!hasQuery) {
      setZoos([]);
      setAnimals([]);
      setSeenAnimals([]);
      setIsLoading(false);
      setHasError(false);
      return;
    }

    const controller = new AbortController();
    const limit = 50;
    const zooParams = new URLSearchParams({
      q: normalizedQuery,
      limit: String(limit),
    });
    const animalParams = new URLSearchParams({
      q: normalizedQuery,
      limit: String(limit),
    });

    setIsLoading(true);
    setHasError(false);

    const loadResults = async () => {
      try {
        const [zoosResponse, animalsResponse] = await Promise.all([
          authFetch(`${API}/zoos?${zooParams.toString()}`, {
            signal: controller.signal,
          }),
          authFetch(`${API}/animals?${animalParams.toString()}`, {
            signal: controller.signal,
          }),
        ]);

        if (!zoosResponse.ok) {
          throw new Error('Failed to load zoos');
        }
        if (!animalsResponse.ok) {
          throw new Error('Failed to load animals');
        }

        const [zoosData, animalsData] = await Promise.all([
          zoosResponse.json(),
          animalsResponse.json(),
        ]);

        setZoos(Array.isArray(zoosData?.items) ? zoosData.items : []);
        setAnimals(Array.isArray(animalsData) ? animalsData : []);
      } catch (err) {
        if (err.name === 'AbortError') {
          return;
        }
        setZoos([]);
        setAnimals([]);
        setHasError(true);
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    };

      void loadResults();

    return () => { controller.abort(); };
  }, [authFetch, hasQuery, normalizedQuery]);

  useEffect(() => {
    if (!isAuthenticated || !uid) {
      setSeenAnimals([]);
      return;
    }

    let cancelled = false;

      void authFetch(`${API}/users/${uid}/animals`)
        .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        if (!cancelled) {
          setSeenAnimals(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSeenAnimals([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [authFetch, isAuthenticated, uid]);

  const seenIds = useMemo(
    () => new Set(seenAnimals.map((animal) => animal.id)),
    [seenAnimals]
  );

  // Shared loading indicator used for both result sections
  const loadingIndicator = (
    <div
      className="d-flex align-items-center gap-2 text-muted"
      aria-live="polite"
    >
      <div
        className="spinner-border spinner-border-sm text-primary"
        role="status"
        aria-hidden="true"
      />
      <span>{t('actions.loading')}</span>
    </div>
  );

  return (
    <div className="container py-4 search-results-page">
      <Seo
        title={t('searchPage.seoTitle')}
        description={t('searchPage.seoDescription')}
        robots="noindex, follow"
      />
      <div className="mb-4">
        <h2 className="mb-2">
          {hasQuery
            ? t('searchPage.resultsFor', { query: normalizedQuery })
            : t('searchPage.title')}
        </h2>
        {!hasQuery && (
          <p className="text-muted mb-0">{t('searchPage.enterQuery')}</p>
        )}
      </div>

      {hasError && (
        <div className="alert alert-danger" role="alert">
          {t('searchPage.error')}
        </div>
      )}

      <div className="row g-4">
        <div className="col-lg-5">
          <div className="card h-100">
            <div
              className="card-body"
              aria-busy={hasQuery && isLoading ? 'true' : 'false'}
            >
              <h3 className="h5 mb-3">{t('searchPage.zoosHeading')}</h3>
              {!hasQuery && (
                <p className="text-muted mb-0">
                  {t('searchPage.enterQuery')}
                </p>
              )}
              {hasQuery && isLoading && loadingIndicator}
              {hasQuery && !isLoading && hasError && (
                <p className="text-muted mb-0">{t('searchPage.error')}</p>
              )}
              {hasQuery && !isLoading && !hasError && zoos.length === 0 && (
                <p className="text-muted mb-0">{t('searchPage.noZoos')}</p>
              )}
              {hasQuery && !isLoading && !hasError && zoos.length > 0 && (
                <ul className="list-group">
                  {zoos.map((z) => {
                    const displayName = getZooDisplayName(z);
                    return (
                    <li
                      key={z.slug || z.id}
                      className="list-group-item p-0 border-0"
                    >
                      <Link
                        to={`${prefix}/zoos/${z.slug || z.id}`}
                        className="list-group-item list-group-item-action text-start w-100 border-0"
                      >
                        <div className="fw-bold">
                          {displayName}
                        </div>
                        {z.city && (
                          <div className="text-muted small">{z.city}</div>
                        )}
                      </Link>
                    </li>
                  );
                  })}
                </ul>
              )}
            </div>
          </div>
        </div>
        <div className="col-lg-7">
          <div className="card h-100">
            <div
              className="card-body"
              aria-busy={hasQuery && isLoading ? 'true' : 'false'}
            >
              <h3 className="h5 mb-3">{t('searchPage.animalsHeading')}</h3>
              {!hasQuery && (
                <p className="text-muted mb-0">
                  {t('searchPage.enterQuery')}
                </p>
              )}
              {hasQuery && isLoading && loadingIndicator}
              {hasQuery && !isLoading && hasError && (
                <p className="text-muted mb-0">{t('searchPage.error')}</p>
              )}
              {hasQuery && !isLoading && !hasError && animals.length === 0 && (
                <p className="text-muted mb-0">{t('searchPage.noAnimals')}</p>
              )}
              {hasQuery && !isLoading && !hasError && animals.length > 0 && (
                <div className="animals-grid">
                  {animals.map((a) => (
                    <AnimalTile
                      key={a.slug || a.id}
                      to={`${prefix}/animals/${a.slug || a.id}`}
                      animal={a}
                      lang={lang}
                      seen={seenIds.has(a.id)}
                    >
                      {typeof a.zoo_count === 'number' && a.zoo_count > 0 && (
                        <div className="small text-muted">
                          {t('searchPage.foundInZoos', { count: a.zoo_count })}
                        </div>
                      )}
                    </AnimalTile>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
