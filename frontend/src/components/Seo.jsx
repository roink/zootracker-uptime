import React from 'react';
import { Helmet } from 'react-helmet-async';
import PropTypes from 'prop-types';

// Reusable component for setting page title and social meta tags.
export default function Seo({ title, description, image }) {
  // Base site URL used to resolve static assets
  const siteUrl = 'https://www.ZooTracker.app';
  const currentUrl =
    typeof window !== 'undefined' ? window.location.href : siteUrl;
  const imageUrl = image || `${siteUrl}/og-image.jpg`;
  return (
    <Helmet>
      <title>{title}</title>
      <link rel="canonical" href={currentUrl} />
      <meta name="description" content={description} />
      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      <meta property="og:url" content={currentUrl} />
      <meta property="og:type" content="website" />
      <meta property="og:image" content={imageUrl} />
      <meta property="og:site_name" content="ZooTracker" />
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
};
