import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { API } from '../api';

export default function RegisterPage({ onSignedUp }) {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');

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
    <form onSubmit={submit} style={{ padding: '20px' }}>
      <h2>Sign Up</h2>
      <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
      <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <input type="password" placeholder="Confirm Password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      <button type="submit">Create Account</button>
      <div style={{ marginTop: '10px' }}>
        <Link to="/login">Back to Log In</Link>
      </div>
    </form>
  );
}
