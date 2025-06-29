function ZoosPage({ token }) {
  const navigate = ReactRouterDOM.useNavigate();
  const [zoos, setZoos] = React.useState([]);
  const [visits, setVisits] = React.useState([]);
  const [query, setQuery] = React.useState("");
  const [region, setRegion] = React.useState("All");
  const [visitedOnly, setVisitedOnly] = React.useState(false);

  React.useEffect(() => {
    fetch(`${API}/zoos`).then((r) => r.json()).then(setZoos);
  }, []);

  React.useEffect(() => {
    if (!token) return;
    fetch(`${API}/visits`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : []))
      .then(setVisits)
      .catch(() => setVisits([]));
  }, [token]);

  const visitedIds = React.useMemo(() => visits.map((v) => v.zoo_id), [visits]);

  const filtered = zoos
    .filter((z) => z.name.toLowerCase().includes(query.toLowerCase()))
    .filter((z) =>
      visitedOnly ? visitedIds.includes(z.id) : true
    )
    .filter((z) =>
      region === "All" ? true : (z.address || "").toLowerCase().includes(region.toLowerCase())
    );

  return (
    <div style={{ padding: "20px" }}>
      <div style={{ marginBottom: "10px" }}>
        <input
          placeholder="Search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          style={{ marginLeft: "10px" }}
        >
          <option value="All">All Regions</option>
          <option value="Europe">Europe</option>
          <option value="Asia">Asia</option>
          <option value="Africa">Africa</option>
          <option value="Americas">Americas</option>
          <option value="Oceania">Oceania</option>
        </select>
        <label style={{ marginLeft: "10px" }}>
          <input
            type="checkbox"
            checked={visitedOnly}
            onChange={(e) => setVisitedOnly(e.target.checked)}
          />
          {' '}Visited
        </label>
      </div>
      <div>
        {filtered.map((z) => (
          <div
            key={z.id}
            onClick={() => navigate(`/zoos/${z.id}`)}
            style={{
              border: "1px solid #ccc",
              padding: "10px",
              marginBottom: "10px",
              cursor: "pointer",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontWeight: "bold" }}>{z.name}</div>
                <div style={{ color: "#555" }}>📍 {z.address}</div>
              </div>
              {visitedIds.includes(z.id) && (
                <span
                  style={{
                    background: "#4caf50",
                    color: "white",
                    padding: "2px 6px",
                    borderRadius: "4px",
                    alignSelf: "center",
                  }}
                >
                  Visited
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
