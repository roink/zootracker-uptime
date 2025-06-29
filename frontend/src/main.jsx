import React, { useState, useEffect } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useParams } from "react-router-dom";

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
import { LogVisit, LogSighting } from "./components/logForms";




function ZooDetail({ zoo, token, userId, onBack }) {
  const [animals, setAnimals] = useState([]);
  const [visits, setVisits] = useState([]);
  const [seenAnimals, setSeenAnimals] = useState([]);
  const [showVisitForm, setShowVisitForm] = useState(false);
  const [loggingAnimal, setLoggingAnimal] = useState(null);
  const navigate = useNavigate();

  const loadAnimals = () => {
    fetch(`${API}/zoos/${zoo.id}/animals`).then((r) => r.json()).then(setAnimals);
  };

  const loadVisits = () => {
    if (!token) return;
    fetch(`${API}/visits`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then(setVisits)
      .catch(() => setVisits([]));
  };

  const loadSeen = () => {
    if (!token || !userId) return;
    fetch(`${API}/users/${userId}/animals`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then(setSeenAnimals)
      .catch(() => setSeenAnimals([]));
  };

  useEffect(() => {
    loadAnimals();
    loadVisits();
    loadSeen();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoo, token, userId]);

  const visited = visits.some((v) => v.zoo_id === zoo.id);
  const seenIds = new Set(seenAnimals.map((a) => a.id));

  return (
    <div style={{ padding: '20px' }}>
      <button onClick={onBack} style={{ marginBottom: '10px' }}>
        Back
      </button>
      {zoo.image_url && (
        <img
          src={zoo.image_url}
          alt={zoo.name}
          style={{ width: '100%', maxHeight: '200px', objectFit: 'cover' }}
        />
      )}
      <h3>{zoo.name}</h3>
      {zoo.address && <div style={{ color: '#555' }}>📍 {zoo.address}</div>}
      {zoo.latitude && zoo.longitude && (
        <iframe
          title="map"
          width="100%"
          height="200"
          style={{ border: 0, marginTop: '5px' }}
          src={`https://maps.google.com/maps?q=${zoo.latitude},${zoo.longitude}&z=14&output=embed`}
        ></iframe>
      )}
      {zoo.description && (
        <p style={{ marginTop: '10px', whiteSpace: 'pre-wrap' }}>{zoo.description}</p>
      )}
      <div style={{ marginTop: '10px' }}>Visited? {visited ? '☑️ Yes' : '✘ No'}</div>
      <button onClick={() => setShowVisitForm((v) => !v)} style={{ marginTop: '10px' }}>
        Log a Visit
      </button>
      {showVisitForm && (
        <div style={{ marginTop: '10px' }}>
          <LogVisit
            token={token}
            userId={userId}
            zoos={[zoo]}
            onLogged={() => {
              loadVisits();
              setShowVisitForm(false);
            }}
          />
        </div>
      )}
      <h4 style={{ marginTop: '20px' }}>Animals</h4>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th align="left">Name</th>
            <th style={{ textAlign: 'center' }}>Seen?</th>
            <th style={{ textAlign: 'center' }}></th>
          </tr>
        </thead>
        <tbody>
          {animals.map((a) => (
            <tr
              key={a.id}
              style={{ borderTop: '1px solid #ccc', cursor: 'pointer' }}
              onClick={() => navigate(`/animals/${a.id}`)}
            >
              <td>{a.common_name}</td>
              <td style={{ textAlign: 'center' }}>{seenIds.has(a.id) ? '✔️' : '—'}</td>
              <td style={{ textAlign: 'center' }}>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setLoggingAnimal(a);
                  }}
                >
                  ➕
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {loggingAnimal && (
        <div style={{ marginTop: '10px' }}>
          <LogSighting
            token={token}
            userId={userId}
            animals={[loggingAnimal]}
            zoos={[zoo]}
            onLogged={() => {
              loadSeen();
              setLoggingAnimal(null);
            }}
          />
        </div>
      )}
    </div>
  );
}


function ZooSearch({ onSelectZoo }) {
  const [query, setQuery] = useState("");
  const [zoos, setZoos] = useState([]);

  const search = () => {
    fetch(`${API}/zoos?q=${encodeURIComponent(query)}`)
      .then((r) => r.json())
      .then(setZoos);
  };

  useEffect(search, []);

  return (
    <div>
      <h2>Search Zoos</h2>
      <input
        placeholder="Search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <button onClick={search}>Search</button>
      <ul>
        {zoos.map((z) => (
          <li key={z.id}>
            <button onClick={() => onSelectZoo(z)}>{z.name}</button>
          </li>
        ))}
      </ul>
    </div>
  );
}


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

function LegacyZoosPage({ selectedZoo, onSelectZoo, onBack }) {
  return (
    <div>
      <ZooSearch onSelectZoo={onSelectZoo} />
      {selectedZoo && <ZooDetail zoo={selectedZoo} onBack={onBack} />}
    </div>
  );
}

function ZooDetailPage({ token, userId }) {
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

function NavBar({ onAddClick }) {
  const navigate = useNavigate();
  return (
    <nav
      style={{
        position: "fixed",
        bottom: 0,
        width: "100%",
        background: "#eee",
        padding: "10px",
        display: "flex",
        justifyContent: "space-around",
      }}
    >
      <button onClick={() => navigate("/")}>🏠</button>
      <button onClick={() => navigate("/zoos")}>🏛️</button>
      <button onClick={() => navigate("/animals")}>🐾</button>
      <button onClick={onAddClick}>➕</button>
      <button onClick={() => navigate("/badges")}>🎖️</button>
      <button onClick={() => navigate("/profile")}>👤</button>
    </nav>
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
  const [showAdd, setShowAdd] = useState(false);

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
      {token && <NavBar onAddClick={() => setShowAdd((s) => !s)} />}
      {showAdd && token && (
        <div
          style={{
            position: "fixed",
            bottom: "60px",
            right: "10px",
            background: "white",
            border: "1px solid #ccc",
            padding: "10px",
          }}
        >
          <LogVisit
            token={token}
            userId={userId}
            zoos={zoos}
            onLogged={() => {
              refreshSeen();
              setShowAdd(false);
            }}
          />
          <LogSighting
            token={token}
            userId={userId}
            animals={animals}
            zoos={zoos}
            onLogged={() => {
              refreshSeen();
              setShowAdd(false);
            }}
          />
        </div>
      )}
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
