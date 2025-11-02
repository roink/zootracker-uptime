import type { Map as MapLibreMap, Marker as MapLibreMarker } from 'maplibre-gl';
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { applyBaseMapLanguage } from '../utils/mapLanguage';

// Reusable map centered on given coordinates using MapLibre and OpenFreeMap tiles.
export const MAP_STYLE_URL =
  import.meta.env['VITE_MAP_STYLE_URL'] ||
  'https://tiles.openfreemap.org/styles/liberty';

interface MapViewProps {
  latitude: number;
  longitude: number;
  zoom?: number;
}

export default function MapView({ latitude, longitude, zoom = 14 }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markerRef = useRef<MapLibreMarker | null>(null);
  const { i18n } = useTranslation();

  // Initialize map once on mount
  useEffect(() => {
    const containerElement = containerRef.current;
    if (!containerElement) return;
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return;

    void (async () => {
      // Dynamically load MapLibre so the heavy library only loads when needed
      const { default: maplibregl } = await import('maplibre-gl');
      if (!containerElement.isConnected) return;

      const mapInstance = new maplibregl.Map({
        container: containerElement,
        style: MAP_STYLE_URL,
        center: [longitude, latitude],
        zoom,
      });

      mapRef.current = mapInstance;

      mapInstance.on('load', () => {
        applyBaseMapLanguage(mapInstance, i18n.language);
      });

      markerRef.current = new maplibregl.Marker()
        .setLngLat([longitude, latitude])
        .addTo(mapInstance);
    })();

    return () => {
      mapRef.current?.remove();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Update center and marker when coordinates change
  useEffect(() => {
    if (!mapRef.current) return;
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return;
    mapRef.current.setCenter([longitude, latitude]);
    if (markerRef.current) markerRef.current.setLngLat([longitude, latitude]);
  }, [latitude, longitude]);

  useEffect(() => {
    if (!mapRef.current) return;
    applyBaseMapLanguage(mapRef.current, i18n.language);
  }, [i18n.language]);

  return (
    <div
      ref={containerRef}
      className="map-container"
      role="region"
      aria-label="Map showing zoo location"
    />
  );
}
