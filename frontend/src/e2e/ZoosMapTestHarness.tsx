import { useCallback, useEffect, useMemo, useState } from 'react';

import ZoosMap from '../components/ZoosMap';
import { loadLocale } from '../i18n';
import type { CameraState, NormalizedCameraState } from '../types/zoos';

const DEFAULT_VIEW: NormalizedCameraState = {
  center: [13.405, 52.52] as [number, number],
  zoom: 5,
  bearing: 0,
  pitch: 0,
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

type HarnessView = {
  center?: unknown;
  zoom?: unknown;
  bearing?: unknown;
  pitch?: unknown;
};

function normalizeView(view: unknown): CameraState {
  const candidate = view as HarnessView | null | undefined;
  if (!candidate || !Array.isArray(candidate.center) || candidate.center.length !== 2) {
    return DEFAULT_VIEW;
  }
  const [lng, lat] = candidate.center as [unknown, unknown];
  const center: [number, number] = [Number(lng), Number(lat)];
  const zoom =
    typeof candidate.zoom === 'number' && Number.isFinite(candidate.zoom)
      ? candidate.zoom
      : DEFAULT_VIEW.zoom;
  const bearing =
    typeof candidate.bearing === 'number' && Number.isFinite(candidate.bearing)
      ? candidate.bearing
      : DEFAULT_VIEW.bearing;
  const pitch =
    typeof candidate.pitch === 'number' && Number.isFinite(candidate.pitch)
      ? candidate.pitch
      : DEFAULT_VIEW.pitch;
  return {
    center,
    zoom,
    bearing,
    pitch,
  };
}

type HarnessZoo = { id: string; name: string; latitude: number; longitude: number };

declare global {
  interface Window {
    __setZoosData?: (entries: unknown) => void;
    __setInitialView?: (view: unknown) => void;
    __mapHarnessReady?: boolean;
    __mapInstance?: unknown;
    __mapInstanceReady?: boolean;
    __waitForIdle?: () => Promise<void>;
    __currentZooCount?: number;
  }
}

export default function ZoosMapTestHarness() {
  const [zoos, setZoos] = useState<HarnessZoo[]>([]);
  const [view, setView] = useState<CameraState>(DEFAULT_VIEW);

  useEffect(() => {
    void loadLocale('en');
  }, []);

  useEffect(() => {
    window.__setZoosData = (entries) => {
      if (!Array.isArray(entries)) {
        setZoos([]);
        return;
      }
        const normalized = (entries as unknown[])
          .map((rawEntry, index) => {
            if (!isRecord(rawEntry)) {
              return null;
            }
            const entry = rawEntry;
          const pickNumber = (value: unknown): number | null => {
            if (typeof value === 'number') return Number.isFinite(value) ? value : null;
            if (typeof value === 'string') {
              const parsed = Number(value);
              return Number.isFinite(parsed) ? parsed : null;
            }
            return null;
          };
          const latitudeCandidate =
            pickNumber((entry as { latitude?: unknown }).latitude) ??
            pickNumber((entry as { lat?: unknown }).lat);
          const longitudeCandidate =
            pickNumber((entry as { longitude?: unknown }).longitude) ??
            pickNumber((entry as { lon?: unknown }).lon) ??
            pickNumber((entry as { lng?: unknown }).lng);
          if (latitudeCandidate === null || longitudeCandidate === null) {
            return null;
          }
          const idRaw = entry['id'];
          const idValue =
            typeof idRaw === 'string' || typeof idRaw === 'number'
              ? idRaw
              : `fixture-${index + 1}`;
          return {
            id: String(idValue),
            name:
              typeof entry['name'] === 'string'
                ? entry['name']
                : `Fixture Zoo ${index + 1}`,
            latitude: latitudeCandidate,
            longitude: longitudeCandidate,
          };
        })
          .filter((value): value is { id: string; name: string; latitude: number; longitude: number } => value !== null);
        setZoos(normalized);
      };

    window.__setInitialView = (nextView) => {
      setView(normalizeView(nextView));
    };

    window.__mapHarnessReady = true;

    return () => {
      delete window.__setZoosData;
      delete window.__setInitialView;
      delete window.__mapHarnessReady;
    };
  }, []);

  useEffect(() => {
    window.__currentZooCount = zoos.length;
    return () => {
      delete window.__currentZooCount;
    };
  }, [zoos]);

  const handleMapReady = useCallback((map) => {
    window.__mapInstance = map;
    window.__mapInstanceReady = true;
    window.__waitForIdle = () =>
      new Promise((resolve) => {
        if (!map || typeof map.once !== 'function') {
          resolve();
          return;
        }
        const shouldResolveImmediately =
          typeof map.isStyleLoaded === 'function' &&
          typeof map.isMoving === 'function' &&
          map.isStyleLoaded() &&
          !map.isMoving();
        if (shouldResolveImmediately) {
          resolve();
          return;
        }
        map.once('idle', () => {
          resolve();
        });
      });
  }, []);

  useEffect(
    () => () => {
      delete window.__mapInstance;
      delete window.__mapInstanceReady;
      delete window.__waitForIdle;
    },
    []
  );

  const initialView = useMemo<CameraState>(() => normalizeView(view), [view]);

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div style={{ width: '800px', height: '600px' }}>
        <ZoosMap
          ariaLabel="E2E zoos map"
          initialView={initialView}
          suppressAutoFit
          zoos={zoos}
          onMapReady={handleMapReady}
          disableClusterCount
        />
      </div>
    </div>
  );
}
