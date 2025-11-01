import type { Feature, FeatureCollection, Point } from 'geojson';
import type * as maplibre from 'maplibre-gl';
import PropTypes from 'prop-types';
import type { MutableRefObject } from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { MAP_STYLE_URL } from './MapView';
import type {
  CameraState,
  CameraViewChange,
  LocationEstimate,
  MapZooFeature,
} from '../types/zoos';
import { normalizeCoordinates } from '../utils/coordinates';
import { applyBaseMapLanguage } from '../utils/mapLanguage';
import { getZooDisplayName } from '../utils/zooDisplayName';

// Interactive map showing multiple zoos with clickable markers or clusters.
// NOTE: React plans to remove support for defaultProps on function components.
// Use JS default parameters instead: https://react.dev/learn/passing-props-to-a-component
const DEFAULT_ZOOM = 5;
const FOCUS_ZOOM = 8;
const ZOOS_SOURCE_ID = 'zoos';
const CLUSTERS_LAYER_ID = 'zoos-clusters';
const CLUSTER_COUNT_LAYER_ID = 'zoos-cluster-count';
const UNCLUSTERED_LAYER_ID = 'zoos-unclustered';
const SET_DATA_TIMEOUT_MS = 32;

// eslint-disable-next-line @typescript-eslint/consistent-type-imports
type MaplibreModule = typeof import('maplibre-gl');
type MaplibreImport = MaplibreModule & { default?: MaplibreModule };
type GeoJSONSource = maplibre.GeoJSONSource;
type LngLatLike = maplibre.LngLatLike;
type LngLatBoundsLike = maplibre.LngLatBoundsLike;
type MaplibreMap = maplibre.Map;
type MapLayerMouseEvent = maplibre.MapLayerMouseEvent;

type ClusterGeoJSONSource = GeoJSONSource & {
  getClusterExpansionZoom?: (clusterId: number) => Promise<number>;
};

interface ZoosMapProps {
  zoos?: MapZooFeature[];
  center?: LocationEstimate | null;
  onSelect?: (zoo: MapZooFeature, view: CameraViewChange | null) => void;
  resizeToken?: number;
  initialView?: CameraState | null;
  suppressAutoFit?: boolean;
  onViewChange?: (view: CameraViewChange | null) => void;
  ariaLabel?: string;
  onMapReady?: (map: MaplibreMap) => void;
  disableClusterCount?: boolean;
}

interface ScheduledFrame {
  type: 'raf' | 'timeout';
  id: number;
  cancel: () => void;
}

interface ZooFeatureProperties {
  zoo_id: string;
  name: string;
}

/**
 * @typedef {Object} CameraState
 * @property {[number, number]} center Longitude and latitude pair used to restore the viewport.
 * @property {number} zoom Zoom level applied when persisting and restoring camera state.
 * @property {number} bearing Map bearing in degrees.
 * @property {number} pitch Map pitch in degrees.
 * @description Shared camera schema used by ZoosMap and Zoos.jsx when persisting map position.
 */

