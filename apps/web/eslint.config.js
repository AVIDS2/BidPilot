import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: ["dist/**", "coverage/**", "node_modules/**"],
  },
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      // TypeScript's `noUnused*` checks are already enabled in tsconfig.
      "@typescript-eslint/no-unused-vars": "off",
      // Tool payloads cross provider boundaries as opaque data; narrow them
      // at the adapter boundary instead of forcing false type precision here.
      "@typescript-eslint/no-explicit-any": "off",
      // These catch invalid hook order; broader React Compiler advisories are
      // intentionally non-blocking until the UI reconstruction owns them.
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
);
