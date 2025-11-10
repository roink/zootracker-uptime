// @ts-nocheck
import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ZoosMap from './ZoosMap';
import maplibreMock from '../test-utils/maplibreMock';

vi.mock('maplibre-gl', () => ({
  __esModule: true,
  default: maplibreMock,
  ...maplibreMock,
}));

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
    expect(onSelect).toHaveBeenCalled();
    const [selectedZoo, viewState] = onSelect.mock.calls[0];
    expect(selectedZoo).toEqual(
      expect.objectContaining({ id: '1', name: 'Test Zoo' })
    );
    expect(viewState).toEqual(
      expect.objectContaining({
        center: [0, 0],
      })
    );
  });

  it('accepts zoos with lat/lon keys', async () => {
    const onSelect = vi.fn();
    render(
      <ZoosMap
        zoos={[
          {
            id: '2',
            name: 'Alt Keys Zoo',
            lat: 10.1,
            lon: 20.2,
          },
        ]}
        center={{ lat: 0, lon: 0 }}
        onSelect={onSelect}
      />
    );

    const marker = await screen.findByRole('link', {
      name: 'Open details for Alt Keys Zoo',
    });

    expect(marker).toBeInTheDocument();
  });

  it('skips setData when feature ids are unchanged', async () => {
    const { rerender } = render(
      <ZoosMap
        zoos={[
          { id: '1', name: 'First Zoo', latitude: 10, longitude: 10 },
          { id: '2', name: 'Second Zoo', latitude: 20, longitude: 20 },
        ]}
        center={{ lat: 0, lon: 0 }}
      />
    );

    await screen.findAllByRole('link');

    const maplibregl = await import('maplibre-gl');
    const [mapInstance] = maplibregl.default.__getMaps().slice(-1);
    const setDataSpy = mapInstance?.sourceSetDataSpies?.get('zoos');
    expect(setDataSpy).toBeDefined();
    expect(setDataSpy).toHaveBeenCalledTimes(1);

    rerender(
      <ZoosMap
        zoos={[
          { id: '1', name: 'First Zoo', latitude: 10, longitude: 10 },
          { id: '2', name: 'Second Zoo', latitude: 20, longitude: 20 },
        ]}
        center={{ lat: 0, lon: 0 }}
      />
    );

    // Allow pending microtasks/timeouts to flush.
    await new Promise((resolve) => {
      setTimeout(resolve, 0);
    });

    expect(setDataSpy).toHaveBeenCalledTimes(1);
  });

  it('resizes the map when the resize token changes', async () => {
    const { rerender } = render(
      <ZoosMap
        zoos={[
          { id: '1', name: 'Resize Zoo', latitude: 10, longitude: 10 },
        ]}
        center={{ lat: 0, lon: 0 }}
        resizeToken={0}
      />
    );

    await screen.findAllByRole('link');

    const maplibregl = await import('maplibre-gl');
    const [mapInstance] = maplibregl.default.__getMaps().slice(-1);
    const resizeSpy = vi.spyOn(mapInstance, 'resize');

    rerender(
      <ZoosMap
        zoos={[
          { id: '1', name: 'Resize Zoo', latitude: 10, longitude: 10 },
        ]}
        center={{ lat: 0, lon: 0 }}
        resizeToken={1}
      />
    );

    await waitFor(() => {
      expect(resizeSpy).toHaveBeenCalled();
    });
  });

  it('notifies when the WebGL context is lost and restored', async () => {
    const onContextLostChange = vi.fn();

    render(
      <ZoosMap
        zoos={[
          { id: '1', name: 'Context Zoo', latitude: 12.3, longitude: 45.6 },
        ]}
        center={{ lat: 0, lon: 0 }}
        onContextLostChange={onContextLostChange}
      />
    );

    await screen.findAllByRole('link');

    const maplibregl = await import('maplibre-gl');
    const [mapInstance] = maplibregl.default.__getMaps().slice(-1);
    const resizeSpy = vi.spyOn(mapInstance, 'resize');
    const canvas = mapInstance.getCanvas();
    const preventDefault = vi.fn();

    canvas.dispatchEvent({ type: 'webglcontextlost', preventDefault } as Event);

    expect(preventDefault).toHaveBeenCalled();
    expect(onContextLostChange).toHaveBeenCalledWith(true);
    await waitFor(() => {
      expect(resizeSpy).toHaveBeenCalled();
    });

    canvas.dispatchEvent({ type: 'webglcontextrestored' } as Event);
    await waitFor(() => {
      expect(onContextLostChange).toHaveBeenCalledWith(false);
    });
  });
});
