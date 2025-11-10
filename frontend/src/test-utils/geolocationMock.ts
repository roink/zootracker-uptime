import type { Position, PositionOptions } from '@capacitor/geolocation';
import { vi } from 'vitest';

// Mock implementation that simulates geolocation failure by default
export const mockGeolocation = {
  getCurrentPosition: vi.fn(
    (_options?: PositionOptions): Promise<Position> => {
      throw new Error('Geolocation not available');
    }
  ),
  watchPosition: vi.fn((_options: PositionOptions, callback: (position: Position | null, err?: unknown) => void) => {
    // Call error callback by default
    callback(null, new Error('Geolocation not available'));
    return Promise.resolve('mock-watch-id');
  }),
  clearWatch: vi.fn(() => Promise.resolve()),
  checkPermissions: vi.fn(() => Promise.resolve({
    location: 'denied' as const,
    coarseLocation: 'denied' as const,
  })),
  requestPermissions: vi.fn(() => Promise.resolve({
    location: 'denied' as const,
    coarseLocation: 'denied' as const,
  })),
};

// Mock success case
export function mockGeolocationSuccess(lat = 51.5074, lon = -0.1278) {
  const position: Position = {
    coords: {
      latitude: lat,
      longitude: lon,
      accuracy: 10,
      altitude: null,
      altitudeAccuracy: null,
      heading: null,
      speed: null,
    },
    timestamp: Date.now(),
  };

  mockGeolocation.getCurrentPosition.mockResolvedValue(position);
  mockGeolocation.watchPosition.mockImplementation(
    (_options: PositionOptions, callback: (position: Position | null, err?: unknown) => void) => {
      callback(position, undefined);
      return Promise.resolve('mock-watch-id');
    }
  );
}

// Mock error case
export function mockGeolocationError(errorMessage = 'Geolocation not available') {
  const error = new Error(errorMessage);
  
  mockGeolocation.getCurrentPosition.mockRejectedValue(error);
  mockGeolocation.watchPosition.mockImplementation(
    (_options: PositionOptions, callback: (position: Position | null, err?: unknown) => void) => {
      callback(null, error);
      return Promise.resolve('mock-watch-id');
    }
  );
}

// Reset all mocks
export function resetGeolocationMock() {
  mockGeolocation.getCurrentPosition.mockReset();
  mockGeolocation.watchPosition.mockReset();
  mockGeolocation.clearWatch.mockReset();
  mockGeolocation.checkPermissions.mockReset();
  mockGeolocation.requestPermissions.mockReset();
  mockGeolocationError(); // Set default to error
}

// Setup the mock module
vi.mock('@capacitor/geolocation', () => ({
  Geolocation: mockGeolocation,
}));
