import type { NextConfig } from 'next';
// Separate build directories let browser QA use an isolated API/database while
// the farmer's existing local workspace remains running.
const config: NextConfig = {
  ...(process.env.NETLIFY==='true'?{}:{output:'standalone'}),
  distDir: process.env.AGROSPHERE_NEXT_DIST_DIR || '.next',
};
export default config;
