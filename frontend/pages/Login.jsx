function LoginPage({ email, onLoggedIn }) {
  return (
    <div style={{ padding: '20px' }}>
      <Login emailPrefill={email} onLoggedIn={onLoggedIn} />
    </div>
  );
}

