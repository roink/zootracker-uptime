import { useState, useEffect, useRef } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Link, useNavigate, useLocation, useParams } from 'react-router-dom';

import { API } from '../api';
import { DATA_PROTECTION_VERSION } from './DataProtection';
import { useAuth } from '../auth/AuthContext';
import Seo from '../components/Seo';
import { useVerificationResend } from '../hooks/useVerificationResend';

// Combined authentication page with log in on top and sign up below.
export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { lang } = useParams();
  const prefix = lang ? `/${lang}` : '';
  const dataProtectionHref = `${prefix}/data-protection`;
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
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptError, setAcceptError] = useState('');
  const consentCheckboxRef = useRef<any>(null);
  // Show a success message after signing up
  const [successMessage, setSuccessMessage] = useState('');
  const [pendingEmail, setPendingEmail] = useState('');
  const [loginError, setLoginError] = useState('');
  const [verificationBanner, setVerificationBanner] = useState('');
  const RESEND_DELAY_SECONDS = 60;
  const {
    status: loginResendStatus,
    message: loginResendMessage,
    request: triggerLoginResend,
    reset: resetLoginResend,
  } = useVerificationResend();
  const {
    status: signupResendStatus,
    message: signupResendMessage,
    cooldown: signupResendCooldown,
    request: triggerSignupResend,
    reset: resetSignupResend,
  } = useVerificationResend({ cooldownSeconds: RESEND_DELAY_SECONDS });
  const verifyHref = pendingEmail
    ? `${prefix}/verify?email=${encodeURIComponent(pendingEmail)}`
    : `${prefix}/verify`;
  // Prevent double submits while network requests are pending
  const [loggingIn, setLoggingIn] = useState(false);
  const [signingUp, setSigningUp] = useState(false);

  // Extract a one-time message from navigation state then clear it
  useEffect(() => {
      if (location.state?.message) {
        setSuccessMessage(location.state.message);
        void navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location, navigate]);

  useEffect(() => {
    const cookieParts = document.cookie.split('; ').filter(Boolean);
    const flag = cookieParts.find((part) => part.startsWith('ztr_verify_success='));
    if (flag) {
      const [, rawValue = ''] = flag.split('=');
      let decoded = '';
      if (rawValue) {
        try {
          decoded = decodeURIComponent(rawValue);
        } catch (err) {
          decoded = rawValue;
        }
      }
      setVerificationBanner(decoded
        ? t('auth.login.verificationSuccessEmail', { email: decoded })
        : t('auth.login.verificationSuccess'));
      document.cookie = 'ztr_verify_success=; Max-Age=0; path=/';
    }
  }, [t]);

  // Scroll to the sign up section when the URL contains "#signup".
  useEffect(() => {
    if (location.hash === '#signup') {
      const el = document.getElementById('signup');
      if (el && typeof el.scrollIntoView === 'function') {
        el.scrollIntoView();
      }
    }
  }, [location.hash]);

  useEffect(() => {
    if (acceptError && consentCheckboxRef.current) {
      consentCheckboxRef.current.focus();
    }
  }, [acceptError]);

  useEffect(() => {
    if (successMessage && pendingEmail) {
      resetSignupResend();
    }
  }, [successMessage, pendingEmail, resetSignupResend]);

  useEffect(() => {
    if (!pendingEmail) {
      resetLoginResend();
    }
  }, [pendingEmail, resetLoginResend]);

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
    setVerificationBanner('');
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
          user: { id: data.user_id, email: cleanEmail, emailVerified: data.email_verified },
          expiresIn: data.expires_in,
        });
        setPendingEmail('');
        setLoginError('');
        resetLoginResend();
          void navigate(prefix, { replace: true });
      } else if (resp.status === 403) {
        const payload = await resp.json().catch(() => ({}));
        const detail = typeof payload.detail === 'string' ? payload.detail : t('auth.login.unverified');
        setPendingEmail(cleanEmail);
        setLoginError(detail);
        resetLoginResend();
      } else {
        setLoginError(t('auth.login.error'));
      }
    } catch (err) {
      const networkError = err instanceof Error ? err : new Error(String(err));
      setLoginError(t('auth.common.networkError', { message: networkError.message }));
    } finally {
      setLoggingIn(false);
    }
  };

  // Handle new account creation and show a message prompting the user to log in.
  const handleSignup = async (e) => {
    e.preventDefault();
    if (signingUp) return;
    if (!acceptTerms) {
      setAcceptError(t('auth.errors.consentRequired'));
      return;
    }
    if (regPassword.length < 8) {
      setPwError(t('auth.errors.passwordTooShort'));
      return;
    }
    if (regPassword !== confirm) {
      setPwError(t('auth.errors.passwordMismatch'));
      return;
    }
    setPwError('');
    setAcceptError('');
    setSigningUp(true);
    const cleanEmail = regEmail.trim();
    try {
      const resp = await fetch(`${API}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          email: cleanEmail,
          password: regPassword,
          accepted_data_protection: acceptTerms,
          privacy_consent_version: DATA_PROTECTION_VERSION,
        }),
      });
      if (resp.ok) {
        await resp.json();
        setInputEmail(cleanEmail);
        setPendingEmail(cleanEmail);
        setSuccessMessage(t('auth.signup.success', { email: cleanEmail }));
        resetSignupResend();
        setName('');
        setRegEmail('');
        setRegPassword('');
        setConfirm('');
        setAcceptTerms(false);
        window.scrollTo(0, 0);
      } else {
        alert(t('auth.signup.error'));
      }
    } catch (err) {
      const networkError = err instanceof Error ? err : new Error(String(err));
      alert(t('auth.common.networkError', { message: networkError.message }));
    } finally {
      setSigningUp(false);
    }
  };

  return (
    <>
      <Seo
        title={t('auth.seo.loginTitle')}
        description={t('auth.seo.loginDescription')}
      />
      {/* Log in section */}
      <form onSubmit={handleLogin} className="container auth-form">
        {verificationBanner && (
          <div className="alert alert-success" role="alert">
            {verificationBanner}
          </div>
        )}
        {loginError && (
          <div className="alert alert-warning" role="alert">
            <p className="mb-2">{loginError}</p>
            {pendingEmail && (
              <div className="small">
                {loginResendStatus === 'success' ? (
                  <span className="text-success">{loginResendMessage || t('auth.verification.resendGeneric', { email: pendingEmail })}</span>
                ) : (
                  <>
                    <button
                      type="button"
                      className="btn btn-link p-0 align-baseline"
                      onClick={() => triggerLoginResend(pendingEmail)}
                      disabled={loginResendStatus === 'loading'}
                    >
                      {loginResendStatus === 'loading'
                        ? t('auth.verification.resendLoading')
                        : t('auth.login.resendLink')}
                    </button>
                    {loginResendStatus === 'error' && loginResendMessage && (
                      <div className="text-danger mt-1">{loginResendMessage}</div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        )}
        {successMessage && (
          <div className="alert alert-success" role="alert">
            <p className="mb-2">{successMessage}</p>
            <div className="d-flex flex-wrap gap-2">
              <button
                type="button"
                className="btn btn-light"
                onClick={() => void navigate(verifyHref)}
              >
                {t('auth.verification.openForm')}
              </button>
              {pendingEmail && (
                <button
                  type="button"
                  className="btn btn-outline-secondary"
                  onClick={() => triggerSignupResend(pendingEmail)}
                  disabled={signupResendStatus === 'loading' || signupResendCooldown > 0}
                >
                  {signupResendStatus === 'loading'
                    ? t('auth.verification.resendLoading')
                    : t('auth.signup.resendLink')}
                </button>
              )}
            </div>
            {signupResendCooldown > 0 && (
              <p className="small text-muted mb-0 mt-2">
                {t('auth.signup.resendCountdown', { seconds: signupResendCooldown })}
              </p>
            )}
            {signupResendStatus === 'success' && (
              <p className="small text-success mb-0 mt-2">{signupResendMessage || t('auth.verification.resendGeneric', { email: pendingEmail })}</p>
            )}
            {signupResendStatus === 'error' && signupResendMessage && (
              <p className="small text-danger mb-0 mt-2">{signupResendMessage}</p>
            )}
          </div>
        )}
        <h2 className="mb-3">{t('auth.login.heading')}</h2>
        <div className="mb-3">
          <input
            type="email"
            className="form-control"
            placeholder={t('auth.login.emailPlaceholder')}
            required
            autoComplete="email"
            value={inputEmail}
            onChange={(e) => { setInputEmail(e.target.value); }}
          />
        </div>
        <div className="mb-3">
          <input
            type="password"
            className="form-control"
            placeholder={t('auth.login.passwordPlaceholder')}
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => { setPassword(e.target.value); }}
          />
          <Link
            to={`${prefix}/forgot-password`}
            state={inputEmail.trim() ? { email: inputEmail.trim() } : undefined}
            className="btn btn-link px-0 auth-forgot-link"
          >
            {t('auth.login.forgotLink')}
          </Link>
        </div>
        <button className="btn btn-primary w-100" type="submit" disabled={loggingIn}>
          {loggingIn ? t('auth.login.submitting') : t('auth.login.submit')}
        </button>
      </form>

      {/* Sign up section */}
      <form id="signup" onSubmit={handleSignup} className="container auth-form mt-5">
        <h2 className="mb-3">{t('auth.signup.heading')}</h2>
        <div className="mb-3">
          <input
            type="text"
            className="form-control"
            placeholder={t('auth.signup.namePlaceholder')}
            required
            autoComplete="name"
            value={name}
            onChange={(e) => { setName(e.target.value); }}
          />
        </div>
        <div className="mb-3">
          <input
            type="email"
            className="form-control"
            placeholder={t('auth.signup.emailPlaceholder')}
            required
            autoComplete="email"
            value={regEmail}
            onChange={(e) => { setRegEmail(e.target.value); }}
          />
        </div>
        <div className="mb-3">
          <input
            type="password"
            className={`form-control${pwError ? ' is-invalid' : ''}`}
            placeholder={t('auth.signup.passwordPlaceholder')}
            required
            autoComplete="new-password"
            value={regPassword}
            onChange={(e) => {
              setRegPassword(e.target.value);
              if (pwError) {
                setPwError('');
              }
            }}
          />
          <div className="form-text">{t('auth.signup.passwordHelp')}</div>
          {pwError && <div className="invalid-feedback">{pwError}</div>}
        </div>
        <div className="mb-3">
          <input
            type="password"
            className="form-control"
            placeholder={t('auth.signup.confirmPlaceholder')}
            required
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => {
              setConfirm(e.target.value);
              if (pwError) {
                setPwError('');
              }
            }}
          />
        </div>
        <div className="form-check mb-3">
          <input
            type="checkbox"
            className={`form-check-input${acceptError ? ' is-invalid' : ''}`}
            id="signup-data-protection"
            checked={acceptTerms}
            ref={consentCheckboxRef}
            onChange={(e) => {
              setAcceptTerms(e.target.checked);
              if (e.target.checked) {
                setAcceptError('');
              }
            }}
            required
            aria-invalid={acceptError ? 'true' : undefined}
            aria-describedby={acceptError ? 'signup-data-protection-error' : undefined}
            onInvalid={(event) => {
              event.preventDefault();
              setAcceptError(t('auth.errors.consentRequired'));
            }}
          />
          <label className="form-check-label" htmlFor="signup-data-protection">
            <Trans
              i18nKey="auth.signup.acceptLabel"
              components={{
                link: (
                  <Link
                    className="text-decoration-underline"
                    to={dataProtectionHref}
                  >
                    {t('auth.signup.linkText')}
                  </Link>
                ),
              }}
            />
          </label>
          <div className="mt-1" aria-live="polite">
            {acceptError && (
              <div
                id="signup-data-protection-error"
                className="invalid-feedback d-block"
                role="alert"
              >
                {acceptError}
              </div>
            )}
          </div>
        </div>
        <button
          className="btn btn-primary w-100"
          type="submit"
          disabled={signingUp}
        >
          {signingUp ? t('auth.signup.submitting') : t('auth.signup.submit')}
        </button>
      </form>
    </>
  );
}
