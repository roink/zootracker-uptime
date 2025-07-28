// Base URL for API requests. By default the development build talks
// to the backend on localhost:8000. You can override this by setting
// the VITE_API_URL environment variable when running the dev server
// to test from other machines on the network.
const defaultApi = import.meta.env.DEV ? 'http://localhost:8000' : '';
export const API = import.meta.env.VITE_API_URL || defaultApi;
