import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { LogSighting } from './logForms';
import { API } from '../api';
import useAuthFetch from '../hooks/useAuthFetch';

// Modal wrapper for creating or editing sightings. When a `sightingId`
// is provided the existing entry is loaded and the form works in edit mode.
export default function SightingModal({
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
  const { lang } = useParams();
  const getName = (a) =>
    lang === 'de' ? a.name_de || a.name_en : a.name_en || a.name_de;

  // Load zoo list when none were provided
  useEffect(() => {
    const loadZoos = async () => {
      if (propZoos && propZoos.length > 0) {
        setZoos(propZoos);
        return;
      }
      try {
        const resp = await fetch(`${API}/zoos`);
        if (resp.ok) setZoos(await resp.json());
      } catch {
        setZoos([]);
      }
    };
    loadZoos();
  }, [propZoos]);

  // Load animal list when none were provided
  useEffect(() => {
    const loadAnimals = async () => {
      if (propAnimals && propAnimals.length > 0) {
        setAnimals(propAnimals);
        return;
      }
      try {
        const resp = await fetch(`${API}/animals`);
        if (resp.ok) setAnimals(await resp.json());
      } catch {
        setAnimals([]);
      }
    };
    loadAnimals();
  }, [propAnimals]);

  // Fetch existing sighting when editing
  useEffect(() => {
    if (!sightingId) return;
    const loadSighting = async () => {
      try {
        const resp = await authFetch(`${API}/sightings/${sightingId}`);
        if (resp.ok) setSighting(await resp.json());
      } catch {
        setSighting(null);
      }
    };
    loadSighting();
  }, [sightingId, authFetch]);

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
              ? getName(
                  animals.find((a) => a.id === sighting.animal_id) || {}
                ) || defaultAnimalName
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

