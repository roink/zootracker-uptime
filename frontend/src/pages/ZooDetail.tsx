// @ts-nocheck
import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import ZooDetail from '../components/ZooDetail';
import { API } from '../api';
import Seo from '../components/Seo';
import { getZooDisplayName } from '../utils/zooDisplayName';
import { normalizeLang } from '../i18n';
import useAuthFetch from '../hooks/useAuthFetch';

const META_DESCRIPTION_LIMIT = 160;

// Sanitize description copy for SEO snippets by removing tags, collapsing whitespace and truncating at word boundaries.
function sanitizeDescription(value) {
  if (typeof value !== 'string') {
    return '';
  }
  const withoutTags = value.replace(/<[^>]*>/g, ' ');
  const collapsed = withoutTags.replace(/\s+/g, ' ').trim();
  if (collapsed.length <= META_DESCRIPTION_LIMIT) {
    return collapsed;
  }
  const truncated = collapsed.slice(0, META_DESCRIPTION_LIMIT);
  const lastSpace = truncated.lastIndexOf(' ');
  if (lastSpace > 0) {
    return `${truncated.slice(0, lastSpace).trim()}…`;
  }
  return `${truncated.trim()}…`;
}

// Page that fetches a single zoo and renders the ZooDetail component
export default function ZooDetailPage({ refresh, onLogged }: any) {
  const { slug, lang: langParam } = useParams();
  const [zoo, setZoo] = useState<any>(null);
  const { i18n } = useTranslation();
  const authFetch = useAuthFetch();
  const urlLang = typeof langParam === 'string' ? normalizeLang(langParam) : null;
  const detectedLang = normalizeLang(i18n.language);
  const activeLang = urlLang ?? detectedLang;
  const t = useMemo(
    () => i18n.getFixedT(activeLang, 'translation'),
    [i18n, activeLang],
  );

  useEffect(() => {
    const controller = new AbortController();
    setZoo(null);
    (async () => {
      try {
        const response = await authFetch(`${API}/zoos/${slug}`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        setZoo(data);
      } catch (err) {
        if (!controller.signal.aborted) {
          setZoo(null);
        }
      }
    })();
    return () => controller.abort();
  }, [slug, authFetch]);

  const displayName = useMemo(
    () => (zoo ? getZooDisplayName(zoo) : ''),
    [zoo],
  );
  const fallbackName = (displayName || slug || '').trim();
  const metaDescription = useMemo(() => {
    if (!zoo) {
      const fallbackCopy = t('zoo.seoFallback', { name: fallbackName });
      return sanitizeDescription(fallbackCopy);
    }
    const candidates =
      activeLang === 'de'
        ? [
            zoo.seo_description_de,
            zoo.description_de,
            zoo.seo_description_en,
            zoo.description_en,
          ]
        : [
            zoo.seo_description_en,
            zoo.description_en,
            zoo.seo_description_de,
            zoo.description_de,
          ];
    const chosen = candidates.find(
      (value) => typeof value === 'string' && value.trim().length > 0,
    );
    const fallbackCopy = t('zoo.seoFallback', {
      name: (displayName || zoo?.name || fallbackName).trim(),
    });
    return sanitizeDescription(chosen ?? fallbackCopy);
  }, [activeLang, zoo, t, displayName, fallbackName]);

  if (!zoo) {
    const loadingPath = slug ? `/${activeLang}/zoos/${slug}` : `/${activeLang}/zoos`;
    return (
      <>
        <Seo title={fallbackName} description={metaDescription} canonical={loadingPath} />
        <div>Loading...</div>
      </>
    );
  }

  const slugOrId = zoo.slug || zoo.id || '';

  const localizedPath = `/${activeLang}/zoos/${slugOrId}`;

  const structuredData = {
    '@context': 'https://schema.org',
    '@type': 'Zoo',
    '@id': `https://zootracker.app${localizedPath}#zoo`,
    name: displayName,
    url: `https://zootracker.app${localizedPath}`,
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
        canonical={localizedPath}
        jsonLd={structuredData}
      />
      <ZooDetail
        zoo={zoo}
        displayName={displayName}
        headingLevel="h1"
        refresh={refresh}
        onLogged={onLogged}
        onFavoriteChange={(next) =>
          setZoo((prev) => (prev ? { ...prev, is_favorite: next } : prev))
        }
      />
    </>
  );
}
