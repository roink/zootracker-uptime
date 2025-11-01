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
import type {
  AnimalNameSource,
  LandingMapCoordinates,
  LandingMetric,
  LandingPopularAnimal,
  LandingSiteSummary,
  RecentSearches
} from './types';
import { API } from '../../api';
import Seo from '../../components/Seo';

const STORAGE_KEY = 'zt-landing-recents';
const DEFAULT_COORDS: LandingMapCoordinates = { lat: 50.9394, lon: 6.9583 };
const RECENT_LIMIT = 5;

type LandingRouteParams = {
  lang?: string;
};

type UnknownRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === 'object' && value !== null;

const isStringArray = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === 'string');

const parseSiteSummary = (value: unknown): LandingSiteSummary => {
  if (!isRecord(value)) {
    throw new Error('Invalid site summary payload');
  }
  const readCount = (input: unknown): number =>
    typeof input === 'number' && Number.isFinite(input) ? input : 0;
  return {
    species: readCount(value.species),
    zoos: readCount(value.zoos),
    countries: readCount(value.countries),
    sightings: readCount(value.sightings)
  };
};

const parsePopularAnimals = (value: unknown): LandingPopularAnimal[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  const animals: LandingPopularAnimal[] = [];
  value.forEach((entry) => {
    if (!isRecord(entry) || typeof entry.id !== 'string') {
      return;
    }
    const slug = typeof entry.slug === 'string' && entry.slug.length > 0 ? entry.slug : undefined;
    const nameEn =
      typeof entry.name_en === 'string'
        ? entry.name_en
        : entry.name_en === null
          ? null
          : undefined;
    const nameDe =
      typeof entry.name_de === 'string'
        ? entry.name_de
        : entry.name_de === null
          ? null
          : undefined;
    const scientificName =
      typeof entry.scientific_name === 'string'
        ? entry.scientific_name
        : entry.scientific_name === null
          ? null
          : undefined;
    const zooCount =
      typeof entry.zoo_count === 'number' && Number.isFinite(entry.zoo_count)
        ? entry.zoo_count
        : null;
    const conservation =
      typeof entry.iucn_conservation_status === 'string'
        ? entry.iucn_conservation_status
        : entry.iucn_conservation_status === null
          ? null
          : undefined;
    const imageUrl =
      typeof entry.default_image_url === 'string'
        ? entry.default_image_url
        : entry.default_image_url === null
          ? null
          : undefined;

    const animal: LandingPopularAnimal = {
      id: entry.id,
      zoo_count: zooCount,
      iucn_conservation_status: conservation ?? null,
      default_image_url: imageUrl ?? null
    };

    if (slug) {
      animal.slug = slug;
    }
    if (nameEn !== undefined) {
      animal.name_en = nameEn;
    }
    if (nameDe !== undefined) {
      animal.name_de = nameDe;
    }
    if (scientificName !== undefined) {
      animal.scientific_name = scientificName;
    }

    animals.push(animal);
  });
  return animals;
};

const readStoredSearches = (): RecentSearches => {
  if (typeof window === 'undefined') {
    return [];
  }
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return [];
    }
    const parsed = JSON.parse(stored) as unknown;
    return isStringArray(parsed) ? parsed.slice(0, RECENT_LIMIT) : [];
  } catch (error) {
    console.warn('Failed to read recent searches', error);
    return [];
  }
};

// Marketing landing page that introduces ZooTracker and funnels visitors into the app.
export default function Landing() {
  const navigate = useNavigate();
  const params = useParams<LandingRouteParams>();
  const urlLang = typeof params.lang === 'string' && params.lang.length > 0 ? params.lang : 'en';
  const prefix = `/${urlLang}`;
  const { t, i18n } = useTranslation();

  const [recentSearches, setRecentSearches] = useState<RecentSearches>(() => readStoredSearches());
  const [mapCoords, setMapCoords] = useState<LandingMapCoordinates>(DEFAULT_COORDS);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(recentSearches));
    } catch (error) {
      console.warn('Failed to persist recent searches', error);
    }
  }, [recentSearches]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const { navigator } = window;
    if (!('geolocation' in navigator)) {
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
          setMapCoords({ lat: latitude, lon: longitude });
        }
      },
      () => undefined,
      { enableHighAccuracy: false, timeout: 4000, maximumAge: 600000 }
    );
  }, []);

  const recordRecent = useCallback((term: string) => {
    const normalized = term.trim();
    if (!normalized) return;
    setRecentSearches((prev) => {
      const existing = prev.filter(
        (item) => item.toLowerCase() !== normalized.toLowerCase()
      );
      return [normalized, ...existing].slice(0, RECENT_LIMIT);
    });
  }, []);

  const handleNavigate = useCallback(
    (url: string) => {
      void navigate(url);
    },
    [navigate]
  );

  const numberFormatter = useMemo(() => {
    const locale = i18n.language || (urlLang === 'de' ? 'de-DE' : 'en-US');
    return new Intl.NumberFormat(locale);
  }, [i18n.language, urlLang]);

  const formatCount = useCallback(
    (value: number | null | undefined) => numberFormatter.format(value ?? 0),
    [numberFormatter]
  );

  const summaryQuery = useQuery<LandingSiteSummary>({
    queryKey: ['site', 'summary'],
    queryFn: async () => {
      const response = await fetch(`${API}/site/summary`);
      if (!response.ok) {
        throw new Error('Failed to load site summary');
      }
      const body = (await response.json()) as unknown;
      return parseSiteSummary(body);
    },
    staleTime: 5 * 60 * 1000
  });

  const popularQuery = useQuery<LandingPopularAnimal[]>({
    queryKey: ['site', 'popular-animals', 8],
    queryFn: async () => {
      const response = await fetch(`${API}/site/popular-animals?limit=8`);
      if (!response.ok) {
        throw new Error('Failed to load popular animals');
      }
      const body = (await response.json()) as unknown;
      return parsePopularAnimals(body);
    },
    staleTime: 3 * 60 * 1000
  });

  const metrics = useMemo<LandingMetric[]>(() => {
    const summary = summaryQuery.data;
    return [
      {
        key: 'species',
        value: summary ? formatCount(summary.species) : '—',
        label: t('landing.metrics.labels.species')
      },
      {
        key: 'zoos',
        value: summary ? formatCount(summary.zoos) : '—',
        label: t('landing.metrics.labels.zoos')
      },
      {
        key: 'countries',
        value: summary ? formatCount(summary.countries) : '—',
        label: t('landing.metrics.labels.countries')
      },
      {
        key: 'sightings',
        value: summary ? formatCount(summary.sightings) : '—',
        label: t('landing.metrics.labels.sightings')
      }
    ];
  }, [summaryQuery.data, formatCount, t]);

  const getAnimalName = useCallback(
    (animal: AnimalNameSource) =>
      urlLang === 'de'
        ? animal.name_de || animal.name_en || undefined
        : animal.name_en || animal.name_de || undefined,
    [urlLang]
  );

  const organizationJsonLd = useMemo(
    () =>
      JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'Organization',
        name: 'ZooTracker',
        url: 'https://www.ZooTracker.app/',
        logo: 'https://www.ZooTracker.app/og-image.jpg'
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
        popular={popularQuery.data ?? []}
        isLoading={popularQuery.isLoading}
        isError={popularQuery.isError}
        getAnimalName={getAnimalName}
      />
      <HowItWorks t={t} />
      <FinalCta t={t} prefix={prefix} />
    </div>
  );
}
