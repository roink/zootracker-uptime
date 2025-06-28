const { useState, useEffect } = React;

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

function Login({ emailPrefill, onLoggedIn }) {
  const [email, setEmail] = useState(emailPrefill || "");
  const [password, setPassword] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    const body = new URLSearchParams();
    body.append("username", email);
    body.append("password", password);
    const resp = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (resp.ok) {
      const data = await resp.json();
      localStorage.setItem("token", data.access_token);
      onLoggedIn(data.access_token, data.user_id, email);
    } else {
      alert("Login failed");
    }
  };

  return (
    <form onSubmit={submit}>
      <h2>Login</h2>
      <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <button type="submit">Login</button>
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
  return (
    <div>
      {token ? <p>Logged in as {email}</p> : <p>Not logged in</p>}
    </div>
  );
}

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [userId, setUserId] = useState(null);
  const [userEmail, setUserEmail] = useState(null);
  const [zoos, setZoos] = useState([]);
  const [animals, setAnimals] = useState([]);
  const [selectedZoo, setSelectedZoo] = useState(null);
  const [refreshCounter, setRefreshCounter] = useState(0);

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

  const handleZooSelect = (z) => {
    setSelectedZoo(z);
  };

  const handleBack = () => {
    setSelectedZoo(null);
  };

  const refreshSeen = () => {
    setRefreshCounter((c) => c + 1);
  };

  return (
    <div>
      <AuthStatus token={token} email={userEmail} />
      <Signup onSignedUp={handleSignedUp} />
      <Login emailPrefill={userEmail} onLoggedIn={handleLoggedIn} />
      <ZooSearch onSelectZoo={handleZooSelect} />
      {selectedZoo && <ZooDetail zoo={selectedZoo} onBack={handleBack} />}
      <AnimalSearch />
      {token && userId && (
        <>
          <LogVisit token={token} userId={userId} zoos={zoos} onLogged={refreshSeen} />
          <LogSighting token={token} userId={userId} animals={animals} zoos={zoos} onLogged={refreshSeen} />
          <SeenAnimals token={token} userId={userId} refresh={refreshCounter} />
        </>
      )}
    </div>
  );
}

ReactDOM.render(<App />, document.getElementById("root"));
