import { useEffect, useRef, useState } from 'react';

import { API } from '../api';
import searchCache from '../searchCache';
import type { SearchResults, ZooSummary, AnimalSummary } from '../types/domain';

const createEmptyResults = (): SearchResults => ({ zoos: [], animals: [] });

export default function useSearchSuggestions(query: string, enabled = true): SearchResults {
  const [results, setResults] = useState<SearchResults>(createEmptyResults);
  const fetchRef = useRef<AbortController | null>(null);

  useEffect(() => {
      const rawQuery = query.trim();
    if (!enabled || !rawQuery) {
      setResults(createEmptyResults());
      if (fetchRef.current) fetchRef.current.abort();
      return;
    }
    const q = rawQuery.toLowerCase();
    const cached = searchCache[q];
    if (cached) {
      setResults(cached);
      return;
    }
    const controller = new AbortController();
    fetchRef.current = controller;
    const timeout = setTimeout(() => {
      const params = new URLSearchParams({ limit: '5', q });

      const loadSuggestions = async () => {
        try {
          const [zoosRes, animalsRes] = await Promise.all([
            fetch(`${API}/zoos?${params.toString()}`, { signal: controller.signal }),
            fetch(`${API}/animals?${params.toString()}`, { signal: controller.signal })
          ]);

          if (!zoosRes.ok || !animalsRes.ok) {
            throw new Error('Search request failed');
          }

          const [zoosBody, animalsBody] = await Promise.all([
            zoosRes.json(),
            animalsRes.json()
          ]);

          const combined: SearchResults = {
              zoos: Array.isArray((zoosBody as { items?: unknown }).items)
                ? (zoosBody as { items: ZooSummary[] }).items
                : [],
            animals: Array.isArray(animalsBody)
              ? (animalsBody as AnimalSummary[])
              : []
          };

          searchCache[q] = combined;
          if (!controller.signal.aborted) {
            setResults(combined);
          }
        } catch {
          if (!controller.signal.aborted) {
            setResults(createEmptyResults());
          }
        }
      };

      void loadSuggestions();
    }, 500);
    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, [query, enabled]);

  return results;
}
