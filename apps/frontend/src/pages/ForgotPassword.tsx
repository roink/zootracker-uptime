import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useParams } from 'react-router-dom';

import { API } from '../api';
import Seo from '../components/Seo';
import { saveMaskedEmailHint } from '../utils/passwordReset';

// Password reset request page that keeps the flow anonymous while guiding users.
export default function ForgotPasswordPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const { lang } = useParams();
  const prefix = lang ? `/${lang}` : '';
  const locationEmail =
    typeof location.state?.email === 'string' && location.state.email.trim() ? location.state.email.trim() : '';
  const [email, setEmail] = useState(locationEmail);
  const [emailTouched, setEmailTouched] = useState(false);
  const [emailFocused, setEmailFocused] = useState(false);
  const [status, setStatus] = useState('idle');
  const [statusMessage, setStatusMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState('');
  const inputRef = useRef<any>(null);
  const alertRef = useRef<any>(null);
  const successRef = useRef<any>(null);

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

  const emailTrimmed = email.trim();
  const emailPattern = /^[^\s@]+@[^\s@]+$/;
  const emailRequiredError = emailTouched && emailTrimmed === '';
  const emailInvalidError = emailTouched && emailTrimmed !== '' && !emailPattern.test(emailTrimmed);
  const emailError = emailRequiredError
    ? t('auth.passwordReset.request.emailErrorRequired')
    : emailInvalidError
      ? t('auth.passwordReset.request.emailErrorInvalid')
      : '';
  const showHelperText = emailFocused || !emailTouched;
  const emailDescribedBy = showHelperText ? 'reset-email-help' : undefined;

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (submitting) return;

    const valid = emailTrimmed !== '' && emailPattern.test(emailTrimmed);
    setEmailTouched(true);

    if (!valid) {
      setStatus('idle');
      setStatusMessage('');
      if (inputRef.current) {
        inputRef.current.focus();
      }
      return;
    }

    setSubmitting(true);
    setStatus('loading');
    setStatusMessage(t('auth.passwordReset.request.statusLoading'));

    try {
      const response = await fetch(`${API}/auth/password/forgot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailTrimmed }),
      });
      if (response.ok) {
        setSubmittedEmail(emailTrimmed);
        setStatus('success');
        setStatusMessage('');
        saveMaskedEmailHint(emailTrimmed);
        setEmail('');
        setEmailTouched(false);
      } else if (response.status === 429) {
        const data = await response.json().catch(() => ({}));
        const detail = typeof data.detail === 'string' ? data.detail : '';
        setStatus('rateLimited');
        setStatusMessage(detail || t('auth.passwordReset.request.rateLimited'));
      } else {
        const data = await response.json().catch(() => ({}));
        const detail = typeof data.detail === 'string' ? data.detail : '';
        setStatus('error');
        setStatusMessage(detail || t('auth.passwordReset.request.error'));
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setStatus('error');
      setStatusMessage(t('auth.common.networkError', { message }));
    } finally {
      setSubmitting(false);
    }
  };

  const handleEmailChange = (event) => {
    setEmail(event.target.value);
    if (status !== 'idle' && status !== 'loading') {
      setStatus('idle');
      setStatusMessage('');
    }
  };

  return (
    <div className="container auth-form">
      <Seo
        title={t('auth.seo.forgotTitle')}
        description={t('auth.seo.forgotDescription')}
        robots="noindex, follow"
      />
      <h1 className="mb-3">{t('auth.passwordReset.request.heading')}</h1>
      <p>{t('auth.passwordReset.request.intro')}</p>

      {status !== 'success' && status !== 'idle' && (
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
          <h2 className="h4">{t('auth.passwordReset.request.successHeading')}</h2>
          <p className="mb-3">
            {t('auth.passwordReset.request.successBody', { email: submittedEmail })}
          </p>
          <Link to={`${prefix}/login`} className="btn btn-primary w-100">
            {t('auth.passwordReset.request.successCta')}
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="card p-4 shadow-sm">
          <div className="mb-3">
            <label className="form-label" htmlFor="reset-email">
              {t('auth.passwordReset.request.emailLabel')}
            </label>
            <input
              ref={inputRef}
              id="reset-email"
              type="email"
              className={`form-control${emailError ? ' is-invalid' : ''}`}
              value={email}
              autoComplete="email"
              onFocus={() => { setEmailFocused(true); }}
              onBlur={() => {
                setEmailFocused(false);
                setEmailTouched(true);
              }}
              onChange={handleEmailChange}
              aria-describedby={emailDescribedBy}
              required
            />
            {showHelperText && (
              <div id="reset-email-help" className="form-text">
                {t('auth.passwordReset.request.emailHelper')}
              </div>
            )}
            {emailError && <div className="invalid-feedback">{emailError}</div>}
          </div>
          <button type="submit" className="btn btn-primary w-100" disabled={submitting}>
            {submitting
              ? t('auth.passwordReset.request.submitting')
              : t('auth.passwordReset.request.submit')}
          </button>
        </form>
      )}

      <div className="mt-4">
        <Link to={`${prefix}/login`} className="btn btn-outline-secondary w-100">
          {t('auth.passwordReset.request.backToLogin')}
        </Link>
      </div>
    </div>
  );
}
