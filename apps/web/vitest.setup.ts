import { vi } from 'vitest';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import '@testing-library/jest-dom/vitest';

import enCommon from './public/locales/en/common.json';
import enAdmin from './public/locales/en/admin.json';
import enLanding from './public/locales/en/landing.json';
import enAuth from './public/locales/en/auth.json';
import enProjects from './public/locales/en/projects.json';
import enAccount from './public/locales/en/account.json';
import enPricing from './public/locales/en/pricing.json';
import enOnboarding from './public/locales/en/onboarding.json';
import enAIAssistant from './public/locales/en/ai-assistant.json';
import enSettings from './public/locales/en/settings.json';
import enRuns from './public/locales/en/runs.json';
import enKnowledgePortfolio from './public/locales/en/knowledge-portfolio.json';

vi.mock('@/lib/i18n', () => ({ default: i18n }));

if (!document.doctype) {
  document.insertBefore(
    document.implementation.createDocumentType('html', '', ''),
    document.documentElement
  );
}
if (document.compatMode !== 'CSS1Compat') {
  Object.defineProperty(document, 'compatMode', { configurable: true, value: 'CSS1Compat' });
}

if (!Element.prototype.getAnimations) {
  Element.prototype.getAnimations = () => [];
}

if (!globalThis.ResizeObserver) {
  class ResizeObserverPolyfill {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = ResizeObserverPolyfill;
}

const requestAnimationFramePolyfill: typeof requestAnimationFrame = (callback) =>
  window.setTimeout(() => {
    if (typeof globalThis.requestAnimationFrame !== 'function') return;
    callback(globalThis.performance?.now?.() ?? Date.now());
  }, 16);
const cancelAnimationFramePolyfill: typeof cancelAnimationFrame = (handle) =>
  window.clearTimeout(handle);

globalThis.requestAnimationFrame = requestAnimationFramePolyfill;
globalThis.cancelAnimationFrame = cancelAnimationFramePolyfill;
window.requestAnimationFrame = requestAnimationFramePolyfill;
window.cancelAnimationFrame = cancelAnimationFramePolyfill;

if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn()
  }));
}

i18n.use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  ns: [
    'common',
    'admin',
    'auth',
    'landing',
    'projects',
    'account',
    'pricing',
    'onboarding',
    'ai-assistant',
    'settings',
    'runs',
    'knowledge-portfolio'
  ],
  defaultNS: 'common',
  resources: {
    en: {
      common: enCommon,
      admin: enAdmin,
      auth: enAuth,
      landing: enLanding,
      projects: enProjects,
      account: enAccount,
      pricing: enPricing,
      onboarding: enOnboarding,
      'ai-assistant': enAIAssistant,
      settings: enSettings,
      runs: enRuns,
      'knowledge-portfolio': enKnowledgePortfolio
    }
  },
  interpolation: { escapeValue: false }
});
