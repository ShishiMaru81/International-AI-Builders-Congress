import {pathToFileURL} from 'node:url';
import {isIP} from 'node:net';
import {promises as dns} from 'node:dns';

const SPECIAL_USE_V4 = [
  /^0\./,
  /^127\./,
  /^10\./,
  /^192\.168\./,
  /^169\.254\./,          // link-local / cloud metadata adjacency
  /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\./, // CGNAT 100.64/10
  /^172\.(1[6-9]|2\d|3[01])\./,
];

function isSpecialUseIPv4(host){
  return SPECIAL_USE_V4.some((re)=>re.test(host));
}

function isSpecialUseIPv6(host){
  const h=host.replace(/^\[|\]$/g,'').toLowerCase();
  if(h==='::1'||h==='::'||h==='0:0:0:0:0:0:0:1')return true;
  // Unique local fc00::/7 and link-local fe80::/10
  if(h.startsWith('fc')||h.startsWith('fd')||h.startsWith('fe8')||h.startsWith('fe9')||h.startsWith('fea')||h.startsWith('feb'))return true;
  return false;
}

export function isBlockedHost(hostname){
  const host=hostname.toLowerCase();
  if(host==='localhost'||host.endsWith('.localhost')||host.endsWith('.local'))return true;
  if(host.startsWith('[')||host.includes(':'))return isSpecialUseIPv6(host);
  if(isIP(host)===4)return isSpecialUseIPv4(host);
  if(isIP(host)===6)return isSpecialUseIPv6(host);
  return false;
}

export function backendUrl(value){
  if(!value)throw new Error('Set NEXT_PUBLIC_API_URL in Netlify to the hosted Python API URL ending /api/v1. Local Docker addresses cannot serve public visitors.');
  const url=new URL(value);
  const host=url.hostname.toLowerCase();
  if(url.protocol!=='https:'||isBlockedHost(host)||url.username||url.password||url.search||url.hash||!url.pathname.replace(/\/$/,'').endsWith('/api/v1')){
    throw new Error('NEXT_PUBLIC_API_URL must be a public HTTPS backend URL ending /api/v1, without credentials, query, fragment, or special-use/private addresses (including link-local, ULA, and CGNAT).');
  }
  return url.href.replace(/\/$/,'');
}

function sleep(ms, sleeper){
  return sleeper(ms);
}

function retryAfterMs(response, attempt, baseDelayMs){
  const raw=response?.headers?.get?.('retry-after');
  if(raw){
    const asInt=Number(raw);
    if(Number.isFinite(asInt)&&asInt>=0)return Math.min(asInt*1000,60_000);
    const asDate=Date.parse(raw);
    if(Number.isFinite(asDate))return Math.min(Math.max(0, asDate-Date.now()),60_000);
  }
  // Exponential backoff with jitter bound: 1s, 2s, 4s...
  return Math.min(baseDelayMs * (2 ** attempt), 15_000);
}

function isTransientStatus(status){
  return status===408||status===425||status===429||status>=500;
}

export async function verifyDeployment(
  env=process.env,
  fetcher=fetch,
  {
    attempts=6,
    totalDeadlineMs=60_000,
    baseDelayMs=1000,
    sleeper=(ms)=>new Promise((resolve)=>setTimeout(resolve, ms)),
    resolveDns=dns.lookup,
    now=()=>Date.now(),
  }={},
){
  const api=backendUrl(env.NEXT_PUBLIC_API_URL);
  const origin=env.DEPLOY_PRIME_URL||env.URL;
  const host=new URL(api).hostname;

  // DNS special-use check for hostnames (OP-04). Literal IPs already rejected in backendUrl.
  if(isIP(host)===0){
    try{
      const lookup=await resolveDns(host, {all:true});
      const addresses=Array.isArray(lookup)?lookup:[lookup];
      for(const entry of addresses){
        const address=entry.address||entry;
        if(isBlockedHost(String(address))){
          throw new Error(`NEXT_PUBLIC_API_URL hostname resolves to a special-use/private address (${address}).`);
        }
      }
    }catch(error){
      if(String(error.message||error).includes('special-use/private'))throw error;
      // DNS failure is treated as configuration/transient later during health fetch
    }
  }

  const started=now();
  let last;
  for(let attempt=0; attempt<attempts; attempt++){
    if(now()-started>totalDeadlineMs)break;
    try{
      const response=await fetcher(`${api}/health`, {
        headers: origin ? {Origin: new URL(origin).origin} : {},
        signal: AbortSignal.timeout(25_000),
      });
      if(!response.ok){
        const err=new Error(`Backend health returned HTTP ${response.status}`);
        err.status=response.status;
        err.response=response;
        throw err;
      }
      const data=await response.json();
      if(data.status!=='ok')throw new Error('Backend did not return the AgroSphere health response.');
      if(origin && response.headers.get('access-control-allow-origin')!==new URL(origin).origin){
        throw new Error('Backend CORS_ORIGINS must include this Netlify site origin before browser uploads and sign-in can work.');
      }
      return {api, healthy:true, cors_checked:Boolean(origin), attempts_used: attempt+1};
    }catch(error){
      last=error;
      const status=error?.status || error?.response?.status;
      const retryable=status==null || isTransientStatus(status);
      // Persistent configuration/CORS errors fail promptly without burning the warm-up window.
      if(!retryable || String(error.message||'').includes('CORS_ORIGINS'))break;
      if(attempt>=attempts-1)break;
      const wait=retryAfterMs(error.response, attempt, baseDelayMs);
      if(now()-started+wait>totalDeadlineMs)break;
      await sleep(wait, sleeper);
    }
  }
  throw new Error(`Netlify deployment check failed: ${last?.message}. Free backends may need a minute to wake up; confirm the API is running and redeploy.`);
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  try{console.log(JSON.stringify(await verifyDeployment()))}
  catch(error){console.error(error.message);process.exitCode=1}
}
