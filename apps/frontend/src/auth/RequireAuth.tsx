import { Navigate, Outlet, useLocation, useParams } from 'react-router-dom';

import { useAuth } from './AuthContext';

// Guard component that redirects unauthenticated users to the login page.
export default function RequireAuth() {
  const { isAuthenticated, hydrated } = useAuth();
  const location = useLocation();
  const { lang } = useParams();

  if (!hydrated) {
    return null;
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to={`/${lang}/login`}
        state={{ from: location }}
        replace
      />
    );
  }

  return <Outlet />;
}
