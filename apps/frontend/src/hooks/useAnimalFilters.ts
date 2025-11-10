import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

interface UseAnimalFiltersResult {
  searchInput: string;
  setSearchInput: (value: string) => void;
  query: string;
  selectedClass: number | null;
  setSelectedClass: (value: number | null) => void;
  selectedOrder: number | null;
  setSelectedOrder: (value: number | null) => void;
  selectedFamily: number | null;
  setSelectedFamily: (value: number | null) => void;
  seenOnly: boolean;
  setSeenOnly: (value: boolean) => void;
  favoritesOnly: boolean;
  setFavoritesOnly: (value: boolean) => void;
  hasActiveFilters: boolean;
  clearAllFilters: () => void;
  handleClassChange: (value: string) => void;
  handleOrderChange: (value: string) => void;
  handleFamilyChange: (value: string) => void;
}

// Hook for managing animal filter state and URL synchronization
export function useAnimalFilters(): UseAnimalFiltersResult {
  const [searchParams, setSearchParams] = useSearchParams();

  // Parse initial values from URL
  const initialQuery = searchParams.get('q') || '';
  const classParam = searchParams.get('class');
  const initialClass = classParam ? Number.parseInt(classParam, 10) : null;
  const orderParam = searchParams.get('order');
  const initialOrder = orderParam ? Number.parseInt(orderParam, 10) : null;
  const familyParam = searchParams.get('family');
  const initialFamily = familyParam ? Number.parseInt(familyParam, 10) : null;
  const initialSeenOnly = searchParams.get('seen') === '1';
  const initialFavoritesOnly = searchParams.get('favorites') === '1';

  // State
  const [searchInput, setSearchInput] = useState(initialQuery);
  const [query, setQuery] = useState(initialQuery.trim());
  const [selectedClass, setSelectedClass] = useState<number | null>(initialClass);
  const [selectedOrder, setSelectedOrder] = useState<number | null>(initialOrder);
  const [selectedFamily, setSelectedFamily] = useState<number | null>(initialFamily);
  const [seenOnly, setSeenOnly] = useState(initialSeenOnly);
  const [favoritesOnly, setFavoritesOnly] = useState(initialFavoritesOnly);

  // Sync from URL to state only when URL changes
  const searchParamsStr = searchParams.toString();
  useEffect(() => {
    const urlQuery = searchParams.get('q') || '';
    if (urlQuery !== searchInput) {
      setSearchInput(urlQuery);
    }
    const trimmedUrlQuery = urlQuery.trim();
    if (trimmedUrlQuery !== query) {
      setQuery(trimmedUrlQuery);
    }

    const classStr = searchParams.get('class');
    const urlClass = classStr ? Number.parseInt(classStr, 10) : null;
    if (urlClass !== selectedClass) {
      setSelectedClass(urlClass);
    }
    const orderStr = searchParams.get('order');
    const urlOrder = orderStr ? Number.parseInt(orderStr, 10) : null;
    if (urlOrder !== selectedOrder) {
      setSelectedOrder(urlOrder);
    }
    const familyStr = searchParams.get('family');
    const urlFamily = familyStr ? Number.parseInt(familyStr, 10) : null;
    if (urlFamily !== selectedFamily) {
      setSelectedFamily(urlFamily);
    }
    const nextSeen = searchParams.get('seen') === '1';
    if (nextSeen !== seenOnly) {
      setSeenOnly(nextSeen);
    }
    const nextFavorites = searchParams.get('favorites') === '1';
    if (nextFavorites !== favoritesOnly) {
      setFavoritesOnly(nextFavorites);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParamsStr]);

  // Debounce search input
  useEffect(() => {
    const handle = window.setTimeout(() => {
      const trimmed = searchInput.trim();
      if (trimmed !== query) {
        setQuery(trimmed);
      }
    }, 250);
    return () => {
      window.clearTimeout(handle);
    };
  }, [searchInput, query]);

  // Sync from state to URL only when filters change
  useEffect(() => {
    const params = new URLSearchParams();
    if (query) {
      params.set('q', query);
    }
    if (selectedClass !== null) {
      params.set('class', String(selectedClass));
    }
    if (selectedOrder !== null) {
      params.set('order', String(selectedOrder));
    }
    if (selectedFamily !== null) {
      params.set('family', String(selectedFamily));
    }
    if (seenOnly) {
      params.set('seen', '1');
    }
    if (favoritesOnly) {
      params.set('favorites', '1');
    }
    const next = params.toString();
    const current = searchParams.toString();
    if (next !== current) {
      setSearchParams(params, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    favoritesOnly,
    query,
    selectedClass,
    selectedFamily,
    selectedOrder,
    seenOnly,
  ]);

  const handleClassChange = useCallback((value: string) => {
    const numValue = value ? Number.parseInt(value, 10) : null;
    setSelectedClass(numValue);
    setSelectedOrder(null);
    setSelectedFamily(null);
  }, []);

  const handleOrderChange = useCallback((value: string) => {
    const numValue = value ? Number.parseInt(value, 10) : null;
    setSelectedOrder(numValue);
    setSelectedFamily(null);
  }, []);

  const handleFamilyChange = useCallback((value: string) => {
    const numValue = value ? Number.parseInt(value, 10) : null;
    setSelectedFamily(numValue);
  }, []);

  const clearAllFilters = useCallback(() => {
    setQuery('');
    setSearchInput('');
    setSelectedClass(null);
    setSelectedOrder(null);
    setSelectedFamily(null);
    setSeenOnly(false);
    setFavoritesOnly(false);
  }, []);

  const hasActiveFilters =
    Boolean(query) ||
    selectedClass !== null ||
    selectedOrder !== null ||
    selectedFamily !== null ||
    seenOnly ||
    favoritesOnly;

  return {
    searchInput,
    setSearchInput,
    query,
    selectedClass,
    setSelectedClass,
    selectedOrder,
    setSelectedOrder,
    selectedFamily,
    setSelectedFamily,
    seenOnly,
    setSeenOnly,
    favoritesOnly,
    setFavoritesOnly,
    hasActiveFilters,
    clearAllFilters,
    handleClassChange,
    handleOrderChange,
    handleFamilyChange,
  };
}
