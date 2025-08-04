import React, { useState, useEffect } from 'react';
import { LogSighting } from './logForms';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';

// Modal wrapper for creating or editing sightings. When a `sightingId`
// is provided the existing entry is loaded and the form works in edit mode.
export default function SightingModal({
  token,
  sightingId = null,
  defaultZooId = '',
  defaultAnimalId = '',
  defaultZooName = '',
  defaultAnimalName = '',
  // Optional pre-fetched lists to skip fetching inside the modal
  zoos: propZoos = null,
  animals: propAnimals = null,
  onLogged,
  onUpdated,
  onClose,
}) {
  // Start with provided lists if available
  const [zoos, setZoos] = useState(propZoos || []);
  const [animals, setAnimals] = useState(propAnimals || []);
  const [sighting, setSighting] = useState(null);
  const authFetch = useAuthFetch();

  // Load lists only when not supplied and fetch existing sighting when editing
  useEffect(() => {
    const loadData = async () => {
      // Fetch zoos when none were supplied or the array is empty
      if (!propZoos || propZoos.length === 0) {
        try {
          const resp = await fetch(`${API}/zoos`);
          if (resp.ok) setZoos(await resp.json());
        } catch {
          setZoos([]);
        }
      } else {
        setZoos(propZoos);
      }

      // Fetch animals when none were supplied or the array is empty
      if (!propAnimals || propAnimals.length === 0) {
        try {
          const resp = await fetch(`${API}/animals`);
          if (resp.ok) setAnimals(await resp.json());
        } catch {
          setAnimals([]);
        }
      } else {
        setAnimals(propAnimals);
      }
      if (sightingId) {
        try {
          const resp = await authFetch(`${API}/sightings/${sightingId}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (resp.ok) setSighting(await resp.json());
        } catch {
          setSighting(null);
        }
      }
    };
    loadData();
  }, [sightingId, token, authFetch, propZoos, propAnimals]);

  // Notify parent and close the modal after saving or deleting
  const handleDone = () => {
    if (sightingId) {
      onUpdated && onUpdated();
    } else {
      onLogged && onLogged();
    }
    onClose && onClose();
  };

  return (
    <div className="modal-overlay">
      <div className="modal-box">
        <LogSighting
          token={token}
          zoos={zoos}
          animals={animals}
          defaultZooId={sighting ? sighting.zoo_id : defaultZooId}
          defaultAnimalId={sighting ? sighting.animal_id : defaultAnimalId}
          defaultDate={
            sighting ? sighting.sighting_datetime.slice(0, 10) : undefined
          }
          initialZooName={
            sighting
              ? zoos.find((z) => z.id === sighting.zoo_id)?.name || defaultZooName
              : defaultZooName
          }
          initialAnimalName={
            sighting
              ? animals.find((a) => a.id === sighting.animal_id)?.common_name ||
                defaultAnimalName
              : defaultAnimalName
          }
          sightingId={sightingId}
          onLogged={handleDone}
          onDeleted={handleDone}
          onCancel={() => onClose && onClose()}
        />
      </div>
    </div>
  );
}

