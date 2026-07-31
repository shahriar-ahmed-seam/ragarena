// eslint-config-next 16 ships native flat configs, so no FlatCompat bridge:
// routing the eslintrc-format entrypoints through @eslint/eslintrc throws on a
// circular reference during config validation.
import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

const config = [
  {
    ignores: [".next/**", "out/**", "node_modules/**", "next-env.d.ts"],
  },
  ...coreWebVitals,
  ...typescript,
];

export default config;
