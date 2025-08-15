module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  parserOptions: { ecmaVersion: "latest", sourceType: "module", ecmaFeatures: { jsx: true } },
  settings: {
    react: { version: "detect" },
    'import/resolver': { node: { extensions: ['.js', '.jsx'] } }
  },
  extends: [
    "eslint:recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended",
    "plugin:jsx-a11y/recommended",
    "plugin:import/recommended",
    "prettier" // if using Prettier
  ],
  rules: {
    // project-specific overrides
    "react/prop-types": "off",
    "react/react-in-jsx-scope": "off"
  }
};
