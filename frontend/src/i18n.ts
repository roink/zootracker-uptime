import i18n from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { initReactI18next } from 'react-i18next';

export const DEFAULT_LANG = 'en';
export const SUPPORTED_LANGS = ['en', 'de'] as const;
type SupportedLang = (typeof SUPPORTED_LANGS)[number];

type LocaleModule = { default: Record<string, unknown> };

export const LOCALE_MODULES = import.meta.glob<LocaleModule>('./locales/*/common.json');

const inFlightLoads = new Map<SupportedLang, Promise<SupportedLang>>();

export function normalizeLang(lang: unknown): SupportedLang {
  if (typeof lang !== 'string') {
    return DEFAULT_LANG;
  }
  const lower = lang.toLowerCase();
  if ((SUPPORTED_LANGS as readonly string[]).includes(lower)) {
    return lower as SupportedLang;
  }
  const partialMatch = SUPPORTED_LANGS.find(
    (lng) => lower === lng || lower.startsWith(`${lng}-`) || lower.startsWith(`${lng}_`)
  );
  return (partialMatch ?? DEFAULT_LANG);
}

void i18n
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
      lookupLocalStorage: 'lang'
    }
  });

export async function loadLocale(requestedLang: unknown): Promise<SupportedLang> {
  const activeLang = normalizeLang(requestedLang);
  if (i18n.language === activeLang && i18n.hasResourceBundle(activeLang, 'translation')) {
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
    i18n.addResourceBundle(activeLang, 'translation', module.default, true, true);
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
