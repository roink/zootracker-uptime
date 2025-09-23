import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { MAP_STYLE_URL } from './MapView.jsx';

// Interactive map showing multiple zoos with clickable markers.
const DEFAULT_ZOOM = 5;
const FOCUS_ZOOM = 8;

export default function ZoosMap({ zoos, center, onSelect, resizeToken }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const maplibreRef = useRef(null);
  const markersRef = useRef([]);
  const pendingResizeRef = useRef(false);
  const resizeCleanupsRef = useRef([]);
  const { t } = useTranslation();
  const [mapReady, setMapReady] = useState(false);

  const centerLat = center?.lat;
  const centerLon = center?.lon;

  const normalizedZoos = useMemo(
    () =>
      (zoos || [])
        .map((zoo) => {
          const rawLat = zoo.latitude;
          const rawLon = zoo.longitude;
          if (
            rawLat === null ||
            rawLat === undefined ||
            rawLat === '' ||
            rawLon === null ||
            rawLon === undefined ||
            rawLon === ''
          ) {
            return null;
          }

          const latitude = Number(rawLat);
          const longitude = Number(rawLon);
          if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
            return null;
          }
          return { ...zoo, latitude, longitude };
        })
        .filter(Boolean),
    [zoos]
  );

  const fallbackZoo = useMemo(
    () => (normalizedZoos.length > 0 ? normalizedZoos[0] : null),
    [normalizedZoos]
  );

  const initialState = useMemo(() => {
    if (Number.isFinite(centerLat) && Number.isFinite(centerLon)) {
      return { coords: [centerLon, centerLat], zoom: FOCUS_ZOOM };
    }
    if (
      fallbackZoo &&
      Number.isFinite(fallbackZoo.latitude) &&
      Number.isFinite(fallbackZoo.longitude)
    ) {
      return {
        coords: [fallbackZoo.longitude, fallbackZoo.latitude],
        zoom: DEFAULT_ZOOM,
      };
    }
    return null;
  }, [centerLat, centerLon, fallbackZoo]);

  const clearMarkers = () => {
    markersRef.current.forEach(({ marker, handleClick, handleKeyDown }) => {
      const element = marker.getElement();
      if (handleClick) element.removeEventListener('click', handleClick);
      if (handleKeyDown) element.removeEventListener('keydown', handleKeyDown);
      marker.remove();
    });
    markersRef.current = [];
  };

  const scheduleResize = useCallback(() => {
    if (!mapRef.current) return () => {};
    mapRef.current.resize();
    if (typeof window === 'undefined') {
      return () => {};
    }

    const frame = window.requestAnimationFrame(() => {
      mapRef.current?.resize();
    });
    const timeout = window.setTimeout(() => {
      mapRef.current?.resize();
    }, 150);

    const cleanup = () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timeout);
    };

    resizeCleanupsRef.current.push(cleanup);
    return cleanup;
  }, []);

  // Initialize the map when we have a target center.
  useEffect(() => {
    if (mapRef.current) return;
    if (!containerRef.current) return;
    if (!initialState) return;

    let cancelled = false;

    (async () => {
      const { default: maplibregl } = await import('maplibre-gl');
      if (cancelled) return;

      maplibreRef.current = maplibregl;
      mapRef.current = new maplibregl.Map({
        container: containerRef.current,
        style: MAP_STYLE_URL,
        center: initialState.coords,
        zoom: initialState.zoom,
        attributionControl: true,
      });

      setMapReady(true);

      if (pendingResizeRef.current || typeof window !== 'undefined') {
        pendingResizeRef.current = false;
        if (mapRef.current?.once) {
          mapRef.current.once('load', scheduleResize);
        } else {
          scheduleResize();
        }
      }
    })();

    return () => {
      cancelled = true;
      resizeCleanupsRef.current.forEach((cleanup) => cleanup());
      resizeCleanupsRef.current = [];
      clearMarkers();
      mapRef.current?.remove();
      mapRef.current = null;
      maplibreRef.current = null;
    };
  }, [initialState, scheduleResize]);

  // Keep the map centered on the user/estimated location when it becomes available.
  useEffect(() => {
    if (!mapRef.current) return;
    if (!Number.isFinite(centerLat) || !Number.isFinite(centerLon)) return;

    mapRef.current.easeTo({
      center: [centerLon, centerLat],
      zoom: FOCUS_ZOOM,
      duration: 800,
    });
  }, [centerLat, centerLon]);

  // Render markers for the filtered zoos and wire up click navigation.
  useEffect(() => {
    if (!mapRef.current) return;
    if (!mapReady) return;
    if (!maplibreRef.current) return;

    clearMarkers();

    const validPositions = [];

    normalizedZoos.forEach((zoo) => {
      validPositions.push([zoo.longitude, zoo.latitude]);

      const marker = new maplibreRef.current.Marker({ color: '#0d6efd' })
        .setLngLat([zoo.longitude, zoo.latitude])
        .addTo(mapRef.current);

      const handleClick = () => {
        if (onSelect) onSelect(zoo);
      };

      const handleKeyDown = (event) => {
        if (
          event.key === 'Enter' ||
          event.key === ' ' ||
          event.key === 'Spacebar'
        ) {
          event.preventDefault();
          if (onSelect) onSelect(zoo);
        }
      };

      const element = marker.getElement();
      element.setAttribute('role', 'link');
      element.setAttribute('tabindex', '0');
      if (zoo.name) {
        element.setAttribute('title', zoo.name);
        element.setAttribute(
          'aria-label',
          t('zoo.openDetail', { name: zoo.name })
        );
      }
      element.addEventListener('click', handleClick);
      element.addEventListener('keydown', handleKeyDown);

      markersRef.current.push({ marker, handleClick, handleKeyDown });
    });

    const hasCenter = Number.isFinite(centerLat) && Number.isFinite(centerLon);

    if (!hasCenter && validPositions.length > 0) {
      const [firstLon, firstLat] = validPositions[0];
      const bounds = new maplibreRef.current.LngLatBounds(
        [firstLon, firstLat],
        [firstLon, firstLat]
      );
      validPositions.forEach((pos) => bounds.extend(pos));
      mapRef.current.fitBounds(bounds, {
        padding: 40,
        maxZoom: FOCUS_ZOOM,
        duration: 500,
      });
    }
  }, [normalizedZoos, onSelect, centerLat, centerLon, t, mapReady]);

  useEffect(() => {
    if (!mapRef.current) {
      pendingResizeRef.current = true;
      return undefined;
    }

    pendingResizeRef.current = false;
    const map = mapRef.current;
    const cleanup = scheduleResize();
    return () => {
      cleanup();
      resizeCleanupsRef.current = resizeCleanupsRef.current.filter(
        (fn) => fn !== cleanup
      );
    };
  }, [resizeToken, scheduleResize]);

  return (
    <div
      ref={containerRef}
      className="map-container zoos-map"
      role="region"
      aria-label={t('zoo.mapAriaLabel')}
    />
  );
}

ZoosMap.propTypes = {
  zoos: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
      name: PropTypes.string,
      slug: PropTypes.string,
      latitude: PropTypes.number,
      longitude: PropTypes.number,
    })
  ),
  center: PropTypes.shape({
    lat: PropTypes.number,
    lon: PropTypes.number,
  }),
  onSelect: PropTypes.func,
  resizeToken: PropTypes.number,
};

ZoosMap.defaultProps = {
  zoos: [],
  center: null,
  onSelect: undefined,
  resizeToken: 0,
};

