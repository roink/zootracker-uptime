import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { API } from '../api';

// Registration form for creating a new user account.

export default function RegisterPage({ onSignedUp }) {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');

  // Send the new user details to the backend and navigate home on success.
  const submit = async (e) => {
    e.preventDefault();
    if (password !== confirm) {
      alert('Passwords do not match');
      return;
    }
    const resp = await fetch(`${API}/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password })
    });
    if (resp.ok) {
      const user = await resp.json();
      onSignedUp(user, email);
      navigate('/');
    } else {
      alert('Sign up failed');
    }
  };

  return (
    <form onSubmit={submit} className="container" style={{ maxWidth: '400px' }}>
      <h2 className="mb-3">Sign Up</h2>
      <div className="mb-3">
        <input
          className="form-control"
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      <div className="mb-3">
        <input
          className="form-control"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
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
      <div className="mb-3">
        <input
          className="form-control"
          type="password"
          placeholder="Confirm Password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
      </div>
      <button className="btn btn-primary w-100" type="submit">Create Account</button>
      <div className="mt-3">
        <Link to="/login">Back to Log In</Link>
      </div>
    </form>
  );
}
