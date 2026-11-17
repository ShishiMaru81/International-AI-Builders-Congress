import {defineConfig,globalIgnores} from 'eslint/config';
import next from 'eslint-config-next/core-web-vitals';
export default defineConfig([
  ...next,
  globalIgnores(['.next/**','.next-rescue-e2e/**','next-env.d.ts']),
  {
    rules: {
      // Session bootstrap, map fallback and stale-result invalidation intentionally sync
      // React state from external systems inside effects (FE-01/FE-03/MAP-01).
      'react-hooks/set-state-in-effect': 'off',
    },
  },
]);
