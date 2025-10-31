import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import MapView from './MapView';

// Wrapper that loads the map only when scrolled into view to save resources.
export default function LazyMap({ latitude, longitude }: any) {
  const holderRef = useRef<any>(null);
  const [visible, setVisible] = useState(false);

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
    return () => io.disconnect();
  }, []);

  return (
    <div ref={holderRef}>
      {visible ? (
        <MapView latitude={latitude} longitude={longitude} />
      ) : (
        <div className="map-container" />
      )}
    </div>
  );
}

LazyMap.propTypes = {
  latitude: PropTypes.number,
  longitude: PropTypes.number,
};

