// Base URL for API requests. During development the frontend might be
// accessed via a local IP such as 192.168.x.x when testing on a phone.
// In that case requests should go to the same host on port 8000. This
// fallback avoids using `localhost` which would resolve to the mobile
// device itself and fail.
const hostname = window.location.hostname;
const defaultApi = import.meta.env.DEV ? `http://${hostname}:8000` : '';

// `VITE_API_URL` can override this if the backend runs elsewhere.
export const API = import.meta.env.VITE_API_URL || defaultApi;
