const { useState, useEffect } = React;

const API = ""; // same origin

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
      onSignedUp(user, email, password);
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
      onLoggedIn(data.access_token, data.user_id);
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

function ZooList({ token, onSelectZoo }) {
  const [zoos, setZoos] = useState([]);

  useEffect(() => {
    fetch(`${API}/zoos`).then((r) => r.json()).then(setZoos);
  }, []);

  return (
    <div>
      <h2>Zoos</h2>
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

function ZooDetail({ zoo, token, onBack }) {
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

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [userId, setUserId] = useState(null);
  const [step, setStep] = useState(token ? "zoos" : "signup");
  const [zoos, setZoos] = useState([]);
  const [animals, setAnimals] = useState([]);
  const [selectedZoo, setSelectedZoo] = useState(null);
  const [refreshCounter, setRefreshCounter] = useState(0);

  useEffect(() => {
    if (token) {
      fetch(`${API}/zoos`).then((r) => r.json()).then(setZoos);
      fetch(`${API}/animals`).then((r) => r.json()).then(setAnimals);
      // decode token to get user id not necessary because API doesn't provide
    }
  }, [token]);

  const handleSignedUp = (user, email, password) => {
    setUserId(user.id);
    setStep("login");
  };

  const handleLoggedIn = (tok, uid) => {
    setToken(tok);
    setUserId(uid);
    setStep("zoos");
  };

  const handleZooSelect = (z) => {
    setSelectedZoo(z);
    setStep("zooDetail");
  };

  const handleBack = () => {
    setStep("zoos");
  };

  const refreshSeen = () => {
    setRefreshCounter((c) => c + 1);
  };

  return (
    <div>
      {step === "signup" && <Signup onSignedUp={handleSignedUp} />}
      {step === "login" && <Login onLoggedIn={handleLoggedIn} />}
      {step === "zoos" && (
        <>
          <ZooList token={token} onSelectZoo={handleZooSelect} />
          {token && userId && (
            <LogSighting token={token} userId={userId} animals={animals} zoos={zoos} onLogged={refreshSeen} />
          )}
          {token && userId && (
            <SeenAnimals token={token} userId={userId} refresh={refreshCounter} />
          )}
        </>
      )}
      {step === "zooDetail" && selectedZoo && (
        <ZooDetail zoo={selectedZoo} token={token} onBack={handleBack} />
      )}
    </div>
  );
}

ReactDOM.render(<App />, document.getElementById("root"));
