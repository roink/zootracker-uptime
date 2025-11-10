# Frontend package overview

The `frontend/` directory contains a Vite-powered React application for tracking zoo visits and animal sightings.

Key directories:
- `src/components/` – shared React components
- `src/pages/` – route pages
- `src/styles/` – custom CSS loaded by `main.jsx`
- `src/locales/` – translation files (English and German)
- `src/api.ts` – API configuration
- `src/auth/` – authentication context and helpers

## Testing and validation

When making changes to the frontend, always run:

1. **Linting**: `pnpm --filter zoo-tracker-frontend run lint`
2. **Type checking**: `pnpm --filter zoo-tracker-frontend run typecheck`
3. **Tests**: `pnpm --filter zoo-tracker-frontend run test`

The test command runs both unit tests (Vitest) and end-to-end tests (Playwright).

## Geolocation

The app uses the Capacitor Geolocation plugin (`@capacitor/geolocation`) for location services across web, iOS, and Android platforms. The plugin automatically detects the platform and uses the appropriate native APIs.

### Fallback Strategy

The app implements a two-tier location strategy:

1. **Primary**: GPS/device location via Capacitor Geolocation plugin
2. **Fallback**: Cloudflare geolocation estimate via `/api/location/estimate` endpoint

When `getCurrentPositionWithFallback()` is called, it first attempts to get precise device location. If the user denies permission or GPS fails, it automatically falls back to the Cloudflare estimate derived from the user's IP address. This ensures users always see nearby zoos sorted by distance, even without granting location permission.

### Configuration

**iOS** (`ios/App/App/Info.plist`):
Add both location usage descriptions (Capacitor requires both due to the underlying iOS component's capability to report location in the background):

```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>We use your location to show nearby zoos and sort them by distance.</string>
<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
<string>We use your location to show nearby zoos and sort them by distance.</string>
```

**Android** (`android/app/src/main/AndroidManifest.xml`):
Add location permissions:

```xml
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-feature android:name="android.hardware.location.gps" android:required="false" />
```

*Note for Android 12+*: Users can choose between "Approximate location" (`ACCESS_COARSE_LOCATION`) or "Precise location" (`ACCESS_FINE_LOCATION`). Since this app uses `enableHighAccuracy: false`, you can request only coarse location for lower friction:

```ts
import { Geolocation } from '@capacitor/geolocation';
const permissions = await Geolocation.requestPermissions({ permissions: ['coarseLocation'] });
```

The plugin exposes separate `location` and `coarseLocation` entries in `PermissionStatus`.

**Web**:
No additional configuration needed. The plugin uses the browser's Geolocation API. Note that `requestPermissions()` is not available on web; permission is handled by the browser's native prompt.

### Default Options

The app uses consistent geolocation options across all requests (defined in `src/utils/geolocation.ts`):

- `timeout`: 4000ms (4 seconds)
- `maximumAge`: 600000ms (10 minutes) - cached positions are acceptable
- `enableHighAccuracy`: false (prioritizes battery life over precision)

These defaults work well for zoo discovery and sorting use cases where approximate location is sufficient.
