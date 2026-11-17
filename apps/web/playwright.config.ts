import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./e2e',use:{baseURL:process.env.PLAYWRIGHT_BASE_URL||'http://127.0.0.1:3000',headless:true,screenshot:'only-on-failure'},workers:1,reporter:'list',timeout:45000,projects:[{name:'chromium',use:{browserName:'chromium',...(process.env.PLAYWRIGHT_CHANNEL==='chromium'?{}:{channel:'msedge'})}}]});
