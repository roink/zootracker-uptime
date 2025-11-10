import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import i18n, { normalizeLang } from '../i18n';

// Redirect to the language-prefixed reset password route while preserving query params.
export default function ResetPasswordRedirect() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
      const stored = localStorage.getItem('lang');
      const detector = i18n.services.languageDetector;
      const detected =
        detector && typeof detector.detect === 'function' ? detector.detect() : undefined;
    const candidate = stored || (Array.isArray(detected) ? detected[0] : detected);
    const targetLang = normalizeLang(candidate);
    const search = location.search || '';
    const hash = location.hash || '';
    void navigate(`/${targetLang}/reset-password${search}${hash}`, { replace: true });
  }, [navigate, location.search, location.hash]);

  return null;
}
