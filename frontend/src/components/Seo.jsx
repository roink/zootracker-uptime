import { Helmet } from 'react-helmet-async';
import PropTypes from 'prop-types';
import { useParams } from 'react-router-dom';

// Reusable component for setting page title and social meta tags.
export default function Seo({ title, description, image, canonical }) {
  const { lang } = useParams();
  const siteUrl = 'https://www.ZooTracker.app';
  const currentUrl =
    typeof window !== 'undefined' ? window.location.href : siteUrl;
  const canonicalUrl = canonical ? `${siteUrl}${canonical}` : currentUrl;
  const imageUrl = image || `${siteUrl}/og-image.jpg`;
  const other = lang === 'de' ? 'en' : 'de';
  const altPath =
    canonical ||
    (typeof window !== 'undefined'
      ? new URL(currentUrl).pathname
      : `/${lang}`);
  const alternateUrl = `${siteUrl}${altPath.replace(/^\/(en|de)/, `/${other}`)}`;
  const xDefaultUrl = `${siteUrl}${altPath.replace(/^\/(en|de)/, '/en')}`;
  return (
    <Helmet>
      {/* Keep the html lang in sync for crawlers */}
      <html lang={lang} />
      <title>{title}</title>
      <link rel="canonical" href={canonicalUrl} />
      <link rel="alternate" hrefLang={lang} href={canonicalUrl} />
      <link rel="alternate" hrefLang={other} href={alternateUrl} />
      <link rel="alternate" hrefLang="x-default" href={xDefaultUrl} />
      <meta name="description" content={description} />
      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      <meta property="og:url" content={canonicalUrl} />
      <meta property="og:type" content="website" />
      <meta property="og:image" content={imageUrl} />
      <meta property="og:site_name" content="ZooTracker" />
      <meta
        property="og:locale"
        content={lang === 'de' ? 'de_DE' : 'en_US'}
      />
      <meta
        property="og:locale:alternate"
        content={lang === 'de' ? 'en_US' : 'de_DE'}
      />
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={title} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={imageUrl} />
    </Helmet>
  );
}

Seo.propTypes = {
  title: PropTypes.string.isRequired,
  description: PropTypes.string,
  image: PropTypes.string,
  canonical: PropTypes.string,
};
