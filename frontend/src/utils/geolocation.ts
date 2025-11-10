import { Geolocation } from '@capacitor/geolocation';
import type { Position, PositionOptions } from '@capacitor/geolocation';

import { API } from '../api';

export interface GeolocationCoords {
  lat: number;
  lon: number;
}

export type GeolocationSource = 'gps' | 'cloudflare' | 'none';

// Shared timeout for geolocation requests (in milliseconds)
export const GEO_TIMEOUT_MS = 4000;
export const GEO_MAX_AGE_MS = 600000; // 10 minutes

// Default options for geolocation requests
export const DEFAULT_GEO_OPTIONS: PositionOptions = {
  enableHighAccuracy: false,
  timeout: GEO_TIMEOUT_MS,
  maximumAge: GEO_MAX_AGE_MS,
};

// Fetch location estimate from Cloudflare headers via API
async function getLocationFromAPI(signal?: AbortSignal): Promise<GeolocationCoords | null> {
  try {
    const response = await fetch(`${API}/location/estimate`, {
      ...(signal && { signal }),
      cache: 'no-store',
    });
    if (!response.ok) {
      return null;
    }
    const data = await response.json() as { latitude?: unknown; longitude?: unknown };
    const lat = typeof data.latitude === 'number' ? data.latitude : null;
    const lon = typeof data.longitude === 'number' ? data.longitude : null;
    
    if (lat !== null && lon !== null && Number.isFinite(lat) && Number.isFinite(lon)) {
      return { lat, lon };
    }
    return null;
  } catch (error) {
    console.warn('Failed to get location from API:', error);
    return null;
  }
}

// Wrapper for getCurrentPosition that returns a Promise with simplified coords
export async function getCurrentPosition(
  options: PositionOptions = DEFAULT_GEO_OPTIONS
): Promise<GeolocationCoords | null> {
  // SSR safety guard
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    const position: Position = await Geolocation.getCurrentPosition(options);
    const { latitude, longitude } = position.coords;
    
    if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
      return { lat: latitude, lon: longitude };
    }
    return null;
  } catch (error) {
    console.warn('Failed to get current position:', error);
    return null;
  }
}

// Get location with automatic fallback: tries GPS first, then Cloudflare estimate
export async function getCurrentPositionWithFallback(
  options: PositionOptions = DEFAULT_GEO_OPTIONS,
  signal?: AbortSignal
): Promise<{ coords: GeolocationCoords | null; source: GeolocationSource }> {
  // SSR safety guard
  if (typeof window === 'undefined') {
    return { coords: null, source: 'none' };
  }

  // Try GPS first
  const gpsCoords = await getCurrentPosition(options);
  if (gpsCoords !== null) {
    return { coords: gpsCoords, source: 'gps' };
  }

  // Fall back to Cloudflare estimate
  const apiCoords = await getLocationFromAPI(signal);
  if (apiCoords !== null) {
    return { coords: apiCoords, source: 'cloudflare' };
  }

  return { coords: null, source: 'none' };
}

// Wrapper for watchPosition
export async function watchPosition(
  options: PositionOptions,
  onSuccess: (coords: GeolocationCoords) => void,
  onError?: (error: unknown) => void
): Promise<string> {
  // SSR safety guard
  if (typeof window === 'undefined') {
    return 'noop-watch-id';
  }

  const watchId = await Geolocation.watchPosition(options, (position, err) => {
    if (err) {
      console.warn('Watch position error:', err);
      if (onError) {
        onError(err);
      }
    } else if (position) {
      const { latitude, longitude } = position.coords;
      if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
        onSuccess({ lat: latitude, lon: longitude });
      }
    }
  });
  
  return watchId;
}

// Clear a watch by ID
export async function clearWatch(watchId: string): Promise<void> {
  // SSR safety guard
  if (typeof window === 'undefined') {
    return;
  }

  await Geolocation.clearWatch({ id: watchId });
}

// Check location permissions
export async function checkPermissions() {
  // SSR safety guard
  if (typeof window === 'undefined') {
    return { location: 'denied' as const, coarseLocation: 'denied' as const };
  }

  return await Geolocation.checkPermissions();
}

// Request location permissions
export async function requestPermissions() {
  // SSR safety guard
  if (typeof window === 'undefined') {
    return { location: 'denied' as const, coarseLocation: 'denied' as const };
  }

  return await Geolocation.requestPermissions();
}
