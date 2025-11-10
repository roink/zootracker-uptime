import type { Coordinates } from '../utils/coordinates';

export interface CameraState {
  center: [number, number];
  zoom?: number;
  bearing?: number;
  pitch?: number;
}

export interface CameraViewChange extends CameraState {
  isUserInteraction?: boolean;
}

export interface LocationEstimate {
  lat: number;
  lon: number;
}

export interface RegionOption {
  id: string;
  name_en?: string | null;
  name_de?: string | null;
}

export interface RawZooRecord {
  id: string;
  slug?: string | null;
  name?: string | null;
  name_en?: string | null;
  name_de?: string | null;
  city?: string | null;
  country_name_en?: string | null;
  country_name_de?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  distance_km?: number | null;
  is_favorite?: boolean | null;
  location?: Coordinates | null | undefined | Record<string, unknown>;
  [key: string]: unknown;
}

export interface ZooListItem extends RawZooRecord {
  latitude?: number | null;
  longitude?: number | null;
}

export interface PaginatedZooPage {
  items: ZooListItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface ListFilters {
  q: string;
  continent: string;
  country: string;
  favoritesOnly: boolean;
  latitude: number | null;
  longitude: number | null;
}

export interface MapFilters {
  q: string;
  continent: string;
  country: string;
  favoritesOnly: boolean;
}

export interface RequestConfig {
  url: string | null;
  requiresAuth: boolean;
  ready: boolean;
}

export interface MapZooFeature extends ZooListItem {
  latitude: number;
  longitude: number;
}

export interface NormalizedCameraState {
  center: [number, number];
  zoom: number;
  bearing: number;
  pitch: number;
}
