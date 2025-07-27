import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ZooDetail from '../components/ZooDetail';
import { API } from '../api';

// Page that fetches a single zoo and renders the ZooDetail component
export default function ZooDetailPage({ token, userId, refresh }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [zoo, setZoo] = useState(null);

  useEffect(() => {
    fetch(`${API}/zoos/${id}`).then((r) => r.json()).then(setZoo);
  }, [id]);

  if (!zoo) {
    return <div>Loading...</div>;
  }

  return (
    <ZooDetail
      zoo={zoo}
      token={token}
      userId={userId}
      onBack={() => navigate(-1)}
      refresh={refresh}
    />
  );
}
