import { useTranslation } from 'react-i18next';
import Seo from '../components/Seo';

// Detailed data protection information for the application.
export default function DataProtectionPage() {
  const { t } = useTranslation();

  return (
    <div className="container py-4">
      <Seo
        title={t('nav.dataProtection')}
        description={t('dataProtectionPage.seoDescription')}
      />
      <h2>{t('dataProtectionPage.title')}</h2>
      <p>{t('dataProtectionPage.intro')}</p>

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

      <section className="mt-4">
        <h4>{t('dataProtectionPage.rights.title')}</h4>
        <p>{t('dataProtectionPage.rights.text')}</p>
      </section>
    </div>
  );
}
