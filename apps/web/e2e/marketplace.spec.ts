import {test, expect, type APIRequestContext, type Page} from '@playwright/test';
import type {Product} from '../src/lib/marketplace-types';

const API = (process.env.E2E_API_URL || process.env.AGROSPHERE_API_URL || 'http://127.0.0.1:8300/api/v1').replace(/\/$/, '');
const WEB=process.env.E2E_BASE_URL||process.env.PLAYWRIGHT_BASE_URL||'http://127.0.0.1:3300';
test.use({baseURL:WEB});
async function account(request: APIRequestContext, role: 'farmer'|'customer') {
  const response = await request.post(API+'/auth/register', {data:{name:`Market ${role}`,email:`market-${role}-${crypto.randomUUID()}@example.test`,password:'Market-test-8274!',role}});
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json() as Promise<{token:string;user:{id:string}}>;
}
async function signIn(page: Page, token:string) {
  await page.goto('/en/marketplace');
  await page.evaluate(token=>localStorage.setItem('agrosphere-token',token),token);
  await page.reload();
  await expect(page.getByRole('heading',{name:'Fresh from the farm.'})).toBeVisible();
}
test('public marketplace is usable in English and Bengali without location permission',async({page})=>{
  const catalog=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/market/products'&&r.ok());
  await page.goto('/en/marketplace');
  await expect(page.getByRole('heading',{name:'Fresh from the farm.'})).toBeVisible();
  await catalog;
  await expect(page.locator('.mk-root').getByText('Loading…',{exact:true})).toBeHidden();
  await expect(page.getByRole('button',{name:'Use my location',exact:true})).toBeVisible();
  await expect(page.getByLabel('Search produce')).toBeVisible();
  await page.setViewportSize({width:360,height:800});
  const bengaliCatalog=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/market/products'&&r.ok());
  await page.goto('/bn/marketplace');
  await expect(page.getByRole('heading',{name:'সরাসরি খামার থেকে।'})).toBeVisible();
  await bengaliCatalog;
  await expect(page.locator('.mk-root').getByText('লোড হচ্ছে…',{exact:true})).toBeHidden();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
test('farmer listing, customer direct purchase with MOQ, and fulfillment',async({page,request,browser})=>{
  const farmer=await account(request,'farmer'); const customer=await account(request,'customer');
  const headers={Authorization:`Bearer ${farmer.token}`};
  const profile=await request.patch(API+'/market/profile',{headers,data:{public_name:'Test harvest farm',district:'Dhaka',area:'Savar',latitude:23.85,longitude:90.25,bio:'Fresh test produce',phone:'01700000001'}});
  expect(profile.ok(),await profile.text()).toBeTruthy();
  const farmResponse=await request.post(API+'/farms',{headers,data:{name:'E2E harvest farm',district:'Dhaka'}});expect(farmResponse.ok(),await farmResponse.text()).toBeTruthy();const farm=await farmResponse.json();
  await signIn(page,farmer.token);
  await page.getByRole('link',{name:'Seller studio',exact:true}).click();
  await page.getByRole('button',{name:'New listing',exact:true}).click();
  const name=`Fresh tomato ${crypto.randomUUID().slice(0,8)}`;
  await page.getByLabel('Farm',{exact:true}).selectOption(farm.id);
  await page.getByLabel('Product name', {exact:true}).fill(name);
  await page.getByLabel('Description',{exact:true}).fill('Harvested locally for a real marketplace flow.');
  await page.getByLabel('Price (BDT)',{exact:true}).fill('60');
  await page.getByLabel('Stock quantity',{exact:true}).fill('20');
  await page.getByLabel('Minimum order quantity (optional)',{exact:true}).fill('2');
  await page.getByLabel('Listing status',{exact:true}).selectOption('published');
  await page.getByRole('button',{name:'Save listing',exact:true}).click();
  await expect(page.getByRole('heading',{name})).toBeVisible();
  const upload=page.getByLabel('Product photo',{exact:true});
  await expect(upload).toBeEnabled();
  // Use an actual viewable produce photo for the seller-upload journey.
  // Tiny tracking/placeholder pixels are covered by crop-images.spec.ts.
  await upload.setInputFiles('public/crops/tomato.jpg');
  await page.getByRole('button',{name:'Upload photo',exact:true}).click();
  await expect(page.getByText('Photo added.',{exact:true})).toBeVisible();
  const buyerContext=await browser.newContext({baseURL:WEB}); const buyer=await buyerContext.newPage();
  await signIn(buyer,customer.token);
  await buyer.getByLabel('Search produce').fill(name);
  await buyer.getByLabel('District (manual)').fill('Dhaka');
  await buyer.getByLabel('Latitude (optional)').fill('23.85');
  await buyer.getByLabel('Longitude (optional)').fill('90.25');
  await buyer.getByRole('button',{name:'Find produce',exact:true}).click();
  await buyer.getByRole('link',{name:name,exact:true}).click();
  const photo=buyer.getByRole('img',{name:name+' 1',exact:true}).first();
  await expect(photo).toBeVisible();
  await expect.poll(()=>photo.evaluate((img:HTMLImageElement)=>img.complete&&img.naturalWidth>0)).toBeTruthy();
  await expect(buyer.getByRole('button',{name:'Buy now',exact:true})).toBeVisible();
  await expect(buyer.getByText(/Minimum order: 2(?:\.000)? kg/)).toBeVisible();
  await buyer.getByLabel('Quantity',{exact:true}).fill('1');
  await buyer.getByRole('button',{name:'Buy now',exact:true}).click();
  await expect(buyer.getByRole('alert').filter({hasText:'Minimum order'})).toBeVisible();
  await buyer.getByLabel('Quantity',{exact:true}).fill('2');
  await buyer.getByRole('button',{name:'Buy now',exact:true}).click();
  await buyer.getByLabel('Recipient name').fill('Test Buyer');
  await buyer.getByLabel('Phone',{exact:true}).fill('01700000002');
  await buyer.getByLabel('Address line').fill('Test pickup address');
  await buyer.getByLabel('District',{exact:true}).fill('Dhaka');
  await buyer.getByLabel('Area',{exact:true}).fill('Savar');
  await buyer.getByRole('button',{name:'Save address',exact:true}).click();
  await buyer.getByRole('radio').first().check();
  await buyer.getByRole('button',{name:'Place demo order',exact:true}).click();
  await expect(buyer.getByText('demo_unpaid',{exact:true}).first()).toBeVisible();
  await page.getByRole('link',{name:'Orders',exact:true}).click();
  for(const status of ['confirmed','preparing','ready_for_pickup','delivered']) {
    const order=page.locator('[data-seller-order]').filter({hasText:name}).first();
    await order.getByLabel('Next status').selectOption(status);
    await order.getByRole('button',{name:'Update fulfillment',exact:true}).click();
    await expect(order.getByText(status,{exact:true})).toBeVisible();
  }
  await buyer.reload();
  await expect(buyer.getByText('delivered',{exact:true}).first()).toBeVisible();
  await buyerContext.close();
});

test('optional auction retains direct buy and creates an unpaid winner order',async({page,request})=>{
  const farmer=await account(request,'farmer');const customer=await account(request,'customer');
  const headers={Authorization:`Bearer ${farmer.token}`};const buyerHeaders={Authorization:`Bearer ${customer.token}`};
  const profile=await request.patch(API+'/market/profile',{headers,data:{district:'Dhaka',area:'Savar'}});expect(profile.ok(),await profile.text()).toBeTruthy();
  const farmResponse=await request.post(API+'/farms',{headers,data:{name:'Auction grower',district:'Dhaka'}});expect(farmResponse.ok(),await farmResponse.text()).toBeTruthy();const farm=await farmResponse.json();
  const productResponse=await request.post(API+'/market/products',{headers,data:{farm_id:farm.id,name:'Auction harvest '+crypto.randomUUID().slice(0,8),category:'vegetables',description:'Optional separate auction lot',price_bdt:'50',unit:'kg',quantity_step:'1',stock_quantity:'30',status:'published',pickup_enabled:true}});expect(productResponse.ok(),await productResponse.text()).toBeTruthy();const product=await productResponse.json();
  const addressResponse=await request.post(API+'/market/addresses',{headers:buyerHeaders,data:{name:'Auction buyer',phone:'01700000003',line1:'Pickup address',district:'Dhaka',area:'Savar'}});expect(addressResponse.ok(),await addressResponse.text()).toBeTruthy();
  await signIn(page,customer.token);await page.goto('/en/marketplace/products/'+product.id);
  await expect(page.getByRole('button',{name:'Buy now',exact:true})).toBeVisible();
  const now=Date.now();const auctionResponse=await request.post(API+'/market/auctions',{headers,data:{product_id:product.id,lot_quantity:'5',starting_bid_bdt:'200',minimum_increment_bdt:'10',starts_at:new Date(now-1000).toISOString(),ends_at:new Date(now+12000).toISOString(),draft:false}});expect(auctionResponse.ok(),await auctionResponse.text()).toBeTruthy();const auction=await auctionResponse.json();
  await page.reload();await expect(page.getByRole('heading',{name:'Optional auction lot',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Buy now',exact:true})).toBeVisible();
  await page.getByLabel('Your bid for the whole lot (BDT)').fill('200');
  await expect(page.getByRole('button',{name:'Confirm and place bid',exact:true})).toBeDisabled();
  await page.getByRole('checkbox',{name:/I confirm a bid/}).check();
  await page.getByRole('button',{name:'Confirm and place bid',exact:true}).click();
  await expect(page.getByText('Your bid was recorded.',{exact:true})).toBeVisible();
  await expect.poll(async()=>{const r=await request.get(API+'/market/auctions/'+auction.id,{headers:buyerHeaders});return (await r.json()).state;},{timeout:20000,intervals:[300,500,1000]}).toBe('awarded');
  await page.getByRole('button',{name:'Refresh auction state',exact:true}).click();
  await expect(page.getByRole('heading',{name:'You won this lot',exact:true})).toBeVisible();
  await page.getByRole('radio').first().check();
  await page.getByRole('button',{name:'Confirm winning lot',exact:true}).click();
  await expect(page.getByText('Winning lot confirmed as an unpaid demo order.',{exact:true})).toBeVisible();
  await page.getByRole('link',{name:'Orders',exact:true}).click();
  await expect(page.getByText('Auction lot order',{exact:true})).toBeVisible();
  await expect(page.getByText('demo_unpaid',{exact:true}).first()).toBeVisible();
});

// Isolated UI regressions: every API request is intercepted; these tests do not
// depend on the native API process or modify the marketplace database.
const regressionProduce:Product={id:'regression-produce',farmer_id:'grower',seller_name:'Regression farm',seller_verification:'unverified',farm_id:'farm',name:'Regression tomatoes',category:'vegetables',description:'Fixture produce',price_bdt:'60.00',currency:'BDT',unit:'kg',quantity_step:'1',stock_quantity:'20',auction_reserved:'0',minimum_order_quantity:null,maximum_order_quantity:null,status:'published',version:1,district:'Dhaka',area:'Savar',distance_km:null,nearby:false,images:[],pickup_enabled:true,delivery_enabled:false,nationwide_delivery:false,delivery_districts:[],delivery_fee_bdt:'0',auction:null,moderation_status:'visible',created_at:'2026-11-17T00:00:00Z',updated_at:'2026-11-17T00:00:00Z'};
async function isolatedAPI(page:Page,handler:(path:string,method:string,body:unknown)=>unknown|Promise<unknown>){
  await page.route('**/api/v1/**',async route=>{
    const request=route.request();const path=new URL(request.url()).pathname.replace('/api/v1','');
    const response=await handler(path,request.method(),request.postDataJSON());
    const result=response as {status?:number;body?:unknown}|undefined;
    const defaults=path==='/me'?{id:'regression-customer',name:'Regression buyer',role:'customer',preferences:{language:'en',theme:'light',retraining_consent:false}}:path==='/doctor/models/current'?{models:[]}:path==='/doctor/capabilities'?{models:[]}:[];
    await route.fulfill({status:result?.status||200,json:result?.body??defaults,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*'}});
  });
}
test('isolated regression: discovery defaults nearby and retains nationwide results with coordinates',async({page})=>{
  const queries:URLSearchParams[]=[];
  await isolatedAPI(page,(path)=>{
    if(path==='/market/products')return {body:{items:[{...regressionProduce,id:'near',name:'Near harvest',distance_km:2,nearby:true},{...regressionProduce,id:'far',name:'Nationwide harvest',district:'Rangpur',distance_km:200,nearby:false}],total:2,offset:0,limit:12,has_more:false,notice:'Nationwide results remain available.'}};
  });
  page.on('request',r=>{const url=new URL(r.url());if(url.pathname==='/api/v1/market/products')queries.push(url.searchParams);});
  await page.goto('/en/marketplace');
  await expect(page.getByLabel('Sort by',{exact:true})).toHaveValue('nearby');
  await expect.poll(()=>queries[0]?.get('sort')).toBe('nearby');
  await page.getByLabel('District (manual)',{exact:true}).fill('Dhaka');
  await page.getByLabel('Latitude (optional)',{exact:true}).fill('23.85');
  await page.getByLabel('Longitude (optional)',{exact:true}).fill('90.25');
  await page.getByRole('button',{name:'Find produce',exact:true}).click();
  await expect.poll(()=>queries.at(-1)?.get('lat')).toBe('23.85');
  expect(queries.at(-1)?.get('sort')).toBe('nearby');
  expect(queries.at(-1)?.has('district_filter')).toBe(false);
  await expect(page.getByText('Nationwide results remain available.',{exact:true})).toBeVisible();
  await expect(page.getByRole('link',{name:'Near harvest',exact:true}).first()).toBeVisible();
  await expect(page.getByRole('link',{name:'Nationwide harvest',exact:true}).first()).toBeVisible();
});
test('isolated regression: checkout conflict refreshes quote and requires a deliberate retry',async({page})=>{
  let cartReads=0;const submissions:{quote_hash:string}[]=[];const idempotencyKeys:string[]=[];
  await page.addInitScript(()=>localStorage.setItem('agrosphere-token','isolated-regression-session'));
  await isolatedAPI(page,(path,method,body)=>{
    if(path==='/market/cart'){cartReads++;const price=submissions.length?'80.00':'60.00';return {body:{items:[{id:'cart-line',quantity:'2',product:{...regressionProduce,price_bdt:price},total_bdt:String(Number(price)*2)}],subtotal_bdt:String(Number(price)*2),quote_hash:submissions.length?'quote-refreshed':'quote-stale',currency:'BDT'}};}
    if(path==='/market/addresses')return {body:[{id:'address',name:'Regression buyer',phone:'01700000000',line1:'Test address',district:'Dhaka',area:'Savar',country:'Bangladesh'}]};
    if(path==='/market/orders'&&method==='POST'){submissions.push({quote_hash:(body as {quote_hash:string}).quote_hash});return submissions.length===1?{status:409,body:{code:'CONFLICT',message:'Quote has changed'}}:{body:{id:'order-created'}};}
    if(path==='/market/orders')return {body:{items:[],total:0,offset:0,limit:20,has_more:false}};
  });
  page.on('request',r=>{if(new URL(r.url()).pathname==='/api/v1/market/orders'&&r.method()==='POST')idempotencyKeys.push(r.headers()['idempotency-key']||'');});
  await page.goto('/en/marketplace/cart');
  await page.getByRole('radio',{name:/Select Regression buyer/}).check();
  await page.getByRole('button',{name:'Place demo order',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:/Review the refreshed/})).toBeVisible();
  expect(cartReads).toBeGreaterThan(1);
  expect(submissions).toHaveLength(1);
  await expect(page.getByText('৳80.00 / kg',{exact:false})).toBeVisible();
  await expect(page.getByRole('button',{name:'Place demo order',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'Place demo order',exact:true}).click();
  await expect.poll(()=>submissions.length).toBe(2);
  expect(submissions.map(s=>s.quote_hash)).toEqual(['quote-stale','quote-refreshed']);
  expect(idempotencyKeys).toHaveLength(2);
  expect(idempotencyKeys.every(Boolean)).toBeTruthy();
  expect(idempotencyKeys[0]).not.toBe(idempotencyKeys[1]);
});
test('isolated regression: failed quote refresh blocks another checkout until cart reloads',async({page})=>{
  let posts=0;let permitRefresh=false;
  await page.addInitScript(()=>localStorage.setItem('agrosphere-token','isolated-regression-session'));
  await isolatedAPI(page,(path,method)=>{
    if(path==='/market/cart'){if(posts&&!permitRefresh)return {status:503,body:{message:'Cart temporarily unavailable'}};return {body:{items:[{id:'cart-line',quantity:'2',product:regressionProduce,total_bdt:'120.00'}],subtotal_bdt:'120.00',quote_hash:posts?'quote-refreshed':'quote-stale',currency:'BDT'}};}
    if(path==='/market/addresses')return {body:[{id:'address',name:'Regression buyer',phone:'01700000000',line1:'Test address',district:'Dhaka',area:'Savar',country:'Bangladesh'}]};
    if(path==='/market/orders'&&method==='POST'){posts++;return {status:409,body:{code:'CONFLICT',message:'Quote has changed'}};}
  });
  await page.goto('/en/marketplace/cart');
  await page.getByRole('radio',{name:/Select Regression buyer/}).check();
  await page.getByRole('button',{name:'Place demo order',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'Your cart changed and could not refresh'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Place demo order',exact:true})).toBeDisabled();
  expect(posts).toBe(1);
  permitRefresh=true;
  await page.getByRole('button',{name:'Retry',exact:true}).click();
  await expect(page.getByRole('button',{name:'Place demo order',exact:true})).toBeEnabled();
  expect(posts).toBe(1);
});
test('isolated regression: ineligible historical bids remain visibly labelled',async({page})=>{
  await isolatedAPI(page,path=>path==='/market/auctions'?{body:{items:[{id:'auction-history',product_id:regressionProduce.id,product:regressionProduce,farmer_id:'grower',lot_quantity:'5',unit:'kg',starting_bid_bdt:'100',minimum_increment_bdt:'10',highest_bid_bdt:'100',state:'awarded',starts_at:'2026-11-17T00:00:00Z',ends_at:'2026-11-17T01:00:00Z',server_time:'2026-11-17T02:00:00Z',winner_is_you:false,confirmed_order_id:null,reserve_met:true,confirmation_deadline:null,bids:[{id:'inactive-bid',bidder_alias:'Historical bidder',amount_bdt:'200',created_at:'2026-11-17T00:10:00Z',is_yours:false,eligible:false},{id:'active-bid',bidder_alias:'Eligible bidder',amount_bdt:'100',created_at:'2026-11-17T00:05:00Z',is_yours:false,eligible:true}]}],total:1,offset:0,limit:10,has_more:false}}:undefined);
  await page.goto('/en/marketplace/auctions');
  await page.getByText('Bid history (2)',{exact:true}).click();
  await expect(page.locator('p').filter({hasText:'Historical bidder'})).toContainText('Ineligible bid');
  await expect(page.locator('p').filter({hasText:'Eligible bidder'})).not.toContainText('Ineligible bid');
});
