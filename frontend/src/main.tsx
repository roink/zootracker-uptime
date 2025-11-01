import { createAsyncStoragePersister } from '@tanstack/query-async-storage-persister';
import type { Query } from '@tanstack/query-core';
import { QueryClient } from '@tanstack/react-query';
import {
  PersistQueryClientProvider,
  type PersistQueryClientProviderProps
} from '@tanstack/react-query-persist-client';
import { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { Helmet, HelmetProvider } from 'react-helmet-async';
import { useTranslation } from 'react-i18next';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
  useParams,
  useNavigate
} from 'react-router-dom';

import { AuthProvider, useAuth } from './auth/AuthContext';
import RequireAuth from './auth/RequireAuth';
import EmailVerificationAlert from './components/EmailVerificationAlert';
import Footer from './components/Footer';
import Header from './components/Header';
import i18n, { loadLocale, normalizeLang } from './i18n';
// Base URL of the FastAPI backend. When the frontend is served on a different
// port (e.g. via `python -m http.server`), the API won't be on the same origin
// anymore, so we explicitly point to the backend running on port 8000.
import AnimalDetailPage from './pages/AnimalDetail';
import AnimalsPage from './pages/Animals';
import ContactPage from './pages/Contact';
import Dashboard from './pages/Dashboard';
import DataProtectionPage from './pages/DataProtection';
import ForgotPasswordPage from './pages/ForgotPassword';
import ImageAttributionPage from './pages/ImageAttribution';
import Landing from './pages/Landing';
import LegalNoticePage from './pages/LegalNotice';
import LoginPage from './pages/Login';
import ResetPasswordPage from './pages/ResetPassword';
import ResetPasswordRedirect from './pages/ResetPasswordRedirect';
import SearchPage from './pages/Search';
import VerifyEmailPage from './pages/VerifyEmail';
import ZooDetailPage from './pages/ZooDetail';
import ZoosPage from './pages/Zoos';
import 'bootstrap/dist/css/bootstrap.min.css';
import './styles/app.css';
import './styles/landing.css';
import 'maplibre-gl/dist/maplibre-gl.css';
import 'bootstrap/dist/js/bootstrap.bundle.min.js';

type DashboardPageProps = {
  refresh: number;
  onUpdate: () => void;
};

type LangAppProps = {
  refreshCounter: number;
  refreshSeen: () => void;
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 24 * 60 * 60 * 1000,
      refetchOnWindowFocus: false
    }
  }
});

const localStoragePersister = createAsyncStoragePersister({
  storage: {
    async getItem(key: string) {
      if (typeof window === 'undefined') {
        return null;
      }
      return window.localStorage.getItem(key);
    },
    async setItem(key: string, value: string) {
      if (typeof window === 'undefined') {
        return;
      }
      window.localStorage.setItem(key, value);
    },
    async removeItem(key: string) {
      if (typeof window === 'undefined') {
        return;
      }
      window.localStorage.removeItem(key);
    }
  }
});

const persistOptions: PersistQueryClientProviderProps['persistOptions'] = {
  persister: localStoragePersister,
  dehydrateOptions: {
    shouldDehydrateQuery: (query: Query) =>
      !Array.isArray(query.queryKey) || query.queryKey[0] !== 'user'
  },
  maxAge: 24 * 60 * 60 * 1000,
  buster: 'app@1.0.0'
};

export function DashboardPage({ refresh, onUpdate }: DashboardPageProps) {
  return <Dashboard refresh={refresh} onUpdate={onUpdate} />;
}

export function BadgesPage() {
  return <h2>Badges</h2>;
}

export function ProfilePage() {
  const { user } = useAuth();
  return (
    <div>
      <h2>Profile</h2>
      <p>{user?.email ?? '—'}</p>
    </div>
  );
}

