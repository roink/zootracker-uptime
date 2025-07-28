// Base URL for API requests. When running the React dev server we
// talk to the backend on port 8000. In production we use the same
// origin as the frontend to avoid hardcoding localhost which breaks
// on mobile devices.
export const API = import.meta.env.DEV ? 'http://localhost:8000' : '';
