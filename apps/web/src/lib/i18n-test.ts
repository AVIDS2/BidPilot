/** Vitest setup: initialize i18n with inline English resources. */
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import enCommon from "../../public/locales/en/common.json";
import enAdmin from "../../public/locales/en/admin.json";
import enAuth from "../../public/locales/en/auth.json";
import enLanding from "../../public/locales/en/landing.json";
import enProjects from "../../public/locales/en/projects.json";
import enAccount from "../../public/locales/en/account.json";
import enPricing from "../../public/locales/en/pricing.json";
import enRuns from "../../public/locales/en/runs.json";
import enKnowledgePortfolio from "../../public/locales/en/knowledge-portfolio.json";

i18n.use(initReactI18next).init({
  lng: "en",
  fallbackLng: "en",
  ns: ["common", "admin", "auth", "projects", "landing", "account", "pricing", "runs", "knowledge-portfolio"],
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
      runs: enRuns,
      "knowledge-portfolio": enKnowledgePortfolio,
    },
  },
  interpolation: { escapeValue: false },
});

export default i18n;
