import {test,expect} from '@playwright/test';
test('farmer completes the connected software-first journey',async({page,request})=>{
 await page.goto('/en');await page.getByRole('button',{name:'Explore a demo farm'}).click();await expect(page.getByRole('heading',{name:'Your farm, in perspective.'})).toBeVisible();
 await page.getByRole('link',{name:'AgroDoctor AI',exact:false}).first().click();
 // An intentionally flat, generated image exercises uncertainty without a licensed leaf photograph.
 const token=await page.evaluate(()=>localStorage.getItem('agrosphere-token'));
 const fixture=await request.get((process.env.AGROSPHERE_API_URL||'http://127.0.0.1:8000/api/v1')+'/health');expect(fixture.ok()).toBeTruthy();
 await expect(page.getByRole('button',{name:'Choose a photo'})).toBeEnabled();
 await page.locator('input[aria-label="Upload leaf photo"]').setInputFiles({name:'quality-fixture.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=','base64')});
 await page.getByRole('button',{name:'Screen & save observation'}).click();await expect(page.getByRole('heading',{name:'Unable to classify reliably'})).toBeVisible();await expect(page.getByRole('link',{name:'Open',exact:true})).toBeVisible();
 await page.getByRole('link',{name:'FloodCrop AI',exact:false}).first().click();await expect(page.getByText('Preparedness, explained.')).toBeVisible();await expect(page.getByText('Simulated scenario', {exact:true})).toBeVisible();
 await page.getByRole('button',{name:'72 hours'}).click();await expect(page.getByText('72-HOUR RAIN OUTLOOK')).toBeVisible();
 await page.getByRole('link',{name:'KrishiMarket AI',exact:false}).first().click();await page.getByLabel('Transport (BDT)').fill('500');await page.getByLabel('Handling (BDT)').fill('100');await page.getByLabel('Fees / storage (BDT)').fill('0');await page.getByRole('button',{name:'Compare expected proceeds'}).click();await expect(page.getByText('৳16200.00',{exact:true})).toBeVisible();await expect(page.getByText('৳17800.00',{exact:true})).toBeVisible();
 await page.getByRole('link',{name:'Action center',exact:false}).first().click();await expect(page.getByText('Review your net selling comparison')).toBeVisible();
 await page.getByRole('link',{name:'Future devices',exact:false}).click();await page.getByRole('button',{name:'Register virtual device'}).click();await page.getByRole('button',{name:'Send simulated reading'}).click();await expect(page.getByText('SIMULATED_DATA',{exact:true})).toBeVisible();
 await page.getByRole('link',{name:'Data & models',exact:false}).first().click();await expect(page.getByText(/Trained · not field-validated|No trained model installed/)).toBeVisible();expect(token).toBeTruthy();
});
test('mobile navigation and Bengali route remain usable',async({page})=>{await page.setViewportSize({width:360,height:800});await page.goto('/bn');await page.getByRole('button',{name:'ডেমো খামার দেখুন'}).click();await expect(page.getByRole('heading',{name:'আপনার খামারের সারসংক্ষেপ।'})).toBeVisible();await page.getByRole('button',{name:'Open navigation'}).click();await page.getByRole('link',{name:'এগ্রোডক্টর AI'}).click();await expect(page.getByRole('heading',{name:'পাতার ছবি আপলোড করুন'})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy()});