export default function ZoosMap({
  zoos = [],
  center = null,
  onSelect,
  resizeToken = 0,
  initialView = null,
  suppressAutoFit = false,
  onViewChange,
  ariaLabel,
  onMapReady,
  disableClusterCount = false,
}: ZoosMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const maplibreRef: MutableRefObject<MaplibreModule | null> = useRef(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const setDataFrameRef = useRef<ScheduledFrame | null>(null);
  const onSelectRef = useRef<ZoosMapProps['onSelect']>(onSelect);
  const onViewChangeRef = useRef<ZoosMapProps['onViewChange']>(onViewChange);
  const onMapReadyRef = useRef<ZoosMapProps['onMapReady']>(onMapReady);
  const zooLookupRef = useRef<Map<string, MapZooFeature>>(new Map());
  const previousFeatureIdsRef = useRef<string[]>([]);
  const hasFitToZoosRef = useRef<boolean>(false);
  const skipNextCenterRef = useRef<boolean>(false);
  const { t, i18n } = useTranslation();
  const [mapReady, setMapReady] = useState<boolean>(false);

  const centerLat = center?.lat ?? null;
  const centerLon = center?.lon ?? null;

  const normalizedZoos = useMemo<MapZooFeature[]>(
    () =>
      zoos
        .map((zoo) => {
          const coords = normalizeCoordinates(zoo);
          if (!coords) {
            return null;
          }
          return { ...zoo, latitude: coords.latitude, longitude: coords.longitude };
        })
        .filter((value): value is MapZooFeature => value !== null),
    [zoos]
  );

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    onViewChangeRef.current = onViewChange;
  }, [onViewChange]);

  useEffect(() => {
    onMapReadyRef.current = onMapReady;
  }, [onMapReady]);

  useEffect(() => {
    const lookup = new Map<string, MapZooFeature>();
    normalizedZoos.forEach((zoo) => {
      lookup.set(String(zoo.id), zoo);
    });
    zooLookupRef.current = lookup;
  }, [normalizedZoos]);

  const persistentInitialView = useMemo<CameraState | null>(() => {
    if (!initialView?.center) return null;
    const [lon, lat] = initialView.center;
    const lonNumber = typeof lon === 'number' ? lon : Number(lon);
    const latNumber = typeof lat === 'number' ? lat : Number(lat);
    if (!Number.isFinite(lonNumber) || !Number.isFinite(latNumber)) {
      return null;
    }
    return {
      center: [lonNumber, latNumber],
      zoom: Number.isFinite(initialView.zoom) ? (initialView.zoom as number) : FOCUS_ZOOM,
      bearing: Number.isFinite(initialView.bearing) ? (initialView.bearing as number) : 0,
      pitch: Number.isFinite(initialView.pitch) ? (initialView.pitch as number) : 0,
    };
  }, [initialView]);

  const initialState = useMemo<CameraState | null>(() => {
    if (persistentInitialView) {
      return persistentInitialView;
    }
    if (centerLat !== null && centerLon !== null) {
      return {
        center: [centerLon, centerLat],
        zoom: FOCUS_ZOOM,
        bearing: 0,
        pitch: 0,
      };
    }
    const firstZoo = normalizedZoos[0];
    if (firstZoo) {
      return {
        center: [firstZoo.longitude, firstZoo.latitude],
        zoom: DEFAULT_ZOOM,
        bearing: 0,
        pitch: 0,
      };
    }
    return null;
  }, [centerLat, centerLon, normalizedZoos, persistentInitialView]);

  useEffect(() => {
    if (persistentInitialView) {
      skipNextCenterRef.current = true;
    }
  }, [persistentInitialView]);

    const captureView = useCallback((): CameraState | null => {
      const map = mapRef.current;
      if (!map) return null;
      const center = map.getCenter();
      const lon = Number(center.lng.toFixed(6));
      const lat = Number(center.lat.toFixed(6));
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return null;
      }
      const zoomValue = map.getZoom();
      const bearingValue = map.getBearing();
      const pitchValue = map.getPitch();
      const zoom = Number.isFinite(zoomValue) ? Number(zoomValue.toFixed(4)) : undefined;
      const bearing = Number.isFinite(bearingValue)
        ? Number((bearingValue).toFixed(2))
        : undefined;
      const pitch = Number.isFinite(pitchValue)
        ? Number((pitchValue).toFixed(2))
        : undefined;
    return {
      center: [lon, lat],
      ...(zoom !== undefined ? { zoom } : {}),
      ...(bearing !== undefined ? { bearing } : {}),
      ...(pitch !== undefined ? { pitch } : {}),
    };
  }, []);

  type MapEventLike = { originalEvent?: unknown } | MapLayerMouseEvent | null | undefined;

  const emitViewChange = useCallback(
    (event?: MapEventLike): CameraState | null => {
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
        map.resize();
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
      const container = containerRef.current;
      if (!container) return undefined;
      if (!initialState) return undefined;

      const abortController = new AbortController();

      void (async () => {
        const loadedModule = (await import('maplibre-gl')) as MaplibreImport;
        const maplibregl: MaplibreModule = loadedModule.default ?? loadedModule;
        if (abortController.signal.aborted || !container.isConnected) {
          return;
        }

        maplibreRef.current = maplibregl;
        const mapInstance = new maplibregl.Map({
          container,
          style: MAP_STYLE_URL,
          center: initialState.center,
          zoom: initialState.zoom ?? FOCUS_ZOOM,
          bearing: initialState.bearing ?? 0,
          pitch: initialState.pitch ?? 0,
        });

        mapRef.current = mapInstance;

        const handleLoad = (event: MapEventLike) => {
          if (abortController.signal.aborted) {
            return;
          }
          if (persistentInitialView) {
            mapInstance.jumpTo({
              center: persistentInitialView.center,
              zoom: persistentInitialView.zoom ?? FOCUS_ZOOM,
              bearing: persistentInitialView.bearing ?? 0,
              pitch: persistentInitialView.pitch ?? 0,
            });
          }
          setMapReady(true);
          triggerResize();
          emitViewChange(event);
          const readyHandler = onMapReadyRef.current;
          if (readyHandler) {
            readyHandler(mapInstance);
          }
        };

        if (typeof mapInstance.once === 'function') {
          void mapInstance.once('load', handleLoad);
        } else {
          mapInstance.on('load', handleLoad);
        }
      })();

      return () => {
        abortController.abort();
      };
    }, [emitViewChange, initialState, persistentInitialView, triggerResize]);

  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    applyBaseMapLanguage(mapRef.current, i18n.language);
  }, [i18n.language, mapReady]);

  const cancelPendingSetData = useCallback(() => {
    const pending = setDataFrameRef.current;
    if (pending) {
      pending.cancel();
      setDataFrameRef.current = null;
    }
  }, []);

  const scheduleDataUpdate = useCallback(
    (callback: () => void): (() => void) | void => {
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
          mapRef.current.remove();
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
      if (centerLat === null || centerLon === null) return;
      if (skipNextCenterRef.current) {
        skipNextCenterRef.current = false;
        return;
      }

      const map = mapRef.current;
      map.easeTo({
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

    if (
      !disableClusterCount &&
      hasAddLayer &&
      hasGetLayer &&
      !map.getLayer(CLUSTER_COUNT_LAYER_ID)
    ) {
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

    const handleClusterClick = (event: MapLayerMouseEvent) => {
      void (async () => {
        const feature = event.features?.[0];
        if (!feature) return;
        const properties = feature.properties as Record<string, unknown>;
        const clusterId = properties['cluster_id'] as number | undefined;
        if (clusterId == null) return;
        const clusterRawSource = hasGetSource ? map.getSource(ZOOS_SOURCE_ID) : null;
        const clusterSource =
          clusterRawSource &&
          typeof (clusterRawSource as ClusterGeoJSONSource).getClusterExpansionZoom === 'function'
            ? (clusterRawSource as ClusterGeoJSONSource)
            : null;
        if (!clusterSource) return;
        try {
          const zoom = await clusterSource.getClusterExpansionZoom(clusterId);
            if (feature.geometry.type !== 'Point') {
              return;
            }
            const coordinates = feature.geometry.coordinates as unknown;
            if (!Array.isArray(coordinates)) {
              return;
            }
            const currentZoom = typeof map.getZoom === 'function' ? map.getZoom() : undefined;
            const nextZoom = Number.isFinite(zoom) ? zoom : currentZoom ?? FOCUS_ZOOM;
            map.easeTo({ center: coordinates as LngLatLike, zoom: nextZoom });
        } catch (_error) {
          // Ignore zoom errors to avoid breaking user interaction.
        }
      })();
    };

    const handlePointClick = (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        if (!feature) return;
        const properties = feature.properties as Record<string, unknown>;
        const idCandidate = properties['zoo_id'];
        const id =
          typeof idCandidate === 'string'
            ? idCandidate
            : typeof idCandidate === 'number'
              ? String(idCandidate)
              : null;
      if (!id) return;
      const target = zooLookupRef.current.get(id);
      if (target && onSelectRef.current) {
        const view = emitViewChange(event);
        onSelectRef.current(target, view);
      }
    };

    const handlePointerEnter = () => {
      const canvas = typeof map.getCanvas === 'function' ? map.getCanvas() : null;
      if (canvas) {
        canvas.style.cursor = 'pointer';
      }
    };

    const handlePointerLeave = () => {
      const canvas = typeof map.getCanvas === 'function' ? map.getCanvas() : null;
      if (canvas) {
        canvas.style.cursor = '';
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
  }, [disableClusterCount, emitViewChange, mapReady]);

  useEffect(() => {
    if (!mapReady || !mapRef.current) {
      cancelPendingSetData();
      return undefined;
    }

    const map = mapRef.current;
    const rawSource = typeof map.getSource === 'function' ? map.getSource(ZOOS_SOURCE_ID) : null;
    const source = rawSource && typeof (rawSource as GeoJSONSource).setData === 'function'
      ? (rawSource as GeoJSONSource)
      : null;
    if (!source) return undefined;

    const updateFeatures = () => {
      const nextIds: string[] = [];
      const features: Feature<Point, ZooFeatureProperties>[] = normalizedZoos.map((zoo) => {
        const zooId = String(zoo.id);
        nextIds.push(zooId);
        return {
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [zoo.longitude, zoo.latitude] as [number, number],
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

      const collection: FeatureCollection<Point, ZooFeatureProperties> = {
        type: 'FeatureCollection',
        features,
      };

      source.setData(collection);
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
    if (suppressAutoFit) {
      hasFitToZoosRef.current = false;
      return;
    }

    const hasCenter = centerLat !== null && centerLon !== null;
    if (hasCenter) {
      hasFitToZoosRef.current = false;
      return;
    }

    const firstZoo = normalizedZoos[0];
    if (!firstZoo) {
      hasFitToZoosRef.current = false;
      return;
    }

    if (hasFitToZoosRef.current) return;

      const maplibre = maplibreRef.current;
    const bounds = new maplibre.LngLatBounds(
      [firstZoo.longitude, firstZoo.latitude],
      [firstZoo.longitude, firstZoo.latitude]
    );
    normalizedZoos.forEach((zoo) => {
      bounds.extend([zoo.longitude, zoo.latitude]);
    });
    const map = mapRef.current;
    map.fitBounds(bounds as LngLatBoundsLike, {
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
    suppressAutoFit,
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
  suppressAutoFit: PropTypes.bool,
  onViewChange: PropTypes.func,
  ariaLabel: PropTypes.string,
  onMapReady: PropTypes.func,
  disableClusterCount: PropTypes.bool,
};

