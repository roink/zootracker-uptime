import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import Seo from '../components/Seo';
import { API } from '../api';

const maskEmail = (value) => {
  const [localPart, domain] = value.split('@');
  if (!localPart || !domain) {
    return '';
  }
  const first = localPart[0];
  const last = localPart.length > 1 ? localPart[localPart.length - 1] : '';
  const maskLength = Math.min(Math.max(localPart.length - 2, 3), 6);
  const masked = '•'.repeat(maskLength);
  return `${first}${masked}${last}@${domain}`;
};

// Password reset confirmation page that validates the token and records a new password.
export default function ResetPasswordPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const { lang } = useParams();
  const prefix = lang ? `/${lang}` : '';
  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const token = (searchParams.get('token') ?? '').trim();
  const emailFromQuery = (searchParams.get('email') ?? '').trim();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordTouched, setPasswordTouched] = useState(false);
  const [confirmTouched, setConfirmTouched] = useState(false);
  const [passwordFocused, setPasswordFocused] = useState(false);
  const [confirmFocused, setConfirmFocused] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [status, setStatus] = useState('idle');
  const [statusMessage, setStatusMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const passwordRef = useRef(null);
  const confirmRef = useRef(null);
  const alertRef = useRef(null);
  const successRef = useRef(null);

  const maskedEmail = useMemo(() => maskEmail(emailFromQuery), [emailFromQuery]);

  useEffect(() => {
    if (['loading', 'error', 'rateLimited'].includes(status) && alertRef.current) {
      alertRef.current.focus();
    }
  }, [status, statusMessage]);

  useEffect(() => {
    if (status === 'success' && successRef.current) {
      successRef.current.focus();
    }
  }, [status]);

  if (!token) {
    return (
      <div className="container auth-form">
        <Seo
          title={t('auth.seo.resetTitle')}
          description={t('auth.seo.resetDescription')}
        />
        <h1 className="mb-3">{t('auth.passwordReset.reset.heading')}</h1>
        <div className="alert alert-warning" role="alert">
          {t('auth.passwordReset.reset.tokenMissing')}
        </div>
        <Link to={`${prefix}/forgot-password`} className="btn btn-primary w-100">
          {t('auth.passwordReset.reset.requestLink')}
        </Link>
      </div>
    );
  }

  const passwordTooShort = passwordTouched && password.length < 8;
  const confirmMismatch = confirmTouched && confirmPassword !== password;
  const showPasswordHelper = passwordFocused || !passwordTouched;
  const showConfirmHelper = confirmFocused || !confirmTouched;
  const passwordDescribedBy = showPasswordHelper ? 'new-password-help' : undefined;
  const confirmDescribedBy = showConfirmHelper ? 'confirm-password-help' : undefined;

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (submitting) return;

    setPasswordTouched(true);
    setConfirmTouched(true);

    if (password.length < 8) {
      if (passwordRef.current) {
        passwordRef.current.focus();
      }
      return;
    }
    if (confirmPassword !== password) {
      if (confirmRef.current) {
        confirmRef.current.focus();
      }
      return;
    }

    setSubmitting(true);
    setStatus('loading');
    setStatusMessage(t('auth.passwordReset.reset.statusLoading'));

    try {
      const response = await fetch(`${API}/auth/password/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password, confirmPassword }),
      });
      if (response.ok) {
        setStatus('success');
        setStatusMessage('');
        setPassword('');
        setConfirmPassword('');
      } else if (response.status === 429) {
        const data = await response.json().catch(() => ({}));
        const detail = typeof data.detail === 'string' ? data.detail : '';
        setStatus('rateLimited');
        setStatusMessage(detail || t('auth.passwordReset.reset.statusRateLimited'));
      } else {
        const data = await response.json().catch(() => ({}));
        const detail = typeof data.detail === 'string' ? data.detail : '';
        setStatus('error');
        setStatusMessage(detail || t('auth.passwordReset.reset.statusError'));
      }
    } catch (error) {
      setStatus('error');
      setStatusMessage(t('auth.common.networkError', { message: error.message }));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container auth-form">
      <Seo
        title={t('auth.seo.resetTitle')}
        description={t('auth.seo.resetDescription')}
      />
      <h1 className="mb-3">{t('auth.passwordReset.reset.heading')}</h1>
      <p>{t('auth.passwordReset.reset.intro')}</p>

      {status !== 'idle' && status !== 'success' && (
        <div
          ref={alertRef}
          className={`alert ${status === 'loading' ? 'alert-info' : status === 'rateLimited' ? 'alert-warning' : 'alert-danger'}`}
          role="status"
          aria-live="polite"
          tabIndex={-1}
        >
          {statusMessage}
        </div>
      )}

      {status === 'success' ? (
        <div
          ref={successRef}
          className="card p-4 shadow-sm"
          role="status"
          aria-live="polite"
          tabIndex={-1}
        >
          <h2 className="h4">{t('auth.passwordReset.reset.successHeading')}</h2>
          <p className="mb-3">
            {maskedEmail
              ? t('auth.passwordReset.reset.successBodyEmail', { email: maskedEmail })
              : t('auth.passwordReset.reset.successBody')}
          </p>
          <Link to={`${prefix}/login`} className="btn btn-primary w-100">
            {t('auth.passwordReset.reset.loginCta')}
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="card p-4 shadow-sm">
          <div className="mb-3">
            <label className="form-label" htmlFor="new-password">
              {t('auth.passwordReset.reset.passwordLabel')}
            </label>
            <div className="input-group">
              <input
                ref={passwordRef}
                id="new-password"
                type={showPassword ? 'text' : 'password'}
                className={`form-control${passwordTooShort ? ' is-invalid' : ''}`}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                onFocus={() => setPasswordFocused(true)}
                onBlur={() => {
                  setPasswordFocused(false);
                  setPasswordTouched(true);
                }}
                aria-describedby={passwordDescribedBy}
                autoComplete="new-password"
                required
              />
              <button
                type="button"
                className="btn btn-outline-secondary"
                onClick={() => setShowPassword((prev) => !prev)}
                aria-label={
                  showPassword
                    ? t('auth.passwordReset.reset.hidePassword')
                    : t('auth.passwordReset.reset.showPassword')
                }
              >
                {showPassword
                  ? t('auth.passwordReset.reset.hidePasswordShort')
                  : t('auth.passwordReset.reset.showPasswordShort')}
              </button>
            </div>
            {showPasswordHelper && (
              <div id="new-password-help" className="form-text">
                {t('auth.passwordReset.reset.passwordHelper')}
              </div>
            )}
            {passwordTooShort && (
              <div className="invalid-feedback">{t('auth.errors.passwordTooShort')}</div>
            )}
          </div>
          <div className="mb-3">
            <label className="form-label" htmlFor="confirm-password">
              {t('auth.passwordReset.reset.confirmLabel')}
            </label>
            <div className="input-group">
              <input
                ref={confirmRef}
                id="confirm-password"
                type={showConfirm ? 'text' : 'password'}
                className={`form-control${confirmMismatch ? ' is-invalid' : ''}`}
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                onFocus={() => setConfirmFocused(true)}
                onBlur={() => {
                  setConfirmFocused(false);
                  setConfirmTouched(true);
                }}
                aria-describedby={confirmDescribedBy}
                autoComplete="new-password"
                required
              />
              <button
                type="button"
                className="btn btn-outline-secondary"
                onClick={() => setShowConfirm((prev) => !prev)}
                aria-label={
                  showConfirm
                    ? t('auth.passwordReset.reset.hidePassword')
                    : t('auth.passwordReset.reset.showPassword')
                }
              >
                {showConfirm
                  ? t('auth.passwordReset.reset.hidePasswordShort')
                  : t('auth.passwordReset.reset.showPasswordShort')}
              </button>
            </div>
            {showConfirmHelper && (
              <div id="confirm-password-help" className="form-text">
                {t('auth.passwordReset.reset.confirmHelper')}
              </div>
            )}
            {confirmMismatch && (
              <div className="invalid-feedback">{t('auth.errors.passwordMismatch')}</div>
            )}
          </div>
          <button type="submit" className="btn btn-primary w-100" disabled={submitting}>
            {submitting
              ? t('auth.passwordReset.reset.submitting')
              : t('auth.passwordReset.reset.submit')}
          </button>
        </form>
      )}

      <div className="mt-4 d-grid gap-2">
        <Link to={`${prefix}/login`} className="btn btn-outline-secondary">
          {t('auth.passwordReset.reset.loginCta')}
        </Link>
        <Link to={`${prefix}/forgot-password`} className="btn btn-link auth-forgot-link px-0">
          {t('auth.passwordReset.reset.requestLink')}
        </Link>
      </div>
    </div>
  );
}
