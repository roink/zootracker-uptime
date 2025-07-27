import React, { useState, useEffect } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

// Base URL of the FastAPI backend. When the frontend is served on a different
// port (e.g. via `python -m http.server`), the API won't be on the same origin
// anymore, so we explicitly point to the backend running on port 8000.
import { API } from "./api";
import Landing from "./pages/Landing";
import RegisterPage from "./pages/Register";
import LoginPage from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import ZoosPage from "./pages/Zoos";
import AnimalsPage from "./pages/Animals";
import AnimalDetailPage from "./pages/AnimalDetail";
import NewVisitPage from "./pages/NewVisit";
import NewSightingPage from "./pages/NewSighting";
import Header from "./components/Header";
import SearchPage from "./pages/Search";
import ZooDetailPage from "./pages/ZooDetail";
import "./styles/app.css";




function AuthStatus({ token, email }) {
  return <div>{token ? <p>Logged in as {email}</p> : <p>Not logged in</p>}</div>;
}


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
  return token ? children : <Navigate to="/" replace />;
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

  const refreshSeen = () => {
    setRefreshCounter((c) => c + 1);
  };

  return (
    <BrowserRouter>
      <Header token={token} />
      <Routes>
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
          path="/register"
          element={<RegisterPage onSignedUp={handleSignedUp} />}
        />
        <Route
          path="/login"
          element={<LoginPage email={userEmail} onLoggedIn={handleLoggedIn} />}
        />
        <Route
          path="/zoos"
          element={
            <RequireAuth token={token}>
              <ZoosPage token={token} />
            </RequireAuth>
          }
        />
        <Route
          path="/zoos/:id"
          element={
            <RequireAuth token={token}>
              <ZooDetailPage token={token} userId={userId} />
            </RequireAuth>
          }
        />
        <Route
          path="/animals"
          element={
            <RequireAuth token={token}>
              <AnimalsPage token={token} userId={userId} />
            </RequireAuth>
          }
        />
        <Route
          path="/animals/:id"
          element={
            <RequireAuth token={token}>
              <AnimalDetailPage token={token} userId={userId} />
            </RequireAuth>
          }
        />
        <Route path="/search" element={<SearchPage />} />
        <Route
          path="/sightings/new"
          element={
            <RequireAuth token={token}>
              <NewSightingPage token={token} />
            </RequireAuth>
          }
        />
        <Route
          path="/visits/new"
          element={
            <RequireAuth token={token}>
              <NewVisitPage token={token} />
            </RequireAuth>
          }
        />
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
      </Routes>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
