import { useParams } from 'react-router-dom';

// Small hook to read the current language from the route.
export default function useLang() {
  const { lang } = useParams();
  return lang === 'de' ? 'de' : 'en';
}
