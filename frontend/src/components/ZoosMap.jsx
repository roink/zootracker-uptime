import { useEffect, useMemo, useRef } from 'react';
import PropTypes from 'prop-types';
import { MAP_STYLE_URL } from './MapView.jsx';

// Interactive map showing multiple zoos with clickable markers.
const DEFAULT_ZOOM = 5;
const FOCUS_ZOOM = 8;

export default function ZoosMap({ zoos, center, onSelect }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const maplibreRef = useRef(null);
  const markersRef = useRef([]);

  const centerLat = center?.lat;
  const centerLon = center?.lon;

  const fallbackZoo = useMemo(
    () =>
      zoos.find(
        (z) => Number.isFinite(z.latitude) && Number.isFinite(z.longitude)
      ),
    [zoos]
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
    })();

    return () => {
      cancelled = true;
      clearMarkers();
      mapRef.current?.remove();
      mapRef.current = null;
      maplibreRef.current = null;
    };
  }, [initialState]);

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
    if (!maplibreRef.current) return;

    clearMarkers();

    const validPositions = [];

    zoos.forEach((zoo) => {
      if (!Number.isFinite(zoo.latitude) || !Number.isFinite(zoo.longitude)) {
        return;
      }

      validPositions.push([zoo.longitude, zoo.latitude]);

      const marker = new maplibreRef.current.Marker({ color: '#0d6efd' })
        .setLngLat([zoo.longitude, zoo.latitude])
        .addTo(mapRef.current);

      const handleClick = () => {
        if (onSelect) onSelect(zoo);
      };

      const handleKeyDown = (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          if (onSelect) onSelect(zoo);
        }
      };

      const element = marker.getElement();
      element.setAttribute('role', 'button');
      element.setAttribute('tabindex', '0');
      if (zoo.name) {
        element.setAttribute('title', zoo.name);
        element.setAttribute('aria-label', zoo.name);
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
  }, [zoos, onSelect, centerLat, centerLon]);

  return (
    <div
      ref={containerRef}
      className="map-container zoos-map"
      role="region"
      aria-label="Map showing zoos that match the current filters"
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
};

ZoosMap.defaultProps = {
  zoos: [],
  center: null,
  onSelect: undefined,
};

