import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { API } from '../api';

export default function LoginPage({ email, onLoggedIn }) {
  const navigate = useNavigate();
  const [inputEmail, setInputEmail] = useState(email || '');
  const [password, setPassword] = useState('');

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
    <form onSubmit={submit} style={{ padding: '20px' }}>
      <h2>Login</h2>
      <input
        placeholder="Email"
        value={inputEmail}
        onChange={(e) => setInputEmail(e.target.value)}
      />
      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <button type="submit">Login</button>
      <div style={{ marginTop: '10px' }}>
        <Link to="#">Forgot Password?</Link>
      </div>
      <div style={{ marginTop: '5px' }}>
        <Link to="/register">Sign Up</Link>
      </div>
    </form>
  );
}
