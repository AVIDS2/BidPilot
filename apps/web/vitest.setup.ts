import { vi } from "vitest";
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import enCommon from "./public/locales/en/common.json";
import enAdmin from "./public/locales/en/admin.json";
import enAuth from "./public/locales/en/auth.json";
import enLanding from "./public/locales/en/landing.json";
import enProjects from "./public/locales/en/projects.json";
import enAccount from "./public/locales/en/account.json";
import enPricing from "./public/locales/en/pricing.json";
import enOnboarding from "./public/locales/en/onboarding.json";
import enAIAssistant from "./public/locales/en/ai-assistant.json";
import enSettings from "./public/locales/en/settings.json";

vi.mock("@/lib/i18n", () => ({ default: i18n }));

if (!Element.prototype.getAnimations) {
  Element.prototype.getAnimations = () => [];
}

if (!globalThis.requestAnimationFrame) {
  globalThis.requestAnimationFrame = ((callback: FrameRequestCallback) =>
    setTimeout(() => callback(performance.now()), 16)) as typeof requestAnimationFrame;
}

if (!globalThis.cancelAnimationFrame) {
  globalThis.cancelAnimationFrame = ((handle: number) => clearTimeout(handle)) as typeof cancelAnimationFrame;
}

if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

i18n.use(initReactI18next).init({
  lng: "en",
  fallbackLng: "en",
  ns: ["common", "admin", "auth", "landing", "projects", "account", "pricing", "onboarding", "ai-assistant", "settings"],
  defaultNS: "common",
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
      "ai-assistant": enAIAssistant,
      settings: enSettings,
    },
  },
  interpolation: { escapeValue: false },
});
