import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

// Simple footer matching the header color and linking to legal pages.
export default function Footer() {
  const { lang } = useParams();
  const prefix = `/${lang}`;
  const { t } = useTranslation();
  // Ensure footer navigation resets the scroll position to the top of the page.
  const handleFooterNav = () => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  };
  return (
    <footer className="navbar navbar-dark bg-success mt-auto py-3">
      <div className="container-fluid justify-content-center">
        <Link className="nav-link footer-link" to={`${prefix}/legal-notice`} onClick={handleFooterNav}>
          {t('nav.legalNotice')}
        </Link>
        <span className="text-white mx-2">|</span>
        <Link className="nav-link footer-link" to={`${prefix}/data-protection`} onClick={handleFooterNav}>
          {t('nav.dataProtection')}
        </Link>
        <span className="text-white mx-2">|</span>
        <Link className="nav-link footer-link" to={`${prefix}/contact`} onClick={handleFooterNav}>
          {t('nav.contact')}
        </Link>
      </div>
    </footer>
  );
}
