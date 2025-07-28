import { useNavigate } from 'react-router-dom';

// Hook returning a fetch wrapper that redirects to the login
// page if the response status is 401.
export default function useAuthFetch() {
  const navigate = useNavigate();
  return async (url, options = {}) => {
    const resp = await fetch(url, options);
    if (resp.status === 401) {
      navigate('/login');
    }
    return resp;
  };
}
