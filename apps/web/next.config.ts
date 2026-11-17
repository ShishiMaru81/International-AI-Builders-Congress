import type { NextConfig } from 'next';
const config: NextConfig = process.env.NETLIFY==='true'?{}:{output:'standalone'};
export default config;
