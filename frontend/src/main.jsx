import { useState, useEffect } from "react";
import ReactDOM from "react-dom/client";
import { Helmet, HelmetProvider } from 'react-helmet-async';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";

// Base URL of the FastAPI backend. When the frontend is served on a different
// port (e.g. via `python -m http.server`), the API won't be on the same origin
// anymore, so we explicitly point to the backend running on port 8000.
import { API } from "./api";
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
import ImpressPage from "./pages/Impress";
import DataProtectionPage from "./pages/DataProtection";
import ContactPage from "./pages/Contact";
import Footer from "./components/Footer";
import "./styles/app.css";
// MapLibre default styles for the OpenFreeMap tiles
import "maplibre-gl/dist/maplibre-gl.css";

function DashboardPage({ token, userId, zoos, animals, refresh, onUpdate }) {
  return (
    <Dashboard
      token={token}
      userId={userId}
      zoos={zoos}
      animals={animals}
      refresh={refresh}
      onUpdate={onUpdate}
    />
  );
}


function BadgesPage() {
  return <h2>Badges</h2>;
}

function ProfilePage({ email }) {
  return (
    <div>
      <h2>Profile</h2>
      <p>{email}</p>
    </div>
  );
}


function RequireAuth({ token, children }) {
  return token ? children : <Navigate to="/login" replace />;
}

function AppRoutes({
  token,
  userId,
  userEmail,
  zoos,
  animals,
  refreshCounter,
  onSignedUp,
  onLoggedIn,
  onLoggedOut,
  refreshSeen,
}) {
  const location = useLocation();
  return (
    <div className="d-flex flex-column page-wrapper">
      <Header token={token} onLogout={onLoggedOut} />
      <main className="flex-grow-1 pb-5">
        <Routes location={location}>
        <Route
          path="/"
          element={
            token ? (
              <DashboardPage
                token={token}
                userId={userId}
                zoos={zoos}
                animals={animals}
                refresh={refreshCounter}
                onUpdate={refreshSeen}
              />
            ) : (
              <Landing />
            )
          }
        />
        <Route path="/landing" element={<Navigate to="/" replace />} />
        <Route
          path="/home"
          element={
            <RequireAuth token={token}>
              <DashboardPage
                token={token}
                userId={userId}
                zoos={zoos}
                animals={animals}
                refresh={refreshCounter}
                onUpdate={refreshSeen}
              />
            </RequireAuth>
          }
        />
        <Route
          path="/login"
          element={
            <LoginPage
              email={userEmail}
              onLoggedIn={onLoggedIn}
              onSignedUp={onSignedUp}
            />
          }
        />
        <Route path="/zoos" element={<ZoosPage token={token} />} />
        <Route
          path="/zoos/:id"
          element={
            <ZooDetailPage
              token={token}
              userId={userId}
              refresh={refreshCounter}
              onLogged={refreshSeen}
            />
          }
        />
        <Route path="/animals" element={<AnimalsPage token={token} userId={userId} />} />
        <Route
          path="/animals/:id"
          element={
            <AnimalDetailPage
              token={token}
              userId={userId}
              refresh={refreshCounter}
              onLogged={refreshSeen}
            />
          }
        />
        <Route path="/images/:mid" element={<ImageAttributionPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route
          path="/badges"
          element={
            <RequireAuth token={token}>
              <BadgesPage />
            </RequireAuth>
          }
        />
        <Route
          path="/profile"
          element={
            <RequireAuth token={token}>
              <ProfilePage email={userEmail} />
            </RequireAuth>
          }
        />
        <Route path="/impress" element={<ImpressPage />} />
        <Route path="/data-protection" element={<DataProtectionPage />} />
        <Route path="/contact" element={<ContactPage />} />
      </Routes>
      </main>
      <Footer />
    </div>
  );
}

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [userId, setUserId] = useState(localStorage.getItem("userId"));
  const [userEmail, setUserEmail] = useState(localStorage.getItem("userEmail"));
  const [zoos, setZoos] = useState([]);
  const [animals, setAnimals] = useState([]);
  const [refreshCounter, setRefreshCounter] = useState(0);

  useEffect(() => {
    fetch(`${API}/zoos`).then((r) => r.json()).then(setZoos);
    fetch(`${API}/animals`).then((r) => r.json()).then(setAnimals);
  }, []);

  const handleSignedUp = (user, email) => {
    setUserId(user.id);
    setUserEmail(email);
    localStorage.setItem("userId", user.id);
    localStorage.setItem("userEmail", email);
  };

  const handleLoggedIn = (tok, uid, email) => {
    setToken(tok);
    setUserId(uid);
    setUserEmail(email);
    localStorage.setItem("token", tok);
    localStorage.setItem("userId", uid);
    localStorage.setItem("userEmail", email);
  };

  const handleLoggedOut = () => {
    setToken(null);
    setUserId(null);
    setUserEmail(null);
    localStorage.removeItem("token");
    localStorage.removeItem("userId");
    localStorage.removeItem("userEmail");
  };

  const refreshSeen = () => {
    setRefreshCounter((c) => c + 1);
  };

  // Opt in to React Router v7 behaviors to silence future warnings
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AppRoutes
        token={token}
        userId={userId}
        userEmail={userEmail}
        zoos={zoos}
        animals={animals}
        refreshCounter={refreshCounter}
        onSignedUp={handleSignedUp}
        onLoggedIn={handleLoggedIn}
        onLoggedOut={handleLoggedOut}
        refreshSeen={refreshSeen}
      />
    </BrowserRouter>
  );
}

const helmetContext = {};

ReactDOM.createRoot(document.getElementById("root")).render(
  <HelmetProvider context={helmetContext}>
    <Helmet titleTemplate="%s - ZooTracker" defaultTitle="ZooTracker" />
    <App />
  </HelmetProvider>
);
