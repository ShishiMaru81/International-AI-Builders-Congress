import {pathToFileURL} from 'node:url';

export function backendUrl(value){
  if(!value)throw new Error('Set NEXT_PUBLIC_API_URL in Netlify to the hosted Python API URL ending /api/v1. Local Docker addresses cannot serve public visitors.');
  const url=new URL(value);
  const host=url.hostname.toLowerCase();
  const privateHost=host==='localhost'||host.endsWith('.localhost')||host.endsWith('.local')||host==='[::1]'||host==='[::]'||/^(127\.|10\.|192\.168\.|0\.)/.test(host)||/^172\.(1[6-9]|2\d|3[01])\./.test(host);
  if(url.protocol!=='https:'||privateHost||url.username||url.password||url.search||url.hash||!url.pathname.replace(/\/$/,'').endsWith('/api/v1')){
    throw new Error('NEXT_PUBLIC_API_URL must be a public HTTPS backend URL ending /api/v1, without credentials, query or fragment.');
  }
  return url.href.replace(/\/$/,'');
}

export async function verifyDeployment(env=process.env,fetcher=fetch,{attempts=4}={}){
  const api=backendUrl(env.NEXT_PUBLIC_API_URL);
  const origin=env.DEPLOY_PRIME_URL||env.URL;
  let last;
  for(let attempt=0;attempt<attempts;attempt++){
    try{
      const response=await fetcher(`${api}/health`,{headers:origin?{Origin:new URL(origin).origin}:{},signal:AbortSignal.timeout(25000)});
      if(!response.ok)throw new Error(`Backend health returned HTTP ${response.status}`);
      const data=await response.json();
      if(data.status!=='ok')throw new Error('Backend did not return the AgroSphere health response.');
      if(origin&&response.headers.get('access-control-allow-origin')!==new URL(origin).origin){
        throw new Error('Backend CORS_ORIGINS must include this Netlify site origin before browser uploads and sign-in can work.');
      }
      return {api,healthy:true,cors_checked:Boolean(origin)};
    }catch(error){last=error}
  }
  throw new Error(`Netlify deployment check failed: ${last?.message}. Free backends may need a minute to wake up; confirm the API is running and redeploy.`);
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  try{console.log(JSON.stringify(await verifyDeployment()))}
  catch(error){console.error(error.message);process.exitCode=1}
}
