// Flat config. ESLint 9 requires it, and eslint-config-next@16 requires
// ESLint >= 9, so moving to Next 16 forced this migration too.
//
// eslint-config-next@16 ships flat config directly (see its `exports` map), so
// it is imported rather than translated through FlatCompat — passing it through
// the compat layer fails with a circular-structure error.
import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';

const config = [
  {
    // Flat config has no implicit ignores beyond node_modules, so build output
    // must be excluded explicitly or `eslint .` lints .next/.
    ignores: ['.next/**', 'out/**', 'build/**', 'next-env.d.ts'],
  },
  ...(Array.isArray(nextCoreWebVitals) ? nextCoreWebVitals : [nextCoreWebVitals]),
  {
    rules: {
      // React Compiler-era rule, new in this config version. It fires on three
      // pre-existing places: the two "reset pagination when the inputs change"
      // effects, and the next-themes mount guard in ThemeToggle (which exists
      // precisely to avoid a hydration mismatch and has no effect-free form).
      //
      // Downgraded to a warning rather than disabled: the reset-on-change
      // effects would be better expressed as derived state or a `key`, and that
      // is worth doing — but as its own change, not smuggled into a framework
      // upgrade where a behavioural regression would be hard to attribute.
      'react-hooks/set-state-in-effect': 'warn',
    },
  },
];

export default config;
