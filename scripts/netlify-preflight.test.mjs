import test from 'node:test';
import assert from 'node:assert/strict';
import {backendUrl,verifyDeployment} from './netlify-preflight.mjs';

test('public deploy rejects missing, local and credential-bearing backend URLs',()=>{
 for(const value of [undefined,'http://127.0.0.1:8100/api/v1','https://localhost/api/v1','https://192.168.1.10/api/v1','https://172.16.2.3/api/v1','https://[::1]/api/v1','https://user:secret@api.example.org/api/v1','https://api.example.org/','https://api.example.org/api/v1?token=secret']){
  assert.throws(()=>backendUrl(value));
 }
 assert.equal(backendUrl('https://api.example.org/api/v1/'),'https://api.example.org/api/v1');
});
test('deploy checks actual backend health and the browser CORS origin',async()=>{
 const env={NEXT_PUBLIC_API_URL:'https://api.example.org/api/v1',URL:'https://agrosphere.netlify.app'};
 const okay=async(url,options)=>{
  assert.equal(url,'https://api.example.org/api/v1/health');assert.equal(options.headers.Origin,env.URL);
  return new Response(JSON.stringify({status:'ok'}),{headers:{'access-control-allow-origin':env.URL}});
 };
 assert.equal((await verifyDeployment(env,okay)).healthy,true);
 await assert.rejects(verifyDeployment(env,async()=>new Response(JSON.stringify({status:'ok'})),{attempts:1}),/CORS_ORIGINS/);
 await assert.rejects(verifyDeployment(env,async()=>new Response('Unavailable',{status:503}),{attempts:1}),/HTTP 503/);
});
