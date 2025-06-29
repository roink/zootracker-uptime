const { useState, useEffect } = React;
const { BrowserRouter, Routes, Route, Link, Navigate, useNavigate } = ReactRouterDOM;

// Base URL of the FastAPI backend. When the frontend is served on a different
// port (e.g. via `python -m http.server`), the API won't be on the same origin
// anymore, so we explicitly point to the backend running on port 8000.
const API = "http://localhost:8000";

function Signup({ onSignedUp }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    const resp = await fetch(`${API}/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    });
    if (resp.ok) {
      const user = await resp.json();
      onSignedUp(user, email);
    } else {
      alert("Sign up failed");
    }
  };

  return (
    <form onSubmit={submit}>
      <h2>Sign Up</h2>
      <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
      <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <button type="submit">Create Account</button>
    </form>
  );
}



function ZooDetail({ zoo, onBack }) {
  const [animals, setAnimals] = useState([]);

  useEffect(() => {
    fetch(`${API}/zoos/${zoo.id}/animals`).then((r) => r.json()).then(setAnimals);
  }, [zoo]);

  return (
    <div>
      <button onClick={onBack}>Back</button>
      <h3>{zoo.name}</h3>
      <ul>
        {animals.map((a) => (
          <li key={a.id}>{a.common_name}</li>
        ))}
      </ul>
    </div>
  );
}

function LogSighting({ token, userId, animals, zoos, onLogged }) {
  const [animalId, setAnimalId] = useState(animals[0]?.id || "");
  const [zooId, setZooId] = useState(zoos[0]?.id || "");

  const submit = async (e) => {
    e.preventDefault();
    const sighting = {
      zoo_id: zooId,
      animal_id: animalId,
      user_id: userId,
      sighting_datetime: new Date().toISOString(),
    };
    const resp = await fetch(`${API}/sightings`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(sighting),
    });
    if (resp.ok) {
      onLogged();
    } else {
      alert("Failed to log sighting");
    }
  };

  return (
    <form onSubmit={submit}>
      <h3>Log Sighting</h3>
      <select value={zooId} onChange={(e) => setZooId(e.target.value)}>
        {zoos.map((z) => (
          <option key={z.id} value={z.id}>{z.name}</option>
        ))}
      </select>
      <select value={animalId} onChange={(e) => setAnimalId(e.target.value)}>
        {animals.map((a) => (
          <option key={a.id} value={a.id}>{a.common_name}</option>
        ))}
      </select>
      <button type="submit">Log</button>
    </form>
  );
}

function SeenAnimals({ token, userId, refresh }) {
  const [animals, setAnimals] = useState([]);

  useEffect(() => {
    fetch(`${API}/users/${userId}/animals`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then(setAnimals);
  }, [userId, refresh]);

  return (
    <div>
      <h3>Animals Seen</h3>
      <ul>
        {animals.map((a) => (
          <li key={a.id}>{a.common_name}</li>
        ))}
      </ul>
    </div>
  );
}

function LogVisit({ token, userId, zoos, onLogged }) {
  const [zooId, setZooId] = useState(zoos[0]?.id || "");
  const [visitDate, setVisitDate] = useState("");

  useEffect(() => {
    if (!zooId && zoos.length > 0) {
      setZooId(zoos[0].id);
    }
  }, [zoos]);

  const submit = async (e) => {
    e.preventDefault();
    const visit = { zoo_id: zooId, visit_date: visitDate };
    const resp = await fetch(`${API}/users/${userId}/visits`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(visit),
    });
    if (resp.ok) {
      onLogged && onLogged();
      setVisitDate("");
    } else {
      alert("Failed to log visit");
    }
  };

  return (
    <form onSubmit={submit}>
      <h3>Log Visit</h3>
      <select value={zooId} onChange={(e) => setZooId(e.target.value)}>
        {zoos.map((z) => (
          <option key={z.id} value={z.id}>{z.name}</option>
        ))}
      </select>
      <input
        type="date"
        value={visitDate}
        onChange={(e) => setVisitDate(e.target.value)}
      />
      <button type="submit">Log Visit</button>
    </form>
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

function AnimalSearch() {
  const [query, setQuery] = useState("");
  const [animals, setAnimals] = useState([]);

  const search = () => {
    fetch(`${API}/animals?q=${encodeURIComponent(query)}`)
      .then((r) => r.json())
      .then(setAnimals);
  };

  useEffect(search, []);

  return (
    <div>
      <h2>Search Animals</h2>
      <input
        placeholder="Search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <button onClick={search}>Search</button>
      <ul>
        {animals.map((a) => (
          <li key={a.id}>{a.common_name}</li>
        ))}
      </ul>
    </div>
  );
}

function AuthStatus({ token, email }) {
  return <div>{token ? <p>Logged in as {email}</p> : <p>Not logged in</p>}</div>;
}

function LandingPage({ onSignedUp, onLoggedIn, email }) {
  return (
    <div>
      <Signup onSignedUp={onSignedUp} />
      <Login emailPrefill={email} onLoggedIn={onLoggedIn} />
    </div>
  );
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

function ZoosPage({ selectedZoo, onSelectZoo, onBack }) {
  return (
    <div>
      <ZooSearch onSelectZoo={onSelectZoo} />
      {selectedZoo && <ZooDetail zoo={selectedZoo} onBack={onBack} />}
    </div>
  );
}

function AnimalsPage() {
  return <AnimalSearch />;
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
  const [userId, setUserId] = useState(null);
  const [userEmail, setUserEmail] = useState(null);
  const [zoos, setZoos] = useState([]);
  const [animals, setAnimals] = useState([]);
  const [selectedZoo, setSelectedZoo] = useState(null);
  const [refreshCounter, setRefreshCounter] = useState(0);
  const [showAdd, setShowAdd] = useState(false);

  useEffect(() => {
    fetch(`${API}/zoos`).then((r) => r.json()).then(setZoos);
    fetch(`${API}/animals`).then((r) => r.json()).then(setAnimals);
  }, []);

  const handleSignedUp = (user, email) => {
    setUserId(user.id);
    setUserEmail(email);
  };

  const handleLoggedIn = (tok, uid, email) => {
    setToken(tok);
    setUserId(uid);
    setUserEmail(email);
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
              <ZoosPage
                selectedZoo={selectedZoo}
                onSelectZoo={setSelectedZoo}
                onBack={() => setSelectedZoo(null)}
              />
            </RequireAuth>
          }
        />
        <Route
          path="/animals"
          element={
            <RequireAuth token={token}>
              <AnimalsPage />
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
