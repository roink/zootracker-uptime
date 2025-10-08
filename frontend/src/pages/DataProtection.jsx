import { Trans, useTranslation } from 'react-i18next';
import { useParams } from 'react-router-dom';
import Seo from '../components/Seo';
import { ORG } from '../config/org';

// Update this date whenever the data protection statement content changes so consent records stay accurate.
export const DATA_PROTECTION_VERSION = '2025-10-01';

// Detailed data protection information for the application.
export default function DataProtectionPage() {
  const { t, i18n } = useTranslation();
  const { lang } = useParams();
  const locale = (lang ?? i18n.language ?? 'en');
  const langSegment = locale.split('-')[0] || 'en';
  const legalNoticeHref = `/${langSegment}/legal-notice`;

  return (
    <div className="container py-4">
      <Seo
        title={t('nav.dataProtection')}
        description={t('dataProtectionPage.seoDescription')}
      />
      <h2 className="text-2xl font-semibold">{t('dataProtectionPage.title')}</h2>
      <p className="text-sm text-gray-600">{t('dataProtectionPage.lastUpdated')}</p>
      <p>{t('dataProtectionPage.intro')}</p>

      {/* Controller & Contact (no DPO) */}
      <section className="mt-4">
        <h4 className="font-semibold">{t('dataProtectionPage.controller.title')}</h4>
        <p>
          <Trans
            i18nKey="dataProtectionPage.controller.text"
            values={{ email: ORG.email }}
            components={{
              email: (
                <a
                  href={`mailto:${ORG.email}`}
                  className="underline"
                  rel="noopener noreferrer"
                />
              ),
              legalNotice: (
                <a
                  href={legalNoticeHref}
                  className="underline"
                  rel="noopener noreferrer"
                />
              ),
            }}
          />
        </p>
      </section>

      <section className="mt-4">
        <h4 className="font-semibold">{t('dataProtectionPage.emailProcessing.title')}</h4>
        <p>
          <Trans
            i18nKey="dataProtectionPage.emailProcessing.text"
            components={{
              strong: <strong />,
            }}
          />
        </p>
        <p>
          <Trans
            i18nKey="dataProtectionPage.emailProcessing.links"
            components={{
              privacy: (
                <a
                  href="https://www.zoho.com/privacy.html"
                  className="underline"
                  target="_blank"
                  rel="noopener noreferrer"
                />
              ),
              gdpr: (
                <a
                  href="https://www.zoho.com/gdpr.html"
                  className="underline"
                  target="_blank"
                  rel="noopener noreferrer"
                />
              ),
              subprocessors: (
                <a
                  href="https://www.zoho.com/privacy/sub-processors.html"
                  className="underline"
                  target="_blank"
                  rel="noopener noreferrer"
                />
              ),
            }}
          />
        </p>
      </section>

      <section className="mt-4">
        <h4 className="font-semibold">{t('dataProtectionPage.cookies.title')}</h4>
        <p>{t('dataProtectionPage.cookies.text')}</p>
      </section>

      <section className="mt-4">
        <h4>{t('dataProtectionPage.logging.title')}</h4>
        <p>
          <Trans
            i18nKey="dataProtectionPage.logging.raw"
            components={{ strong: <strong /> }}
          />
        </p>
        <p>
          <Trans
            i18nKey="dataProtectionPage.logging.anonymized"
            components={{ strong: <strong /> }}
          />
        </p>
      </section>

      <section className="mt-4">
        <h4>{t('dataProtectionPage.legalBasis.title')}</h4>
        <p>{t('dataProtectionPage.legalBasis.text')}</p>
      </section>

      <section className="mt-4">
        <h4>{t('dataProtectionPage.automated.title')}</h4>
        <p>{t('dataProtectionPage.automated.text')}</p>
      </section>

      {/* Processors & Transfers */}
      <section className="mt-4">
        <h4 className="font-semibold">{t('dataProtectionPage.processors.title')}</h4>
        <ul className="list-disc ml-6">
          <li>
            {t('dataProtectionPage.processors.hetzner')}{' '}
            (<a href="https://www.hetzner.com/legal/privacy-policy" className="underline" target="_blank" rel="noopener noreferrer">Privacy</a>)
          </li>
          <li>
            {t('dataProtectionPage.processors.cloudflare')}{' '}
            (<a href="https://www.cloudflare.com/cloudflare-customer-dpa/" className="underline" target="_blank" rel="noopener noreferrer">DPA</a>,{' '}
            <a href="https://www.cloudflare.com/cloudflare-customer-scc/" className="underline" target="_blank" rel="noopener noreferrer">SCCs</a>)
          </li>
          <li>
            <Trans
              i18nKey="dataProtectionPage.processors.zohoMail"
              components={{
                privacy: (
                  <a
                    href="https://www.zoho.com/privacy.html"
                    className="underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  />
                ),
                gdpr: (
                  <a
                    href="https://www.zoho.com/gdpr.html"
                    className="underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  />
                ),
                subprocessors: (
                  <a
                    href="https://www.zoho.com/privacy/sub-processors.html"
                    className="underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  />
                ),
              }}
            />
          </li>
        </ul>
      </section>

      <section className="mt-4">
        <h4 className="font-semibold">{t('dataProtectionPage.transfers.title')}</h4>
        <p>
          <Trans
            i18nKey="dataProtectionPage.transfers.text"
            components={{ strong: <strong /> }}
          />
        </p>
      </section>

      {/* Maps / third-party */}
      <section className="mt-4">
        <h4 className="font-semibold">{t('dataProtectionPage.maps.title')}</h4>
        <p>
          <Trans i18nKey="dataProtectionPage.maps.text">
            Interactive maps use MapLibre with tiles from OpenFreeMap (tiles.openfreemap.org).
          </Trans>{' '}
          (<a href="https://openfreemap.org/privacy/" className="underline" target="_blank" rel="noopener noreferrer">OpenFreeMap&nbsp;Privacy</a>)
        </p>
      </section>

      {/* Retention table */}
      <section className="mt-4">
        <h4 className="font-semibold">{t('dataProtectionPage.retention.title')}</h4>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border border-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="p-2 text-left border-b">{t('dataProtectionPage.retention.headers.data')}</th>
                <th className="p-2 text-left border-b">{t('dataProtectionPage.retention.headers.basis')}</th>
                <th className="p-2 text-left border-b">{t('dataProtectionPage.retention.headers.retention')}</th>
              </tr>
            </thead>
            <tbody>
              {['rawLogs','incident','analytics','account','visits'].map((key) => (
                <tr key={key}>
                  <td className="p-2 border-b">{t(`dataProtectionPage.retention.rows.${key}.data`)}</td>
                  <td className="p-2 border-b">{t(`dataProtectionPage.retention.rows.${key}.basis`)}</td>
                  <td className="p-2 border-b">{t(`dataProtectionPage.retention.rows.${key}.retention`)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-4">
        <h4>{t('dataProtectionPage.anonymous.title')}</h4>
        <p>{t('dataProtectionPage.anonymous.description')}</p>
        <ul>
          <li>{t('dataProtectionPage.anonymous.items.technical')}</li>
          <li>{t('dataProtectionPage.anonymous.items.security')}</li>
          <li>{t('dataProtectionPage.anonymous.items.analytics')}</li>
        </ul>
      </section>

      <section className="mt-4">
        <h4>{t('dataProtectionPage.loggedIn.title')}</h4>
        <p>{t('dataProtectionPage.loggedIn.description')}</p>
        <p>{t('dataProtectionPage.loggedIn.requirement')}</p>
        <ul>
          <li>{t('dataProtectionPage.loggedIn.items.account')}</li>
          <li>{t('dataProtectionPage.loggedIn.items.security')}</li>
          <li>{t('dataProtectionPage.loggedIn.items.history')}</li>
        </ul>
        <p>{t('dataProtectionPage.loggedIn.historyReason')}</p>
        <p>{t('dataProtectionPage.loggedIn.visitsSaved')}</p>
        <p>{t('dataProtectionPage.loggedIn.sightingsSaved')}</p>
      </section>

      {/* Objection & Opt-out */}
      <section className="mt-4">
        <h4 className="font-semibold">{t('dataProtectionPage.optOut.title')}</h4>
        <p>{t('dataProtectionPage.optOut.text')}</p>
      </section>

      <section className="mt-4">
        <h4>{t('dataProtectionPage.rights.title')}</h4>
        <p>
          <Trans
            i18nKey="dataProtectionPage.rights.text"
            components={{
              authority: (
                <a
                  href="https://www.ldi.nrw.de/kontakt/ihre-beschwerde"
                  className="underline"
                  target="_blank"
                  rel="noopener noreferrer"
                />
              ),
            }}
          />
        </p>
      </section>
    </div>
  );
}
