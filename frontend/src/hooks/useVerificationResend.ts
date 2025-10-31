// @ts-nocheck
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { requestVerificationEmailResend } from '../utils/verification';

export function useVerificationResend({ cooldownSeconds = 0 }: any = {}) {
  const { t } = useTranslation();
  const [status, setStatus] = useState('idle');
  const [message, setMessage] = useState('');
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) {
      return undefined;
    }
    const timer = setTimeout(() => {
      setCooldown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const reset = useCallback(() => {
    setStatus('idle');
    setMessage('');
    setCooldown(0);
  }, []);

  const request = useCallback(
    async (email, options = {}) => {
      const trimmed = (email ?? '').trim();
      if (!trimmed) return;
      setStatus('loading');
      setMessage('');
      const {
        successMessage,
        errorMessage,
        rateLimitedMessage,
        networkMessageBuilder,
        onSuccess,
        cooldownSeconds: overrideCooldown,
      } = options;
      try {
        const { response, detail } = await requestVerificationEmailResend(trimmed);
        if (response.status === 429) {
          setStatus('error');
          setMessage(rateLimitedMessage ?? detail ?? t('auth.verification.resendRateLimited'));
          return;
        }
        if (!response.ok) {
          setStatus('error');
          setMessage(detail ?? errorMessage ?? t('auth.verification.resendError'));
          return;
        }
        setStatus('success');
        setMessage(detail ?? successMessage ?? t('auth.verification.resendGeneric', { email: trimmed }));
        const nextCooldown = overrideCooldown ?? cooldownSeconds;
        if (nextCooldown > 0) {
          setCooldown(nextCooldown);
        }
        if (typeof onSuccess === 'function') {
          onSuccess();
        }
      } catch (error) {
        const buildNetworkMessage =
          networkMessageBuilder ?? ((err) => t('auth.common.networkError', { message: err.message }));
        setStatus('error');
        setMessage(buildNetworkMessage(error));
      }
    },
    [cooldownSeconds, t],
  );

  return {
    status,
    message,
    cooldown,
    request,
    reset,
  };
}
