import { useState, useEffect, useRef } from 'react';
import { API } from '../api';
import searchCache from '../searchCache';

// Hook that returns zoo/animal search suggestions for a query.
// Uses a 500ms debounce and shared cache so components don't
// repeatedly fetch the same results.
export default function useSearchSuggestions(query, enabled = true) {
  const [results, setResults] = useState({ zoos: [], animals: [] });
  const fetchRef = useRef(null);

  useEffect(() => {
    if (!enabled || !query.trim()) {
      setResults({ zoos: [], animals: [] });
      if (fetchRef.current) fetchRef.current.abort();
      return;
    }
    const q = query.trim().toLowerCase();
    const cached = searchCache[q];
    if (cached) {
      setResults(cached);
      return;
    }
    const controller = new AbortController();
    fetchRef.current = controller;
    const timeout = setTimeout(() => {
      fetch(`${API}/search?q=${encodeURIComponent(q)}&limit=5`, {
        signal: controller.signal,
      })
        .then((r) => r.json())
        .then((res) => {
          searchCache[q] = res;
          if (!controller.signal.aborted) setResults(res);
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setResults({ zoos: [], animals: [] });
          }
        });
    }, 500);
    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, [query, enabled]);

  return results;
}
