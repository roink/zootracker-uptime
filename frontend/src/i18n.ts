// @ts-nocheck
/* eslint-disable import/no-named-as-default-member */
import i18n from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { initReactI18next } from 'react-i18next';

export const DEFAULT_LANG = 'en';
export const SUPPORTED_LANGS = ['en', 'de'];
export const LOCALE_MODULES = import.meta.glob('./locales/*/common.json');

const inFlightLoads = new Map();

export function normalizeLang(lang) {
  if (typeof lang !== 'string') {
    return DEFAULT_LANG;
  }
  const lower = lang.toLowerCase();
  if (SUPPORTED_LANGS.includes(lower)) {
    return lower;
  }
  const partialMatch = SUPPORTED_LANGS.find((lng) =>
    lower === lng || lower.startsWith(`${lng}-`) || lower.startsWith(`${lng}_`)
  );
  return partialMatch ?? DEFAULT_LANG;
}

// Initialize i18next without bundled resources; languages are loaded lazily.
i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: DEFAULT_LANG,
    interpolation: { escapeValue: false },
    react: { useSuspense: false },
    supportedLngs: SUPPORTED_LANGS,
    nonExplicitSupportedLngs: true,
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'lang',
      checkForSimilarInWhitelist: true,
    },
  });

export async function loadLocale(requestedLang) {
  const activeLang = normalizeLang(requestedLang);
  if (
    i18n.language === activeLang &&
    i18n.hasResourceBundle(activeLang, 'translation')
  ) {
    document.documentElement.lang = activeLang;
    return activeLang;
  }

  const existingLoad = inFlightLoads.get(activeLang);
  if (existingLoad) {
    return existingLoad;
  }

  const loadPromise = (async () => {
    const localeKey = `./locales/${activeLang}/common.json`;
    const loader = LOCALE_MODULES[localeKey];

    if (!loader) {
      if (activeLang === DEFAULT_LANG) {
        document.documentElement.lang = DEFAULT_LANG;
        return DEFAULT_LANG;
      }
      return loadLocale(DEFAULT_LANG);
    }

    const module = await loader();
    i18n.addResourceBundle(
      activeLang,
      'translation',
      module.default,
      true,
      true,
    );
    await i18n.changeLanguage(activeLang);
    document.documentElement.lang = activeLang;
    return activeLang;
  })();

  inFlightLoads.set(activeLang, loadPromise);

  try {
    return await loadPromise;
  } finally {
    inFlightLoads.delete(activeLang);
  }
}

export default i18n;
