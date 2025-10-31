// @ts-nocheck
import { useState, useEffect, useRef, useId, useMemo, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useLocation, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import SearchSuggestions from './SearchSuggestions';
import useSearchSuggestions from '../hooks/useSearchSuggestions';
import LanguageSwitcher from './LanguageSwitcher';
import { useAuth } from '../auth/AuthContext';
import { API } from '../api';
import { getZooDisplayName } from '../utils/zooDisplayName';

// Navigation header shown on all pages. Includes a simple search
// form and links that depend on authentication state.

export default function Header() {
  const [query, setQuery] = useState('');
  const [focused, setFocused] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [liveMessage, setLiveMessage] = useState('');
  // keep a ref for the blur timeout so we can cancel it if focus returns quickly
  const blurRef = useRef<any>(null);
  const liveRegionTimeout = useRef<any>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const { t } = useTranslation();
  const collapseRef = useRef<any>(null);
  const toggleRef = useRef<any>(null);
  const { isAuthenticated, logout } = useAuth();
  const queryClient = useQueryClient();
  const searchId = useId();
  const searchInputId = `header-search-${searchId.replace(/:/g, '')}`;
  const searchLabelId = `${searchInputId}-label`;
  const suggestionListId = `${searchInputId}-listbox`;

  // Close the mobile menu when the route changes
  useEffect(() => {
    const menu = collapseRef.current;
    if (menu && menu.classList.contains('show')) {
      const inst = (window as any).bootstrap?.Collapse.getInstance(menu);
      if (inst) inst.hide();
      else menu.classList.remove('show');
      setMenuOpen(false);
    }
  }, [location]);

  // Hide menu when clicking outside of it
  useEffect(() => {
    const handle = (e) => {
      const menu = collapseRef.current;
      if (
        menu &&
        menu.classList.contains('show') &&
        !menu.contains(e.target) &&
        !toggleRef.current.contains(e.target)
      ) {
        const inst = (window as any).bootstrap?.Collapse.getInstance(menu);
        if (inst) inst.hide();
        else menu.classList.remove('show');
        setMenuOpen(false);
      }
    };
    document.addEventListener('click', handle);
    return () => document.removeEventListener('click', handle);
  }, []);

  // Track collapse state to keep ARIA attributes in sync
  useEffect(() => {
    const menu = collapseRef.current;
    if (!menu) return undefined;
    const handleShown = () => setMenuOpen(true);
    const handleHidden = () => setMenuOpen(false);
    menu.addEventListener('shown.bs.collapse', handleShown);
    menu.addEventListener('hidden.bs.collapse', handleHidden);
    return () => {
      menu.removeEventListener('shown.bs.collapse', handleShown);
      menu.removeEventListener('hidden.bs.collapse', handleHidden);
    };
  }, []);

  // Fetch suggestions with a small delay and shared cache
  const results = useSearchSuggestions(query, true);

  // Navigate to the search page with the entered query.
  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`${prefix}/search?q=${encodeURIComponent(query.trim())}`);
    }
  };

  const handleSelect = useCallback((option) => {
    setQuery('');
    setFocused(false);
    setActiveIndex(-1);
    if (option.type === 'zoo') {
      navigate(`${prefix}/zoos/${option.value}`);
    } else {
      navigate(`${prefix}/animals/${option.value}`);
    }
  }, [navigate, prefix]);

  // Clear auth info and return to the home page when logging out
  const handleLogout = () => {
    logout({ reason: 'manual' })
      .catch(() => {})
      .finally(() => {
        navigate(prefix, { replace: true });
      });
  };

  const suggestionsOpen =
    focused &&
    query &&
    (results.zoos.length || results.animals.length);

  const getAnimalName = useCallback(
    (animal) =>
      lang === 'de'
        ? animal.name_de || animal.name_en
        : animal.name_en || animal.name_de,
    [lang]
  );

  const options = useMemo(() => {
    const list = [] as any[];
    if (results.animals.length) {
      const groupLabel = t('nav.searchGroupAnimals');
      results.animals.forEach((animal, index) => {
        const identifier = animal.id ?? animal.slug;
        list.push({
          id: `${suggestionListId}-a-${identifier}`,
          key: `a-${identifier}`,
          type: 'animal',
          value: animal.slug || animal.id,
          label: t('nav.searchAnimalOption', { name: getAnimalName(animal) }),
          secondary: animal.scientific_name || '',
          groupKey: 'animals',
          groupLabel,
          firstInGroup: index === 0,
        });
      });
    }
    if (results.zoos.length) {
      const groupLabel = t('nav.searchGroupZoos');
      results.zoos.forEach((zoo, index) => {
        const identifier = zoo.id ?? zoo.slug;
        const displayName = getZooDisplayName(zoo);
        list.push({
          id: `${suggestionListId}-z-${identifier}`,
          key: `z-${identifier}`,
          type: 'zoo',
          value: zoo.slug || zoo.id,
          label: zoo.city
            ? t('nav.searchZooOptionWithCity', {
                name: zoo.name,
                city: zoo.city,
              })
            : t('nav.searchZooOption', { name: zoo.name }),
          secondary: zoo.city || '',
          groupKey: 'zoos',
          groupLabel,
          firstInGroup: index === 0,
          displayName,
        });
      });
    }
    return list;
  }, [results, suggestionListId, t, getAnimalName]);

  const activeOptionId =
    activeIndex >= 0 && activeIndex < options.length
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

  useEffect(() => {
    if (liveRegionTimeout.current) {
      clearTimeout(liveRegionTimeout.current);
    }
    if (!query) {
      setLiveMessage('');
      return;
    }
    liveRegionTimeout.current = setTimeout(() => {
      if (!query) return;
      setLiveMessage(
        options.length
          ? t('nav.searchSuggestionCount', { count: options.length })
          : t('nav.searchSuggestionEmpty')
      );
    }, 150);
    return () => {
      if (liveRegionTimeout.current) {
        clearTimeout(liveRegionTimeout.current);
      }
    };
  }, [options.length, query, t]);

  useEffect(() => () => {
    if (liveRegionTimeout.current) {
      clearTimeout(liveRegionTimeout.current);
    }
  }, []);

  const moveActive = useCallback(
    (delta) => {
      if (!options.length) return;
      setActiveIndex((prev) => {
        if (prev < 0) {
          return delta > 0 ? 0 : options.length - 1;
        }
        const next = prev + delta;
        if (next < 0) {
          return options.length - 1;
        }
        if (next >= options.length) {
          return 0;
        }
        return next;
      });
    },
    [options.length]
  );

  const handleKeyDown = useCallback(
    (event) => {
      if (event.key === 'ArrowDown') {
        if (!options.length) return;
        event.preventDefault();
        setFocused(true);
        moveActive(1);
      } else if (event.key === 'ArrowUp') {
        if (!options.length) return;
        event.preventDefault();
        setFocused(true);
        moveActive(-1);
      } else if (event.key === 'Enter') {
        if (!suggestionsOpen) return;
        if (activeIndex < 0 || activeIndex >= options.length) return;
        event.preventDefault();
        const option = options[activeIndex];
        handleSelect(option);
      } else if (event.key === 'Escape') {
        if (!suggestionsOpen) return;
        event.preventDefault();
        setFocused(false);
        setActiveIndex(-1);
      } else if (event.key === 'Tab') {
        setActiveIndex(-1);
        setFocused(false);
      }
    },
    [activeIndex, handleSelect, moveActive, options, suggestionsOpen]
  );

  const prefetchLandingData = useCallback(() => {
    queryClient.prefetchQuery({
      queryKey: ['site', 'summary'],
      queryFn: async () => {
        const response = await fetch(`${API}/site/summary`);
        if (!response.ok) {
          throw new Error('Failed to load site summary');
        }
        return response.json();
      },
      staleTime: 5 * 60 * 1000,
    });
    queryClient.prefetchQuery({
      queryKey: ['site', 'popular-animals', 8],
      queryFn: async () => {
        const response = await fetch(`${API}/site/popular-animals?limit=8`);
        if (!response.ok) {
          throw new Error('Failed to load popular animals');
        }
        return response.json();
      },
      staleTime: 3 * 60 * 1000,
    });
  }, [queryClient]);

  return (
    <nav className="navbar navbar-expand-lg navbar-dark bg-success mb-3">
      <div className="container-fluid">
        <Link
          className="navbar-brand"
          to={prefix}
          onMouseEnter={prefetchLandingData}
          onFocus={prefetchLandingData}
        >
          ZooTracker
        </Link>
        <button
          className="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#navbarContent"
          ref={toggleRef}
          aria-label={t('nav.toggleMenu')}
          aria-controls="navbarContent"
          aria-expanded={menuOpen}
        >
          <span className="navbar-toggler-icon"></span>
        </button>
        <div className="collapse navbar-collapse" id="navbarContent" ref={collapseRef}>
          <ul className="navbar-nav me-auto mb-2 mb-lg-0">
            <li className="nav-item">
              <Link
                className="nav-link"
                to={{ pathname: `${prefix}/zoos`, search: '?view=list' }}
                state={{ mapView: null }}
              >
                {t('nav.zoos')}
              </Link>
            </li>
            <li className="nav-item">
              <Link className="nav-link" to={`${prefix}/animals`}>
                {t('nav.animals')}
              </Link>
            </li>
            {isAuthenticated ? (
              <>
                <li className="nav-item">
                  <Link className="nav-link" to={`${prefix}/home`}>
                    {t('nav.dashboard')}
                  </Link>
                </li>
                <li className="nav-item">
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="btn btn-link nav-link"
                  >
                    {t('nav.logout')}
                  </button>
                </li>
              </>
            ) : (
              <>
                <li className="nav-item">
                  <Link className="nav-link" to={`${prefix}/login`}>
                    {t('nav.login')}
                  </Link>
                </li>
              </>
            )}
            <li className="nav-item">
              <LanguageSwitcher />
            </li>
          </ul>
          <form className="d-flex position-relative" onSubmit={handleSubmit}>
            <label
              htmlFor={searchInputId}
              className="visually-hidden"
              id={searchLabelId}
            >
              {t('nav.searchLabel')}
            </label>
            <input
              className="form-control"
              type="search"
              placeholder={t('nav.searchPlaceholder')}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => {
                // cancel pending blur when focusing again
                if (blurRef.current) clearTimeout(blurRef.current);
                setFocused(true);
              }}
              onBlur={() => {
                // delay hiding suggestions to allow clicks on them
                blurRef.current = setTimeout(() => {
                  setFocused(false);
                  setActiveIndex(-1);
                }, 100);
              }}
              id={searchInputId}
              role="combobox"
              aria-autocomplete="list"
              aria-haspopup="listbox"
              aria-expanded={Boolean(suggestionsOpen)}
              aria-controls={suggestionsOpen ? suggestionListId : undefined}
              aria-activedescendant={suggestionsOpen ? activeOptionId : undefined}
              autoComplete="off"
              onKeyDown={handleKeyDown}
            />
            <span className="visually-hidden" aria-live="polite" role="status">
              {liveMessage}
            </span>
            {suggestionsOpen ? (
              <SearchSuggestions
                id={suggestionListId}
                labelledBy={searchLabelId}
                options={options}
                activeIndex={activeIndex}
                onSelect={handleSelect}
                onActivate={(index) => setActiveIndex(index)}
              />
            ) : null}
          </form>
        </div>
      </div>
    </nav>
  );
}
