import {test,expect} from '@playwright/test';
const api=process.env.E2E_API_URL||'http://127.0.0.1:8300/api/v1';
const photo={name:'leaf.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aXfoAAAAASUVORK5CYII=','base64')};
test('catalog, plot creation, crop identity and stale upload protection',async({page,request})=>{
 const session=await (await request.post(api+'/auth/demo',{data:{}})).json();
 await page.addInitScript(token=>localStorage.setItem('agrosphere-token',token),session.token);
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('/en/agrodoctor');
 await expect(page.getByLabel('Screening crop',{exact:true})).toBeEnabled();
 await expect(page.getByLabel('Screening crop',{exact:true}).locator('option')).toHaveCount(12);
 for(const crop of ['potato','maize','rice']){
  await page.getByLabel('Screening crop',{exact:true}).selectOption(crop);
  await page.getByLabel('New crop plot name',{exact:true}).fill(crop+' test plot');
  await page.getByRole('button',{name:'Create crop plot'}).click();
  await expect(page.getByLabel('Screening plot',{exact:true})).toContainText(crop+' test plot');
 }
 await page.getByLabel('Upload leaf photo',{exact:true}).setInputFiles(photo);
 let started=false;
 await page.route('**/doctor/cases',async route=>{
  if(route.request().method()!=='POST')return route.continue();
  started=true;
  await new Promise(resolve=>setTimeout(resolve,1500));
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({id:'stale',model:{version:'OLD-UPLOAD'}})}).catch(()=>{});
 });
 await page.getByRole('button',{name:'Screen & save observation'}).click();
 await expect.poll(()=>started).toBe(true);
 await expect(page.getByLabel('Screening crop',{exact:true})).toBeDisabled();
 const preview=page.getByAltText('Selected leaf for screening');
 const selectedPreview=await preview.getAttribute('src');
 await page.locator('.dropzone').evaluate(element=>{
  const data=new DataTransfer();data.items.add(new File(['other'],'other.png',{type:'image/png'}));
  element.dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:data}));
 });
 await expect(preview).toHaveAttribute('src',selectedPreview!);
 await page.getByLabel('Select plot',{exact:true}).selectOption(session.plot_id);
 await expect(page.getByLabel('Screening crop',{exact:true})).toHaveValue('tomato');
 await page.waitForTimeout(1800);
 await expect(page.getByText('OLD-UPLOAD')).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Screen & save observation'})).toBeDisabled();
 expect(errors).toEqual([]);
});

test('history loads older records and clears when plots change',async({page,request})=>{
 const session=await (await request.post(api+'/auth/demo',{data:{}})).json();
 const headers={Authorization:'Bearer '+session.token};
 const farm=(await (await request.get(api+'/farms',{headers})).json())[0];
 const second=await (await request.post(api+'/plots',{headers,data:{farm_id:farm.id,name:'Empty rice plot',crop:'rice',area_acres:'1'}})).json();
 await page.addInitScript(token=>localStorage.setItem('agrosphere-token',token),session.token);
 await page.route('**/doctor/cases?*',async route=>{
  const query=new URL(route.request().url()).searchParams;
  const offset=Number(query.get('offset')||0);const total=query.get('plot_id')===session.plot_id?21:0;
  const items=Array.from({length:Math.min(20,Math.max(0,total-offset))},(_,i)=>({id:'history-'+(offset+i),crop:'tomato',plot_id:session.plot_id,plot_name:'Tomato history',created_at:'2026-11-17T00:00:00Z',classification:{abstained:true,top_label:'unknown'},model:{version:'legacy-tomato'}}));
  await route.fulfill({json:{items,total,offset,limit:20,has_more:offset+20<total}});
 });
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('/en/history');
 await page.getByLabel('Select plot',{exact:true}).selectOption(session.plot_id);
 await expect(page.getByText('Showing 20 of 21 saved screenings for this plot.')).toBeVisible();
 await page.getByRole('button',{name:'Load older screenings'}).click();
 await expect(page.getByText('Showing 21 of 21 saved screenings for this plot.')).toBeVisible();
 await page.getByLabel('Select plot',{exact:true}).selectOption(second.id);
 await expect(page.getByText('Showing 0 of 0 saved screenings for this plot.')).toBeVisible();
 await expect(page.getByText('Tomato history')).toHaveCount(0);expect(errors).toEqual([]);
});

