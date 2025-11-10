// @ts-nocheck
import { test, expect } from '@playwright/test';
import { promises as fs } from 'node:fs';

import { mockLocationEstimate } from '../fixtures/api-mocks';

type ZooPoint = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
};

const STYLE_URL = new URL('../fixtures/minimal-style.json', import.meta.url);
const ZOOS_FIXTURE_URL = new URL('../fixtures/zoos.fixture.geojson', import.meta.url);
const ZOOS_SOURCE_ID = 'zoos';
const CLUSTER_LAYER_ID = 'zoos-clusters';
const UNCLUSTERED_LAYER_ID = 'zoos-unclustered';

declare global {
  interface Window {
    __mapHarnessReady?: boolean;
    __setZoosData?: (points: ZooPoint[]) => void;
    __setInitialView?: (view: {
      center: [number, number];
      zoom: number;
      bearing: number;
      pitch: number;
    }) => void;
    __mapInstanceReady?: boolean;
    __mapInstance?: any;
  }
}

test.describe('ZoosMap clustering behaviour', () => {
  test('clusters render at low zoom and expand into single markers', async ({ page }) => {
    const [styleBody, fixtureBody] = await Promise.all([
      fs.readFile(STYLE_URL, 'utf-8'),
      fs.readFile(ZOOS_FIXTURE_URL, 'utf-8'),
    ]);

    // Mock API endpoints for deterministic tests
    await mockLocationEstimate(page);

    await page.route('**/__map-style', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: styleBody,
      })
    );

    await page.goto('/zoos-map-e2e.html');

    await page.waitForFunction(() => window.__mapHarnessReady === true);
    await page.waitForFunction(
      () =>
        typeof window.__setZoosData === 'function' &&
        typeof window.__setInitialView === 'function'
    );

    const geojson = JSON.parse(fixtureBody) as {
      features: Array<{
        properties?: { id?: string; name?: string };
        geometry: { coordinates: [number, number] };
      }>;
    };

    const zoos: ZooPoint[] = geojson.features.map((feature, index) => ({
      id: feature.properties?.id ?? `fixture-${index + 1}`,
      name: feature.properties?.name ?? `Fixture Zoo ${index + 1}`,
      longitude: feature.geometry.coordinates[0],
      latitude: feature.geometry.coordinates[1],
    }));

    const accumulated = zoos.reduce(
      (acc, zoo) => ({
        lon: acc.lon + zoo.longitude,
        lat: acc.lat + zoo.latitude,
      }),
      { lon: 0, lat: 0 }
    );

    const viewCenter: [number, number] = [
      accumulated.lon / zoos.length,
      accumulated.lat / zoos.length,
    ];

    const bounds = zoos.reduce(
      (acc, zoo) => ({
        west: Math.min(acc.west, zoo.longitude),
        south: Math.min(acc.south, zoo.latitude),
        east: Math.max(acc.east, zoo.longitude),
        north: Math.max(acc.north, zoo.latitude),
      }),
      {
        west: zoos[0].longitude,
        south: zoos[0].latitude,
        east: zoos[0].longitude,
        north: zoos[0].latitude,
      }
    );

    await page.evaluate(
      ({ view, points }) => {
        window.__setInitialView?.(view);
        window.__setZoosData?.(points);
      },
      {
        view: { center: viewCenter, zoom: 5, bearing: 0, pitch: 0 },
        points: zoos,
      }
    );

    await page.waitForFunction(
      () =>
        window.__mapInstanceReady === true &&
        typeof window.__mapInstance?.isStyleLoaded === 'function' &&
        window.__mapInstance.isStyleLoaded(),
      { timeout: 15000 }
    );

    await page.waitForFunction(
      ({ clusterLayerId, unclusteredLayerId }) => {
        const map = window.__mapInstance;
        return (
          Boolean(map?.getLayer?.(clusterLayerId)) &&
          Boolean(map?.getLayer?.(unclusteredLayerId))
        );
      },
      { clusterLayerId: CLUSTER_LAYER_ID, unclusteredLayerId: UNCLUSTERED_LAYER_ID },
      { timeout: 10000 }
    );

    await page.waitForFunction(
      (sourceId) => {
        const map = window.__mapInstance;
        const source = map?.getSource(sourceId) as any;
        return Boolean(source?._data?.features?.length);
      },
      ZOOS_SOURCE_ID,
      { timeout: 10000 }
    );

    const lowZoomLevel = 5;

    const lowZoomClusters = await page.evaluate(
      async ({ zoom, clusterLayerId, center }) => {
        const map = window.__mapInstance;
        if (!map) throw new Error('Map instance not ready');

        await new Promise<void>((resolve) => {
          let resolved = false;
          const finish = () => {
            if (resolved) return;
            resolved = true;
            resolve();
          };
          map.once('idle', finish);
          map.jumpTo({ zoom, center });
          if (!map.isMoving?.()) {
            finish();
          }
          setTimeout(finish, 2000);
        });

        const canvas = map.getCanvas();
        const bounds = canvas
          ? [
              [0, 0],
              [canvas.clientWidth || canvas.width, canvas.clientHeight || canvas.height],
            ]
          : undefined;

        const start = Date.now();
        while (Date.now() - start < 5000) {
          const features = map.queryRenderedFeatures(bounds, { layers: [clusterLayerId] });
          if (features.length > 0) {
            return features.map((feature: any) => ({
              cluster: Boolean(feature.properties?.cluster),
              pointCount: Number(feature.properties?.point_count ?? 0),
              clusterId: feature.properties?.cluster_id ?? null,
            }));
          }
          await new Promise((resolve) => setTimeout(resolve, 100));
        }

        return [];
      },
      { zoom: lowZoomLevel, clusterLayerId: CLUSTER_LAYER_ID, center: viewCenter }
    );

    expect(lowZoomClusters.length).toBeGreaterThan(0);
    expect(lowZoomClusters.every((entry) => entry.cluster && entry.pointCount > 1)).toBe(true);

    const firstClusterId = lowZoomClusters.find((entry) => entry.clusterId != null)?.clusterId;
    expect(firstClusterId).toBeDefined();

    const clusterApiInfo = await page.evaluate(
      async ({ clusterId, sourceId }) => {
        const map = window.__mapInstance;
        if (!map || clusterId == null) return null;
        const source = map.getSource(sourceId);
        if (!source || typeof source.getClusterChildren !== 'function') {
          return null;
        }
        const children = await source.getClusterChildren(clusterId);
        const expansionZoom = await source.getClusterExpansionZoom(clusterId);
        return {
          childCount: Array.isArray(children) ? children.length : 0,
          expansionZoom: Number(expansionZoom),
          currentZoom: Number(map.getZoom?.() ?? 0),
        };
      },
      { clusterId: firstClusterId, sourceId: ZOOS_SOURCE_ID }
    );

    expect(clusterApiInfo).not.toBeNull();
    expect(clusterApiInfo?.childCount).toBeGreaterThan(1);
    expect(clusterApiInfo?.expansionZoom).toBeGreaterThan(clusterApiInfo?.currentZoom ?? 0);

    const highZoomLevel = Math.max((clusterApiInfo?.expansionZoom ?? 12) + 2, 14);

    const highZoomResult = await page.evaluate(
      async ({
        zoom,
        expectedCount,
        clusterLayerId,
        unclusteredLayerId,
        bounds: fitBounds,
      }) => {
        const map = window.__mapInstance;
        if (!map) throw new Error('Map instance not ready');

        map.fitBounds(
          [
            [fitBounds.west, fitBounds.south],
            [fitBounds.east, fitBounds.north],
          ],
          { padding: 40, duration: 0 }
        );

        await new Promise<void>((resolve) => {
          let resolved = false;
          const finish = () => {
            if (resolved) return;
            resolved = true;
            resolve();
          };
          map.once('idle', finish);
          map.jumpTo({ zoom });
          if (!map.isMoving?.()) {
            finish();
          }
          setTimeout(finish, 2000);
        });

        const canvas = map.getCanvas();
        const bounds = canvas
          ? [
              [0, 0],
              [canvas.clientWidth || canvas.width, canvas.clientHeight || canvas.height],
            ]
          : undefined;

        const start = Date.now();
        while (Date.now() - start < 5000) {
          const clusterFeatures = map.queryRenderedFeatures(bounds, { layers: [clusterLayerId] });
          const singleFeatures = map.queryRenderedFeatures(bounds, { layers: [unclusteredLayerId] });
          if (clusterFeatures.length === 0 && singleFeatures.length >= expectedCount) {
            return {
              clusterCount: 0,
              singleCount: singleFeatures.length,
            };
          }
          await new Promise((resolve) => setTimeout(resolve, 100));
        }

        const clusterFeatures = map.queryRenderedFeatures(bounds, { layers: [clusterLayerId] });
        const singleFeatures = map.queryRenderedFeatures(bounds, { layers: [unclusteredLayerId] });
        return {
          clusterCount: clusterFeatures.length,
          singleCount: singleFeatures.length,
        };
      },
      {
        zoom: highZoomLevel,
        expectedCount: zoos.length,
        clusterLayerId: CLUSTER_LAYER_ID,
        unclusteredLayerId: UNCLUSTERED_LAYER_ID,
        bounds,
      }
    );

    expect(highZoomResult.clusterCount).toBe(0);
    expect(highZoomResult.singleCount).toBeGreaterThanOrEqual(zoos.length);
    expect(highZoomResult.singleCount).toBeLessThanOrEqual(zoos.length);
  });
});
