import type { SearchResults } from './types/domain';

// Simple in-memory cache for search results keyed by the query string.
// Components can import this object to avoid repeated API calls.
const searchCache: Record<string, SearchResults> = {};

export default searchCache;
