import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

// Simple footer matching the header color and linking to legal pages.
export default function Footer() {
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const { t } = useTranslation();
  return (
    <footer className="navbar navbar-dark bg-success mt-auto py-3">
      <div className="container-fluid justify-content-center">
        <Link className="nav-link footer-link" to={`${prefix}/impress`}>
          {t('nav.impress')}
        </Link>
        <span className="text-white mx-2">|</span>
        <Link className="nav-link footer-link" to={`${prefix}/data-protection`}>
          {t('nav.dataProtection')}
        </Link>
        <span className="text-white mx-2">|</span>
        <Link className="nav-link footer-link" to={`${prefix}/contact`}>
          {t('nav.contact')}
        </Link>
      </div>
    </footer>
  );
}
