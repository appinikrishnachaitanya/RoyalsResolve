// Verify the production server's public surface, without a browser.
import assert from 'node:assert/strict';
const base=process.argv[2]||'http://127.0.0.1:4174';
const home=await fetch(base);assert.equal(home.status,200);assert.match(await home.text(),/Royals/);
const response=await fetch(base+'/results/analysis.json');assert.equal(response.status,200);const d=await response.json();
assert.equal(d.batters.length,10);assert.equal(d.bowlers.length,10);
const pdf=await fetch(base+'/results/methodology.pdf');assert.equal(pdf.status,200);assert.equal(pdf.headers.get('content-type'),'application/pdf');assert.equal((await pdf.text()).slice(0,4),'%PDF');
for(const route of ['/data/incoming/pack.zip','/artifacts/private/audit.json','/results/../../README.md','/%2e%2e%2fREADME.md','/missing.js']){
 assert.equal((await fetch(base+route)).status,404,route);
}
assert.equal((await fetch(base,{method:'POST'})).status,405);
assert.equal((await fetch(base,{method:'HEAD'})).status,200);
console.log('Static HTTP checks passed; analysis '+d.analysis_id+'. Private paths return 404.');
