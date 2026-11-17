import test from 'node:test';
import assert from 'node:assert/strict';
import {backendUrl, verifyDeployment, isBlockedHost} from './netlify-preflight.mjs';

test('public deploy rejects missing, local, special-use and credential-bearing backend URLs', () => {
  for (const value of [
    undefined,
    'http://127.0.0.1:8100/api/v1',
    'https://localhost/api/v1',
    'https://192.168.1.10/api/v1',
    'https://172.16.2.3/api/v1',
    'https://[::1]/api/v1',
    'https://169.254.169.254/api/v1',
    'https://[fc00::1]/api/v1',
    'https://100.64.0.1/api/v1',
    'https://user:secret@api.example.org/api/v1',
    'https://api.example.org/',
    'https://api.example.org/api/v1?token=secret',
  ]) {
    assert.throws(() => backendUrl(value));
  }
  assert.equal(backendUrl('https://api.example.org/api/v1/'), 'https://api.example.org/api/v1');
  assert.equal(isBlockedHost('169.254.169.254'), true);
  assert.equal(isBlockedHost('100.64.0.1'), true);
});

test('deploy checks actual backend health and the browser CORS origin', async () => {
  const env = {NEXT_PUBLIC_API_URL: 'https://api.example.org/api/v1', URL: 'https://agrosphere.netlify.app'};
  const okay = async (url, options) => {
    assert.equal(url, 'https://api.example.org/api/v1/health');
    assert.equal(options.headers.Origin, env.URL);
    return new Response(JSON.stringify({status: 'ok'}), {
      headers: {'access-control-allow-origin': env.URL},
    });
  };
  assert.equal((await verifyDeployment(env, okay, {attempts: 1, resolveDns: async () => []})).healthy, true);
  await assert.rejects(
    verifyDeployment(env, async () => new Response(JSON.stringify({status: 'ok'})), {
      attempts: 1,
      resolveDns: async () => [],
    }),
    /CORS_ORIGINS/,
  );
  await assert.rejects(
    verifyDeployment(env, async () => new Response('Unavailable', {status: 503}), {
      attempts: 1,
      resolveDns: async () => [],
    }),
    /HTTP 503/,
  );
});

test('warm-up retries wait with backoff instead of burning attempts in milliseconds', async () => {
  const env = {NEXT_PUBLIC_API_URL: 'https://api.example.org/api/v1', URL: 'https://agrosphere.netlify.app'};
  let calls = 0;
  const waits = [];
  const fakeNowValues = [0, 0, 1200, 1200, 3500, 3500];
  let nowIdx = 0;
  const result = await verifyDeployment(
    env,
    async () => {
      calls += 1;
      if (calls < 3) return new Response('spinning up', {status: 503});
      return new Response(JSON.stringify({status: 'ok'}), {
        headers: {'access-control-allow-origin': env.URL},
      });
    },
    {
      attempts: 4,
      baseDelayMs: 1000,
      totalDeadlineMs: 60_000,
      sleeper: async (ms) => {
        waits.push(ms);
      },
      now: () => fakeNowValues[Math.min(nowIdx++, fakeNowValues.length - 1)],
      resolveDns: async () => [],
    },
  );
  assert.equal(result.healthy, true);
  assert.equal(calls, 3);
  assert.deepEqual(waits, [1000, 2000]);
  assert.ok(waits.reduce((a, b) => a + b, 0) >= 3000);
});
