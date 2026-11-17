import {test,expect} from '@playwright/test';

const api=process.env.AGROSPHERE_API_URL||'http://127.0.0.1:8000/api/v1';
test.setTimeout(60000);

test('search an area, save it with consent and retain its forecast location after reload',async({page,request})=>{
 await page.goto('/en');
 await page.getByRole('button',{name:'Explore a demo farm'}).click();
 await expect(page.getByRole('heading',{name:'Your farm, in perspective.'})).toBeVisible({timeout:15000});
 const token=await page.evaluate(()=>localStorage.getItem('agrosphere-token'));
 const headers={Authorization:`Bearer ${token}`};
 await page.route('**/locations/search?*',route=>route.fulfill({json:{results:[{id:'1',name:'Sylhet',label:'Sylhet, Sylhet Division, Bangladesh',district:'Sylhet',country:'Bangladesh',latitude:24.8949,longitude:91.8687}],source_name:'TEST FIXTURE · Open-Meteo response contract'}}));
 // Keep this regression deterministic/offline; backend tests verify provider dispatch.
 await page.route('**/flood/plots/*/outlook?*',async route=>{
  const farm=(await (await request.get(api+'/farms',{headers})).json())[0];
  const live=new URL(route.request().url()).searchParams.get('mode')==='LIVE';
  await route.fulfill({json:{hourly:Array.from({length:72},(_,i)=>({time:new Date(Date.now()+i*3600000).toISOString(),rain_mm:1})),total_mm:48,horizon_hours:48,threshold_mm:75,level:'monitor',reasons:[],disclaimer:'Test fixture, not a forecast',location:{lat:farm.latitude??24.0023,lon:farm.longitude??90.4264},meta:{mode:live?'LIVE':'DEMO',source_name:'TEST FIXTURE',is_simulated:!live,retrieved_at:new Date().toISOString()}}});
 });
 try{
  await page.getByRole('link',{name:'FloodCrop AI',exact:false}).first().click();
  await page.getByRole('textbox',{name:'Search any area'}).fill('Sylhet');
  await page.getByRole('button',{name:'Search',exact:true}).click();
  await page.getByRole('button',{name:'Sylhet, Sylhet Division, Bangladesh',exact:false}).click();
  await expect(page.getByLabel('Latitude',{exact:true})).toHaveValue('24.8949');
  const save=page.getByRole('button',{name:'Save area & use live weather'});
  await expect(save).toBeDisabled();
  await page.getByRole('checkbox',{name:'Save this location for my farm'}).check();
  const patched=page.waitForResponse(r=>r.url().endsWith('/location')&&r.request().method()==='PATCH');
  await save.click();expect((await patched).ok()).toBeTruthy();
  await expect(page.getByLabel('Weather data mode')).toHaveValue('LIVE');
  await expect(page.getByRole('heading',{name:'Sylhet, Sylhet Division, Bangladesh',exact:true})).toBeVisible();
  const saved=(await (await request.get(api+'/farms',{headers})).json())[0];
  expect(saved.latitude).toBe(24.8949);expect(saved.longitude).toBe(91.8687);
  await page.reload();
  await expect(page.getByLabel('Latitude',{exact:true})).toHaveValue('24.8949');
  await expect(page.getByLabel('Weather data mode')).toHaveValue('LIVE');
  // A map click must change the draft coordinate, rather than only panning a static map.
  const canvas=page.getByTestId('area-map').locator('canvas');
  await expect(canvas).toBeVisible();
  await canvas.click({position:{x:35,y:40}});
  await expect(page.getByLabel('Longitude',{exact:true})).not.toHaveValue('91.8687');
 }finally{await request.delete(api+'/me',{headers})}
});

test('manual coordinates remain available when area search is offline on mobile',async({page,request})=>{
 await page.setViewportSize({width:360,height:800});await page.goto('/en');
 await page.getByRole('button',{name:'Explore a demo farm'}).click();
 await expect(page.getByRole('heading',{name:'Your farm, in perspective.'})).toBeVisible({timeout:15000});
 const token=await page.evaluate(()=>localStorage.getItem('agrosphere-token'));
 try{
  await page.route('**/locations/search?*',route=>route.fulfill({status:503,json:{message:'Area search is unavailable. Select a map point or enter coordinates instead.'}}));
  await page.goto('/en/floodcrop');
  await page.getByRole('textbox',{name:'Search any area'}).fill('Village');
  await page.getByRole('button',{name:'Search',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'Area search is unavailable'})).toBeVisible();
  await page.getByLabel('Latitude',{exact:true}).fill('0');await page.getByLabel('Longitude',{exact:true}).fill('90');
  await page.getByRole('button',{name:'Use coordinates',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'Map point'})).toContainText('0.00000, 90.00000');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 }finally{await request.delete(api+'/me',{headers:{Authorization:`Bearer ${token}`}})}
});
