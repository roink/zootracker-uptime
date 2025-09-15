import { useState, useEffect, useRef } from 'react';
import { Link, useNavigate, useLocation, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import SearchSuggestions from './SearchSuggestions';
import useSearchSuggestions from '../hooks/useSearchSuggestions';
import LanguageSwitcher from './LanguageSwitcher';
import { useAuth } from '../auth/AuthContext.jsx';

// Navigation header shown on all pages. Includes a simple search
// form and links that depend on authentication state.

export default function Header() {
  const [query, setQuery] = useState('');
  const [focused, setFocused] = useState(false);
  // keep a ref for the blur timeout so we can cancel it if focus returns quickly
  const blurRef = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const { t } = useTranslation();
  const collapseRef = useRef(null);
  const toggleRef = useRef(null);
  const { isAuthenticated, logout } = useAuth();

  // Close the mobile menu when the route changes
  useEffect(() => {
    const menu = collapseRef.current;
    if (menu && menu.classList.contains('show')) {
      const inst = window.bootstrap?.Collapse.getInstance(menu);
      if (inst) inst.hide();
      else menu.classList.remove('show');
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
        const inst = window.bootstrap?.Collapse.getInstance(menu);
        if (inst) inst.hide();
        else menu.classList.remove('show');
      }
    };
    document.addEventListener('click', handle);
    return () => document.removeEventListener('click', handle);
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

  const handleSelect = (type, id) => {
    setQuery('');
    setFocused(false);
    if (type === 'zoo') {
      navigate(`${prefix}/zoos/${id}`);
    } else {
      navigate(`${prefix}/animals/${id}`);
    }
  };

  // Clear auth info and return to the home page when logging out
  const handleLogout = () => {
    logout({ reason: 'manual' })
      .catch(() => {})
      .finally(() => {
        navigate(prefix, { replace: true });
      });
  };

  return (
    <nav className="navbar navbar-expand-lg navbar-dark bg-success mb-3">
      <div className="container-fluid">
        <Link className="navbar-brand" to={prefix}>
          ZooTracker
        </Link>
        <button
          className="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#navbarContent"
          ref={toggleRef}
        >
          <span className="navbar-toggler-icon"></span>
        </button>
        <div className="collapse navbar-collapse" id="navbarContent" ref={collapseRef}>
          <ul className="navbar-nav me-auto mb-2 mb-lg-0">
            <li className="nav-item">
              <Link className="nav-link" to={`${prefix}/zoos`}>
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
            <input
              className="form-control"
              type="search"
              placeholder={t('nav.search')}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => {
                // cancel pending blur when focusing again
                if (blurRef.current) clearTimeout(blurRef.current);
                setFocused(true);
              }}
              onBlur={() => {
                // delay hiding suggestions to allow clicks on them
                blurRef.current = setTimeout(() => setFocused(false), 100);
              }}
            />
            {focused && query && (results.zoos.length || results.animals.length) ? (
              <SearchSuggestions results={results} onSelect={handleSelect} />
            ) : null}
          </form>
        </div>
      </div>
    </nav>
  );
}
