import { useState, useEffect } from "react";
import { QueryClient } from "@tanstack/react-query";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import ReactDOM from "react-dom/client";
import { Helmet, HelmetProvider } from 'react-helmet-async';
import { useTranslation } from 'react-i18next';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
  useParams,
  useNavigate,
} from "react-router-dom";
import i18n, { loadLocale, normalizeLang } from './i18n';
import { AuthProvider, useAuth } from './auth/AuthContext.jsx';
import RequireAuth from './auth/RequireAuth.jsx';

// Base URL of the FastAPI backend. When the frontend is served on a different
// port (e.g. via `python -m http.server`), the API won't be on the same origin
// anymore, so we explicitly point to the backend running on port 8000.
import Landing from "./pages/Landing";
import LoginPage from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import ZoosPage from "./pages/Zoos";
import AnimalsPage from "./pages/Animals";
import AnimalDetailPage from "./pages/AnimalDetail";
import ImageAttributionPage from "./pages/ImageAttribution";
import Header from "./components/Header";
import SearchPage from "./pages/Search";
import ZooDetailPage from "./pages/ZooDetail";
import LegalNoticePage from "./pages/LegalNotice";
import DataProtectionPage from "./pages/DataProtection";
import ContactPage from "./pages/Contact";
import Footer from "./components/Footer";
import "./styles/app.css";
import "./styles/landing.css";
// MapLibre default styles for the OpenFreeMap tiles
import "maplibre-gl/dist/maplibre-gl.css";

// Cache API data and persist between reloads
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 24 * 60 * 60 * 1000,
      refetchOnWindowFocus: false,
    },
  },
});

const persister = createSyncStoragePersister({ storage: window.localStorage });
const persistOptions = {
  persister,
  dehydrateOptions: {
    shouldDehydrateQuery: (q) =>
      !Array.isArray(q.queryKey) || q.queryKey[0] !== 'user',
  },
  maxAge: 24 * 60 * 60 * 1000,
  buster: 'app@1.0.0',
};

function DashboardPage({ refresh, onUpdate }) {
  return <Dashboard refresh={refresh} onUpdate={onUpdate} />;
}

function BadgesPage() {
  return <h2>Badges</h2>;
}

function ProfilePage() {
  const { user } = useAuth();
  return (
    <div>
      <h2>Profile</h2>
      <p>{user?.email || '—'}</p>
    </div>
  );
}

function AppRoutes({ refreshCounter, refreshSeen }) {
  const location = useLocation();
  const { isAuthenticated } = useAuth();
  return (
    <div className="d-flex flex-column page-wrapper">
      <Header />
      <main className="flex-grow-1 pb-5">
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
              element={
                <DashboardPage refresh={refreshCounter} onUpdate={refreshSeen} />
              }
            />
            <Route path="badges" element={<BadgesPage />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>
          <Route path="login" element={<LoginPage />} />
          <Route path="zoos" element={<ZoosPage />} />
          <Route
            path="zoos/:slug"
            element={
              <ZooDetailPage
                refresh={refreshCounter}
                onLogged={refreshSeen}
              />
            }
          />
          <Route path="animals" element={<AnimalsPage />} />
          <Route
            path="animals/:slug"
            element={
              <AnimalDetailPage
                refresh={refreshCounter}
                onLogged={refreshSeen}
              />
            }
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

function LangApp({ refreshCounter, refreshSeen }) {
  const params = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const lang = params.lang;
  const rest = params['*'] ?? '';
  const { ready } = useTranslation();

  useEffect(() => {
    let isActive = true;

    const applyLocale = async () => {
      try {
        // Load the locale and redirect to a supported language if the URL
        // contains an unknown lang segment (e.g. direct visits to /animals).
        const activeLang = await loadLocale(lang);
        if (!isActive) return;

        localStorage.setItem('lang', activeLang);

        if (activeLang !== lang) {
          const suffix = rest ? `/${rest}` : '';
          const search = location.search || '';
          const hash = location.hash || '';
          navigate(`/${activeLang}${suffix}${search}${hash}`, { replace: true });
        }
      } catch (error) {
        // eslint-disable-next-line no-console
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

  return (
    <AppRoutes refreshCounter={refreshCounter} refreshSeen={refreshSeen} />
  );
}

function RootRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    const detected = i18n.services?.languageDetector?.detect?.();
    const candidate = Array.isArray(detected) ? detected[0] : detected;
    const targetLang = normalizeLang(candidate);
    navigate(`/${targetLang}`, { replace: true });
  }, [navigate]);
  return null;
}

function App() {
  const [refreshCounter, setRefreshCounter] = useState(0);

  const refreshSeen = () => {
    setRefreshCounter((c) => c + 1);
  };

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route
          path="/:lang/*"
          element={
            <LangApp
              refreshCounter={refreshCounter}
              refreshSeen={refreshSeen}
            />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

const helmetContext = {};

ReactDOM.createRoot(document.getElementById("root")).render(
  <HelmetProvider context={helmetContext}>
    <Helmet titleTemplate="%s - ZooTracker" defaultTitle="ZooTracker" />
    <PersistQueryClientProvider client={queryClient} persistOptions={persistOptions}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </PersistQueryClientProvider>
  </HelmetProvider>
);
