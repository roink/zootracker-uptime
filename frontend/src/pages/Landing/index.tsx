// @ts-nocheck
import { useQuery } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import About from './About';
import FinalCta from './FinalCta';
import Hero from './Hero';
import HowItWorks from './HowItWorks';
import Metrics from './Metrics';
import Paths from './Paths';
import Popular from './Popular';
import { API } from '../../api';
import Seo from '../../components/Seo';

// Marketing landing page that introduces ZooTracker and funnels visitors into the app.
export default function Landing() {
  const navigate = useNavigate();
  const params = useParams();
  const urlLang = typeof params.lang === 'string' && params.lang.length > 0 ? params.lang : 'en';
  const prefix = `/${urlLang}`;
  const { t, i18n } = useTranslation();

  const [recentSearches, setRecentSearches] = useState([]);
  const [mapCoords, setMapCoords] = useState({ lat: 50.9394, lon: 6.9583 });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const stored = window.localStorage.getItem('zt-landing-recents');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) setRecentSearches(parsed);
      }
    } catch (error) {
       
      console.warn('Failed to read recent searches', error);
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(
        'zt-landing-recents',
        JSON.stringify(recentSearches)
      );
    } catch (error) {
       
      console.warn('Failed to persist recent searches', error);
    }
  }, [recentSearches]);

  useEffect(() => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setMapCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude });
      },
      () => {},
      { enableHighAccuracy: false, timeout: 4000, maximumAge: 600000 }
    );
  }, []);

  const recordRecent = useCallback((term) => {
    const normalized = term.trim();
    if (!normalized) return;
    setRecentSearches((prev) => {
      const existing = prev.filter(
        (item) => item.toLowerCase() !== normalized.toLowerCase()
      );
      return [normalized, ...existing].slice(0, 5);
    });
  }, []);

    const handleNavigate = useCallback(
      (url) => {
        void navigate(url);
      },
      [navigate]
    );

  const numberFormatter = useMemo(() => {
    const locale = i18n.language || (urlLang === 'de' ? 'de-DE' : 'en-US');
    return new Intl.NumberFormat(locale);
  }, [i18n.language, urlLang]);

  const formatCount = useCallback(
    (value) => numberFormatter.format(value ?? 0),
    [numberFormatter]
  );

  const summaryQuery = useQuery({
    queryKey: ['site', 'summary'],
    queryFn: async () => {
      const response = await fetch(`${API}/site/summary`);
      if (!response.ok) {
        throw new Error('Failed to load site summary');
      }
      return response.json();
    },
    staleTime: 5 * 60 * 1000,
  });

  const popularQuery = useQuery({
    queryKey: ['site', 'popular-animals', 8],
    queryFn: async () => {
      const response = await fetch(`${API}/site/popular-animals?limit=8`);
      if (!response.ok) {
        throw new Error('Failed to load popular animals');
      }
      return response.json();
    },
    staleTime: 3 * 60 * 1000,
  });

  const metrics = useMemo(() => {
    const summary = summaryQuery.data;
    return [
      {
        key: 'species',
        value: summary ? formatCount(summary.species) : '—',
        label: t('landing.metrics.labels.species'),
      },
      {
        key: 'zoos',
        value: summary ? formatCount(summary.zoos) : '—',
        label: t('landing.metrics.labels.zoos'),
      },
      {
        key: 'countries',
        value: summary ? formatCount(summary.countries) : '—',
        label: t('landing.metrics.labels.countries'),
      },
      {
        key: 'sightings',
        value: summary ? formatCount(summary.sightings) : '—',
        label: t('landing.metrics.labels.sightings'),
      },
    ];
  }, [summaryQuery.data, formatCount, t]);

  const getAnimalName = useCallback(
    (animal) =>
      urlLang === 'de'
        ? animal.name_de || animal.name_en
        : animal.name_en || animal.name_de,
    [urlLang]
  );

  const organizationJsonLd = useMemo(
    () =>
      JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'Organization',
        name: 'ZooTracker',
        url: 'https://www.ZooTracker.app/',
        logo: 'https://www.ZooTracker.app/og-image.jpg',
      }),
    []
  );

  return (
    <div className="landing-page">
      <Seo
        title={t('landing.seo.title')}
        description={t('landing.seo.description')}
        canonical={`/${urlLang}`}
      />
      <Helmet>
        <link rel="preconnect" href="https://tiles.openfreemap.org" crossOrigin="anonymous" />
        <script type="application/ld+json">{organizationJsonLd}</script>
      </Helmet>
      <Hero
        t={t}
        prefix={prefix}
        recentSearches={recentSearches}
        onRecordRecent={recordRecent}
        onNavigate={handleNavigate}
        mapCoords={mapCoords}
        getAnimalName={getAnimalName}
      />
      <Paths t={t} prefix={prefix} />
      <Metrics
        t={t}
        metrics={metrics}
        isLoading={summaryQuery.isLoading}
        isError={summaryQuery.isError}
      />
      <About t={t} />
      <Popular
        t={t}
        prefix={prefix}
        popular={Array.isArray(popularQuery.data) ? popularQuery.data : []}
        isLoading={popularQuery.isLoading}
        isError={popularQuery.isError}
        getAnimalName={getAnimalName}
      />
      <HowItWorks t={t} />
      <FinalCta t={t} prefix={prefix} />
    </div>
  );
}
