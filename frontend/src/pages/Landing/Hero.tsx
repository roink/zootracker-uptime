// @ts-nocheck
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import LazyMap from '../../components/LazyMap';
import useSearchSuggestions from '../../hooks/useSearchSuggestions';
import { getZooDisplayName } from '../../utils/zooDisplayName';
import LandingSuggestionList from './SuggestionList';

// Hero section with search, CTAs and a live map preview.
export default function Hero({
  t,
  prefix,
  recentSearches,
  onRecordRecent,
  onNavigate,
  mapCoords,
  getAnimalName,
}) {
  const [query, setQuery] = useState('');
  const [focused, setFocused] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const searchId = useId();
  const searchInputId = `landing-search-${searchId.replace(/:/g, '')}`;
  const searchLabelId = `${searchInputId}-label`;
  const suggestionListId = `${searchInputId}-listbox`;
  const searchInputRef = useRef(null);
  const blurTimeout = useRef(null);
  const mapCardRef = useRef(null);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    const node = mapCardRef.current;
    if (!node) return undefined;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setMapReady(true);
          observer.disconnect();
        }
      },
      { rootMargin: '200px' }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(
    () => () => {
      if (blurTimeout.current) {
        clearTimeout(blurTimeout.current);
      }
    },
    []
  );

  const results = useSearchSuggestions(query, query.trim().length > 0);

  const options = useMemo(() => {
    const list = [];
    if (results.animals.length) {
      const groupLabel = t('nav.searchGroupAnimals');
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
          groupKey: 'animals',
          groupLabel,
          firstInGroup: index === 0,
          recordValue: displayName,
        });
      });
    }
    if (results.zoos.length) {
      const groupLabel = t('nav.searchGroupZoos');
      results.zoos.forEach((zoo, index) => {
        const identifier = zoo.id ?? zoo.slug;
        const displayName = getZooDisplayName(zoo);
        list.push({
          id: `${suggestionListId}-zoo-${identifier}`,
          key: `zoo-${identifier}`,
          type: 'zoo',
          value: zoo.slug || zoo.id,
          displayName,
          subtitle: zoo.city || '',
          groupKey: 'zoos',
          groupLabel,
          firstInGroup: index === 0,
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

  const closeSuggestions = useCallback(() => {
    setFocused(false);
    setActiveIndex(-1);
  }, []);

  const handleOptionSelect = useCallback(
    (option) => {
      onRecordRecent(option.recordValue || '');
      setQuery('');
      closeSuggestions();
      if (option.type === 'zoo') {
        onNavigate(`${prefix}/zoos/${option.value}`);
      } else {
        onNavigate(`${prefix}/animals/${option.value}`);
      }
    },
    [closeSuggestions, onNavigate, onRecordRecent, prefix]
  );

  const handleSearchSubmit = useCallback(
    (event) => {
      event.preventDefault();
      const normalized = query.trim();
      if (!normalized) return;
      onRecordRecent(normalized);
      setQuery('');
      closeSuggestions();
      onNavigate(`${prefix}/search?q=${encodeURIComponent(normalized)}`);
    },
    [closeSuggestions, onNavigate, onRecordRecent, prefix, query]
  );

  const handleKeyDown = useCallback(
    (event) => {
      if (event.key === 'ArrowDown') {
        if (!options.length) return;
        event.preventDefault();
        setActiveIndex((prev) => (prev + 1) % options.length);
      } else if (event.key === 'ArrowUp') {
        if (!options.length) return;
        event.preventDefault();
        setActiveIndex((prev) => (prev <= 0 ? options.length - 1 : prev - 1));
      } else if (event.key === 'Enter') {
        if (activeIndex >= 0 && activeIndex < options.length) {
          event.preventDefault();
          handleOptionSelect(options[activeIndex]);
        }
      } else if (event.key === 'Escape') {
        event.preventDefault();
        closeSuggestions();
        searchInputRef.current?.focus();
      } else if (event.key === 'Tab') {
        closeSuggestions();
      }
    },
    [activeIndex, closeSuggestions, handleOptionSelect, options]
  );

  const handleRecentClick = useCallback(
    (term) => {
      onRecordRecent(term);
      closeSuggestions();
      setQuery('');
      onNavigate(`${prefix}/search?q=${encodeURIComponent(term)}`);
    },
    [closeSuggestions, onNavigate, onRecordRecent, prefix]
  );

  const handleFocus = () => {
    if (blurTimeout.current) {
      clearTimeout(blurTimeout.current);
    }
    setFocused(true);
  };

  const handleBlur = () => {
    blurTimeout.current = setTimeout(() => {
      closeSuggestions();
    }, 100);
  };

  const showEmptyState =
    focused && query.trim().length >= 3 && options.length === 0;

  return (
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
                  role="combobox"
                  aria-autocomplete="list"
                  aria-expanded={suggestionsOpen}
                  aria-controls={suggestionsOpen ? suggestionListId : undefined}
                  aria-activedescendant={activeDescendant}
                  autoComplete="off"
                />
                <button className="btn btn-primary" type="submit">
                  {t('landing.hero.submit')}
                </button>
              </div>
              <span className="visually-hidden" role="status" aria-live="polite">
                {options.length
                  ? t('nav.searchSuggestionCount', { count: options.length })
                  : t('nav.searchSuggestionEmpty')}
              </span>
              {suggestionsOpen ? (
                <LandingSuggestionList
                  id={suggestionListId}
                  labelledBy={searchLabelId}
                  options={options}
                  activeIndex={activeIndex}
                  onSelect={handleOptionSelect}
                  onActivate={(index) => setActiveIndex(index)}
                />
              ) : null}
            </form>
            {showEmptyState ? (
              <p className="text-muted small mt-2" aria-live="polite">
                {t('landing.search.noResults')}
              </p>
            ) : null}
            {recentSearches.length ? (
              <div className="landing-recents mt-4">
                <h2 className="h6 text-muted text-uppercase">
                  {t('landing.hero.recentTitle')}
                </h2>
                <div className="d-flex flex-wrap gap-2 mt-2">
                  {recentSearches.map((term) => (
                    <button
                      key={term}
                      type="button"
                      className="btn btn-outline-secondary btn-sm"
                      onClick={() => handleRecentClick(term)}
                    >
                      {term}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
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
            <div
              className="landing-map card border-0 shadow-sm landing-map-preview"
              ref={mapCardRef}
            >
              <div className="card-body">
                <h2 className="h5">{t('landing.map.title')}</h2>
                <p className="text-muted mb-3">{t('landing.map.subtitle')}</p>
                <div className="landing-map" aria-label={t('landing.map.alt')}>
                  {mapReady ? (
                    <LazyMap latitude={mapCoords.lat} longitude={mapCoords.lon} />
                  ) : (
                    <div className="map-container" aria-hidden="true" />
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
