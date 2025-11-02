// @ts-nocheck
import { vi } from 'vitest';

if (typeof window !== 'undefined') {
  if (typeof window.URL === 'undefined') {
    window.URL = {} as typeof window.URL;
  }
  if (typeof window.URL.createObjectURL !== 'function') {
    window.URL.createObjectURL = vi.fn();
  }
  if (typeof window.URL.revokeObjectURL !== 'function') {
    window.URL.revokeObjectURL = vi.fn();
  }
}

const mockMaps = [] as any[];

class MockMap {
  constructor({ container, center = [0, 0], zoom = 0, bearing = 0, pitch = 0 }) {
    this.container = container;
    this.events = {};
    this.sources = new Map();
    this.layers = new Map();
    const canvasListeners = new Map();
    this.canvas = {
      style: {},
      addEventListener: vi.fn((type, handler) => {
        const handlers = canvasListeners.get(type) || [];
        handlers.push(handler);
        canvasListeners.set(type, handlers);
      }),
      removeEventListener: vi.fn((type, handler) => {
        const handlers = canvasListeners.get(type);
        if (!handlers) return;
        canvasListeners.set(
          type,
          handlers.filter((fn: unknown) => fn !== handler)
        );
      }),
      dispatchEvent: vi.fn((event) => {
        const handlers = canvasListeners.get(event?.type) || [];
        handlers.forEach((fn: (evt: unknown) => void) => {
          fn(event);
        });
        return true;
      }),
    } as unknown as HTMLCanvasElement;
    this.center = { lng: center[0], lat: center[1] };
    this.zoom = zoom;
    this.bearing = bearing;
    this.pitch = pitch;
    this.styleLayers = [
      {
        id: 'country-labels',
        type: 'symbol',
        layout: { 'text-field': ['get', 'name'] },
      },
    ];
    this.sourceSetDataSpies = new Map();
    mockMaps.push(this);
    queueMicrotask(() => {
      this.emit('load');
    });
  }

  once(event, handler) {
    if (!this.events[event]) {
      this.events[event] = [] as any[];
    }
    this.events[event].push({ handler, once: true, layerId: null });
  }

  on(event, layerOrHandler, maybeHandler) {
    let layerId = null;
    let handler = layerOrHandler;
    if (typeof layerOrHandler === 'string' && typeof maybeHandler === 'function') {
      layerId = layerOrHandler;
      handler = maybeHandler;
    }
    if (!this.events[event]) {
      this.events[event] = [] as any[];
    }
    this.events[event].push({ handler, once: false, layerId });
  }

  off(event, layerOrHandler, maybeHandler) {
    let layerId = null;
    let handler = layerOrHandler;
    if (typeof layerOrHandler === 'string' && typeof maybeHandler === 'function') {
      layerId = layerOrHandler;
      handler = maybeHandler;
    }
    if (!this.events[event]) return;
    this.events[event] = this.events[event].filter((listener) => {
      const matchesHandler = listener.handler === handler;
      const matchesLayer = listener.layerId === layerId;
      return !(matchesHandler && matchesLayer);
    });
  }

  emit(event, data, layerId = null) {
    const listeners = this.events[event] || [];
    this.events[event] = listeners.filter((listener) => !listener.once);
    listeners.forEach((listener) => {
      if (listener.layerId && listener.layerId !== layerId) {
        return;
      }
      listener.handler(data);
    });
  }

  resize() {}

  remove() {}

  isStyleLoaded() {
    return true;
  }

  getStyle() {
    return { layers: this.styleLayers };
  }

  setLayoutProperty(id, property, value) {
    const layer = this.styleLayers.find((entry) => entry.id === id);
    if (!layer) return;
    if (!layer.layout) {
      layer.layout = {};
    }
    layer.layout[property] = value;
  }

  easeTo({ center, zoom }) {
    if (center) {
      this.center = { lng: center[0], lat: center[1] };
    }
    if (Number.isFinite(zoom)) {
      this.zoom = zoom;
    }
  }

  fitBounds() {}

  jumpTo({ center, zoom, bearing, pitch }) {
    if (center) {
      this.center = { lng: center[0], lat: center[1] };
    }
    if (Number.isFinite(zoom)) {
      this.zoom = zoom;
    }
    if (Number.isFinite(bearing)) {
      this.bearing = bearing;
    }
    if (Number.isFinite(pitch)) {
      this.pitch = pitch;
    }
  }

  getCenter() {
    return this.center;
  }

  getZoom() {
    return this.zoom;
  }

  getBearing() {
    return this.bearing;
  }

  getPitch() {
    return this.pitch;
  }

  getCanvas() {
    return this.canvas;
  }

  addSource(id, options) {
    const source = {
      options,
      data: options?.data,
      setData: vi.fn((data) => {
        source.data = data;
        if (this.container) {
          this.container.innerHTML = '';
          data.features.forEach((feature) => {
            const link = document.createElement('a');
            link.href = '#';
            link.textContent = `Open details for ${feature.properties?.name ?? 'Unknown zoo'}`;
            link.dataset.zooId = feature.properties?.zoo_id ?? '';
            link.tabIndex = 0;
            link.addEventListener('keydown', (event) => {
              if (event.key === 'Enter') {
                this.emit(
                  'click',
                  {
                    features: [
                      {
                        properties: feature.properties,
                        geometry: feature.geometry,
                      },
                    ],
                    originalEvent: event,
                  },
                  'zoos-unclustered'
                );
              }
            });
            this.container.appendChild(link);
          });
        }
      }),
      getClusterExpansionZoom: async () => 10,
    };
    this.sourceSetDataSpies.set(id, source.setData);
    this.sources.set(id, source);
    return source;
  }

  getSource(id) {
    return this.sources.get(id);
  }

  addLayer(layer) {
    this.layers.set(layer.id, layer);
  }

  getLayer(id) {
    return this.layers.get(id);
  }
}

class MockMarker {
  constructor() {
    this.element = document.createElement('div');
  }

  setLngLat(coords) {
    this.coords = coords;
    return this;
  }

  addTo(map) {
    this.map = map;
    if (map?.container) {
      map.container.appendChild(this.element);
    }
    return this;
  }

  getElement() {
    return this.element;
  }

  remove() {
    this.element.remove();
  }
}

class MockLngLatBounds {
  constructor(sw, ne) {
    this.sw = sw;
    this.ne = ne;
  }

  extend([lon, lat]) {
    this.sw = [Math.min(this.sw[0], lon), Math.min(this.sw[1], lat)];
    this.ne = [Math.max(this.ne[0], lon), Math.max(this.ne[1], lat)];
    return this;
  }
}

const maplibreMock = {
  Map: MockMap,
  Marker: MockMarker,
  LngLatBounds: MockLngLatBounds,
  NavigationControl: class {},
  AttributionControl: class {},
  __getMaps: () => mockMaps,
};

export default maplibreMock;
export { mockMaps };
