import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import ZooDetail from '../components/ZooDetail';
import { API } from '../api';
import Seo from '../components/Seo';
import { getZooDisplayName } from '../utils/zooDisplayName.js';

// Page that fetches a single zoo and renders the ZooDetail component
export default function ZooDetailPage({ refresh, onLogged }) {
  const { slug } = useParams();
  const [zoo, setZoo] = useState(null);

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
  const structuredData = {
    '@context': 'https://schema.org',
    '@type': 'Zoo',
    name: displayName,
    url: `https://zootracker.app/zoos/${slugOrId}`,
    address: {
      '@type': 'PostalAddress',
      addressLocality: zoo.city || zoo.address || '',
      addressCountry: zoo.country || '',
    },
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
        description={`Learn about ${displayName} and track your visit.`}
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
