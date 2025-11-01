import PropTypes from 'prop-types';
import { Helmet } from 'react-helmet-async';
import { useParams } from 'react-router-dom';

interface SeoProps {
  title: string;
  description?: string;
  image?: string;
  canonical?: string;
  jsonLd?: Record<string, unknown> | unknown[];
  robots?: string;
}

// Reusable component for setting page title and social meta tags.
export default function Seo({
  title,
  description,
  image,
  canonical,
  jsonLd,
  robots,
}: SeoProps) {
  const HelmetComponent = Helmet;
  const { lang } = useParams();
  const activeLang =
    typeof lang === 'string' && lang.length > 0 ? lang : 'en';
  const siteUrl = 'https://www.ZooTracker.app';
  const currentUrl =
    typeof window !== 'undefined' ? window.location.href : siteUrl;
  const canonicalUrl = canonical ? `${siteUrl}${canonical}` : currentUrl;
  const imageUrl = image || `${siteUrl}/og-image.jpg`;
  const other = activeLang === 'de' ? 'en' : 'de';
  const altPath =
    canonical ||
    (typeof window !== 'undefined'
      ? new URL(currentUrl).pathname
      : `/${activeLang}`);
  const alternateUrl = `${siteUrl}${altPath.replace(/^\/(en|de)/, `/${other}`)}`;
  const xDefaultUrl = `${siteUrl}${altPath.replace(/^\/(en|de)/, '/en')}`;
  const robotsContent =
    typeof robots === 'string' && robots.trim().length > 0 ? robots : null;
  return (
    <HelmetComponent>
      {/* Keep the html lang in sync for crawlers */}
      <html lang={activeLang} />
      <title>{title}</title>
      <link rel="canonical" href={canonicalUrl} />
      <link rel="alternate" hrefLang={activeLang} href={canonicalUrl} />
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
        content={activeLang === 'de' ? 'de_DE' : 'en_US'}
      />
      <meta
        property="og:locale:alternate"
        content={activeLang === 'de' ? 'en_US' : 'de_DE'}
      />
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={title} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={imageUrl} />
      {robotsContent ? <meta name="robots" content={robotsContent} /> : null}
      {jsonLd && (
        <script type="application/ld+json">
          {JSON.stringify(jsonLd, null, 2)}
        </script>
      )}
    </HelmetComponent>
  );
}

Seo.propTypes = {
  title: PropTypes.string.isRequired,
  description: PropTypes.string,
  image: PropTypes.string,
  canonical: PropTypes.string,
  jsonLd: PropTypes.oneOfType([PropTypes.object, PropTypes.array]),
  robots: PropTypes.string,
};
