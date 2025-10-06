import { useState, useEffect } from 'react';
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import { API } from '../api';
import Seo from '../components/Seo';
import { useAuth } from '../auth/AuthContext.jsx';

// Combined authentication page with log in on top and sign up below.
export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const { login } = useAuth();
  // State for the login form
  const [inputEmail, setInputEmail] = useState('');
  const [password, setPassword] = useState('');
  // State for the sign up form
  const [name, setName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [pwError, setPwError] = useState('');
  // Show a success message after signing up
  const [successMessage, setSuccessMessage] = useState('');
  // Prevent double submits while network requests are pending
  const [loggingIn, setLoggingIn] = useState(false);
  const [signingUp, setSigningUp] = useState(false);

  // Extract a one-time message from navigation state then clear it
  useEffect(() => {
    if (location.state?.message) {
      setSuccessMessage(location.state.message);
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location, navigate]);

  // Scroll to the sign up section when the URL contains "#signup".
  useEffect(() => {
    if (location.hash === '#signup') {
      const el = document.getElementById('signup');
      el && el.scrollIntoView();
    }
  }, [location.hash]);

  // Submit credentials to the backend and store auth data. If the
  // request fails entirely (e.g. when the API URL is unreachable) an
  // error message is shown so the user knows something went wrong.
  const handleLogin = async (e) => {
    e.preventDefault();
    if (loggingIn) return;
    setLoggingIn(true);
    const cleanEmail = inputEmail.trim();
    const body = new URLSearchParams();
    body.append('username', cleanEmail);
    body.append('password', password);
    try {
      const resp = await fetch(`${API}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        credentials: 'include',
        body,
      });
      if (resp.ok) {
        const data = await resp.json();
        login({
          token: data.access_token,
          user: { id: data.user_id, email: cleanEmail },
          expiresIn: data.expires_in,
        });
        navigate(prefix, { replace: true });
      } else {
        alert('Login failed');
      }
    } catch (err) {
      alert('Network error: ' + err.message);
    } finally {
      setLoggingIn(false);
    }
  };

  // Handle new account creation and show a message prompting the user to log in.
  const handleSignup = async (e) => {
    e.preventDefault();
    if (signingUp) return;
    if (regPassword.length < 8) {
      setPwError('Password must be at least 8 characters');
      return;
    }
    setPwError('');
    if (regPassword !== confirm) {
      alert('Passwords do not match');
      return;
    }
    setSigningUp(true);
    const cleanEmail = regEmail.trim();
    try {
      const resp = await fetch(`${API}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email: cleanEmail, password: regPassword }),
      });
      if (resp.ok) {
        await resp.json();
        setInputEmail(cleanEmail);
        setSuccessMessage('Signed up successfully, please log in.');
        setName('');
        setRegEmail('');
        setRegPassword('');
        setConfirm('');
        window.scrollTo(0, 0);
      } else {
        alert('Sign up failed');
      }
    } catch (err) {
      alert('Network error: ' + err.message);
    } finally {
      setSigningUp(false);
    }
  };

  return (
    <>
      <Seo
        title="Log In / Sign Up"
        description="Access your ZooTracker account or create a new one to log visits and sightings."
      />
      {/* Log in section */}
      <form onSubmit={handleLogin} className="container auth-form">
        {successMessage && (
          <div className="alert alert-success" role="alert">
            {successMessage}
          </div>
        )}
        <h2 className="mb-3">Login</h2>
        <div className="mb-3">
          <input
            type="email"
            className="form-control"
            placeholder="Email"
            required
            autoComplete="email"
            value={inputEmail}
            onChange={(e) => setInputEmail(e.target.value)}
          />
        </div>
        <div className="mb-3">
          <input
            type="password"
            className="form-control"
            placeholder="Password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button className="btn btn-primary w-100" type="submit" disabled={loggingIn}>
          {loggingIn ? 'Logging in…' : 'Login'}
        </button>
      </form>

      {/* Sign up section */}
      <form id="signup" onSubmit={handleSignup} className="container auth-form mt-5">
        <h2 className="mb-3">Sign Up</h2>
        <div className="mb-3">
          <input
            type="text"
            className="form-control"
            placeholder="Name"
            required
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="mb-3">
          <input
            type="email"
            className="form-control"
            placeholder="Email"
            required
            autoComplete="email"
            value={regEmail}
            onChange={(e) => setRegEmail(e.target.value)}
          />
        </div>
        <div className="mb-3">
          <input
            type="password"
            className={`form-control${pwError ? ' is-invalid' : ''}`}
            placeholder="Password"
            required
            autoComplete="new-password"
            value={regPassword}
            onChange={(e) => setRegPassword(e.target.value)}
          />
          <div className="form-text">Minimum 8 characters.</div>
          {pwError && <div className="invalid-feedback">{pwError}</div>}
        </div>
        <div className="mb-3">
          <input
            type="password"
            className="form-control"
            placeholder="Confirm Password"
            required
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>
        <button
          className="btn btn-primary w-100"
          type="submit"
          disabled={signingUp}
        >
          {signingUp ? 'Signing up…' : 'Create Account'}
        </button>
      </form>
    </>
  );
}