test('saved photo, newest notes and missing-photo detail stay usable',async({page,request})=>{
 const session=await (await request.post(api+'/auth/demo',{data:{}})).json();
 const headers={Authorization:'Bearer '+session.token};
 const upload=await request.post(api+'/doctor/cases',{headers,multipart:{plot_id:session.plot_id,image:{name:'quality.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=','base64')}}});
 expect(upload.ok()).toBeTruthy();const saved=await upload.json();
 for(const note of ['First saved note','Latest saved note'])await request.post(api+`/doctor/cases/${saved.id}/feedback`,{headers,data:{note}});
 await page.addInitScript(token=>localStorage.setItem('agrosphere-token',token),session.token);
 await page.goto('/en/agrodoctor/'+saved.id);
 await expect(page.getByAltText('Submitted leaf photo')).toBeVisible();
 await expect(page.getByRole('button',{name:'Download photo'})).toBeEnabled();
 await expect(page.getByLabel('New note',{exact:true})).toHaveValue('');
 const notes=page.locator('.timeline-row p');await expect(notes.nth(0)).toHaveText('Latest saved note');
 await page.route('**/doctor/cases/*/image',route=>route.fulfill({status:410,json:{message:'Photo gone'}}));
 await page.reload();
 await expect(page.getByText('Photo no longer available. Case metadata is preserved.')).toBeVisible();
 await expect(page.getByRole('button',{name:'Export CSV'})).toBeEnabled();
});
test('unavailable crop model disables screening',async({page,request})=>{
 const session=await (await request.post(api+'/auth/demo',{data:{}})).json();
 await page.addInitScript(token=>localStorage.setItem('agrosphere-token',token),session.token);
 await page.route('**/doctor/capabilities',async route=>{
  const response=await route.fetch();const data=await response.json();
  data.crops=data.crops.map((crop:Record<string,unknown>)=>({...crop,available:false}));
  await route.fulfill({json:data});
 });
 await page.goto('/en/agrodoctor');
 await expect(page.getByText('Model unavailable for this crop.')).toBeVisible();
 await page.getByLabel('Upload leaf photo',{exact:true}).setInputFiles(photo);
 await expect(page.getByRole('button',{name:'Screen & save observation'})).toBeDisabled();
});

test('delayed plot creation respects a newer selected plot',async({page,request})=>{
 const session=await (await request.post(api+'/auth/demo',{data:{}})).json();
 const headers={Authorization:'Bearer '+session.token};
 const farms=await (await request.get(api+'/farms',{headers})).json();
 const second=await (await request.post(api+'/plots',{headers,data:{farm_id:farms[0].id,name:'Other potato plot',crop:'potato',area_acres:'1'}})).json();
 await page.addInitScript(token=>localStorage.setItem('agrosphere-token',token),session.token);
 await page.goto('/en/agrodoctor');
 await page.getByLabel('Select plot',{exact:true}).selectOption(session.plot_id);
 await page.getByLabel('Screening crop',{exact:true}).selectOption('rice');
 await page.getByLabel('New crop plot name',{exact:true}).fill('Delayed rice plot');
 let started=false;
 await page.route('**/api/v1/plots',async route=>{
  if(route.request().method()!=='POST')return route.continue();
  const response=await route.fetch();started=true;
  await new Promise(resolve=>setTimeout(resolve,1500));
  await route.fulfill({response}).catch(()=>{});
 });
 await page.getByRole('button',{name:'Create crop plot'}).click();
 await expect.poll(()=>started).toBe(true);
 await page.getByLabel('Select plot',{exact:true}).selectOption(second.id);
 await page.waitForTimeout(1800);
 await expect(page.getByLabel('Select plot',{exact:true})).toHaveValue(second.id);
 await expect(page.getByLabel('Screening crop',{exact:true})).toHaveValue('potato');
});

test('photo controls wait for the initial owned plot',async({page,request})=>{
 const session=await (await request.post(api+'/auth/demo',{data:{}})).json();
 await page.addInitScript(token=>localStorage.setItem('agrosphere-token',token),session.token);
 let release:()=>void=()=>{};const gate=new Promise<void>(resolve=>{release=resolve});
 await page.route('**/api/v1/plots',async route=>{const response=await route.fetch();await gate;await route.fulfill({response})});
 await page.goto('/en/agrodoctor');
 await expect(page.getByRole('button',{name:'Choose a photo'})).toBeDisabled();
 release();
 await expect(page.getByRole('button',{name:'Choose a photo'})).toBeEnabled();
});
