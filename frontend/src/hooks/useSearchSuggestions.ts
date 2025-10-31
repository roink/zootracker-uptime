// @ts-nocheck
import { useState, useEffect, useRef } from 'react';
import { API } from '../api';
import searchCache from '../searchCache';

// Hook that returns zoo/animal search suggestions for a query.
// Uses a 500ms debounce and shared cache so components don't
// repeatedly fetch the same results.
export default function useSearchSuggestions(query, enabled = true) {
  const [results, setResults] = useState({ zoos: [], animals: [] });
  const fetchRef = useRef<any>(null);

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
      const params = new URLSearchParams({ limit: '5', q });
      Promise.all([
        fetch(`${API}/zoos?${params.toString()}`, { signal: controller.signal }),
        fetch(`${API}/animals?${params.toString()}`, { signal: controller.signal }),
      ])
        .then(async ([zoosRes, animalsRes]) => {
          if (!zoosRes.ok || !animalsRes.ok) {
            throw new Error('Search request failed');
          }
          const [zoosBody, animalsBody] = await Promise.all([
            zoosRes.json(),
            animalsRes.json(),
          ]);
          const combined = {
            zoos: Array.isArray(zoosBody?.items) ? zoosBody.items : [],
            animals: Array.isArray(animalsBody) ? animalsBody : [],
          };
          searchCache[q] = combined;
          if (!controller.signal.aborted) setResults(combined);
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
