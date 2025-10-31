import { Link, useLocation } from 'react-router-dom';
import useLang from '../hooks/useLang';

// Switch between English and German by linking to the equivalent URL.
export default function LanguageSwitcher() {
  const lang = useLang();
  const { pathname, search, hash } = useLocation();
  const other = lang === 'de' ? 'en' : 'de';
  const otherPath = `/${other}${pathname.replace(/^\/(en|de)/, '')}${search}${hash}`;

  return (
    <Link
      className="nav-link"
      to={otherPath}
      aria-label={`Switch language to ${other === 'de' ? 'Deutsch' : 'English'}`}
    >
      {other.toUpperCase()}
    </Link>
  );
}
