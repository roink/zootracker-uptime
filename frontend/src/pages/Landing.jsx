import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Seo from '../components/Seo';
import LazyMap from '../components/LazyMap';
import useSearchSuggestions from '../hooks/useSearchSuggestions';
import { API } from '../api';

// Suggestion dropdown showing grouped results for the hero search.
function LandingSuggestionList({
  id,
  labelledBy,
  options,
  activeIndex,
  onSelect,
  onActivate,
}) {
  return (
    <ul
      className="list-group position-absolute top-100 start-0 w-100 landing-suggestions shadow"
      role="listbox"
      id={id}
      aria-labelledby={labelledBy}
    >
      {options.map((option, index) => {
        const isActive = index === activeIndex;
        return (
          <li
            key={option.key}
            id={option.id}
            role="option"
            aria-selected={isActive ? 'true' : 'false'}
            className={`list-group-item landing-suggestion-item${
              isActive ? ' active' : ''
            }`}
            onPointerDown={(event) => event.preventDefault()}
            onMouseEnter={() => onActivate?.(index)}
            onMouseMove={() => onActivate?.(index)}
            onClick={() => onSelect(option)}
          >
            {option.showGroupLabel && (
              <div className="landing-suggestion-group text-uppercase small fw-semibold text-muted">
                {option.groupLabel}
              </div>
            )}
            <div className="landing-suggestion-text">
              <div className="landing-suggestion-name">{option.displayName}</div>
              {option.subtitle && (
                <div className="landing-suggestion-subtitle text-muted small">
                  {option.subtitle}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

// Marketing landing page that introduces ZooTracker and funnels visitors into the app.
export default function Landing() {
  const navigate = useNavigate();
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const { t, i18n } = useTranslation();

  const [query, setQuery] = useState('');
  const [focused, setFocused] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [recentSearches, setRecentSearches] = useState([]);
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [summaryError, setSummaryError] = useState(false);
  const [popular, setPopular] = useState([]);
  const [popularStatus, setPopularStatus] = useState('idle'); // idle | loading | loaded | error
  const [mapCoords, setMapCoords] = useState({ lat: 50.9394, lon: 6.9583 });

  const searchId = useId();
  const searchInputId = `landing-search-${searchId.replace(/:/g, '')}`;
  const searchLabelId = `${searchInputId}-label`;
  const suggestionListId = `${searchInputId}-listbox`;
  const searchInputRef = useRef(null);
  const blurTimeout = useRef(null);

  const numberFormatter = useMemo(() => {
    const locale = i18n.language || (lang === 'de' ? 'de-DE' : 'en-US');
    return new Intl.NumberFormat(locale);
  }, [i18n.language, lang]);

  const formatCount = useCallback(
    (value) => numberFormatter.format(value ?? 0),
    [numberFormatter]
  );

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const stored = window.localStorage.getItem('zt-landing-recents');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) setRecentSearches(parsed);
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.warn('Failed to read recent searches', error);
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(
        'zt-landing-recents',
        JSON.stringify(recentSearches)
      );
    } catch (error) {
      // eslint-disable-next-line no-console
      console.warn('Failed to persist recent searches', error);
    }
  }, [recentSearches]);

  useEffect(() => {
    const controller = new AbortController();
    setSummaryLoading(true);
    setSummaryError(false);
    fetch(`${API}/site/summary`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to load summary');
        }
        return response.json();
      })
      .then((data) => {
        setSummary(data);
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setSummary(null);
          setSummaryError(true);
        }
      })
      .finally(() => setSummaryLoading(false));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setPopularStatus('loading');
    fetch(`${API}/site/popular-animals?limit=8`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to load popular animals');
        }
        return response.json();
      })
      .then((data) => {
        setPopular(Array.isArray(data) ? data : []);
        setPopularStatus('loaded');
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setPopular([]);
          setPopularStatus('error');
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setMapCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude });
      },
      () => {},
      { enableHighAccuracy: false, timeout: 4000, maximumAge: 600000 }
    );
  }, []);

  const results = useSearchSuggestions(query, query.trim().length > 0);

  const getAnimalName = useCallback(
    (animal) =>
      lang === 'de'
        ? animal.name_de || animal.name_en
        : animal.name_en || animal.name_de,
    [lang]
  );

  const options = useMemo(() => {
    const list = [];
    if (results.animals.length) {
      const groupLabel = t('landing.search.groups.animals');
      results.animals.forEach((animal, index) => {
        const identifier = animal.id ?? animal.slug;
        const displayName = getAnimalName(animal);
        list.push({
          id: `${suggestionListId}-animal-${identifier}`,
          key: `animal-${identifier}`,
          type: 'animal',
          value: animal.slug || animal.id,
          displayName,
          subtitle: animal.scientific_name || '',
          groupLabel,
          showGroupLabel: index === 0,
          recordValue: displayName,
        });
      });
    }
    if (results.zoos.length) {
      const groupLabel = t('landing.search.groups.zoos');
      results.zoos.forEach((zoo, index) => {
        const identifier = zoo.id ?? zoo.slug;
        const displayName = zoo.city ? `${zoo.city}: ${zoo.name}` : zoo.name;
        list.push({
          id: `${suggestionListId}-zoo-${identifier}`,
          key: `zoo-${identifier}`,
          type: 'zoo',
          value: zoo.slug || zoo.id,
          displayName,
          subtitle: zoo.city || '',
          groupLabel,
          showGroupLabel: index === 0,
          recordValue: displayName,
        });
      });
    }
    return list;
  }, [results, suggestionListId, t, getAnimalName]);

  const suggestionsOpen =
    focused && query.trim().length > 0 && options.length > 0;

  const activeDescendant =
    suggestionsOpen && activeIndex >= 0 && activeIndex < options.length
      ? options[activeIndex].id
      : undefined;

  useEffect(() => {
    if (!suggestionsOpen) {
      setActiveIndex(-1);
    }
  }, [suggestionsOpen]);

  useEffect(() => {
    if (activeIndex >= options.length) {
      setActiveIndex(options.length - 1);
    }
  }, [activeIndex, options.length]);

  useEffect(() => {
    setActiveIndex(-1);
  }, [query]);

  useEffect(
    () => () => {
      if (blurTimeout.current) {
        clearTimeout(blurTimeout.current);
      }
    },
    []
  );

  const recordRecent = useCallback((term) => {
    const normalized = term.trim();
    if (!normalized) return;
    setRecentSearches((prev) => {
      const existing = prev.filter(
        (item) => item.toLowerCase() !== normalized.toLowerCase()
      );
      return [normalized, ...existing].slice(0, 5);
    });
  }, []);

  const handleOptionSelect = useCallback(
    (option) => {
      recordRecent(option.recordValue || '');
      setQuery('');
      setFocused(false);
      setActiveIndex(-1);
      if (option.type === 'zoo') {
        navigate(`${prefix}/zoos/${option.value}`);
      } else {
        navigate(`${prefix}/animals/${option.value}`);
      }
    },
    [navigate, prefix, recordRecent]
  );

  const handleSearchSubmit = useCallback(
    (event) => {
      event.preventDefault();
      const normalized = query.trim();
      if (!normalized) return;
      recordRecent(normalized);
      setQuery('');
      setFocused(false);
      setActiveIndex(-1);
      navigate(`${prefix}/search?q=${encodeURIComponent(normalized)}`);
    },
    [navigate, prefix, query, recordRecent]
  );

  const handleKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (!options.length) return;
      setActiveIndex((prev) => (prev + 1) % options.length);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      if (!options.length) return;
      setActiveIndex((prev) => (prev <= 0 ? options.length - 1 : prev - 1));
    } else if (event.key === 'Enter') {
      if (activeIndex >= 0 && activeIndex < options.length) {
        event.preventDefault();
        handleOptionSelect(options[activeIndex]);
      }
    } else if (event.key === 'Escape') {
      setActiveIndex(-1);
      setFocused(false);
    }
  };

  const handleRecentClick = (term) => {
    recordRecent(term);
    setQuery('');
    setFocused(false);
    setActiveIndex(-1);
    navigate(`${prefix}/search?q=${encodeURIComponent(term)}`);
  };

  const handleFocus = () => {
    if (blurTimeout.current) {
      clearTimeout(blurTimeout.current);
    }
    setFocused(true);
  };

  const handleBlur = () => {
    blurTimeout.current = setTimeout(() => {
      setFocused(false);
    }, 100);
  };

  const showEmptyState =
    focused && query.trim().length >= 3 && options.length === 0;

  const metrics = useMemo(
    () => [
      {
        key: 'species',
        label:
          summary && !summaryError
            ? t('landing.metrics.species', {
                count: formatCount(summary.species),
              })
            : null,
      },
      {
        key: 'zoos',
        label:
          summary && !summaryError
            ? t('landing.metrics.zoos', {
                count: formatCount(summary.zoos),
              })
            : null,
      },
      {
        key: 'countries',
        label:
          summary && !summaryError
            ? t('landing.metrics.countries', {
                count: formatCount(summary.countries),
              })
            : null,
      },
      {
        key: 'sightings',
        label:
          summary && !summaryError
            ? t('landing.metrics.sightings', {
                count: formatCount(summary.sightings),
              })
            : null,
      },
    ],
    [summary, summaryError, t, formatCount]
  );

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

  const exploreCards = [
    {
      key: 'map',
      icon: '🗺️',
      title: t('landing.ways.map.title'),
      description: t('landing.ways.map.description'),
      cta: t('landing.ways.map.cta'),
      to: `${prefix}/zoos`,
    },
    {
      key: 'species',
      icon: '🐾',
      title: t('landing.ways.species.title'),
      description: t('landing.ways.species.description'),
      cta: t('landing.ways.species.cta'),
      to: `${prefix}/animals`,
    },
    {
      key: 'zoos',
      icon: '🏛️',
      title: t('landing.ways.zoos.title'),
      description: t('landing.ways.zoos.description'),
      cta: t('landing.ways.zoos.cta'),
      to: `${prefix}/zoos`,
    },
    {
      key: 'highlights',
      icon: '✨',
      title: t('landing.ways.highlights.title'),
      description: t('landing.ways.highlights.description'),
      cta: t('landing.ways.highlights.cta'),
      to: `${prefix}/search?q=endangered`,
    },
  ];

  const howSteps = [
    {
      key: 'search',
      icon: '🔍',
      title: t('landing.howItWorks.steps.search.title'),
      description: t('landing.howItWorks.steps.search.description'),
    },
    {
      key: 'open',
      icon: '🧭',
      title: t('landing.howItWorks.steps.open.title'),
      description: t('landing.howItWorks.steps.open.description'),
    },
    {
      key: 'plan',
      icon: '📅',
      title: t('landing.howItWorks.steps.plan.title'),
      description: t('landing.howItWorks.steps.plan.description'),
    },
  ];

  return (
    <div className="landing-page">
      <Seo
        title={t('landing.seoTitle')}
        description={t('landing.seoDescription')}
      />

      <section className="landing-hero py-5">
        <div className="container">
          <div className="row align-items-center g-5">
            <div className="col-lg-6">
              <h1 className="display-5 fw-bold mb-3">
                {t('landing.hero.headline')}
              </h1>
              <p className="lead text-muted mb-4">
                {t('landing.hero.subline')}
              </p>
              <form
                className="landing-search position-relative"
                onSubmit={handleSearchSubmit}
                role="search"
                aria-labelledby={searchLabelId}
              >
                <label id={searchLabelId} className="form-label visually-hidden">
                  {t('landing.hero.searchLabel')}
                </label>
                <div className="input-group input-group-lg">
                  <span className="input-group-text" aria-hidden="true">
                    🔍
                  </span>
                  <input
                    ref={searchInputRef}
                    id={searchInputId}
                    className="form-control"
                    value={query}
                    placeholder={t('landing.hero.searchPlaceholder')}
                    onChange={(event) => setQuery(event.target.value)}
                    onKeyDown={handleKeyDown}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                    aria-autocomplete="list"
                    aria-controls={suggestionsOpen ? suggestionListId : undefined}
                    aria-expanded={suggestionsOpen ? 'true' : 'false'}
                    aria-activedescendant={activeDescendant}
                  />
                  <button className="btn btn-primary" type="submit">
                    {t('landing.hero.submit')}
                  </button>
                </div>
                {suggestionsOpen && (
                  <LandingSuggestionList
                    id={suggestionListId}
                    labelledBy={searchLabelId}
                    options={options}
                    activeIndex={activeIndex}
                    onSelect={handleOptionSelect}
                    onActivate={setActiveIndex}
                  />
                )}
                {showEmptyState && (
                  <p className="text-muted small mt-2 mb-0">
                    {t('landing.search.noResults')}
                  </p>
                )}
              </form>
              {recentSearches.length > 0 && (
                <div className="landing-recents mt-3">
                  <div className="small text-muted mb-2">
                    {t('landing.hero.recentTitle')}
                  </div>
                  <div className="d-flex flex-wrap gap-2">
                    {recentSearches.map((item) => (
                      <button
                        key={item}
                        type="button"
                        className="btn btn-sm btn-outline-primary"
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => handleRecentClick(item)}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div className="d-flex flex-wrap gap-3 mt-4">
                <Link className="btn btn-primary btn-lg" to={`${prefix}/zoos`}>
                  {t('landing.hero.primaryCta')}
                </Link>
                <Link
                  className="btn btn-outline-primary btn-lg"
                  to={`${prefix}/animals`}
                >
                  {t('landing.hero.secondaryCta')}
                </Link>
              </div>
            </div>
            <div className="col-lg-6">
              <div className="landing-map card shadow-sm">
                <div className="card-body p-0">
                  <div className="landing-map-preview" aria-hidden="true">
                    <LazyMap latitude={mapCoords.lat} longitude={mapCoords.lon} />
                  </div>
                  <span className="visually-hidden">{t('landing.map.alt')}</span>
                  <div className="p-4">
                    <h2 className="h5 mb-2">{t('landing.map.title')}</h2>
                    <p className="text-muted mb-0">{t('landing.map.subtitle')}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-ways py-5">
        <div className="container">
          <h2 className="h3 text-center mb-4">{t('landing.ways.title')}</h2>
          <div className="row g-4">
            {exploreCards.map((card) => (
              <div className="col-sm-6 col-lg-3" key={card.key}>
                <div className="card h-100 border-0 shadow-sm">
                  <div className="card-body">
                    <div className="landing-card-icon" aria-hidden="true">
                      {card.icon}
                    </div>
                    <h3 className="h5">{card.title}</h3>
                    <p className="text-muted">{card.description}</p>
                    <Link className="stretched-link" to={card.to}>
                      {card.cta}
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-metrics py-5 bg-light">
        <div className="container">
          <h2 className="h4 text-center mb-4">{t('landing.metrics.title')}</h2>
          {summaryLoading ? (
            <div className="d-flex justify-content-center" aria-live="polite">
              <div className="spinner-border text-primary" role="status" />
            </div>
          ) : summaryError ? (
            <p className="text-center text-muted mb-0">
              {t('landing.metrics.error')}
            </p>
          ) : (
            <div className="row row-cols-2 row-cols-md-4 g-3">
              {metrics.map((metric) => (
                <div className="col" key={metric.key}>
                  <div className="landing-metric-card text-center">
                    <div className="landing-metric-value">{metric.label}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="landing-about py-5">
        <div className="container">
          <div className="row g-4 align-items-center">
            <div className="col-lg-6">
              <h2 className="h3 mb-3">{t('landing.about.title')}</h2>
              <p className="text-muted mb-0">{t('landing.about.description')}</p>
            </div>
            <div className="col-lg-6">
              <div className="row g-3">
                <div className="col-sm-6">
                  <div className="landing-about-tile h-100">
                    <div className="landing-about-icon" aria-hidden="true">
                      🐾
                    </div>
                    <h3 className="h6">{t('landing.about.findSpecies.title')}</h3>
                    <p className="text-muted mb-0">
                      {t('landing.about.findSpecies.description')}
                    </p>
                  </div>
                </div>
                <div className="col-sm-6">
                  <div className="landing-about-tile h-100">
                    <div className="landing-about-icon" aria-hidden="true">
                      🏞️
                    </div>
                    <h3 className="h6">{t('landing.about.compareZoos.title')}</h3>
                    <p className="text-muted mb-0">
                      {t('landing.about.compareZoos.description')}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-popular py-5">
        <div className="container">
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h2 className="h4 mb-0">{t('landing.popular.title')}</h2>
            <Link className="btn btn-link" to={`${prefix}/animals`}>
              {t('landing.popular.viewAll')}
            </Link>
          </div>
          {popularStatus === 'loading' && (
            <div className="d-flex justify-content-center" aria-live="polite">
              <div className="spinner-border text-primary" role="status" />
            </div>
          )}
          {popularStatus === 'error' && (
            <p className="text-muted mb-0">{t('landing.popular.error')}</p>
          )}
          {popularStatus === 'loaded' && popular.length === 0 && (
            <p className="text-muted mb-0">{t('landing.popular.empty')}</p>
          )}
          {popularStatus === 'loaded' && popular.length > 0 && (
            <div className="landing-popular-scroll d-flex gap-3 overflow-auto pb-2">
              {popular.map((animal, index) => {
                const name = getAnimalName(animal);
                return (
                  <Link
                    key={animal.id}
                    className="landing-popular-card card text-decoration-none text-reset"
                    to={`${prefix}/animals/${animal.slug || animal.id}`}
                  >
                    {animal.default_image_url && (
                      <img
                        src={animal.default_image_url}
                        alt={name}
                        className="card-img-top landing-popular-image"
                        loading="lazy"
                      />
                    )}
                    <div className="card-body">
                      <span className="badge bg-primary-subtle text-primary-emphasis mb-2">
                        {popularTag(animal, index)}
                      </span>
                      <h3 className="h6 mb-1">{name}</h3>
                      {animal.scientific_name && (
                        <p className="fst-italic text-muted mb-2">
                          {animal.scientific_name}
                        </p>
                      )}
                      {typeof animal.zoo_count === 'number' && (
                        <p className="small text-muted mb-0">
                          {t('searchPage.foundInZoos', {
                            count: animal.zoo_count,
                          })}
                        </p>
                      )}
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </section>

      <section className="landing-how py-5 bg-light">
        <div className="container">
          <h2 className="h4 text-center mb-4">{t('landing.howItWorks.title')}</h2>
          <div className="row g-4 justify-content-center">
            {howSteps.map((step, index) => (
              <div className="col-md-4" key={step.key}>
                <div className="landing-how-card h-100 text-center">
                  <div className="landing-how-step" aria-hidden="true">
                    <span className="landing-how-number">{index + 1}</span>
                    <span className="landing-how-icon">{step.icon}</span>
                  </div>
                  <h3 className="h5 mt-3">{step.title}</h3>
                  <p className="text-muted mb-0">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-final-cta py-5">
        <div className="container text-center">
          <h2 className="h3 mb-3">{t('landing.finalCta.title')}</h2>
          <p className="text-muted mb-4">{t('landing.finalCta.subtitle')}</p>
          <div className="d-flex flex-wrap justify-content-center gap-3">
            <Link className="btn btn-primary btn-lg" to={`${prefix}/zoos`}>
              {t('landing.finalCta.primaryCta')}
            </Link>
            <Link className="btn btn-outline-primary btn-lg" to={`${prefix}/animals`}>
              {t('landing.finalCta.secondaryCta')}
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
