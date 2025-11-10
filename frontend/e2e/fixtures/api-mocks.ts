import type { Page, Route } from '@playwright/test';

/**
 * Stub the /api/location/estimate endpoint with a known location.
 * This ensures E2E tests are deterministic and don't rely on actual IP geolocation.
 * 
 * @param page - Playwright page instance
 * @param latitude - Latitude to return (default: Berlin)
 * @param longitude - Longitude to return (default: Berlin)
 */
export async function mockLocationEstimate(
  page: Page,
  latitude = 52.52,
  longitude = 13.405
): Promise<void> {
  await page.route('**/api/location/estimate', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ latitude, longitude }),
      headers: {
        'Cache-Control': 'private, no-store',
      },
    })
  );
}

/**
 * Stub the /api/location/estimate endpoint to return no location.
 * Useful for testing scenarios where geolocation is unavailable.
 */
export async function mockLocationEstimateUnavailable(page: Page): Promise<void> {
  await page.route('**/api/location/estimate', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ latitude: null, longitude: null }),
      headers: {
        'Cache-Control': 'private, no-store',
      },
    })
  );
}
