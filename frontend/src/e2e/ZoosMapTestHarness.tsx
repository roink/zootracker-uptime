// @ts-nocheck
import { useCallback, useEffect, useMemo, useState } from 'react';

import ZoosMap from '../components/ZoosMap';
import { loadLocale } from '../i18n';

const DEFAULT_VIEW = { center: [13.405, 52.52], zoom: 5, bearing: 0, pitch: 0 };

function normalizeView(view) {
  if (!view || !Array.isArray(view.center) || view.center.length !== 2) {
    return DEFAULT_VIEW;
  }
  return {
    center: [Number(view.center[0]), Number(view.center[1])],
    zoom: Number.isFinite(view.zoom) ? view.zoom : DEFAULT_VIEW.zoom,
    bearing: Number.isFinite(view.bearing) ? view.bearing : DEFAULT_VIEW.bearing,
    pitch: Number.isFinite(view.pitch) ? view.pitch : DEFAULT_VIEW.pitch,
  };
}

export default function ZoosMapTestHarness() {
  const [zoos, setZoos] = useState<any[]>([]);
  const [view, setView] = useState(DEFAULT_VIEW);

  useEffect(() => {
    void loadLocale('en');
  }, []);

  useEffect(() => {
    window.__setZoosData = (entries) => {
      if (!Array.isArray(entries)) {
        setZoos([]);
        return;
      }
      const normalized = entries
        .map((entry, index) => {
          if (!entry) return null;
          const latitude = Number(entry.latitude ?? entry.lat);
          const longitude = Number(entry.longitude ?? entry.lon ?? entry.lng);
          if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
            return null;
          }
          const id = entry.id ?? `fixture-${index + 1}`;
          return {
            id,
            name: entry.name ?? `Fixture Zoo ${index + 1}`,
            latitude,
            longitude,
          };
        })
        .filter(Boolean);
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

  const initialView = useMemo(() => normalizeView(view), [view]);

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