export function AppRoutes({ refreshCounter, refreshSeen }: LangAppProps) {
  const location = useLocation();
  const { isAuthenticated } = useAuth();
  return (
    <div className="d-flex flex-column page-wrapper">
      <Header />
      <main className="flex-grow-1 pb-5">
        <EmailVerificationAlert />
        <Routes location={location}>
          <Route
            index
            element={
              isAuthenticated ? (
                <DashboardPage refresh={refreshCounter} onUpdate={refreshSeen} />
              ) : (
                <Landing />
              )
            }
          />
          <Route path="landing" element={<Navigate to=".." replace />} />
          <Route element={<RequireAuth />}>
            <Route
              path="home"
              element={<DashboardPage refresh={refreshCounter} onUpdate={refreshSeen} />}
            />
            <Route path="badges" element={<BadgesPage />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>
          <Route path="login" element={<LoginPage />} />
          <Route path="forgot-password" element={<ForgotPasswordPage />} />
          <Route path="reset-password" element={<ResetPasswordPage />} />
          <Route path="verify" element={<VerifyEmailPage />} />
          <Route path="zoos" element={<ZoosPage />} />
          <Route
            path="zoos/:slug"
            element={<ZooDetailPage refresh={refreshCounter} onLogged={refreshSeen} />}
          />
          <Route path="animals" element={<AnimalsPage />} />
          <Route
            path="animals/:slug"
            element={<AnimalDetailPage refresh={refreshCounter} onLogged={refreshSeen} />}
          />
          <Route path="images/:mid" element={<ImageAttributionPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="legal-notice" element={<LegalNoticePage />} />
          <Route path="impress" element={<Navigate to="../legal-notice" replace />} />
          <Route path="data-protection" element={<DataProtectionPage />} />
          <Route path="contact" element={<ContactPage />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}

export function LangApp({ refreshCounter, refreshSeen }: LangAppProps) {
  const params = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const lang = params['lang'];
  const rest = params['*'] ?? '';
  const { ready } = useTranslation();

  useEffect(() => {
    let isActive = true;

    const applyLocale = async () => {
      try {
        const activeLang = await loadLocale(lang);
        if (!isActive) return;

        localStorage.setItem('lang', activeLang);

        if (activeLang !== lang) {
          const suffix = rest ? `/${rest}` : '';
          const search = location.search || '';
          const hash = location.hash || '';
          void navigate(`/${activeLang}${suffix}${search}${hash}`, { replace: true });
        }
      } catch (error) {
        console.error('Failed to load locale', error);
      }
    };

    void applyLocale();

    return () => {
      isActive = false;
    };
  }, [lang, rest, navigate, location.search, location.hash]);

  if (!ready) {
    return null;
  }

  return <AppRoutes refreshCounter={refreshCounter} refreshSeen={refreshSeen} />;
}

export function RootRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    const detected = i18n.services?.languageDetector?.detect?.();
    const candidate = Array.isArray(detected) ? detected[0] : detected;
    const targetLang = normalizeLang(candidate);
    void navigate(`/${targetLang}`, { replace: true });
  }, [navigate]);
  return null;
}

export function VerifyEmailRedirect() {
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => {
    const stored = localStorage.getItem('lang');
    const detected = i18n.services?.languageDetector?.detect?.();
    const candidate = stored || (Array.isArray(detected) ? detected[0] : detected);
    const targetLang = normalizeLang(candidate);
    const search = location.search || '';
    const hash = location.hash || '';
    void navigate(`/${targetLang}/verify${search}${hash}`, { replace: true });
  }, [navigate, location.search, location.hash]);
  return null;
}

export function App() {
  const [refreshCounter, setRefreshCounter] = useState(0);

  const refreshSeen = () => {
    setRefreshCounter((c) => c + 1);
  };

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/verify" element={<VerifyEmailRedirect />} />
        <Route path="/reset-password" element={<ResetPasswordRedirect />} />
        <Route
          path="/:lang/*"
          element={<LangApp refreshCounter={refreshCounter} refreshSeen={refreshSeen} />}
        />
      </Routes>
    </BrowserRouter>
  );
}

const helmetContext: Record<string, unknown> = {};

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Unable to find root element');
}

ReactDOM.createRoot(rootElement).render(
  <HelmetProvider context={helmetContext}>
    <Helmet titleTemplate="%s - ZooTracker" defaultTitle="ZooTracker" />
    <PersistQueryClientProvider client={queryClient} persistOptions={persistOptions}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </PersistQueryClientProvider>
  </HelmetProvider>
);
