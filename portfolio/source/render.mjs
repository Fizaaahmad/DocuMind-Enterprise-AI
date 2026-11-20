/** Render authored HTML/SVG with local Edge. No network access or paid services. */
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const require=createRequire(new URL('../../.production-smoke/ui-tools/package.json',import.meta.url));
const {chromium}=require('playwright');
const root=new URL('../',import.meta.url);
const browser=await chromium.launch({channel:'msedge',headless:true});
const checks=[];
try{
 const page=await browser.newPage({viewport:{width:1080,height:1350},deviceScaleFactor:1});
 await page.route('**/*',route=>route.request().url().startsWith('file:')?route.continue():route.abort());
 for(const [file,selector,dest] of [['case-study.html','.page','case-study/DocuMind-Engineering-Case-Study.pdf'],['carousel.html','.slide','carousel/DocuMind-LinkedIn-Carousel.pdf']]){
  await page.goto(new URL('source/'+file,root).href,{waitUntil:'load'});
  await page.evaluate(()=>document.fonts.ready);
  const missing=await page.locator('img').evaluateAll(imgs=>imgs.filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.getAttribute('src')));
  if(missing.length) throw Error('Missing product screenshots: '+missing.join(','));
  const blocks=page.locator(selector);if(await blocks.count()!==8)throw Error('Expected exactly eight pages/slides');
  for(let i=0;i<8;i++){
   const block=blocks.nth(i);
   const check=await block.evaluate(el=>{
    const b=el.getBoundingClientRect(), footer=el.querySelector('footer').getBoundingClientRect();
    const bad=[...el.querySelectorAll('h1,h2,h3,p,.shot,.grid,.step,.stack,.callout')].filter(n=>{
     const r=n.getBoundingClientRect();return r.bottom>footer.top-6||r.right>b.right-30||r.left<b.left;
    }).map(n=>({tag:n.tagName,text:n.textContent.slice(0,70)}));
    return {clipped:bad};
   });
   checks.push({file,index:i+1,...check});
   if(selector==='.slide') await block.screenshot({path:fileURLToPath(new URL(`carousel/png/slide-${String(i+1).padStart(2,'0')}.png`,root))});
  }
  await page.pdf({path:fileURLToPath(new URL(dest,root)),printBackground:true,preferCSSPageSize:true,displayHeaderFooter:false});
 }
 await page.setViewportSize({width:1800,height:1388});
 const svg=await readFile(new URL('architecture/documind-architecture.svg',root),'utf8');
 await page.setContent('<style>html,body{margin:0}svg{display:block}</style>'+svg);
 await page.evaluate(()=>document.fonts.ready);
 const clippedLabels=await page.locator('.architecture-node').evaluateAll(nodes=>nodes.flatMap(node=>{
   const rect=node.querySelector('rect').getBBox();
   return [...node.querySelectorAll('text')].filter(text=>{const b=text.getBBox();return b.x<rect.x||b.x+b.width>rect.x+rect.width-6||b.y+b.height>rect.y+rect.height;}).map(text=>text.textContent);
 }));
 if(clippedLabels.length) throw Error('Architecture node labels overflow: '+clippedLabels.join(';'));
 await page.screenshot({path:fileURLToPath(new URL('architecture/documind-architecture.png',root)),scale:'css'});
 await writeFile(new URL('verification/layout-checks.json',root),JSON.stringify(checks,null,2));
 const clipped=checks.filter(c=>c.clipped.length);
 console.log('Rendered 8-page case study, 8 slides, carousel PDF and architecture PNG.');
 if(clipped.length){console.error(JSON.stringify(clipped));process.exitCode=1;}
}finally{await browser.close();}
