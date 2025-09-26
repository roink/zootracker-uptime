import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { getZooDisplayName } from '../utils/zooDisplayName.js';
import { normalizeCoordinates } from '../utils/coordinates.js';
import { MAP_STYLE_URL } from './MapView.jsx';

// Interactive map showing multiple zoos with clickable markers or clusters.
const DEFAULT_ZOOM = 5;
const FOCUS_ZOOM = 8;
const ZOOS_SOURCE_ID = 'zoos';
const CLUSTERS_LAYER_ID = 'zoos-clusters';
const CLUSTER_COUNT_LAYER_ID = 'zoos-cluster-count';
const UNCLUSTERED_LAYER_ID = 'zoos-unclustered';

export default function ZoosMap({
  zoos,
  center,
  onSelect,
  resizeToken,
  initialView,
  onViewChange,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const maplibreRef = useRef(null);
  const pendingResizeRef = useRef(false);
  const resizeCleanupsRef = useRef([]);
  const onSelectRef = useRef(onSelect);
  const onViewChangeRef = useRef(onViewChange);
  const zooLookupRef = useRef(new Map());
  const hasFitToZoosRef = useRef(false);
  const skipNextCenterRef = useRef(false);
  const { t } = useTranslation();
  const [mapReady, setMapReady] = useState(false);

  const centerLat = center?.lat;
  const centerLon = center?.lon;

  const normalizedZoos = useMemo(
    () =>
      (zoos || [])
        .map((zoo) => {
          const coords = normalizeCoordinates(zoo);
          if (!coords) {
            return null;
          }
          return { ...zoo, ...coords };
        })
        .filter(Boolean),
    [zoos]
  );

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    onViewChangeRef.current = onViewChange;
  }, [onViewChange]);

  useEffect(() => {
    const lookup = new Map();
    normalizedZoos.forEach((zoo) => {
      lookup.set(String(zoo.id), zoo);
    });
    zooLookupRef.current = lookup;
  }, [normalizedZoos]);

  const fallbackZoo = useMemo(
    () => (normalizedZoos.length > 0 ? normalizedZoos[0] : null),
    [normalizedZoos]
  );

  const persistentInitialView = useMemo(() => {
    if (!initialView?.center) return null;
    const [lon, lat] = initialView.center;
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
      return null;
    }
    return {
      center: [lon, lat],
      zoom: Number.isFinite(initialView.zoom) ? initialView.zoom : FOCUS_ZOOM,
      bearing: Number.isFinite(initialView.bearing) ? initialView.bearing : 0,
      pitch: Number.isFinite(initialView.pitch) ? initialView.pitch : 0,
    };
  }, [initialView]);

  const initialState = useMemo(() => {
    if (persistentInitialView) {
      return persistentInitialView;
    }
    if (Number.isFinite(centerLat) && Number.isFinite(centerLon)) {
      return {
        center: [centerLon, centerLat],
        zoom: FOCUS_ZOOM,
        bearing: 0,
        pitch: 0,
      };
    }
    if (
      fallbackZoo &&
      Number.isFinite(fallbackZoo.latitude) &&
      Number.isFinite(fallbackZoo.longitude)
    ) {
      return {
        center: [fallbackZoo.longitude, fallbackZoo.latitude],
        zoom: DEFAULT_ZOOM,
        bearing: 0,
        pitch: 0,
      };
    }
    return null;
  }, [centerLat, centerLon, fallbackZoo, persistentInitialView]);

  useEffect(() => {
    if (persistentInitialView) {
      skipNextCenterRef.current = true;
    }
  }, [persistentInitialView]);

  const captureView = useCallback(() => {
    if (!mapRef.current) return null;
    const center = mapRef.current.getCenter?.();
    if (!center) return null;
    const zoomValue = mapRef.current.getZoom?.();
    const bearingValue = mapRef.current.getBearing?.();
    const pitchValue = mapRef.current.getPitch?.();
    return {
      center: [
        Number.isFinite(center.lng) ? Number(center.lng.toFixed(6)) : center.lng,
        Number.isFinite(center.lat) ? Number(center.lat.toFixed(6)) : center.lat,
      ],
      zoom: Number.isFinite(zoomValue) ? Number(zoomValue.toFixed(4)) : zoomValue,
      bearing: Number.isFinite(bearingValue)
        ? Number(bearingValue.toFixed(2))
        : bearingValue,
      pitch: Number.isFinite(pitchValue)
        ? Number(pitchValue.toFixed(2))
        : pitchValue,
    };
  }, []);

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
    if (mapRef.current) return undefined;
    if (!containerRef.current) return undefined;
    if (!initialState) return undefined;

    let cancelled = false;

    (async () => {
      const { default: maplibregl } = await import('maplibre-gl');
      if (cancelled) return;

      maplibreRef.current = maplibregl;
      mapRef.current = new maplibregl.Map({
        container: containerRef.current,
        style: MAP_STYLE_URL,
        center: initialState.center,
        zoom: initialState.zoom,
        bearing: initialState.bearing,
        pitch: initialState.pitch,
        attributionControl: true,
      });

      const handleLoad = () => {
        if (cancelled) return;
        if (persistentInitialView && mapRef.current) {
          mapRef.current.jumpTo({
            center: persistentInitialView.center,
            zoom: persistentInitialView.zoom,
            bearing: persistentInitialView.bearing,
            pitch: persistentInitialView.pitch,
          });
        }
        setMapReady(true);
        pendingResizeRef.current = false;
        scheduleResize();
        const view = captureView();
        if (view && onViewChangeRef.current) {
          onViewChangeRef.current(view);
        }
      };

      if (mapRef.current?.once) {
        mapRef.current.once('load', handleLoad);
      } else {
        mapRef.current?.on('load', handleLoad);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [initialState, scheduleResize]);

  useEffect(
    () => () => {
      resizeCleanupsRef.current.forEach((cleanup) => cleanup());
      resizeCleanupsRef.current = [];
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      maplibreRef.current = null;
      setMapReady(false);
      hasFitToZoosRef.current = false;
    },
    []
  );

  // Keep the map centered on the user/estimated location when it becomes available.
  useEffect(() => {
    if (!mapRef.current || !mapReady) return;
    if (!Number.isFinite(centerLat) || !Number.isFinite(centerLon)) return;
    if (skipNextCenterRef.current) {
      skipNextCenterRef.current = false;
      return;
    }

    mapRef.current.easeTo({
      center: [centerLon, centerLat],
      zoom: FOCUS_ZOOM,
      duration: 800,
    });
  }, [centerLat, centerLon, mapReady]);

  useEffect(() => {
    if (!mapRef.current || !mapReady || !maplibreRef.current) return;

    const map = mapRef.current;

    if (!map.getSource(ZOOS_SOURCE_ID)) {
      map.addSource(ZOOS_SOURCE_ID, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
        cluster: true,
        clusterMaxZoom: 12,
        clusterRadius: 50,
      });
    }

    if (!map.getLayer(CLUSTERS_LAYER_ID)) {
      map.addLayer({
        id: CLUSTERS_LAYER_ID,
        type: 'circle',
        source: ZOOS_SOURCE_ID,
        filter: ['has', 'point_count'],
        paint: {
          'circle-color': [
            'step',
            ['get', 'point_count'],
            '#0d6efd',
            25,
            '#6610f2',
            100,
            '#d63384',
          ],
          'circle-radius': [
            'step',
            ['get', 'point_count'],
            18,
            25,
            24,
            100,
            32,
          ],
          'circle-opacity': 0.85,
        },
      });
    }

    if (!map.getLayer(CLUSTER_COUNT_LAYER_ID)) {
      map.addLayer({
        id: CLUSTER_COUNT_LAYER_ID,
        type: 'symbol',
        source: ZOOS_SOURCE_ID,
        filter: ['has', 'point_count'],
        layout: {
          'text-field': '{point_count_abbreviated}',
          'text-size': 12,
          'text-font': ['Noto Sans Regular'],
        },
        paint: {
          'text-color': '#ffffff',
        },
      });
    }

    if (!map.getLayer(UNCLUSTERED_LAYER_ID)) {
      map.addLayer({
        id: UNCLUSTERED_LAYER_ID,
        type: 'circle',
        source: ZOOS_SOURCE_ID,
        filter: ['!', ['has', 'point_count']],
        paint: {
          'circle-color': '#0d6efd',
          'circle-radius': 7,
          'circle-stroke-width': 1,
          'circle-stroke-color': '#ffffff',
        },
      });
    }

    const handleClusterClick = async (event) => {
      const feature = event.features?.[0];
      if (!feature) return;
      const clusterId = feature.properties?.cluster_id;
      if (clusterId == null) return;
      const source = map.getSource(ZOOS_SOURCE_ID);
      if (!source?.getClusterExpansionZoom) return;
      try {
        const zoom = await source.getClusterExpansionZoom(clusterId);
        map.easeTo({ center: feature.geometry.coordinates, zoom });
      } catch (error) {
        // Ignore zoom errors to avoid breaking user interaction.
      }
    };

    const handlePointClick = (event) => {
      const feature = event.features?.[0];
      if (!feature) return;
      const id = feature.properties?.zoo_id;
      if (!id) return;
      const target = zooLookupRef.current.get(String(id));
      if (target && onSelectRef.current) {
        const view = captureView();
        if (view && onViewChangeRef.current) {
          onViewChangeRef.current(view);
        }
        onSelectRef.current(target, view);
      }
    };

    const handlePointerEnter = () => {
      if (map.getCanvas()) {
        map.getCanvas().style.cursor = 'pointer';
      }
    };

    const handlePointerLeave = () => {
      if (map.getCanvas()) {
        map.getCanvas().style.cursor = '';
      }
    };

    map.on('click', CLUSTERS_LAYER_ID, handleClusterClick);
    map.on('click', UNCLUSTERED_LAYER_ID, handlePointClick);
    map.on('mouseenter', CLUSTERS_LAYER_ID, handlePointerEnter);
    map.on('mouseleave', CLUSTERS_LAYER_ID, handlePointerLeave);
    map.on('mouseenter', UNCLUSTERED_LAYER_ID, handlePointerEnter);
    map.on('mouseleave', UNCLUSTERED_LAYER_ID, handlePointerLeave);

    return () => {
      map.off('click', CLUSTERS_LAYER_ID, handleClusterClick);
      map.off('click', UNCLUSTERED_LAYER_ID, handlePointClick);
      map.off('mouseenter', CLUSTERS_LAYER_ID, handlePointerEnter);
      map.off('mouseleave', CLUSTERS_LAYER_ID, handlePointerLeave);
      map.off('mouseenter', UNCLUSTERED_LAYER_ID, handlePointerEnter);
      map.off('mouseleave', UNCLUSTERED_LAYER_ID, handlePointerLeave);
    };
  }, [mapReady]);

  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    const source = mapRef.current.getSource(ZOOS_SOURCE_ID);
    if (!source) return;

    const features = normalizedZoos.map((zoo) => ({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [zoo.longitude, zoo.latitude],
      },
      properties: {
        zoo_id: String(zoo.id),
        name: getZooDisplayName(zoo) || '',
      },
    }));

    source.setData({
      type: 'FeatureCollection',
      features,
    });
  }, [normalizedZoos, mapReady]);

  useEffect(() => {
    if (!mapRef.current || !mapReady || !maplibreRef.current) return;
    if (persistentInitialView) return;

    const hasCenter = Number.isFinite(centerLat) && Number.isFinite(centerLon);
    if (hasCenter) {
      hasFitToZoosRef.current = false;
      return;
    }

    if (normalizedZoos.length === 0) {
      hasFitToZoosRef.current = false;
      return;
    }

    if (hasFitToZoosRef.current) return;

    const [firstZoo] = normalizedZoos;
    const bounds = new maplibreRef.current.LngLatBounds(
      [firstZoo.longitude, firstZoo.latitude],
      [firstZoo.longitude, firstZoo.latitude]
    );
    normalizedZoos.forEach((zoo) => {
      bounds.extend([zoo.longitude, zoo.latitude]);
    });
    mapRef.current.fitBounds(bounds, {
      padding: 40,
      maxZoom: FOCUS_ZOOM,
      duration: 500,
    });
    hasFitToZoosRef.current = true;
  }, [
    normalizedZoos,
    centerLat,
    centerLon,
    mapReady,
    persistentInitialView,
  ]);

  useEffect(() => {
    if (!mapReady || !mapRef.current) return undefined;

    const map = mapRef.current;
    const emitViewChange = () => {
      const view = captureView();
      if (view && onViewChangeRef.current) {
        onViewChangeRef.current(view);
      }
    };

    map.on('moveend', emitViewChange);
    return () => {
      map.off('moveend', emitViewChange);
    };
  }, [captureView, mapReady]);

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
      lat: PropTypes.number,
      lon: PropTypes.number,
      lng: PropTypes.number,
      location: PropTypes.shape({
        latitude: PropTypes.number,
        longitude: PropTypes.number,
        lat: PropTypes.number,
        lon: PropTypes.number,
        lng: PropTypes.number,
      }),
    })
  ),
  center: PropTypes.shape({
    lat: PropTypes.number,
    lon: PropTypes.number,
  }),
  onSelect: PropTypes.func,
  resizeToken: PropTypes.number,
  initialView: PropTypes.shape({
    center: PropTypes.arrayOf(PropTypes.number),
    zoom: PropTypes.number,
    bearing: PropTypes.number,
    pitch: PropTypes.number,
  }),
  onViewChange: PropTypes.func,
};

ZoosMap.defaultProps = {
  zoos: [],
  center: null,
  onSelect: undefined,
  resizeToken: 0,
  initialView: null,
  onViewChange: undefined,
};

