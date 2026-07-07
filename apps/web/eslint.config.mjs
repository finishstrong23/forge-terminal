// eslint-config-next 16 ships native flat configs — no FlatCompat needed.
import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

const eslintConfig = [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "playwright-report/**",
      "test-results/**",
      "next-env.d.ts",
    ],
  },
  ...coreWebVitals,
  ...typescript,
  {
    rules: {
      // The data hooks intentionally reset state synchronously when their
      // params change (window switch -> loading skeleton) before kicking
      // off the async fetch. Advisory here, not a gate.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
];

export default eslintConfig;
