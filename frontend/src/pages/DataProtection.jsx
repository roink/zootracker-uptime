import { Trans, useTranslation } from 'react-i18next';
import Seo from '../components/Seo';

// Detailed data protection information for the application.
export default function DataProtectionPage() {
  const { t, i18n } = useTranslation();

  return (
    <div className="container py-4">
      <Seo
        title={t('nav.dataProtection')}
        description={t('dataProtectionPage.seoDescription')}
      />
      <h2 className="text-2xl font-semibold">{t('dataProtectionPage.title')}</h2>
      <p>{t('dataProtectionPage.intro')}</p>

      {/* Controller & Contact (no DPO) */}
      <section className="mt-4">
        <h4 className="font-semibold">{t('dataProtectionPage.controller.title')}</h4>
        <p>
          {t('dataProtectionPage.controller.text')}{' '}
          {i18n.language === 'de' ? (
            <>
              (<a href="/de/impress" className="underline" rel="noopener noreferrer">Impressum</a>,{' '}
              <a href="/de/contact" className="underline" rel="noopener noreferrer">Kontakt</a>)
            </>
          ) : (
            <>
              (<a href="/de/impress" className="underline" rel="noopener noreferrer">Impressum</a>,{' '}
              <a href="/de/contact" className="underline" rel="noopener noreferrer">Contact</a>)
            </>
          )}
        </p>
      </section>

      <section className="mt-4">
        <h4>{t('dataProtectionPage.logging.title')}</h4>
        <p>{t('dataProtectionPage.logging.raw')}</p>
        <p>{t('dataProtectionPage.logging.anonymized')}</p>
        <p>{t('dataProtectionPage.logging.geolocation')}</p>
        <p>{t('dataProtectionPage.logging.justification')}</p>
      </section>

      <section className="mt-4">
        <h4>{t('dataProtectionPage.legalBasis.title')}</h4>
        <p>{t('dataProtectionPage.legalBasis.text')}</p>
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
        </ul>
      </section>

      <section className="mt-4">
        <h4 className="font-semibold">{t('dataProtectionPage.transfers.title')}</h4>
        <p>{t('dataProtectionPage.transfers.text')}</p>
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
        <p>{t('dataProtectionPage.optOut.text')}{' '}
          (<a href="https://globalprivacycontrol.org/" className="underline" target="_blank" rel="noopener noreferrer">GPC</a>)
        </p>
      </section>

      <section className="mt-4">
        <h4>{t('dataProtectionPage.rights.title')}</h4>
        <p>
          {t('dataProtectionPage.rights.text')}{' '}
          {i18n.language === 'de' ? (
            <a href="https://www.ldi.nrw.de/kontakt/ihre-beschwerde" className="underline" target="_blank" rel="noopener noreferrer">LDI&nbsp;NRW</a>
          ) : (
            <a href="https://www.edpb.europa.eu/about-edpb/about-edpb/members_en" className="underline" target="_blank" rel="noopener noreferrer">List of authorities (EDPB)</a>
          )}
        </p>
      </section>
    </div>
  );
}
