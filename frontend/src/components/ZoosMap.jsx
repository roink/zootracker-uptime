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
const SET_DATA_TIMEOUT_MS = 32;

/**
 * @typedef {Object} CameraState
 * @property {[number, number]} center Longitude and latitude pair used to restore the viewport.
 * @property {number} zoom Zoom level applied when persisting and restoring camera state.
 * @property {number} bearing Map bearing in degrees.
 * @property {number} pitch Map pitch in degrees.
 * @description Shared camera schema used by ZoosMap and Zoos.jsx when persisting map position.
 */

export default function ZoosMap({
  zoos,
  center,
  onSelect,
  resizeToken,
  initialView,
  onViewChange,
  ariaLabel,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const maplibreRef = useRef(null);
  const resizeObserverRef = useRef(null);
  const setDataFrameRef = useRef(null);
  const onSelectRef = useRef(onSelect);
  const onViewChangeRef = useRef(onViewChange);
  const zooLookupRef = useRef(new Map());
  const previousFeatureIdsRef = useRef([]);
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

  const emitViewChange = useCallback(
    (event) => {
      const view = captureView();
      if (view && onViewChangeRef.current) {
        onViewChangeRef.current({
          ...view,
          isUserInteraction: Boolean(event?.originalEvent),
        });
      }
      return view;
    },
    [captureView]
  );

  const triggerResize = useCallback(() => {
    const map = mapRef.current;
    if (!map || typeof map.resize !== 'function') return;

    const performResize = () => {
      mapRef.current?.resize?.();
    };

    if (
      typeof window !== 'undefined' &&
      typeof window.requestAnimationFrame === 'function'
    ) {
      window.requestAnimationFrame(performResize);
    } else {
      performResize();
    }
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

      const handleLoad = (event) => {
        if (cancelled) return;
        if (persistentInitialView && mapRef.current) {
          mapRef.current.jumpTo?.({
            center: persistentInitialView.center,
            zoom: persistentInitialView.zoom,
            bearing: persistentInitialView.bearing,
            pitch: persistentInitialView.pitch,
          });
        }
        setMapReady(true);
        triggerResize();
        emitViewChange(event);
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
  }, [emitViewChange, initialState, persistentInitialView, triggerResize]);

  const cancelPendingSetData = useCallback(() => {
    const pending = setDataFrameRef.current;
    if (pending?.cancel) {
      pending.cancel();
    }
    setDataFrameRef.current = null;
  }, []);

  const scheduleDataUpdate = useCallback(
    (callback) => {
      cancelPendingSetData();

      if (typeof window === 'undefined') {
        callback();
        return () => {};
      }

      if (typeof window.requestAnimationFrame === 'function') {
        const frameId = window.requestAnimationFrame(() => {
          if (setDataFrameRef.current?.id === frameId) {
            setDataFrameRef.current = null;
          }
          callback();
        });
        const cancel = () => {
          if (typeof window.cancelAnimationFrame === 'function') {
            window.cancelAnimationFrame(frameId);
          }
          if (setDataFrameRef.current?.id === frameId) {
            setDataFrameRef.current = null;
          }
        };
        setDataFrameRef.current = { type: 'raf', id: frameId, cancel };
        return cancel;
      }

      if (typeof window.setTimeout === 'function') {
        const timeoutId = window.setTimeout(() => {
          if (setDataFrameRef.current?.id === timeoutId) {
            setDataFrameRef.current = null;
          }
          callback();
        }, SET_DATA_TIMEOUT_MS);
        const cancel = () => {
          if (typeof window.clearTimeout === 'function') {
            window.clearTimeout(timeoutId);
          } else {
            clearTimeout(timeoutId);
          }
          if (setDataFrameRef.current?.id === timeoutId) {
            setDataFrameRef.current = null;
          }
        };
        setDataFrameRef.current = { type: 'timeout', id: timeoutId, cancel };
        return cancel;
      }

      callback();
      return () => {};
    },
    [cancelPendingSetData]
  );

  useEffect(
    () => () => {
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
        resizeObserverRef.current = null;
      }
      cancelPendingSetData();
      if (mapRef.current) {
        mapRef.current.remove?.();
        mapRef.current = null;
      }
      maplibreRef.current = null;
      setMapReady(false);
      hasFitToZoosRef.current = false;
      previousFeatureIdsRef.current = [];
    },
    [cancelPendingSetData]
  );

  // Keep the map centered on the user/estimated location when it becomes available.
  useEffect(() => {
    if (!mapRef.current || !mapReady) return;
    if (!Number.isFinite(centerLat) || !Number.isFinite(centerLon)) return;
    if (skipNextCenterRef.current) {
      skipNextCenterRef.current = false;
      return;
    }

    mapRef.current.easeTo?.({
      center: [centerLon, centerLat],
      zoom: FOCUS_ZOOM,
      duration: 800,
    });
  }, [centerLat, centerLon, mapReady]);

  useEffect(() => {
    if (!mapRef.current || !mapReady || !maplibreRef.current) return;

    const map = mapRef.current;

    const hasGetSource = typeof map.getSource === 'function';
    const hasAddSource = typeof map.addSource === 'function';
    if (hasAddSource && hasGetSource && !map.getSource(ZOOS_SOURCE_ID)) {
      map.addSource(ZOOS_SOURCE_ID, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
        cluster: true,
        clusterMaxZoom: 12,
        clusterRadius: 50,
      });
    }

    const hasGetLayer = typeof map.getLayer === 'function';
    const hasAddLayer = typeof map.addLayer === 'function';

    if (hasAddLayer && hasGetLayer && !map.getLayer(CLUSTERS_LAYER_ID)) {
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

    if (hasAddLayer && hasGetLayer && !map.getLayer(CLUSTER_COUNT_LAYER_ID)) {
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

    if (hasAddLayer && hasGetLayer && !map.getLayer(UNCLUSTERED_LAYER_ID)) {
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
      const source = hasGetSource ? map.getSource(ZOOS_SOURCE_ID) : null;
      if (!source?.getClusterExpansionZoom) return;
      try {
        const zoom = await source.getClusterExpansionZoom(clusterId);
        map.easeTo?.({ center: feature.geometry.coordinates, zoom });
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
        const view = emitViewChange(event);
        onSelectRef.current(target, view);
      }
    };

    const handlePointerEnter = () => {
      if (typeof map.getCanvas === 'function' && map.getCanvas()) {
        map.getCanvas().style.cursor = 'pointer';
      }
    };

    const handlePointerLeave = () => {
      if (typeof map.getCanvas === 'function' && map.getCanvas()) {
        map.getCanvas().style.cursor = '';
      }
    };

    if (typeof map.on === 'function') {
      map.on('click', CLUSTERS_LAYER_ID, handleClusterClick);
      map.on('click', UNCLUSTERED_LAYER_ID, handlePointClick);
      map.on('mouseenter', CLUSTERS_LAYER_ID, handlePointerEnter);
      map.on('mouseleave', CLUSTERS_LAYER_ID, handlePointerLeave);
      map.on('mouseenter', UNCLUSTERED_LAYER_ID, handlePointerEnter);
      map.on('mouseleave', UNCLUSTERED_LAYER_ID, handlePointerLeave);
    }

    return () => {
      if (typeof map.off === 'function') {
        map.off('click', CLUSTERS_LAYER_ID, handleClusterClick);
        map.off('click', UNCLUSTERED_LAYER_ID, handlePointClick);
        map.off('mouseenter', CLUSTERS_LAYER_ID, handlePointerEnter);
        map.off('mouseleave', CLUSTERS_LAYER_ID, handlePointerLeave);
        map.off('mouseenter', UNCLUSTERED_LAYER_ID, handlePointerEnter);
        map.off('mouseleave', UNCLUSTERED_LAYER_ID, handlePointerLeave);
      }
    };
  }, [emitViewChange, mapReady]);

  useEffect(() => {
    if (!mapReady || !mapRef.current) {
      cancelPendingSetData();
      return undefined;
    }

    const getSource = mapRef.current.getSource;
    const source =
      typeof getSource === 'function' ? getSource.call(mapRef.current, ZOOS_SOURCE_ID) : null;
    if (!source || typeof source.setData !== 'function') return undefined;

    const updateFeatures = () => {
      const nextIds = [];
      const features = normalizedZoos.map((zoo) => {
        const zooId = String(zoo.id);
        nextIds.push(zooId);
        return {
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [zoo.longitude, zoo.latitude],
          },
          properties: {
            zoo_id: zooId,
            name: getZooDisplayName(zoo) || '',
          },
        };
      });

      const previousIds = previousFeatureIdsRef.current;
      const sameLength = previousIds.length === nextIds.length;
      let idsMatch = sameLength;
      if (idsMatch) {
        for (let index = 0; index < nextIds.length; index += 1) {
          if (previousIds[index] !== nextIds[index]) {
            idsMatch = false;
            break;
          }
        }
      }

      if (idsMatch) {
        return;
      }

      previousFeatureIdsRef.current = nextIds;

      source.setData({
        type: 'FeatureCollection',
        features,
      });
    };

    const cancelScheduledUpdate = scheduleDataUpdate(updateFeatures);

    return () => {
      if (typeof cancelScheduledUpdate === 'function') {
        cancelScheduledUpdate();
      } else {
        cancelPendingSetData();
      }
    };
  }, [
    normalizedZoos,
    mapReady,
    cancelPendingSetData,
    scheduleDataUpdate,
  ]);

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
    mapRef.current.fitBounds?.(bounds, {
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
    if (!mapReady || !mapRef.current || !containerRef.current) return undefined;

    if (
      typeof window === 'undefined' ||
      typeof window.ResizeObserver !== 'function'
    ) {
      triggerResize();
      return undefined;
    }

    const observer = new window.ResizeObserver(() => {
      triggerResize();
    });

    observer.observe(containerRef.current);
    resizeObserverRef.current = observer;

    return () => {
      observer.disconnect();
      if (resizeObserverRef.current === observer) {
        resizeObserverRef.current = null;
      }
    };
  }, [mapReady, triggerResize]);

  useEffect(() => {
    if (!mapReady || !mapRef.current) return undefined;

    const map = mapRef.current;
    if (typeof map.on !== 'function' || typeof map.off !== 'function') {
      return undefined;
    }
    map.on('moveend', emitViewChange);
    return () => {
      map.off('moveend', emitViewChange);
    };
  }, [emitViewChange, mapReady]);

  useEffect(() => {
    if (!mapReady || !mapRef.current) return undefined;

    triggerResize();
    return undefined;
  }, [mapReady, resizeToken, triggerResize]);

  const mapAriaLabel = ariaLabel || t('zoo.mapAriaLabel');

  return (
    <div
      ref={containerRef}
      className="map-container zoos-map"
      role="region"
      aria-label={mapAriaLabel}
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
  ariaLabel: PropTypes.string,
};

ZoosMap.defaultProps = {
  zoos: [],
  center: null,
  onSelect: undefined,
  resizeToken: 0,
  initialView: null,
  onViewChange: undefined,
  ariaLabel: undefined,
};

