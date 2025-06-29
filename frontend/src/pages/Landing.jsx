import React from 'react';
import { useNavigate } from 'react-router-dom';

export default function Landing() {
  const navigate = useNavigate();
  return (
    <div style={{ textAlign: 'center', padding: '20px' }}>
      <h1>Track your zoo adventures</h1>
      <div style={{ display: 'flex', justifyContent: 'center', gap: '10px', marginTop: '20px' }}>
        <img src="https://via.placeholder.com/150" alt="screenshot" />
        <img src="https://via.placeholder.com/150" alt="screenshot" />
        <img src="https://via.placeholder.com/150" alt="screenshot" />
      </div>
      <div style={{ display: 'flex', justifyContent: 'center', gap: '40px', marginTop: '20px' }}>
        <div>
          <div style={{ fontSize: '40px' }}>📍</div>
          <p>Track Visits</p>
        </div>
        <div>
          <div style={{ fontSize: '40px' }}>🎖️</div>
          <p>Earn Badges</p>
        </div>
        <div>
          <div style={{ fontSize: '40px' }}>🐾</div>
          <p>Discover Animals</p>
        </div>
      </div>
      <div style={{ marginTop: '30px' }}>
        <button onClick={() => navigate('/register')} style={{ marginRight: '10px' }}>
          Sign Up
        </button>
        <button onClick={() => navigate('/login')}>Log In</button>
      </div>
    </div>
  );
}
