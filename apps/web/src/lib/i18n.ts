import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import HttpBackend from 'i18next-http-backend';
import { STORAGE_KEYS, getStoredValue, setStoredValue } from '@/lib/browser-storage';

const storedLanguage = getStoredValue('language');
if (storedLanguage) {
  setStoredValue('language', storedLanguage);
} else {
  // Default to Chinese for a Chinese-first product; the language toggle in
  // the header persists an explicit English choice back to localStorage.
  setStoredValue('language', 'zh-CN');
}

i18n
  .use(HttpBackend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: 'zh-CN',
    supportedLngs: ['en', 'zh-CN'],
    ns: [
      'common',
      'admin',
      'auth',
      'projects',
      'landing',
      'account',
      'pricing',
      'onboarding',
      'dashboard',
      'docs',
      'settings',
      'runs',
      'knowledge-portfolio',
      'ai-assistant'
    ],
    defaultNS: 'common',
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: STORAGE_KEYS.language
    },
    backend: {
      loadPath: '/locales/{{lng}}/{{ns}}.json'
    }
  });

export default i18n;
