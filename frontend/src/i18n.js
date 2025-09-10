/* eslint-disable import/no-named-as-default-member */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

export const DEFAULT_LANG = 'en';

// Initialize i18next without bundled resources; languages are loaded lazily.
i18n.use(initReactI18next).init({
  fallbackLng: DEFAULT_LANG,
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
});

export async function loadLocale(lang) {
  const { default: translations } = await import(`./locales/${lang}/common.json`);
  i18n.addResourceBundle(lang, 'translation', translations, true, true);
  await i18n.changeLanguage(lang);
  document.documentElement.lang = lang;
}

export default i18n;
