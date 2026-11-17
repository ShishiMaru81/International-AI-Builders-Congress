import {test, expect, type APIRequestContext, type Page} from '@playwright/test';
const API=(process.env.E2E_API_URL||process.env.AGROSPHERE_API_URL||'http://127.0.0.1:8300/api/v1').replace(/\/$/,'');
test.use({baseURL:process.env.E2E_BASE_URL||process.env.PLAYWRIGHT_BASE_URL||'http://127.0.0.1:3300'});
async function isolatedFarm(request:APIRequestContext){
 const auth=await request.post(API+'/auth/demo',{data:{name:'Rescue E2E isolated farmer'}});
 expect(auth.ok(),await auth.text()).toBeTruthy();const {token}=await auth.json();const headers={Authorization:`Bearer ${token}`};
 const plots=await request.get(API+'/plots',{headers});expect(plots.ok()).toBeTruthy();
 return {token,headers,plot:(await plots.json())[0]};
}
async function open(page:Page,token:string,locale='en'){
 await page.goto('/'+locale);await page.evaluate(t=>localStorage.setItem('agrosphere-token',t),token);await page.goto('/'+locale+'/agrorescue');
 await expect(page.getByTestId('agrorescue')).toBeVisible();
}
async function example(page:Page){await page.getByRole('button',{name:'Load imaginary example'}).click();await page.getByRole('button',{name:'Compare & save plan',exact:true}).click();}
test('declared decimal choices show net proceeds, discard stale results and retain immutable history',async({page,request})=>{
 const farmer=await isolatedFarm(request);
 try{
  await open(page,farmer.token);
  await expect(page.getByLabel('Harvested quantity (kg)',{exact:true})).toHaveValue('');
  await example(page);
  await expect(page.getByTestId('rescue-result')).toContainText('3900.00');
  await expect(page.getByTestId('rescue-result')).toContainText('3700.00');
  await expect(page.getByTestId('rescue-result')).toContainText('Imaginary example');
  await page.getByLabel('Harvested quantity (kg)',{exact:true}).fill('120');
  await expect(page.getByTestId('rescue-result')).toBeHidden();
  await page.getByRole('button',{name:'Open saved plan',exact:true}).first().click();
  await expect(page.getByTestId('rescue-result')).toContainText('3900.00');
  await expect(page.getByTestId('rescue-result')).toContainText('snapshot');
  await page.getByRole('button',{name:'Delete saved plan',exact:true}).first().click();
  await expect(page.getByTestId('rescue-result')).toBeHidden();
  await expect(page.getByRole('button',{name:'Open saved plan',exact:true})).toHaveCount(0);
 }finally{await request.delete(API+'/me',{headers:farmer.headers});}
});
test('unknown transport asks for information and Bengali mobile remains within viewport',async({page,request})=>{
 const farmer=await isolatedFarm(request);
 try{
  await open(page,farmer.token);await page.getByRole('button',{name:'Load imaginary example'}).click();
  await page.getByLabel('Transport (BDT), option 2',{exact:true}).fill('');
  await page.getByRole('button',{name:'Compare & save plan',exact:true}).click();
  await expect(page.getByTestId('rescue-result')).toContainText('More information needed');
  await expect(page.getByTestId('rescue-questions')).toContainText(/transport/i);
  await page.setViewportSize({width:360,height:800});await page.goto('/bn/agrorescue');
  await expect(page.getByLabel('সংগৃহীত পরিমাণ (কেজি)',{exact:true})).toBeVisible();
  await expect(page.getByLabel('সংগৃহীত পরিমাণ (কেজি)',{exact:true})).toHaveValue('');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 }finally{await request.delete(API+'/me',{headers:farmer.headers});}
});
test('saved BDT/kg quotes are selectable, visibly sourced, and compared after farmer confirmation',async({page,request})=>{
 const farmer=await isolatedFarm(request);
 try{
  const response=await request.get(API+'/market/prices',{headers:farmer.headers});expect(response.ok()).toBeTruthy();
  const prices=await response.json();const quote=prices.find((p:{unit:string})=>p.unit.toLowerCase()==='bdt/kg');expect(quote).toBeTruthy();
  const csv='market,commodity,price,unit,price_type,grade,observed_at\nRescue farm gate,tomato,41,BDT/kg,farm-gate,A,2026-11-17\nRescue retail,tomato,49,BDT/kg,retail,A,2026-11-17\n';
  const imported=await request.post(API+'/market/imports',{headers:farmer.headers,multipart:{file:{name:'rescue-prices.csv',mimeType:'text/csv',buffer:Buffer.from(csv)},source_name:'E2E synthetic import',source_url:'https://example.test/synthetic',permission_confirmed:'true'}});
  expect(imported.ok(),await imported.text()).toBeTruthy();expect((await imported.json()).imported).toBe(2);
  await open(page,farmer.token);await page.getByRole('button',{name:'Load imaginary example'}).click();
  const source=page.getByLabel('Price source, option 1',{exact:true});
  await expect(source.locator(`option[value="${quote.id}"]`)).toHaveCount(1);
  await expect(source.getByRole('option',{name:/Rescue farm gate/})).toHaveCount(1);
  await expect(source.getByRole('option',{name:/Rescue retail/})).toHaveCount(1);
  await source.selectOption(quote.id);
  await expect(page.locator('.rescue-quote')).toContainText(quote.market);
  await expect(page.locator('.rescue-quote')).toContainText('DEMO');
  await page.locator('.rescue-option').first().getByRole('checkbox').check();
  const saved=page.waitForResponse(r=>r.url().endsWith('/rescue/plans')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Compare & save plan',exact:true}).click();
  const plan=await (await saved).json();expect(plan.assumptions.options[0].price_id).toBe(quote.id);expect(plan.assumptions.options[0].confirmed).toBe(true);
  await expect(page.getByTestId('rescue-result')).toContainText('DEMO');
  const farmGateOption=source.getByRole('option',{name:/Rescue farm gate/});const farmGateId=await farmGateOption.getAttribute('value');
  await source.selectOption(farmGateId!);await page.locator('.rescue-option').first().getByRole('checkbox').check();
  await page.getByRole('button',{name:'Compare & save plan',exact:true}).click();
  await expect(page.getByTestId('rescue-result')).toContainText('4000.00');
 }finally{await request.delete(API+'/me',{headers:farmer.headers});}
});
test('readiness is required and a supplied hold remains explicitly hypothetical',async({page,request})=>{
 const farmer=await isolatedFarm(request);
 try{
  await open(page,farmer.token);await page.getByRole('button',{name:'Load imaginary example'}).click();
  await page.getByLabel('Ready to sell?',{exact:true}).selectOption({value:''},{timeout:3000});
  await page.getByRole('button',{name:'Compare & save plan',exact:true}).click();
  await expect(page.getByTestId('rescue-result')).toContainText('More information needed');
  await expect(page.locator('.rescue-recommendation')).toHaveCount(0);
  await page.getByLabel('Ready to sell?',{exact:true}).selectOption('yes');
  await page.getByLabel('Include a hold scenario using my own assumptions',{exact:true}).check();
  await page.getByRole('button',{name:'Compare & save plan',exact:true}).click();
  await expect(page.getByTestId('agrorescue').getByRole('alert')).toContainText('Enter a holding assumption');
  await page.getByLabel('Hypothetical future price (BDT/kg)',{exact:true}).fill('60');
  await page.getByLabel('Assumed quantity loss (%)',{exact:true}).fill('10');
  await page.getByLabel('Total holding and later selling costs (BDT)',{exact:true}).fill('300');
  await page.getByLabel('Suitable cold storage available?',{exact:true}).selectOption('yes');
  await page.getByRole('button',{name:'Compare & save plan',exact:true}).click();
  await expect(page.getByTestId('rescue-result')).toContainText('5100.00');
  await expect(page.locator('.rescue-recommendation')).toContainText('Imaginary example — farm gate');
  await expect(page.locator('.rescue-result-card.hypothetical')).toContainText('not a forecast or advice to wait');
 }finally{await request.delete(API+'/me',{headers:farmer.headers,timeout:5000});}
});
test('late comparison response cannot restore edited results and plot switching clears draft inputs',async({page,request})=>{
 const farmer=await isolatedFarm(request);
 let release:()=>void=()=>{};const gate=new Promise<void>(resolve=>{release=resolve;});
 let serverReturned:()=>void=()=>{};const returned=new Promise<void>(resolve=>{serverReturned=resolve;});
 try{
  const second=await request.post(API+'/plots',{headers:farmer.headers,data:{farm_id:farmer.plot.farm_id,name:'Other rescue plot',crop:'tomato',area_acres:'1'}});expect(second.ok()).toBeTruthy();const secondPlot=await second.json();
  await open(page,farmer.token);await page.getByRole('button',{name:'Load imaginary example'}).click();
  await page.route('**/rescue/plans',async route=>{if(route.request().method()!=='POST'){await route.continue();return;}const response=await route.fetch();serverReturned();await gate;await route.fulfill({response}).catch(()=>{});});
  await page.getByRole('button',{name:'Compare & save plan',exact:true}).click();await returned;
  await page.getByLabel('Harvested quantity (kg)',{exact:true}).fill('120');release();
  await expect(page.getByTestId('rescue-result')).toHaveCount(0);
  await page.getByLabel('Select plot',{exact:true}).selectOption(secondPlot.id);
  await expect(page.getByLabel('Harvested quantity (kg)',{exact:true})).toHaveValue('');
  await expect(page.getByRole('button',{name:'Open saved plan',exact:true})).toHaveCount(0);
 }finally{release();await request.delete(API+'/me',{headers:farmer.headers});}
});
test('changing a price invalidates the previous farmer confirmation',async({page,request})=>{
 const farmer=await isolatedFarm(request);
 try{
  await open(page,farmer.token);await page.getByRole('button',{name:'Load imaginary example'}).click();
  const confirmation=page.locator('.rescue-option').first().getByRole('checkbox');
  await confirmation.check();await expect(confirmation).toBeChecked();
  await page.getByLabel('Price (BDT/kg), option 1',{exact:true}).fill('41');
  await expect(confirmation).not.toBeChecked();
  await confirmation.check();
  const source=page.getByLabel('Price source, option 1',{exact:true});
  await expect(source.locator('option')).not.toHaveCount(1);
  const savedId=await source.locator('option').nth(1).getAttribute('value');
  await source.selectOption(savedId!);await expect(confirmation).not.toBeChecked();
 }finally{await request.delete(API+'/me',{headers:farmer.headers});}
});
