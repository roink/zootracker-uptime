import { useEffect, useMemo, useRef, useState } from 'react';

import MapView from './MapView';

interface LazyMapProps {
  latitude?: number | null;
  longitude?: number | null;
}

const resolveCoordinates = (value?: number | null): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

// Wrapper that loads the map only when scrolled into view to save resources.
export default function LazyMap({
  latitude,
  longitude
}: LazyMapProps) {
  const holderRef = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);
  const coords = useMemo(() => {
    const lat = resolveCoordinates(latitude);
    const lon = resolveCoordinates(longitude);
    return lat !== null && lon !== null ? { latitude: lat, longitude: lon } : null;
  }, [latitude, longitude]);

  useEffect(() => {
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry) return;
        if (entry.isIntersecting) {
          setVisible(true);
          io.disconnect();
        }
      },
      { rootMargin: '200px' }
    );
    if (holderRef.current) io.observe(holderRef.current);
    return () => { io.disconnect(); };
  }, []);

  return (
    <div ref={holderRef}>
      {visible && coords ? (
        <MapView latitude={coords.latitude} longitude={coords.longitude} />
      ) : (
        <div className="map-container" />
      )}
    </div>
  );
}

