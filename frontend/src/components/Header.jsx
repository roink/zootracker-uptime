import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

export default function Header({ token }) {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  };

  const linkStyle = { color: 'white', textDecoration: 'none', marginRight: '15px' };

  return (
    <header
      style={{
        background: '#2e7d32',
        color: 'white',
        padding: '10px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <Link to="/" style={{ ...linkStyle, fontWeight: 'bold', fontSize: '20px' }}>
          ZooTracker
        </Link>
        <Link to="/zoos" style={linkStyle}>Zoos</Link>
        <Link to="/animals" style={linkStyle}>Animals</Link>
      </div>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        {token ? (
          <Link to="/home" style={linkStyle}>Dashboard</Link>
        ) : (
          <>
            <Link to="/login" style={linkStyle}>Log In</Link>
            <Link to="/register" style={linkStyle}>Sign Up</Link>
          </>
        )}
        <form onSubmit={handleSubmit} style={{ marginLeft: '10px' }}>
          <input
            type="text"
            placeholder="Search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ padding: '4px', borderRadius: '4px', border: '1px solid #ccc' }}
          />
        </form>
      </div>
    </header>
  );
}
