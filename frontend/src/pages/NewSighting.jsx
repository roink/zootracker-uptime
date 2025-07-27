import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { LogSighting } from '../components/logForms';
import { API } from '../api';

// Page that shows the sighting form as an overlay modal. Used when logging a
// sighting from various parts of the app.
export default function NewSightingPage({ token, onLogged }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [zoos, setZoos] = useState([]);
  const [animals, setAnimals] = useState([]);
  const defaultZooId = location.state?.zooId || '';
  const defaultAnimalId = location.state?.animalId || '';
  // Names are provided so the form can show values immediately
  const defaultZooName = location.state?.zooName || '';
  const defaultAnimalName = location.state?.animalName || '';

  const redirectTo = location.state?.from || '/home';

  // Load the list of zoos and animals for the search fields
  useEffect(() => {
    fetch(`${API}/zoos`).then((r) => r.json()).then(setZoos);
    fetch(`${API}/animals`).then((r) => r.json()).then(setAnimals);
  }, []);

  // Return to the previous page after saving
  const handleSaved = () => {
    onLogged && onLogged();
    if (location.state?.backgroundLocation) {
      // Remove the modal from history and return to the previous page
      navigate(-1);
    } else {
      navigate(redirectTo);
    }
  };

  // Close the modal without saving
  const handleCancel = () => {
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
          defaultZooId={defaultZooId}
          defaultAnimalId={defaultAnimalId}
          initialZooName={defaultZooName}
          initialAnimalName={defaultAnimalName}

          onLogged={handleSaved}
          onCancel={handleCancel}
        />
      </div>
    </div>
  );
}
