import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import ZooDetail from '../components/ZooDetail';
import { API } from '../api';
import Seo from '../components/Seo';

// Page that fetches a single zoo and renders the ZooDetail component
export default function ZooDetailPage({ refresh, onLogged }) {
  const { id } = useParams();
  const [zoo, setZoo] = useState(null);

  useEffect(() => {
    fetch(`${API}/zoos/${id}`)
      .then((r) => r.json())
      .then(setZoo)
      .catch(() => setZoo(null));
  }, [id]);

  if (!zoo) {
    return <div>Loading...</div>;
  }

  return (
    <>
      <Seo
        title={zoo.name}
        description={`Learn about ${zoo.name} and track your visit.`}
      />
      <ZooDetail
        zoo={zoo}
        refresh={refresh}
        onLogged={onLogged}
      />
    </>
  );
}
