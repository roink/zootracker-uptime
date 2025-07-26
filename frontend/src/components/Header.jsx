import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

// Navigation header shown on all pages. Includes a simple search
// form and links that depend on authentication state.

export default function Header({ token }) {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  // Navigate to the search page with the entered query.
  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/search?q=${encodeURIComponent(query.trim())}`);
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
          <form className="d-flex" onSubmit={handleSubmit}>
            <input
              className="form-control"
              type="search"
              placeholder="Search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </form>
        </div>
      </div>
    </nav>
  );
}
