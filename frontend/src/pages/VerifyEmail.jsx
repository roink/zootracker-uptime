import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import Seo from '../components/Seo';
import { API } from '../api';

export default function VerifyEmailPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { lang } = useParams();
  const prefix = lang ? `/${lang}` : '';
  const params = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const initialUid = params.get('uid') ?? '';
  const initialToken = params.get('token') ?? '';
  const initialEmail = params.get('email') ?? '';

  const [email, setEmail] = useState(initialEmail);
  const [code, setCode] = useState('');
  const [status, setStatus] = useState('idle');
  const [message, setMessage] = useState('');

  // Attempt automatic verification when a magic link is opened.
  useEffect(() => {
    if (initialUid && initialToken) {
      const verify = async () => {
        setStatus('loading');
        setMessage('');
        try {
          const resp = await fetch(`${API}/auth/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid: initialUid, token: initialToken }),
          });
          if (resp.status === 200) {
            setStatus('success');
            setMessage(t('auth.verification.success'));
            window.history.replaceState({}, '', `${prefix}/verify${initialEmail ? `?email=${encodeURIComponent(initialEmail)}` : ''}`);
            return;
          }
          if (resp.status === 202) {
            setStatus('invalid');
            setMessage(t('auth.verification.invalid'));
            return;
          }
          const data = await resp.json().catch(() => ({}));
          setStatus('error');
          const detail = typeof data.detail === 'string' ? data.detail : resp.statusText;
          setMessage(detail);
        } catch (err) {
          setStatus('error');
          setMessage(t('auth.common.networkError', { message: err.message }));
        }
      };
      verify();
    }
  }, [initialUid, initialToken, initialEmail, prefix, t]);

  // Allow manual code entry as a fallback to the magic link.
  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!email || !code) return;
    setStatus('loading');
    setMessage('');
    try {
      const resp = await fetch(`${API}/auth/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), code: code.trim() }),
      });
      if (resp.status === 200) {
        setStatus('success');
        setMessage(t('auth.verification.success'));
        return;
      }
      if (resp.status === 202) {
        setStatus('invalid');
        setMessage(t('auth.verification.invalid'));
      } else if (resp.status === 429) {
        const data = await resp.json().catch(() => ({}));
        setStatus('error');
        const detail = typeof data.detail === 'string' ? data.detail : resp.statusText;
        setMessage(detail);
      } else {
        const data = await resp.json().catch(() => ({}));
        setStatus('error');
        const detail = typeof data.detail === 'string' ? data.detail : resp.statusText;
        setMessage(detail);
      }
    } catch (err) {
      setStatus('error');
      setMessage(t('auth.common.networkError', { message: err.message }));
    }
  };

  return (
    <div className="container auth-form">
      <Seo
        title={t('auth.seo.verifyTitle')}
        description={t('auth.seo.verifyDescription')}
      />
      <h1 className="mb-3">{t('auth.verification.heading')}</h1>
      <p>{t('auth.verification.intro')}</p>
      {status === 'success' && (
        <div className="alert alert-success" role="alert">
          {message}
        </div>
      )}
      {status === 'invalid' && (
        <div className="alert alert-warning" role="alert">
          {message}
        </div>
      )}
      {status === 'error' && (
        <div className="alert alert-danger" role="alert">
          {message}
        </div>
      )}
      <form onSubmit={handleSubmit} className="card p-4 shadow-sm mb-4">
        <div className="mb-3">
          <label className="form-label" htmlFor="verify-email">
            {t('auth.verification.emailLabel')}
          </label>
          <input
            id="verify-email"
            type="email"
            className="form-control"
            value={email}
            required
            autoComplete="email"
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div className="mb-3">
          <label className="form-label" htmlFor="verify-code">
            {t('auth.verification.codeLabel')}
          </label>
          <input
            id="verify-code"
            type="text"
            inputMode="numeric"
            pattern="[0-9]{6,8}"
            maxLength={8}
            minLength={6}
            className="form-control"
            value={code}
            required
            onChange={(event) => setCode(event.target.value)}
          />
        </div>
        <button className="btn btn-primary w-100" type="submit" disabled={status === 'loading'}>
          {status === 'loading' ? t('auth.verification.submitting') : t('auth.verification.submit')}
        </button>
      </form>
      <button
        type="button"
        className="btn btn-outline-secondary"
        onClick={() => navigate(`${prefix}/login`)}
      >
        {t('auth.verification.backToLogin')}
      </button>
    </div>
  );
}
