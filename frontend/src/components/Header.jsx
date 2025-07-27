import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { API } from '../api';
import searchCache from '../searchCache';
import SearchSuggestions from './SearchSuggestions';

// Navigation header shown on all pages. Includes a simple search
// form and links that depend on authentication state.

export default function Header({ token }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState({ zoos: [], animals: [] });
  const [focused, setFocused] = useState(false);
  const navigate = useNavigate();
  const fetchRef = useRef(null);

  // Fetch suggestions after the user stops typing and use the shared cache
  useEffect(() => {
    if (!query.trim()) {
      setResults({ zoos: [], animals: [] });
      if (fetchRef.current) fetchRef.current.abort();
      return;
    }
    const q = query.trim().toLowerCase();
    const cached = searchCache[q];
    if (cached) {
      setResults(cached);
      return;
    }
    const controller = new AbortController();
    fetchRef.current = controller;
    const timeout = setTimeout(() => {
      fetch(`${API}/search?q=${encodeURIComponent(q)}&limit=5`, {
        signal: controller.signal,
      })
        .then((r) => r.json())
        .then((res) => {
          searchCache[q] = res;
          if (!controller.signal.aborted) setResults(res);
        })
        .catch(() => {
          if (!controller.signal.aborted)
            setResults({ zoos: [], animals: [] });
        });
    }, 500);
    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, [query]);

  // Navigate to the search page with the entered query.
  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  };

  const handleSelect = (type, id) => {
    setQuery('');
    setResults({ zoos: [], animals: [] });
    setFocused(false);
    if (type === 'zoo') {
      navigate(`/zoos/${id}`);
    } else {
      navigate(`/animals/${id}`);
    }
  };

  return (
    <nav className="navbar navbar-expand-lg navbar-dark bg-success mb-3">
      <div className="container-fluid">
        <Link className="navbar-brand" to="/">ZooTracker</Link>
        <button
          className="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#navbarContent"
        >
          <span className="navbar-toggler-icon"></span>
        </button>
        <div className="collapse navbar-collapse" id="navbarContent">
          <ul className="navbar-nav me-auto mb-2 mb-lg-0">
            <li className="nav-item">
              <Link className="nav-link" to="/zoos">Zoos</Link>
            </li>
            <li className="nav-item">
              <Link className="nav-link" to="/animals">Animals</Link>
            </li>
            {token ? (
              <li className="nav-item">
                <Link className="nav-link" to="/home">Dashboard</Link>
              </li>
            ) : (
              <>
                <li className="nav-item">
                  <Link className="nav-link" to="/login">Log In</Link>
                </li>
                <li className="nav-item">
                  <Link className="nav-link" to="/register">Sign Up</Link>
                </li>
              </>
            )}
          </ul>
          <form className="d-flex position-relative" onSubmit={handleSubmit}>
            <input
              className="form-control"
              type="search"
              placeholder="Search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setFocused(true)}
              onBlur={() => setTimeout(() => setFocused(false), 100)}
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
