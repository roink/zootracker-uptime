import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { getCurrentPosition, getCurrentPositionWithFallback, DEFAULT_GEO_OPTIONS, GEO_TIMEOUT_MS, GEO_MAX_AGE_MS } from './geolocation';
import { mockGeolocationSuccess, mockGeolocationError } from '../test-utils/geolocationMock';

describe('geolocation utility', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    // Reset is handled globally in tests/setup.ts
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  describe('getCurrentPosition', () => {
    it('returns coordinates on success', async () => {
      mockGeolocationSuccess(51.5074, -0.1278);
      
      const result = await getCurrentPosition(DEFAULT_GEO_OPTIONS);
      
      expect(result).toEqual({
        lat: 51.5074,
        lon: -0.1278,
      });
    });

    it('returns null on error', async () => {
      mockGeolocationError('Permission denied');
      
      const result = await getCurrentPosition(DEFAULT_GEO_OPTIONS);
      
      expect(result).toBeNull();
    });

    it('returns null for invalid coordinates', async () => {
      mockGeolocationSuccess(Number.NaN, 0);
      
      const result = await getCurrentPosition(DEFAULT_GEO_OPTIONS);
      
      expect(result).toBeNull();
    });

    it('uses default options when none provided', async () => {
      mockGeolocationSuccess(48.8566, 2.3522);
      
      const result = await getCurrentPosition();
      
      expect(result).toEqual({
        lat: 48.8566,
        lon: 2.3522,
      });
    });
  });

  describe('getCurrentPositionWithFallback', () => {
    it('returns GPS coordinates when available', async () => {
      mockGeolocationSuccess(51.5074, -0.1278);
      
      const result = await getCurrentPositionWithFallback(DEFAULT_GEO_OPTIONS);
      
      expect(result).toEqual({
        coords: { lat: 51.5074, lon: -0.1278 },
        source: 'gps',
      });
    });

    it('falls back to API when GPS fails', async () => {
      mockGeolocationError('Permission denied');
      
      // Mock the API response
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ latitude: 52.52, longitude: 13.405 }),
      } as Response);
      
      const result = await getCurrentPositionWithFallback(DEFAULT_GEO_OPTIONS);
      
      expect(result).toEqual({
        coords: { lat: 52.52, lon: 13.405 },
        source: 'cloudflare',
      });
    });

    it('returns none when both GPS and API fail', async () => {
      mockGeolocationError('Permission denied');
      
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ latitude: null, longitude: null }),
      } as Response);
      
      const result = await getCurrentPositionWithFallback(DEFAULT_GEO_OPTIONS);
      
      expect(result).toEqual({
        coords: null,
        source: 'none',
      });
    });

    it('returns none when request is aborted', async () => {
      mockGeolocationError('Permission denied');
      
      const controller = new AbortController();
      
      // Mock fetch to delay and then check if aborted
      global.fetch = vi.fn().mockImplementation(() => {
        controller.abort();
        return Promise.reject(new DOMException('Aborted', 'AbortError'));
      });
      
      const result = await getCurrentPositionWithFallback(DEFAULT_GEO_OPTIONS, controller.signal);
      
      expect(result).toEqual({
        coords: null,
        source: 'none',
      });
    });
  });

  describe('constants', () => {
    it('exports consistent timeout values', () => {
      expect(GEO_TIMEOUT_MS).toBe(4000);
      expect(GEO_MAX_AGE_MS).toBe(600000);
    });

    it('default options use shared constants', () => {
      expect(DEFAULT_GEO_OPTIONS.timeout).toBe(GEO_TIMEOUT_MS);
      expect(DEFAULT_GEO_OPTIONS.maximumAge).toBe(GEO_MAX_AGE_MS);
      expect(DEFAULT_GEO_OPTIONS.enableHighAccuracy).toBe(false);
    });
  });
});
