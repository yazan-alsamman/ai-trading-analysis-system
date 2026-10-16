// WCAG contrast check for the palette in src/styles/tokens.css (keep values in sync). Run: node scripts/contrast.mjs
const hex = (h) => { h = h.replace('#',''); return [0,2,4].map(i => parseInt(h.slice(i,i+2),16)); };
const lum = ([r,g,b]) => { const f = c => { c/=255; return c<=0.03928 ? c/12.92 : ((c+0.055)/1.055)**2.4; }; return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b); };
const mix = (fg, bg, a) => fg.map((c,i)=>Math.round(c*a+bg[i]*(1-a)));
const ratio = (a,b) => { const [x,y]=[lum(a),lum(b)].sort((p,q)=>q-p); return (x+0.05)/(y+0.05); };
const themes = {
  dark: { canvas:'#07070a', surface:'#0d0d12', raised:'#13131a', inset:'#0a0a0e', hover:'#17171f', selected:'#1c1b26',
    fg:'#f2f1f6', fg2:'#b0afbf', fg3:'#8f8ea0', accent:'#e2bd72', up:'#2fc68f', down:'#ff6f77', forecast:'#b9a0ff', danger:'#ff8a4c', warning:'#f2a541', info:'#6cbcff', demo:'#6cbcff', softA:0.13 },
  light: { canvas:'#f4f3ef', surface:'#ffffff', raised:'#ffffff', inset:'#f8f7f4', hover:'#efeee9', selected:'#f2ede1',
    fg:'#141318', fg2:'#4a4853', fg3:'#5e5c67', accent:'#7c540d', up:'#066b47', down:'#b3262f', forecast:'#6534c8', danger:'#a33c0b', warning:'#7f4700', info:'#0b5a96', demo:'#0b5a96', softA:0.1 },
};
let worst = 99;
for (const [name,t] of Object.entries(themes)) {
  const bgs = ['canvas','surface','raised','inset','hover','selected'];
  const texts = ['fg','fg2','fg3','accent','up','down','forecast','danger','warning','info'];
  const rows = [];
  for (const tx of texts) {
    const r = bgs.map(b => ratio(hex(t[tx]), hex(t[b])));
    // soft badge: tone text on tone-soft over surface
    const soft = ratio(hex(t[tx]), mix(hex(t[tx]), hex(t.surface), t.softA));
    const softSel = ratio(hex(t[tx]), mix(hex(t[tx]), hex(t.selected), t.softA));
    const min = Math.min(...r, soft, softSel); worst = Math.min(worst, min);
    rows.push(`${tx.padEnd(9)} ${r.map(x=>x.toFixed(2)).join(' ')} | soft ${soft.toFixed(2)} softSel ${softSel.toFixed(2)} ${min<4.5?'  <-- FAIL':''}`);
  }
  console.log(`\n${name}: ${bgs.join(' ')}\n` + rows.join('\n'));
  console.log('primary button (canvas on fg):', ratio(hex(t.canvas), hex(t.fg)).toFixed(2), ' accent-fg on accent:', ratio(hex(name==='dark'?'#17110a':'#ffffff'), hex(t.accent)).toFixed(2));
}
console.log('\nworst', worst.toFixed(2));
