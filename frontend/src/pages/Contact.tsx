import type { ChangeEvent, FormEvent } from 'react';
import { useEffect, useRef, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { API } from '../api';
import Seo from '../components/Seo';
import useLang from '../hooks/useLang';

const statusTones = ['success', 'rateLimit', 'validation', 'error', 'tooFast'] as const;

type ContactStatusTone = (typeof statusTones)[number];

type ContactStatusKey =
  | 'contactPage.status.success'
  | 'contactPage.status.rateLimit'
  | 'contactPage.status.validation'
  | 'contactPage.status.error'
  | 'contactPage.status.tooFast';

function isStatusTone(value: string): value is ContactStatusTone {
  return (statusTones as readonly string[]).includes(value);
}

// Contact form where users can send a name, email and message.
export default function ContactPage() {
  const { t } = useTranslation();
  const lang = useLang();
  const langPrefix = `/${lang}`;
  const maxMessageLength = 2000;
  const minMessageLength = 10;
  const minSubmissionTimeMs = 3000;
  const counterId = 'contactMessageHelp';
  const shortHintId = 'contactMessageTooShort';
  const honeypotId = 'contactWebsite';
  const formStartRef = useRef<number>(Date.now());
  const statusRef = useRef<HTMLDivElement | null>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [messageTouched, setMessageTouched] = useState(false);
  const [honeypot, setHoneypot] = useState('');
  const [statusKey, setStatusKey] = useState<ContactStatusKey | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!statusKey || statusKey === 'contactPage.status.success') {
      return;
    }
    const statusNode = statusRef.current;
    if (statusNode) {
      statusNode.focus();
    }
  }, [statusKey]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (sending) return;
    setMessageTouched(true);
    setStatusKey(null);

    const trimmedLength = message.trim().length;
    if (trimmedLength < minMessageLength) {
      setStatusKey('contactPage.status.validation');
      return;
    }

    if (honeypot) {
      setStatusKey('contactPage.status.validation');
      return;
    }

    if (Date.now() - formStartRef.current < minSubmissionTimeMs) {
      setStatusKey('contactPage.status.tooFast');
      return;
    }

    setSending(true);
    try {
      const resp = await fetch(`${API}/contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // Send the form values to the API
        body: JSON.stringify({
          name,
          email,
          message,
        }),
      });
      if (resp.ok) {
        setStatusKey('contactPage.status.success');
        setName('');
        setEmail('');
        setMessage('');
        setMessageTouched(false);
        setHoneypot('');
        const nextStart = Date.now();
        formStartRef.current = nextStart;
      } else if (resp.status === 429) {
        // Show specific guidance when the rate limit is hit
        setStatusKey('contactPage.status.rateLimit');
      } else if (resp.status === 422) {
        let detailPayload: unknown = null;
        try {
          detailPayload = await resp.json();
        } catch (_error) {
          detailPayload = null;
        }
        const detailValue =
          typeof detailPayload === 'object' &&
          detailPayload !== null &&
          'detail' in detailPayload &&
          typeof (detailPayload as { detail?: unknown }).detail === 'string'
            ? (detailPayload as { detail: string }).detail
            : null;
        if (detailValue === 'too_fast') {
          setStatusKey('contactPage.status.tooFast');
        } else {
          setStatusKey('contactPage.status.validation');
        }
      } else {
        setStatusKey('contactPage.status.error');
      }
    } catch {
      setStatusKey('contactPage.status.error');
    } finally {
      setSending(false);
    }
  };

  const messageLength = message.length;
  const trimmedMessageLength = message.trim().length;
  const messageTooShort = messageTouched && trimmedMessageLength < minMessageLength;
  const messageDescribedBy = messageTooShort
    ? `${counterId} ${shortHintId}`
    : counterId;

  const statusTone = statusKey?.split('.').pop();
  const statusClassMap = {
    success: 'alert-success',
    rateLimit: 'alert-warning',
    validation: 'alert-danger',
    error: 'alert-danger',
    tooFast: 'alert-info',
  } satisfies Record<ContactStatusTone, string>;
  const statusClassName =
    statusTone && isStatusTone(statusTone) ? statusClassMap[statusTone] : 'alert-info';

  const handleNameChange = (event: ChangeEvent<HTMLInputElement>) => {
    setName(event.target.value);
  };

  const handleEmailChange = (event: ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value);
  };

  const handleMessageChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(event.target.value);
  };

  const handleHoneypotChange = (event: ChangeEvent<HTMLInputElement>) => {
    setHoneypot(event.target.value);
  };

  const markMessageTouched = () => {
    setMessageTouched(true);
  };

  const dataProtectionHref = `${langPrefix}/data-protection`;
  const legalNoticeHref = `${langPrefix}/legal-notice`;

  return (
    <div className="container py-4">
      <Seo title={t('contactPage.title')} description={t('contactPage.seoDescription')} />
      <h2>{t('contactPage.title')}</h2>
      {statusKey && (
        <div
          ref={statusRef}
          className={`alert ${statusClassName}`}
          role="status"
          aria-live="polite"
          tabIndex={-1}
        >
          {t(statusKey)}
        </div>
      )}
      <form
        onSubmit={handleSubmit}
        className="mt-3"
        aria-busy={sending}
      >
        <div className="mb-3">
          <label htmlFor="contactName" className="form-label">
            {t('contactPage.nameLabel')}
          </label>
          <input
            id="contactName"
            type="text"
            className="form-control"
            value={name}
            onChange={handleNameChange}
            maxLength={100}
            autoComplete="name"
            required
          />
        </div>
        <div className="mb-3">
          <label htmlFor="contactEmail" className="form-label">
            {t('contactPage.emailLabel')}
          </label>
          <input
            id="contactEmail"
            type="email"
            className="form-control"
            value={email}
            onChange={handleEmailChange}
            autoComplete="email"
            inputMode="email"
            required
          />
        </div>
        <div className="mb-3">
          <label htmlFor="contactMessage" className="form-label">
            {t('contactPage.messageLabel')}
          </label>
          <textarea
            id="contactMessage"
            className="form-control"
            rows={4}
            maxLength={maxMessageLength}
            value={message}
            onChange={handleMessageChange}
            onBlur={markMessageTouched}
            onInvalid={markMessageTouched}
            minLength={minMessageLength}
            aria-describedby={messageDescribedBy}
            aria-errormessage={messageTooShort ? shortHintId : undefined}
            aria-invalid={messageTooShort}
            required
          />
          <div id={counterId} className="form-text text-end">
            {t('contactPage.messageHelp', { count: messageLength, max: maxMessageLength })}
          </div>
          {messageTooShort && (
            <div id={shortHintId} className="text-danger small mt-1">
              {t('contactPage.messageTooShort', { min: minMessageLength })}
            </div>
          )}
        </div>
        <div className="visually-hidden" aria-hidden="true">
          <label htmlFor={honeypotId}>Website</label>
          <input
            id={honeypotId}
            type="text"
            tabIndex={-1}
            autoComplete="off"
            aria-hidden="true"
            value={honeypot}
            onChange={handleHoneypotChange}
          />
        </div>
        <button type="submit" className="btn btn-success" disabled={sending}>
          {sending ? t('contactPage.submitting') : t('contactPage.submit')}
        </button>
        <p className="form-text mt-3">
          <Trans
            i18nKey="contactPage.privacyNotice"
            components={{
              dataProtection: <Link to={dataProtectionHref} className="link-underline" />,
              legalNotice: <Link to={legalNoticeHref} className="link-underline" />,
            }}
          />
        </p>
      </form>
    </div>
  );
}
