import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import { LogSighting } from '../components/logForms';
import { API } from '../api';

// Overlay page to edit an existing sighting
export default function EditSightingPage({ token, onUpdated }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [zoos, setZoos] = useState([]);
  const [animals, setAnimals] = useState([]);
  const [sighting, setSighting] = useState(null);

  const defaultZooId = location.state?.zooId || '';
  const defaultAnimalId = location.state?.animalId || '';
  const defaultZooName = location.state?.zooName || '';
  const defaultAnimalName = location.state?.animalName || '';

  const redirectTo = location.state?.from || '/home';

  useEffect(() => {
    fetch(`${API}/zoos`).then((r) => r.json()).then(setZoos);
    fetch(`${API}/animals`).then((r) => r.json()).then(setAnimals);
    fetch(`${API}/sightings/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then(setSighting);
  }, [id, token]);

  const handleDone = () => {
    onUpdated && onUpdated();
    if (location.state?.backgroundLocation) {
      navigate(-1);
    } else {
      navigate(redirectTo);
    }
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
          defaultDate={sighting ? sighting.sighting_datetime.slice(0, 10) : undefined}
          initialZooName={
            sighting
              ? zoos.find((z) => z.id === sighting.zoo_id)?.name || defaultZooName
              : defaultZooName
          }
          initialAnimalName={
            sighting
              ? animals.find((a) => a.id === sighting.animal_id)?.common_name || defaultAnimalName
              : defaultAnimalName
          }
          sightingId={id}
          onLogged={handleDone}
          onDeleted={handleDone}
          onCancel={handleDone}
        />
      </div>
    </div>
  );
}

