import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import ZooDetail from '../components/ZooDetail';
import { API } from '../api';
import Seo from '../components/Seo';
import { getZooDisplayName } from '../utils/zooDisplayName.js';

// Page that fetches a single zoo and renders the ZooDetail component
export default function ZooDetailPage({ refresh, onLogged }) {
  const { slug, lang: langParam } = useParams();
  const [zoo, setZoo] = useState(null);
  const activeLang = langParam === 'de' ? 'de' : 'en';

  useEffect(() => {
    fetch(`${API}/zoos/${slug}`)
      .then((r) => r.json())
      .then(setZoo)
      .catch(() => setZoo(null));
  }, [slug]);

  if (!zoo) {
    return <div>Loading...</div>;
  }

  const displayName = getZooDisplayName(zoo);
  const slugOrId = zoo.slug || zoo.id || '';
  const localizedDescription = (() => {
    const candidates =
      activeLang === 'de'
        ? [zoo.seo_description_de, zoo.description_de, zoo.seo_description_en, zoo.description_en]
        : [zoo.seo_description_en, zoo.description_en, zoo.seo_description_de, zoo.description_de];
    const chosen = candidates.find((value) => typeof value === 'string' && value.trim().length > 0);
    if (!chosen) {
      return null;
    }
    return chosen.trim();
  })();

  const fallbackDescriptions = {
    en: `Learn about ${displayName} and track your visit.`,
    de: `Erfahre mehr über ${displayName} und plane deinen Besuch.`,
  };

  const metaDescription = localizedDescription || fallbackDescriptions[activeLang];

  const structuredData = {
    '@context': 'https://schema.org',
    '@type': 'Zoo',
    name: displayName,
    url: `https://zootracker.app/${activeLang}/zoos/${slugOrId}`,
    address: {
      '@type': 'PostalAddress',
      addressLocality: zoo.city || zoo.address || '',
      addressCountry: zoo.country || '',
    },
    description: metaDescription,
  };

  if (Number.isFinite(zoo.latitude) && Number.isFinite(zoo.longitude)) {
    structuredData.geo = {
      '@type': 'GeoCoordinates',
      latitude: zoo.latitude,
      longitude: zoo.longitude,
    };
  }

  return (
    <>
      <Seo
        title={displayName}
        description={metaDescription}
        jsonLd={structuredData}
      />
      <ZooDetail
        zoo={zoo}
        displayName={displayName}
        headingLevel="h1"
        refresh={refresh}
        onLogged={onLogged}
      />
    </>
  );
}
