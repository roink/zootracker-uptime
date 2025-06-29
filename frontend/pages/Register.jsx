function RegisterPage({ onSignedUp }) {
  const navigate = ReactRouterDOM.useNavigate();
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");

  const submit = async (e) => {
    e.preventDefault();
    if (password !== confirm) {
      alert("Passwords do not match");
      return;
    }
    const resp = await fetch(`${API}/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    });
    if (resp.ok) {
      const user = await resp.json();
      onSignedUp(user, email);
      navigate("/");
    } else {
      alert("Sign up failed");
    }
  };

  return (
    <form onSubmit={submit} style={{ padding: '20px' }}>
      <h2>Sign Up</h2>
      <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
      <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <input type="password" placeholder="Confirm Password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      <button type="submit">Create Account</button>
      <div style={{ marginTop: '10px' }}>
        <ReactRouterDOM.Link to="/login">Back to Log In</ReactRouterDOM.Link>
      </div>
    </form>
  );
}
