import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import VisitForm from '../components/VisitForm';
import { API } from '../api';

export default function NewVisitPage({ token }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [zoos, setZoos] = useState([]);
  const defaultZooId = location.state?.zooId || '';
  const redirectTo = location.state?.from || '/home';

  useEffect(() => {
    fetch(`${API}/zoos`).then(r => r.json()).then(setZoos);
  }, []);

  const handleSaved = (visit) => {
    if (defaultZooId) {
      navigate(`/zoos/${defaultZooId}`);
    } else {
      navigate(redirectTo);
    }
  };

  const handleCancel = () => {
    navigate(redirectTo);
  };

  const isDesktop = typeof window !== 'undefined' && window.innerWidth >= 600;

  const containerStyle = isDesktop
    ? {
        position: 'fixed',
        top: 0,
        bottom: 0,
        left: 0,
        right: 0,
        background: 'rgba(0,0,0,0.3)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }
    : { padding: '20px' };

  const formStyle = isDesktop
    ? { background: 'white', padding: '20px', border: '1px solid #ccc', width: '90%', maxWidth: '400px' }
    : {};

  return (
    <div style={containerStyle}>
      <div style={formStyle}>
        <VisitForm
          token={token}
          zoos={zoos}
          defaultZooId={defaultZooId}
          onSaved={handleSaved}
          onCancel={handleCancel}
        />
      </div>
    </div>
  );
}
