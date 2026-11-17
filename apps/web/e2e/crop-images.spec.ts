import {test,expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
import type {Product} from '../src/lib/marketplace-types';

test.use({baseURL:process.env.E2E_BASE_URL||'http://127.0.0.1:3300'});
const tomatoPhoto=readFileSync('public/crops/tomato.jpg');
const bananaPhoto=readFileSync('public/crops/banana.jpg');
function product(id:string,name:string,images:Product['images']=[],status='published'):Product {
  return {id,farmer_id:'crop-farmer',seller_name:'Crop photo test farm',seller_verification:'unverified',farm_id:null,name,category:'vegetables',description:'Test produce listing',price_bdt:'60',currency:'BDT',unit:'kg',quantity_step:'1',stock_quantity:'10',auction_reserved:'0',minimum_order_quantity:null,maximum_order_quantity:null,status,version:1,district:'Dhaka',area:'Savar',distance_km:null,nearby:false,images,pickup_enabled:true,delivery_enabled:false,nationwide_delivery:false,delivery_districts:[],delivery_fee_bdt:'0',auction:null,moderation_status:'visible',created_at:'2026-11-17T00:00:00Z',updated_at:'2026-11-17T00:00:00Z'};
}
async function catalog(page:Page,products:Product[]) {
  await page.route('**/api/v1/**',route=>{
    const path=new URL(route.request().url()).pathname;
    const found=products.find(p=>path===`/api/v1/market/products/${p.id}`);
    let body:unknown=[];
    if(path==='/api/v1/me')body={id:'crop-owner',name:'Crop owner',role:'farmer',preferences:{language:'en',theme:'light',retraining_consent:false}};
    else if(path==='/api/v1/doctor/capabilities')body={crops:[]};
    else if(path==='/api/v1/doctor/models/current')body={available:false,labels:[],limitations:[]};
    else if(path==='/api/v1/market/products'||path.endsWith('/reviews'))body={items:products,total:products.length,offset:0,limit:12,has_more:false};
    return route.fulfill({json:found||body});
  });
}

test('missing photos use matching local crops with labels; unknown crops stay neutral in both languages',async({page})=>{
  await catalog(page,[product('tomato','Fresh tomato'),product('eggplant','দেশি বেগুন'),product('unknown','Pineapple')]);
  for(const locale of ['en','bn']) {
    await page.goto(`/${locale}/marketplace`);
    const tomato=page.locator('.mk-product').filter({has:page.getByRole('heading',{name:'Fresh tomato',exact:true})});
    await expect(tomato.locator('img')).toHaveAttribute('src','/crops/tomato.jpg');
    await expect(tomato.getByText(locale==='en'?'Illustrative crop image':'ফসলের উদাহরণ ছবি',{exact:true})).toBeVisible();
    const eggplant=page.locator('.mk-product').filter({has:page.getByRole('heading',{name:'দেশি বেগুন',exact:true})});
    await expect(eggplant.locator('img')).toHaveAttribute('src','/crops/eggplant.jpg');
    const unknown=page.locator('.mk-product').filter({has:page.getByRole('heading',{name:'Pineapple',exact:true})});
    await expect(unknown.locator('img')).toHaveCount(0);
    await expect(tomato.locator('img')).toBeVisible();
    expect(await tomato.locator('img').evaluate((im:HTMLImageElement)=>im.complete&&im.naturalWidth>0)).toBe(true);
  }
});

test('private uploads remain authenticated blobs and a late previous request cannot replace the selected image',async({page})=>{
  await page.addInitScript(()=>localStorage.setItem('agrosphere-token','crop-owner-test-token'));
  const p=product('private','Tomato private listing',[{id:'old',url:'/test-produce-private-old.png'},{id:'new',url:'/test-produce-private-new.png'}],'draft');
  await catalog(page,[p]);
  let releaseOld!:()=>void;
  const oldHeld=new Promise<void>(resolve=>{releaseOld=resolve;});
  const privateHeaders:string[]=[];
  await page.route('**/test-produce-private-old.png',async route=>{
    privateHeaders.push(route.request().headers()['authorization']);
    await oldHeld;
    await route.fulfill({contentType:'image/jpeg',body:tomatoPhoto}).catch(()=>{});
  });
  await page.route('**/test-produce-private-new.png',route=>{
    privateHeaders.push(route.request().headers()['authorization']);
    return route.fulfill({contentType:'image/jpeg',body:bananaPhoto});
  });
  await page.goto('/en/marketplace/products/private');
  const gallery=page.locator('.mk-gallery');
  await expect(gallery.getByText('Loading photo…',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'View photo 2',exact:true}).click();
  await expect(gallery.locator('img')).toHaveAttribute('src',/^blob:/);
  await expect.poll(()=>gallery.locator('img').evaluate((im:HTMLImageElement)=>im.naturalHeight)).toBe(846);
  const selected=await gallery.locator('img').getAttribute('src');
  releaseOld();
  // Let all held route responses settle, including the old thumbnail response.
  await expect.poll(()=>page.locator('.mk-thumbnails button').first().locator('img').count()).toBe(1);
  await expect(gallery.locator('img')).toHaveAttribute('src',selected!);
  await expect.poll(()=>gallery.locator('img').evaluate((im:HTMLImageElement)=>im.naturalHeight)).toBe(846);
  expect(privateHeaders.length).toBeGreaterThan(1);
  expect(privateHeaders.every(header=>header==='Bearer crop-owner-test-token')).toBe(true);
  await expect(gallery.getByText('Illustrative crop image',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'View photo 1',exact:true}).click();
  await expect.poll(()=>gallery.locator('img').evaluate((im:HTMLImageElement)=>im.naturalHeight)).toBe(798);
  // The old private object URL is no longer fetchable after its image unmounts.
  expect(await page.evaluate(async url=>{try{await fetch(url!);return true;}catch{return false;}},selected)).toBe(false);
});

test('seller uploads take priority, broken uploads use crop fallback, and another thumbnail can still load',async({page})=>{
  const p=product('uploaded','Fresh tomato',[{id:'broken',url:'/test-produce-broken.png'},{id:'valid',url:'/test-produce-valid.png'}]);
  await catalog(page,[p]);
  await page.route('**/test-produce-broken.png',route=>route.fulfill({status:404,body:'Missing'}));
  await page.route('**/test-produce-valid.png',route=>route.fulfill({contentType:'image/jpeg',body:tomatoPhoto}));
  await page.goto('/en/marketplace/products/uploaded');
  const gallery=page.locator('.mk-gallery');
  await expect(gallery.locator('img')).toHaveAttribute('src','/crops/tomato.jpg');
  await expect(gallery.getByText('Illustrative crop image',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'View photo 2',exact:true}).click();
  await expect(gallery.locator('img')).toHaveAttribute('src','/test-produce-valid.png');
  await expect(gallery.getByText('Illustrative crop image',{exact:true})).toHaveCount(0);
  expect(await gallery.locator('img').evaluate((im:HTMLImageElement)=>im.complete&&im.naturalWidth>0)).toBe(true);
  await page.getByRole('button',{name:'View photo 1',exact:true}).click();
  await expect(gallery.locator('img')).toHaveAttribute('src','/crops/tomato.jpg');
});

test('unusable tiny uploads use labelled crop photos without overriding an image with both sides at least 32 pixels',async({page})=>{
  const fixtures={
    black:'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC',
    transparent:'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABpfZFQAAAAABJRU5ErkJggg==',
    narrow:'iVBORw0KGgoAAAANSUhEUgAAAB8AAABACAIAAABtFDtMAAAAHUlEQVR4nO3BMQEAAADCoPVPbQlPoAAAAAAAgLcBF4AAAURLhYgAAAAASUVORK5CYII=',
    short:'iVBORw0KGgoAAAANSUhEUgAAAEAAAAAfCAIAAADY01yrAAAAHUlEQVR4nO3BMQEAAADCoPVPbQZ/oAAAAAAAgNMAF18AAZPFFFAAAAAASUVORK5CYII=',
    boundary:'iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAKUlEQVR4nO3NMQEAAAjDMEA50jHBvlRA07UVbbJ7AAAAAAAAAAAA8NcBn4kAwO7os6MAAAAASUVORK5CYII=',
  };
  const entries=Object.entries(fixtures);
  await catalog(page,entries.map(([id])=>product(id,`Fresh tomato ${id}`,[{id,url:`/test-produce-tiny-${id}.png`}],id==='transparent'?'draft':'published')));
  await page.route('**/test-produce-tiny-*.png',route=>{
    const id=new URL(route.request().url()).pathname.match(/tiny-(\w+)\.png$/)![1] as keyof typeof fixtures;
    return route.fulfill({contentType:'image/png',body:Buffer.from(fixtures[id],'base64')});
  });
  await page.goto('/en/marketplace');
  for(const id of ['black','transparent','narrow','short']) {
    const card=page.locator('.mk-product').filter({has:page.getByRole('heading',{name:`Fresh tomato ${id}`,exact:true})});
    await expect(card.locator('img')).toHaveAttribute('src','/crops/tomato.jpg');
    await expect(card.getByText('Illustrative crop image',{exact:true})).toBeVisible();
  }
  const valid=page.locator('.mk-product').filter({has:page.getByRole('heading',{name:'Fresh tomato boundary',exact:true})});
  await expect(valid.locator('img')).toHaveAttribute('src','/test-produce-tiny-boundary.png');
  await expect.poll(()=>valid.locator('img').evaluate((im:HTMLImageElement)=>im.naturalWidth)).toBe(32);
  await expect(valid.getByText('Illustrative crop image',{exact:true})).toHaveCount(0);
});

test('a failed bundled photo ends in a neutral placeholder without a broken-image loop',async({page})=>{
  await catalog(page,[product('tomato','Fresh tomato')]);
  await page.route('**/crops/tomato.jpg',route=>route.fulfill({status:404,body:'Unavailable'}));
  await page.goto('/en/marketplace');
  const card=page.locator('.mk-product').first();
  await expect(card.getByLabel('No product photo',{exact:true})).toBeVisible();
  await expect(card.locator('img')).toHaveCount(0);
});
