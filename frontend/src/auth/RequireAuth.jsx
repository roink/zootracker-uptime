import { Navigate, Outlet, useLocation, useParams } from 'react-router-dom';
import { useAuth } from './AuthContext.jsx';

// Guard component that redirects unauthenticated users to the login page.
export default function RequireAuth() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  const { lang } = useParams();

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
