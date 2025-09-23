import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { API } from '../api';
import Seo from '../components/Seo';

// Global search results page

function useQuery() {
  return new URLSearchParams(useLocation().search);
}

export default function SearchPage() {
  const navigate = useNavigate();
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const query = useQuery().get('q') || '';
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

    setIsLoading(true);
    setHasError(false);
    fetch(`${API}/search?q=${encodeURIComponent(normalizedQuery)}&limit=50`)
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
      .catch(() => {
        setZoos([]);
        setAnimals([]);
        setHasError(true);
      })
      .finally(() => setIsLoading(false));
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
            <div className="card-body">
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
                <div className="list-group">
                  {zoos.map((z) => (
                    <button
                      key={z.slug || z.id}
                      type="button"
                      className="list-group-item list-group-item-action text-start w-100"
                      onClick={() => navigate(`${prefix}/zoos/${z.slug || z.id}`)}
                    >
                      <div className="fw-bold">
                        {z.city ? `${z.city}: ${z.name}` : z.name}
                      </div>
                      {z.city && (
                        <div className="text-muted small">{z.city}</div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="col-lg-7">
          <div className="card h-100">
            <div className="card-body">
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
                <div className="d-flex flex-wrap gap-2">
                  {animals.map((a) => (
                    <button
                      key={a.slug || a.id}
                      type="button"
                      className="animal-card"
                      onClick={() => navigate(`${prefix}/animals/${a.slug || a.id}`)}
                    >
                      {a.default_image_url && (
                        <img
                          src={a.default_image_url}
                          alt={localizedAnimalName(a)}
                          className="card-img"
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
                    </button>
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
