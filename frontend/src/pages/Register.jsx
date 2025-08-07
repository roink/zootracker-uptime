import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { API } from '../api';
import Seo from '../components/Seo';

// Registration form for creating a new user account.

export default function RegisterPage({ onSignedUp }) {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  // Store validation state for the password field
  const [pwError, setPwError] = useState('');

  // Send the new user details to the backend and navigate home on success.
  const submit = async (e) => {
    e.preventDefault();
    // Basic length check so short passwords show an inline error
    if (password.length < 8) {
      setPwError('Password must be at least 8 characters');
      return;
    }
    setPwError('');
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
      navigate('/login', {
        state: { message: 'Signed up successfully, please log in.' },
      });
    } else {
      alert('Sign up failed');
    }
  };

  return (
    <>
      <Seo
        title="Sign Up"
        description="Create your ZooTracker account to track zoo visits and animal sightings."
      />
      <form onSubmit={submit} className="container auth-form">
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
          className={`form-control${pwError ? ' is-invalid' : ''}`}
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <div className="form-text">Minimum 8 characters.</div>
        {pwError && <div className="invalid-feedback">{pwError}</div>}
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
    </>
  );
}
