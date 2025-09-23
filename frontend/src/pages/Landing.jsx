import { Link, useParams } from 'react-router-dom';
import Seo from '../components/Seo';

// Simple marketing page shown at the root of the site.

export default function Landing() {
  const { lang } = useParams();
  const prefix = `/${lang}`;
  return (
    <div className="text-center py-4">
      <Seo
        title="Track Your Zoo Adventures"
        description="Log your zoo visits, discover animals and earn badges with ZooTracker."
      />
      <h1>Track your zoo adventures</h1>
      <div className="row justify-content-center mt-3">
        <div className="col-4 col-md-2">
          <img className="img-fluid" src="https://via.placeholder.com/150" alt="screenshot" />
        </div>
        <div className="col-4 col-md-2">
          <img className="img-fluid" src="https://via.placeholder.com/150" alt="screenshot" />
        </div>
        <div className="col-4 col-md-2">
          <img className="img-fluid" src="https://via.placeholder.com/150" alt="screenshot" />
        </div>
      </div>
      <div className="d-flex justify-content-center gap-4 mt-3">
        <div>
          <div className="icon-large">📍</div>
          <p>Track Visits</p>
        </div>
        <div>
          <div className="icon-large">🎖️</div>
          <p>Earn Badges</p>
        </div>
        <div>
          <div className="icon-large">🐾</div>
          <p>Discover Animals</p>
        </div>
      </div>
      <div className="mt-4">
        <Link className="btn btn-primary me-2" to={`${prefix}/login#signup`}>
          Sign Up
        </Link>
        <Link className="btn btn-secondary" to={`${prefix}/login`}>
          Log In
        </Link>
      </div>
    </div>
  );
}
