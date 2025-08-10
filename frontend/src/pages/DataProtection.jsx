import Seo from '../components/Seo';

// Detailed data protection information for the application.
export default function DataProtectionPage() {
  return (
    <div className="container py-4">
      <Seo
        title="Data Protection"
        description="Learn how ZooTracker stores and protects your data."
      />
      <h2>Data Protection</h2>
      <p>
        We take the protection of your personal information seriously. This page
        explains what data we collect and how it is used.
      </p>
      <h4 className="mt-3">Data We Store</h4>
      <ul>
        <li>Your name and e‑mail address for account management</li>
        <li>
          A salted and hashed version of your password so that only you can log
          in
        </li>
        <li>
          Records of your zoo visits and animal sightings including any notes or
          uploaded photo URLs
        </li>
        <li>Your earned achievements within the application</li>
      </ul>
      <p>
        All data is stored in a database hosted on a Hetzner server located in
        Germany. We do not share your information with third parties.
      </p>
      <h4 className="mt-3">Map Tiles</h4>
      <p>
        Some pages embed an interactive map using the MapLibre library and tiles
        served from <code>tiles.openfreemap.org</code> (OpenStreetMap data). When a
        map loads, your browser requests map tiles directly from that server; this
        request includes your IP address and typical browser headers. We do not
        receive or store this connection data.
      </p>
      <p>
        You can prevent map requests by disabling map loading in your browser or
        using content blocking. Our application functionality remains available
        without maps.
      </p>
    </div>
  );
}
