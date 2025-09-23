import React from 'react';
import '@testing-library/jest-dom';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

vi.mock('maplibre-gl', () => {
  class MockMap {
    constructor({ container }) {
      this.container = container;
      this.events = {};
      queueMicrotask(() => {
        this.emit('load');
      });
    }

    once(event, handler) {
      if (!this.events[event]) {
        this.events[event] = [];
      }
      this.events[event].push({ handler, once: true });
    }

    emit(event, data) {
      const listeners = this.events[event] || [];
      this.events[event] = listeners.filter((listener) => !listener.once);
      listeners.forEach((listener) => listener.handler(data));
    }

    resize() {}

    remove() {}

    easeTo() {}

    fitBounds() {}
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

  return {
    default: {
      Map: MockMap,
      Marker: MockMarker,
      LngLatBounds: MockLngLatBounds,
    },
  };
});

import ZoosMap from './ZoosMap.jsx';

describe('ZoosMap', () => {
  it('fires onSelect when pressing Enter on a marker', async () => {
    const onSelect = vi.fn();
    render(
      <ZoosMap
        zoos={[
          {
            id: '1',
            name: 'Test Zoo',
            slug: 'test-zoo',
            latitude: 12.3,
            longitude: 45.6,
          },
        ]}
        center={{ lat: 0, lon: 0 }}
        onSelect={onSelect}
        resizeToken={1}
      />
    );

    const marker = await screen.findByRole('link', {
      name: 'Open details for Test Zoo',
    });

    fireEvent.keyDown(marker, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ id: '1', name: 'Test Zoo' })
    );
  });
});
