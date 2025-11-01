import type { TFunction } from 'i18next';

import type { AnimalSummary, PopularAnimal, SiteSummary } from '../../types/domain';

export type LandingTranslator = TFunction<'common'>;

export interface LandingMapCoordinates {
  lat: number;
  lon: number;
}

export interface LandingSuggestionOption {
  id: string;
  key: string;
  type: 'animal' | 'zoo';
  value: string;
  displayName: string;
  subtitle: string;
  groupKey: 'animals' | 'zoos';
  groupLabel: string;
  firstInGroup: boolean;
  recordValue: string;
}

export interface LandingMetric {
  key: string;
  value: string;
  label: string;
}

export type RecentSearches = string[];

export type AnimalNameSource = Pick<AnimalSummary, 'name_en' | 'name_de'>;

export type LandingPopularAnimal = PopularAnimal;

export type LandingSiteSummary = SiteSummary;
