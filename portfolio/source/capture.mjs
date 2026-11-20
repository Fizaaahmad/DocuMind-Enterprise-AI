import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const require = createRequire(new URL('../../.production-smoke/ui-tools/package.json', import.meta.url));
const { chromium } = require('playwright');
let raw=''; for await (const chunk of process.stdin) raw+=chunk;
const data=JSON.parse(raw);
const root=new URL('../',import.meta.url);
const browser=await chromium.launch({channel:'msedge',headless:true});
const captured=[];
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:2,reducedMotion:'reduce'});
 await context.addCookies(data.cookies);
 await context.addInitScript(()=>{if(!localStorage.getItem('documind.theme'))localStorage.setItem('documind.theme','light');});
 const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',route=>['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
 let prefix='';
 async function save(name,selector){
   await page.screenshot({path:fileURLToPath(new URL(`screenshots/${prefix}${name}.png`,root)),fullPage:true});
   if(selector) await page.locator(selector).screenshot({path:fileURLToPath(new URL(`screenshots/${prefix}${name}-detail.png`,root))});
   if(['01-dashboard','03-assistant','08-comparison','09-operations'].includes(name)){
     const theme=prefix?'dark':'light';
     await mkdir(new URL(`screenshots/post-ready/${theme}/`,root),{recursive:true});
     await page.evaluate(()=>window.scrollTo(0,0));
     await page.screenshot({path:fileURLToPath(new URL(`screenshots/post-ready/${theme}/${name}.png`,root)),fullPage:false});
   }
   captured.push({name:prefix+name,theme:prefix?'dark':'light',url:new URL(page.url()).pathname,provenance:'Actual application with fictional demo data; mock AI only'});
 }
 async function go(path){await page.goto(`http://127.0.0.1:3004/${path}${path.includes('?')?'&':'?'}organization=${data.org}`,{waitUntil:'networkidle'});}
 async function captureScreens(){
 await go('dashboard');await page.locator('.overview-space .metric-number').first().waitFor();await save('01-dashboard','.overview-space');
 await go('documents');await page.getByText('Master Services Agreement.pdf',{exact:true}).first().waitFor();await save('02-document-library');
 await go('assistant');await page.getByRole('button',{name:'What are the service fees and supplier obligations?',exact:true}).click();
 await page.getByRole('button',{name:'Inspect source 1'}).first().waitFor();await save('03-assistant','.assistant-chat');
 await page.getByRole('button',{name:'Inspect source 1'}).first().click();await page.getByRole('dialog',{name:'Source evidence'}).waitFor();await save('04-evidence','dialog');await page.keyboard.press('Escape');
 await go('intelligence');
 await page.getByRole('button',{name:/Extraction ·/}).first().click();await page.getByRole('heading',{name:'contract value'}).waitFor();await save('05-extraction','.intelligence-grid > div');
 await page.getByRole('button',{name:/^Risks \(/}).click();await save('06-risks','.intelligence-grid > div');
 await page.getByRole('button',{name:/^Obligations \(/}).click();await save('07-obligations','.intelligence-grid > div');
 await page.getByRole('button',{name:/Comparison ·/}).first().click();await page.getByRole('heading',{name:'Revision comparison'}).waitFor();await save('08-comparison','.intelligence-grid > div');
 await go('operations?engine=all');await page.getByRole('heading',{name:/Enterprise overview/i}).waitFor();await save('09-operations');
 await page.getByRole('button',{name:/^obligations$/i}).click();await save('10-operations-obligations');
 }
 await captureScreens();
 prefix='dark/';await mkdir(new URL('screenshots/dark/',root),{recursive:true});
 await page.getByLabel('Color theme').selectOption('dark');
 await captureScreens();
 if(errors.length) throw Error('Runtime errors during capture: '+errors.join(';'));
 await writeFile(new URL('verification/screenshots.json',root),JSON.stringify({captured,runtimeErrors:errors},null,2));
} finally {await browser.close();}
