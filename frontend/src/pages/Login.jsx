import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { API } from '../api';

// Login form that stores the returned token in localStorage.

export default function LoginPage({ email, onLoggedIn }) {
  const navigate = useNavigate();
  const [inputEmail, setInputEmail] = useState(email || '');
  const [password, setPassword] = useState('');

  // Submit credentials to the backend and store auth data.
  const submit = async (e) => {
    e.preventDefault();
    const body = new URLSearchParams();
    body.append('username', inputEmail);
    body.append('password', password);
    const resp = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    if (resp.ok) {
      const data = await resp.json();
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('userId', data.user_id);
      localStorage.setItem('userEmail', inputEmail);
      if (onLoggedIn) {
        onLoggedIn(data.access_token, data.user_id, inputEmail);
      }
      navigate('/');
    } else {
      alert('Login failed');
    }
  };

  return (
    <form onSubmit={submit} className="container auth-form">
      <h2 className="mb-3">Login</h2>
      <div className="mb-3">
        <input
          className="form-control"
          placeholder="Email"
          value={inputEmail}
          onChange={(e) => setInputEmail(e.target.value)}
        />
      </div>
      <div className="mb-3">
        <input
          className="form-control"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <button className="btn btn-primary w-100" type="submit">Login</button>
      <div className="mt-3">
        <Link to="#">Forgot Password?</Link>
      </div>
      <div className="mt-2">
        <Link to="/register">Sign Up</Link>
      </div>
    </form>
  );
}
