// @ts-nocheck
import { render, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('maplibre-gl', () => import('../../test-utils/maplibreMock'));

import ZoosMap from '../ZoosMap';

describe('ZoosMap clustering configuration', () => {
  it('configures a clustered GeoJSON source and supporting layers', async () => {
    render(
      <ZoosMap
        ariaLabel="Test map"
        initialView={{ center: [13.405, 52.52], zoom: 5, bearing: 0, pitch: 0 }}
        suppressAutoFit
        zoos={[
          { id: '1', name: 'One', latitude: 52.52, longitude: 13.405 },
          { id: '2', name: 'Two', latitude: 52.521, longitude: 13.406 },
          { id: '3', name: 'Three', latitude: 52.519, longitude: 13.404 },
        ]}
      />
    );

    const maplibregl = await import('maplibre-gl');
    const [map] = maplibregl.default.__getMaps().slice(-1);

    await waitFor(() => {
      expect(map).toBeDefined();
      expect(map.getSource('zoos')).toBeTruthy();
    });

    const source = map.getSource('zoos');
    expect(source?.options?.type).toBe('geojson');
    expect(source?.options?.cluster).toBe(true);
    expect(source?.options?.clusterRadius).toBeGreaterThan(0);
    expect(source?.options?.clusterMaxZoom).toBeGreaterThan(0);

    await waitFor(() => {
      expect(map.getLayer('zoos-clusters')).toBeTruthy();
      expect(map.getLayer('zoos-cluster-count')).toBeTruthy();
      expect(map.getLayer('zoos-unclustered')).toBeTruthy();
    });

    const clusterLayer = map.getLayer('zoos-clusters');
    expect(clusterLayer.filter).toEqual(['has', 'point_count']);

    const countLayer = map.getLayer('zoos-cluster-count');
    expect(countLayer.filter).toEqual(['has', 'point_count']);

    const unclusteredLayer = map.getLayer('zoos-unclustered');
    expect(unclusteredLayer.filter).toEqual(['!', ['has', 'point_count']]);

    const layerOrder = Array.from(map.layers.keys());
    const clustersIndex = layerOrder.indexOf('zoos-clusters');
    const countIndex = layerOrder.indexOf('zoos-cluster-count');
    const unclusteredIndex = layerOrder.indexOf('zoos-unclustered');

    expect(clustersIndex).toBeGreaterThanOrEqual(0);
    expect(countIndex).toBeGreaterThan(clustersIndex);
    expect(unclusteredIndex).toBeGreaterThan(countIndex);
  });
});
