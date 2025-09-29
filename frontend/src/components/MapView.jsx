import { useEffect, useRef } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';

import { applyBaseMapLanguage } from '../utils/mapLanguage.js';

// Reusable map centered on given coordinates using MapLibre and OpenFreeMap tiles.
export const MAP_STYLE_URL =
  import.meta.env.VITE_MAP_STYLE_URL ||
  'https://tiles.openfreemap.org/styles/liberty';

export default function MapView({ latitude, longitude, zoom = 14 }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const { i18n } = useTranslation();

  // Initialize map once on mount
  useEffect(() => {
    if (!containerRef.current) return;
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return;

    let cancelled = false;

    (async () => {
      // Dynamically load MapLibre so the heavy library only loads when needed
      const { default: maplibregl } = await import('maplibre-gl');
      if (cancelled) return;

      mapRef.current = new maplibregl.Map({
        container: containerRef.current,
        style: MAP_STYLE_URL,
        center: [longitude, latitude],
        zoom,
        attributionControl: true,
      });

      if (mapRef.current?.on) {
        mapRef.current.on('load', () => {
          applyBaseMapLanguage(mapRef.current, i18n.language);
        });
      }

      markerRef.current = new maplibregl.Marker()
        .setLngLat([longitude, latitude])
        .addTo(mapRef.current);
    })();

    return () => {
      cancelled = true;
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

MapView.propTypes = {
  latitude: PropTypes.number,
  longitude: PropTypes.number,
  zoom: PropTypes.number,
};

