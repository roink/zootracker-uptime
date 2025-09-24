import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { API } from '../api';
import Seo from '../components/Seo';
import { getZooDisplayName } from '../utils/zooDisplayName.js';

export default function SearchPage() {
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const [searchParams] = useSearchParams();
  const query = searchParams.get('q') || '';
  const [zoos, setZoos] = useState([]);
  const [animals, setAnimals] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const { t } = useTranslation();

  // Trim whitespace so empty queries don't trigger fetches
  const normalizedQuery = useMemo(() => query.trim(), [query]);
  const hasQuery = normalizedQuery.length > 0;

  useEffect(() => {
    if (!hasQuery) {
      setZoos([]);
      setAnimals([]);
      setIsLoading(false);
      setHasError(false);
      return;
    }

    const controller = new AbortController();

    setIsLoading(true);
    setHasError(false);
    fetch(`${API}/search?q=${encodeURIComponent(normalizedQuery)}&limit=50`, {
      signal: controller.signal,
    })
      .then((r) => {
        if (!r.ok) {
          throw new Error('Failed to load search results');
        }
        return r.json();
      })
      .then((res) => {
        setZoos(res.zoos || []);
        setAnimals(res.animals || []);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setZoos([]);
          setAnimals([]);
          setHasError(true);
        }
      })
      .finally(() => setIsLoading(false));

    return () => controller.abort();
  }, [hasQuery, normalizedQuery]);

  // Helper to display the localized animal name consistently
  const localizedAnimalName = (item) =>
    lang === 'de' ? item.name_de || item.name_en : item.name_en || item.name_de;

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
    <div className="container py-4">
      <Seo
        title={t('searchPage.seoTitle')}
        description={t('searchPage.seoDescription')}
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
                <ul className="list-group list-group-horizontal flex-wrap gap-2 border-0">
                  {animals.map((a) => (
                    <li
                      key={a.slug || a.id}
                      className="list-group-item border-0 p-0"
                    >
                      <Link
                        to={`${prefix}/animals/${a.slug || a.id}`}
                        className="animal-card d-block text-decoration-none text-reset"
                      >
                        {a.default_image_url && (
                          <img
                            src={a.default_image_url}
                            alt={localizedAnimalName(a)}
                            className="card-img"
                            loading="lazy"
                          />
                        )}
                        <div className="fw-bold">{localizedAnimalName(a)}</div>
                        {a.scientific_name && (
                          <div className="fst-italic small">{a.scientific_name}</div>
                        )}
                        {typeof a.zoo_count === 'number' && a.zoo_count > 0 && (
                          <div className="small text-muted">
                            {t('searchPage.foundInZoos', { count: a.zoo_count })}
                          </div>
                        )}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
