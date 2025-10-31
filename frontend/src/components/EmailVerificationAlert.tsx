import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { API } from '../api';
import { useAuth } from '../auth/AuthContext';

type ResendStatus = 'idle' | 'loading' | 'success' | 'limit' | 'cooldown' | 'error';

export default function EmailVerificationAlert() {
  const { t } = useTranslation();
  const { lang } = useParams();
  const prefix = lang ? `/${lang}` : '';
  const { user, token } = useAuth();
  const [status, setStatus] = useState<ResendStatus>('idle');
  const [message, setMessage] = useState('');

  if (!user || user.emailVerified) {
    return null;
  }

  const handleResend = async () => {
    if (!token || status === 'loading') return;
    setStatus('loading');
    setMessage('');
    try {
      const resp = await fetch(`${API}/auth/verification/resend`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (resp.ok) {
        setStatus('success');
        setMessage(t('auth.verification.resendSuccess'));
        return;
      }
      if (resp.status === 429) {
        const data = await resp.json().catch(() => ({}));
        const detail = typeof data.detail === 'string' ? data.detail.toLowerCase() : '';
        if (detail.includes('limit')) {
          setStatus('limit');
          setMessage(t('auth.verification.resendLimit'));
        } else {
          setStatus('cooldown');
          setMessage(t('auth.verification.resendCooldown'));
        }
        return;
      }
      setStatus('error');
      setMessage(t('auth.common.networkError', { message: resp.status }));
    } catch (err) {
      const resolvedError = err instanceof Error ? err : new Error(String(err));
      setStatus('error');
      setMessage(t('auth.common.networkError', { message: resolvedError.message }));
    }
  };

  const buttonLabel = status === 'loading'
    ? t('auth.verification.resendLoading')
    : t('auth.verification.resend');

  return (
    <div className="container mt-3">
      <div className="alert alert-warning" role="alert">
        <div className="d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-3">
          <div>
            <strong>{t('auth.verification.banner')}</strong>
            {message && <div className="mt-2 mb-0">{message}</div>}
          </div>
          <div className="d-flex flex-wrap gap-2">
            <button
              type="button"
              className="btn btn-outline-secondary"
              onClick={handleResend}
              disabled={status === 'loading'}
            >
              {buttonLabel}
            </button>
            <Link className="btn btn-primary" to={`${prefix}/verify`}>
              {t('auth.verification.openForm')}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
