import { Link } from 'react-router-dom';

// Horizontally scrollable list of popular animals.
export default function Popular({
  t,
  prefix,
  popular,
  isLoading,
  isError,
  getAnimalName,
}) {
  const popularTag = (animal, index) => {
    if (animal.iucn_conservation_status) {
      const status = animal.iucn_conservation_status.toLowerCase();
      if (status.includes('endangered') || status.includes('critically')) {
        return t('landing.popular.tags.endangered');
      }
    }
    if (index < 2) {
      return t('landing.popular.tags.mostSearched');
    }
    if (animal.zoo_count && animal.zoo_count >= 20) {
      return t('landing.popular.tags.widelyKept');
    }
    return t('landing.popular.tags.trending');
  };

  return (
    <section className="landing-popular py-5">
      <div className="container">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h2 className="h4 mb-0">{t('landing.popular.title')}</h2>
          <Link className="btn btn-link" to={`${prefix}/animals`}>
            {t('landing.popular.viewAll')}
          </Link>
        </div>
        {isLoading ? (
          <div className="d-flex justify-content-center" aria-live="polite">
            <div className="spinner-border text-primary" role="status" />
          </div>
        ) : isError ? (
          <p className="text-muted mb-0">{t('landing.popular.error')}</p>
        ) : !popular.length ? (
          <p className="text-muted mb-0">{t('landing.popular.empty')}</p>
        ) : (
          <div className="landing-popular-scroll d-flex gap-3 overflow-auto pb-2">
            {popular.map((animal, index) => {
              const name = getAnimalName(animal);
              return (
                <Link
                  key={animal.id}
                  className="landing-popular-card card text-decoration-none text-reset"
                  to={`${prefix}/animals/${animal.slug || animal.id}`}
                >
                  {animal.default_image_url ? (
                    <img
                      src={animal.default_image_url}
                      alt={name}
                      className="card-img-top landing-popular-image"
                      loading="lazy"
                    />
                  ) : null}
                  <div className="card-body">
                    <span className="badge bg-primary-subtle text-primary-emphasis mb-2">
                      {popularTag(animal, index)}
                    </span>
                    <h3 className="h6 mb-1">{name}</h3>
                    {animal.scientific_name ? (
                      <p className="fst-italic text-muted mb-2">
                        {animal.scientific_name}
                      </p>
                    ) : null}
                    {typeof animal.zoo_count === 'number' ? (
                      <p className="small text-muted mb-0">
                        {t('searchPage.foundInZoos', { count: animal.zoo_count })}
                      </p>
                    ) : null}
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
