const T = 24, WORLD_W = 48 * T, WORLD_H = 34 * T;
const clamp = (n, a, b) => Math.min(b, Math.max(a, n));
const rand = (seed) => { let n = seed; return () => { n = (n * 1664525 + 1013904223) >>> 0; return n / 4294967296; }; };
const rgba = (hex, alpha) => { if (!/^#[a-f\d]{6}$/i.test(hex || '')) return `rgba(64,80,50,${alpha})`; return `rgba(${parseInt(hex.slice(1,3),16)},${parseInt(hex.slice(3,5),16)},${parseInt(hex.slice(5,7),16)},${alpha})`; };
export function drawPerson(ctx, v, x, y, scale = 1, phase = 0, moving = false, facing = 1) {
  ctx.save(); ctx.translate(Math.round(x), Math.round(y)); ctx.scale(scale, scale);
  const skin = v.skin || '#d5a279', hair = v.hair || '#493e35', shirt = v.color || '#da8668';
  const leg = moving ? Math.round(Math.sin(phase) * 2) : 0;
  ctx.fillStyle = '#32533d33'; ctx.fillRect(-6, 1, 13, 3);
  ctx.fillStyle = '#354c45'; ctx.fillRect(-4, -3, 3, 5 + leg); ctx.fillRect(2, -3, 3, 5 - leg);
  ctx.fillStyle = '#344a3b'; ctx.fillRect(-5, 2 + leg, 4, 2); ctx.fillRect(2, 2 - leg, 4, 2);
  ctx.fillStyle = shirt; ctx.fillRect(-5, -11, 11, 9); ctx.fillRect(-7, -10, 2, 6); ctx.fillRect(6, -10, 2, 6);
  ctx.fillStyle = '#ffffff35'; ctx.fillRect(-3, -10, 2, 7); ctx.fillStyle = '#182d3228'; ctx.fillRect(3, -10, 3, 8);
  ctx.fillStyle = skin; ctx.fillRect(-7, -5, 2, 3); ctx.fillRect(6, -5, 2, 3); if (/fight|brawl|attack/.test(v.action||'') && Math.sin(phase)>.2) { ctx.fillStyle=shirt;ctx.fillRect(facing<0?-12:6,-10,7,3);ctx.fillStyle=skin;ctx.fillRect(facing<0?-15:12,-10,3,3); } ctx.fillStyle=skin;ctx.fillRect(-4, -20, 9, 9); ctx.fillRect(-5, -17, 11, 5);
  ctx.fillStyle = hair; ctx.fillRect(-4, -22, 9, 4); ctx.fillRect(-6, -20, 3, 7); ctx.fillRect(4, -20, 2, 5); ctx.fillRect(-3, -22, 7, 2);
  ctx.fillStyle = '#223c32'; ctx.fillRect(facing < 0 ? -3 : -1, -16, 1, 2); ctx.fillRect(facing < 0 ? 1 : 3, -16, 1, 2);
  ctx.fillStyle = '#c37c6b'; ctx.fillRect(0, -12, 2, 1);
  if (/farmer|gardener|miller/i.test(v.occupation || '')) { ctx.fillStyle='#d5bf75';ctx.fillRect(-7,-22,15,3);ctx.fillRect(-3,-26,8,4);ctx.fillStyle='#ae9160';ctx.fillRect(-3,-23,8,1); }
  if (/baker|doctor|nurse|healer/i.test(v.occupation || '')) { ctx.fillStyle='#f2ebd9';ctx.fillRect(-5,-24,11,4);ctx.fillRect(-3,-26,7,3); }
  ctx.restore();
}

export class VillageScene {
  constructor(canvas, onSelect) {
    this.canvas = canvas; this.ctx = canvas.getContext('2d'); this.onSelect = onSelect;
    this.state = null; this.selected = null; this.follow = false; this.labels = true; this.zoom = 1;
    this.camera = { x: WORLD_W / 2, y: WORLD_H / 2 }; this.people = new Map(); this.hits = [];
    this.base = document.createElement('canvas'); this.base.width = WORLD_W; this.base.height = WORLD_H;
    this.baseCtx = this.base.getContext('2d'); this.lastTime = performance.now(); this.reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.resizeObserver = new ResizeObserver(() => this.resize()); this.resizeObserver.observe(canvas.parentElement);
    this.bind(); this.resize(); requestAnimationFrame((t) => this.frame(t));
  }
  bind() {
    let drag = null;
    this.canvas.addEventListener('pointerdown', e => { this.canvas.setPointerCapture(e.pointerId); drag = { x: e.clientX, y: e.clientY, startX: e.clientX, startY: e.clientY, moved: false }; });
    this.canvas.addEventListener('pointermove', e => {
      if (drag) { const dx=e.clientX-drag.x, dy=e.clientY-drag.y; if(Math.hypot(e.clientX-drag.startX,e.clientY-drag.startY)>4) drag.moved=true; if(drag.moved){this.camera.x-=dx/this.scale;this.camera.y-=dy/this.scale;this.follow=false;this.boundCamera();this.onFollowChange?.(false);} drag.x=e.clientX;drag.y=e.clientY;return; }
      const r=this.canvas.getBoundingClientRect(), hit=this.hitAt(e.clientX-r.left,e.clientY-r.top); this.canvas.style.cursor=hit?'pointer':'grab';
      const tip=document.getElementById('map-tooltip'); if(hit){const v=this.state?.villagers.find(v=>v.id===hit.id);if(v){tip.textContent=`${v.name} · ${v.action_label||v.action||'Taking in the day'}`;tip.hidden=false;tip.style.left=`${clamp(e.clientX-r.left+13,5,r.width-225)}px`;tip.style.top=`${clamp(e.clientY-r.top+15,5,r.height-38)}px`;}}else tip.hidden=true;
    });
    this.canvas.addEventListener('pointerup', e => { if(!drag)return;if(!drag.moved){const r=this.canvas.getBoundingClientRect(),hit=this.hitAt(e.clientX-r.left,e.clientY-r.top);if(hit)this.onSelect(hit.id);}drag=null; });
    this.canvas.addEventListener('pointercancel',()=>drag=null);
    this.canvas.addEventListener('pointerleave',()=>document.getElementById('map-tooltip').hidden=true);
    this.canvas.addEventListener('wheel',e=>{e.preventDefault();const r=this.canvas.getBoundingClientRect();this.changeZoom(e.deltaY<0?1.14:1/1.14,e.clientX-r.left,e.clientY-r.top);},{passive:false});
  }
  resize() { const r=this.canvas.parentElement.getBoundingClientRect();this.w=r.width;this.h=r.height;const dpr=Math.min(devicePixelRatio||1,2);this.canvas.width=Math.round(r.width*dpr);this.canvas.height=Math.round(r.height*dpr);this.dpr=dpr;this.ctx.imageSmoothingEnabled=false;this.fitScale=Math.min((this.w-28)/WORLD_W,(this.h-42)/WORLD_H);this.scale=this.fitScale*this.zoom; }
  fit(){this.zoom=1;this.scale=this.fitScale;this.camera={x:WORLD_W/2,y:WORLD_H/2};this.follow=false;this.onFollowChange?.(false);}
  changeZoom(factor,sx=this.w/2,sy=this.h/2){const old=this.scale;this.zoom=clamp(this.zoom*factor,.7,4.7);this.scale=this.fitScale*this.zoom;this.camera.x+=(sx-this.w/2)/old-(sx-this.w/2)/this.scale;this.camera.y+=(sy-this.h/2)/old-(sy-this.h/2)/this.scale;this.boundCamera();}
  boundCamera(){this.camera.x=clamp(this.camera.x,-100,WORLD_W+100);this.camera.y=clamp(this.camera.y,-100,WORLD_H+100);}
  centerOn(id, zoom=false){const v=this.state?.villagers.find(v=>v.id===id);if(!v)return;this.camera={x:v.x*T,y:v.y*T};if(zoom){this.zoom=Math.max(this.zoom,1.8);this.scale=this.fitScale*this.zoom;}}
  select(id){this.selected=id;}
  setState(state){
    const now=performance.now();
    for(const v of state.villagers){const p=this.people.get(v.id); if(p){const current=this.position(p,now);p.x=current.x;p.y=current.y;p.tx=v.x*T;p.ty=v.y*T;p.t=now;p.moving=Math.hypot(p.x-p.tx,p.y-p.ty)>1;p.facing=p.tx<p.x?-1:1;}else this.people.set(v.id,{x:v.x*T,y:v.y*T,tx:v.x*T,ty:v.y*T,t:now,moving:false,facing:1});}
    const newMapKey=JSON.stringify([state.seed,state.locations]);this.state=state;
    if(newMapKey!==this.mapKey){this.mapKey=newMapKey;this.buildMap();}
  }
  position(p,t){const f=clamp((t-p.t)/900,0,1);return{x:p.x+(p.tx-p.x)*f,y:p.y+(p.ty-p.y)*f};}
  hitAt(x,y){return [...this.hits].reverse().find(p=>p.rect?(x>=p.x&&x<=p.x+p.w&&y>=p.y&&y<=p.y+p.h):Math.hypot(p.x-x,p.y-y)<Math.max(p.radius,13));}
  tree(c,x,y,size=1,variant=0){c.save();c.translate(Math.round(x),Math.round(y));c.scale(size,size);c.fillStyle='#56774533';c.fillRect(-13,2,30,8);c.fillStyle='#7c6950';c.fillRect(-3,-2,7,9);c.fillStyle='#456745';c.fillRect(-13,-22,26,21);c.fillRect(-9,-31,18,12);c.fillRect(-17,-17,34,11);c.fillStyle=variant?'#62834e':'#557847';c.fillRect(-12,-23,25,16);c.fillRect(-8,-30,18,11);c.fillRect(-15,-17,29,10);c.fillStyle=variant?'#7c985b':'#718e50';c.fillRect(-8,-27,12,5);c.fillRect(-12,-17,9,4);c.fillRect(4,-20,6,4);c.fillStyle='#3c6444';c.fillRect(6,-10,9,5);c.fillRect(-8,-5,14,4);c.restore();}
  buildMap(){
    const c=this.baseCtx,rng=rand((this.state.seed||42)+73);c.imageSmoothingEnabled=false;c.fillStyle='#a7bd7e';c.fillRect(0,0,WORLD_W,WORLD_H);
    for(let y=0;y<34;y++)for(let x=0;x<48;x++){c.fillStyle=(x+y)%2?'#a7bd7e':'#a5bc7c';c.fillRect(x*T,y*T,T,T);}
    for(let i=0;i<2400;i++){const x=Math.floor(rng()*WORLD_W/2)*2,y=Math.floor(rng()*WORLD_H/2)*2;c.fillStyle=['#9bb171','#b3c789','#97ae70','#bdcb90'][i%4];c.fillRect(x,y,2+(i%3)*2,2);if(i%4===0)c.fillRect(x+2,y-3,2,3);}
    const locations=this.state.locations||[];
    // Dusty lanes, stone edges, and well-worn shortcuts connect every doorstep.
    c.lineCap='square';c.strokeStyle='#90a96b';c.lineWidth=34;c.beginPath();for(const y of [9.3,19.5,27.6,32.8]){c.moveTo(1*T,y*T);c.lineTo(43.8*T,y*T);}for(const x of [1.6,12.2,23.3,41.7]){c.moveTo(x*T,9.3*T);c.lineTo(x*T,32.8*T);}c.stroke();
    c.strokeStyle='#d4c48b';c.lineWidth=29;c.stroke();c.strokeStyle='#dece99';c.lineWidth=22;c.stroke();
    for(const l of locations){if(['water','park','square','forest'].includes(l.type))continue;const ex=(l.entrance?.x??l.x+l.w/2)*T,ey=(l.entrance?.y??l.y+l.h)*T;const road=[9.3,19.5,27.6,32.8].reduce((a,b)=>Math.abs(a-ey/T)<Math.abs(b-ey/T)?a:b);c.fillStyle='#d4c48b';c.fillRect(ex-9,Math.min(ey,road*T),18,Math.abs(ey-road*T)+10);c.fillStyle='#dece99';c.fillRect(ex-6,Math.min(ey,road*T),12,Math.abs(ey-road*T)+10);}
    for(let i=0;i<480;i++){const x=rng()*43*T,y=rng()*34*T;if([9.3,19.5,27.6,32.8].some(k=>Math.abs(y-k*T)<11)||[1.6,12.2,23.3,41.7].some(k=>Math.abs(x-k*T)<11&&y>9.3*T)){c.fillStyle=i%2?'#c6b982':'#ebdca8';c.fillRect(Math.round(x/2)*2,Math.round(y/2)*2,4,2);}}
    for(const l of locations.filter(l=>l.type==='water'))this.water(c,l);
    if(!locations.some(l=>l.type==='water'&&l.h>20))this.water(c,{x:44,y:0,w:4,h:34});
    // A tiny timber bridge and boardwalk.
    c.fillStyle='#6e795f';c.fillRect(43.3*T,19.5*T-20,4.7*T,44);c.fillStyle='#bba477';c.fillRect(43.3*T,19.5*T-17,4.7*T,35);for(let y=19.5*T-16;y<19.5*T+18;y+=6){c.fillStyle='#917b58';c.fillRect(43.3*T,y,4.7*T,1);}c.fillStyle='#715f49';c.fillRect(43*T,19.5*T-22,5*T,5);c.fillRect(43*T,19.5*T+19,5*T,5);for(const x of [43.2,45.3,47.6]){c.fillRect(x*T,19.5*T-26,4,13);c.fillRect(x*T,19.5*T+14,4,13);}
    for(const l of locations.filter(l=>l.type!=='water'))this.building(c,l,rng);
    const blocked=(x,y)=>locations.some(l=>x>l.x-1&&x<l.x+l.w+1&&y>l.y-1.5&&y<l.y+l.h+1)||[9.3,19.5,27.6,32.8].some(k=>Math.abs(y-k)<1.4)||[1.6,12.2,23.3,41.7].some(k=>Math.abs(x-k)<1&&y>8);
    for(let i=0;i<230;i++){const x=rng()*43.5,y=rng()*34;if(blocked(x,y))continue;if(y<2.1||x<1||x>42.8||rng()<.3)this.tree(c,x*T,y*T, .7+rng()*.6,i%3===0);}
    // A few hand-placed planting beds and flowers give the clearing a lived-in edge.
    for(let i=0;i<140;i++){let x=rng()*43,y=rng()*34;if(blocked(x,y))continue;c.fillStyle=['#d4af68','#e1d29a','#c68d7b','#a4b997'][i%4];c.fillRect(Math.round(x*T),Math.round(y*T),3,3);c.fillStyle='#6d9959';c.fillRect(Math.round(x*T)+1,Math.round(y*T)+3,1,3);}
    for(const [x,y] of [[10.9,18.4],[24.8,19],[32.9,19],[2.9,10.3]]){this.lamp(c,x*T,y*T);}
    // Central gathering well and the village notice board.
    const wx=22*T,wy=18.4*T;c.fillStyle='#78906844';c.fillRect(wx-14,wy-3,33,14);c.fillStyle='#a6aaa0';c.fillRect(wx-11,wy-4,25,13);c.fillStyle='#ced0b7';c.fillRect(wx-13,wy-8,28,7);c.fillStyle='#547e79';c.fillRect(wx-7,wy-8,15,4);c.fillStyle='#6e6550';c.fillRect(wx-13,wy-21,3,16);c.fillRect(wx+12,wy-21,3,16);c.fillStyle='#b97d59';c.fillRect(wx-16,wy-27,34,7);c.fillRect(wx-12,wy-31,26,4);
    c.fillStyle='#8c7757';c.fillRect(24.3*T,18*T,3,21);c.fillRect(25.1*T,18*T,3,21);c.fillStyle='#655f49';c.fillRect(24*T,17.6*T,32,20);c.fillStyle='#dacf9f';c.fillRect(24*T+3,17.6*T+3,26,14);c.fillStyle='#a68c66';c.fillRect(24*T+6,17.6*T+6,8,2);c.fillRect(24*T+6,17.6*T+10,16,2);
  }
  water(c,l){const x=l.x*T,y=l.y*T,w=l.w*T,h=l.h*T;c.fillStyle='#809e72';c.fillRect(x-5,y-5,w+10,h+10);c.fillStyle='#c0c595';c.fillRect(x-3,y-3,w+6,h+6);c.fillStyle='#83b5af';c.fillRect(x,y,w,h);c.fillStyle='#94c2b7';for(let yy=y+7;yy<y+h;yy+=15){for(let xx=x+3+(Math.round(yy)%3)*5;xx<x+w-5;xx+=24)c.fillRect(xx,yy,13,2);}if(h<7*T){c.fillStyle='#67946a';c.fillRect(x+w-15,y+15,8,5);c.fillRect(x+10,y+h-14,8,5);c.fillStyle='#d6c487';c.fillRect(x+12,y+h-15,2,2);}}
  lamp(c,x,y){c.fillStyle='#72725a';c.fillRect(x,y-18,3,20);c.fillStyle='#576551';c.fillRect(x-4,y-24,11,8);c.fillStyle='#ecd595';c.fillRect(x-2,y-23,7,5);c.fillStyle='#77735a';c.fillRect(x-5,y-26,13,2);}
  building(c,l,rng){
    const x=l.x*T,y=l.y*T,w=l.w*T,h=l.h*T;const type=(l.type||'').toLowerCase();
    if(['park','square','forest','plaza'].includes(type)){c.fillStyle='#aec58a';c.fillRect(x,y,w,h);for(let i=0;i<5;i++)this.tree(c,x+12+rng()*(w-24),y+10+rng()*(h-20),.8);return;}
    if(type==='farm'||l.id==='farm'){
      c.fillStyle='#a38b5d';c.fillRect(x,y+8,w,h-13);c.fillStyle='#8d7753';for(let k=0;k<6;k++)c.fillRect(x+5,y+14+k*(h-24)/6,w-10,3);for(let k=0;k<6;k++)for(let q=0;q<12;q++){const px=x+7+q*(w-13)/12,py=y+11+k*(h-24)/6;c.fillStyle=k<3?'#7b9650':'#b69f56';c.fillRect(px,py,5,9);c.fillStyle=k<3?'#a7b767':'#ded27c';c.fillRect(px-2,py+2,9,4);c.fillRect(px+1,py-2,3,10);}
      c.fillStyle='#d5bc86';for(let q=0;q<=w;q+=17){c.fillRect(x+q,y+h-5,3,10);c.fillRect(x+q,y-1,3,10);}c.fillRect(x,y+h-2,w,2);c.fillRect(x,y+3,w,2);this.locationLabel(c,l,x+w/2,y+h+12);return;
    }
    c.fillStyle='#5e73504d';c.fillRect(x+6,y+8,w,h);
    if(type==='market'||l.id==='market'){
      c.fillStyle='#d5c994';c.fillRect(x,y,w,h);for(let k=0;k<3;k++){const bx=x+8+k*(w-12)/3,by=y+12;c.fillStyle='#8f7853';c.fillRect(bx,by+24,33,45);c.fillStyle='#bba579';c.fillRect(bx-2,by+35,37,23);c.fillStyle=k===1?'#92a68c':'#bd8666';c.fillRect(bx-5,by,43,27);for(let z=0;z<5;z++){c.fillStyle=z%2===0?'#ece2b5':k===1?'#7c9d85':'#c48d70';c.fillRect(bx-5+z*8,by,8,25);c.fillRect(bx-5+z*8,by+25,8,5-(z%2)*2);}for(let z=0;z<4;z++){c.fillStyle=['#bd8056','#8d9e58','#d9b467'][k];c.fillRect(bx+z*7,by+39,5,5);}c.fillStyle='#6f7150';c.fillRect(bx,by+61,3,10);c.fillRect(bx+29,by+61,3,10);}this.locationLabel(c,l,x+w/2,y+h-2);return;
    }
    const home=/home|house|cottage|residence/.test(type)||/home|house/.test(l.id);let roof=l.color||['#bf8165','#9aaa83','#d1ad77'][Math.floor(rng()*3)];
    if(!/^#[a-f\d]{6}$/i.test(roof))roof='#b68166';
    const roofH=Math.min(h*.43,45), wallY=y+roofH;
    c.fillStyle='#697760';c.fillRect(x-2,wallY-2,w+4,h-roofH+4);c.fillStyle=home?'#e1d3a6':'#e5d6ac';c.fillRect(x,wallY,w,h-roofH);
    c.fillStyle='#c4b48b';c.fillRect(x,wallY+4,6,h-roofH-4);c.fillRect(x+w-7,wallY+4,7,h-roofH-4);c.fillRect(x,y+h-8,w,8);
    c.fillStyle='#f1e3b8';c.fillRect(x+7,wallY+5,w-14,3);
    c.fillStyle='#795e48';c.fillRect(x-5,wallY-3,w+10,8);c.fillStyle=roof;c.beginPath();c.moveTo(x-5,wallY);c.lineTo(x+12,y+2);c.lineTo(x+w-12,y+2);c.lineTo(x+w+5,wallY);c.closePath();c.fill();
    c.fillStyle='#fff4b929';for(let yy=y+9;yy<wallY-2;yy+=8){const inset=12*(1-(yy-y)/roofH);c.fillRect(x+inset,yy,w-inset*2,2);for(let xx=x+inset+12;xx<x+w-inset;xx+=18)c.fillRect(xx+(Math.round(yy)%2)*7,yy-5,1,6);}
    c.fillStyle='#7b5f4840';c.fillRect(x-3,wallY-1,w+6,3);c.fillStyle='#b6a07b';c.fillRect(x+w-22,y-7,10,19);c.fillStyle='#8d7a60';c.fillRect(x+w-24,y-8,14,4);
    const doorX=(l.entrance?.x??l.x+l.w/2)*T; c.fillStyle='#c3b58c';c.fillRect(doorX-11,y+h-29,22,32);c.fillStyle='#6d765d';c.fillRect(doorX-8,y+h-28,16,28);c.fillStyle='#829074';c.fillRect(doorX-6,y+h-26,12,25);c.fillStyle='#cabc88';c.fillRect(doorX+3,y+h-15,2,2);c.fillStyle='#ded2a7';c.fillRect(doorX-11,y+h+1,22,4);
    const windowY=wallY+Math.max(7,(h-roofH-30)/2);for(const wx of [x+17,x+w-34]){c.fillStyle='#b0a67f';c.fillRect(wx-3,windowY-3,22,22);c.fillStyle='#5d8b85';c.fillRect(wx,windowY,16,15);c.fillStyle='#b8d0b6';c.fillRect(wx+2,windowY+2,5,6);c.fillStyle='#e3d5a5';c.fillRect(wx+7,windowY,2,16);c.fillRect(wx,windowY+7,16,2);c.fillStyle='#8c7c59';c.fillRect(wx-4,windowY+16,24,4);if(home){c.fillStyle='#6e925c';c.fillRect(wx-2,windowY+14,21,5);c.fillStyle='#d09a78';c.fillRect(wx+2,windowY+13,3,3);c.fillRect(wx+11,windowY+12,3,4);}}
    if(/clinic|doctor/.test(type+l.id)){c.fillStyle='#f1ebd3';c.fillRect(x+w/2-11,y+10,22,20);c.fillStyle='#b57563';c.fillRect(x+w/2-2,y+13,5,14);c.fillRect(x+w/2-7,y+18,15,5);}
    if(/town|hall/.test(type+l.id)){c.fillStyle='#eee5c6';c.fillRect(x+w/2-10,y+9,20,20);c.fillStyle='#7a856e';c.fillRect(x+w/2-1,y+13,2,9);c.fillRect(x+w/2-1,y+20,7,2);}
    if(/tavern|inn/.test(type+l.id)){c.fillStyle='#715e43';c.fillRect(x+w-7,wallY+5,21,3);c.fillRect(x+w+10,wallY+8,2,7);c.fillStyle='#b39d6d';c.fillRect(x+w+1,wallY+14,20,19);c.fillStyle='#f1da9c';c.fillRect(x+w+7,wallY+18,7,11);}
    this.locationLabel(c,l,x+w/2,y+h+13);
  }
  locationLabel(c,l,x,y){const text=(l.name||'').toUpperCase();if(!text)return;c.font='bold 8px monospace';const w=c.measureText(text).width+12;c.fillStyle='#f1efccde';c.fillRect(Math.round(x-w/2),y-9,w,14);c.fillStyle='#708060';c.textAlign='center';c.fillText(text,Math.round(x),y+1);c.textAlign='left';}
  drawMonster(c,time){const ctxs=this.state?.contexts||[];if(!ctxs.some(k=>/godzilla|giant|creature|monster|kaiju/i.test(k.text||'')&&k.kind==='threat'))return;c.save();c.translate(44*T,11*T+Math.sin(time/450)*2);c.scale(2.1,2.1);c.fillStyle='#344f44';c.fillRect(-13,-38,22,40);c.fillRect(-10,-55,19,20);c.fillRect(3,-47,15,10);c.fillRect(-18,-17,9,22);c.fillRect(6,-18,9,22);c.fillRect(-24,-24,13,7);c.fillRect(-29,-19,9,6);c.fillRect(8,-30,14,6);c.fillStyle='#668069';for(let i=0;i<5;i++){c.fillRect(-17,-46+i*9,6,6);c.fillRect(-20,-42+i*9,3,4);}c.fillStyle='#a3ab7c';c.fillRect(-5,-31,11,25);c.fillStyle='#e7a25f';c.fillRect(6,-47,3,3);c.fillStyle='#eadab1';c.fillRect(14,-37,3,3);c.restore();}
  frame(time){
    requestAnimationFrame(t=>this.frame(t));const c=this.ctx;if(!this.w)return;const dt=Math.min((time-this.lastTime)/16,3);this.lastTime=time;c.setTransform(this.dpr,0,0,this.dpr,0,0);c.clearRect(0,0,this.w,this.h);c.fillStyle='#7d9968';c.fillRect(0,0,this.w,this.h);
    if(this.follow&&this.selected){const p=this.people.get(this.selected);if(p){const pos=this.position(p,time);this.camera.x+=(pos.x-this.camera.x)*.09*dt;this.camera.y+=(pos.y-this.camera.y)*.09*dt;}}
    const ox=this.w/2-this.camera.x*this.scale,oy=this.h/2-this.camera.y*this.scale;c.save();c.translate(Math.round(ox),Math.round(oy));c.scale(this.scale,this.scale);c.imageSmoothingEnabled=false;
    c.fillStyle='#6f885c';c.fillRect(-5,-5,WORLD_W+10,WORLD_H+10);if(this.state)c.drawImage(this.base,0,0);else{c.fillStyle='#a7bd7e';c.fillRect(0,0,WORLD_W,WORLD_H);c.fillStyle='#456a44';c.font='14px monospace';c.textAlign='center';c.fillText('THE CLEARING IS WAKING UP…',WORLD_W/2,WORLD_H/2);c.textAlign='left';}
    this.hits=[];if(this.state){
      // Moving water is subtle enough to keep the pixel landscape calm.
      c.fillStyle='#d0e2c444';for(let i=0;i<28;i++){const x=44*T+((i*23+time/120)%80),y=((i*59+time/250)%WORLD_H);c.fillRect(Math.round(x),Math.round(y),9,2);}
      this.drawMonster(c,time);
      const drawList=this.state.villagers.map(v=>({v,p:this.people.get(v.id)})).filter(o=>o.p).map(o=>({...o,pos:this.position(o.p,time)})).sort((a,b)=>a.pos.y-b.pos.y);
      for(const {v,p,pos} of drawList){
        const partner=this.people.get(v.target_id);if(partner&&/talk|gossip|flirt|argue|fight|marry|comfort|kiss|debate|negotiate/.test(v.action||'')){const q=this.position(partner,time);if(Math.hypot(q.x-pos.x,q.y-pos.y)<T*5){c.save();c.strokeStyle=/fight|argue/.test(v.action)?'#b85e4760':'#f4edd680';c.lineWidth=1.5;c.setLineDash([3,4]);c.beginPath();c.moveTo(pos.x,pos.y-6);c.lineTo(q.x,q.y-6);c.stroke();c.restore();}}
        if(v.id===this.selected){c.strokeStyle='#f9f7da';c.lineWidth=2;c.strokeRect(Math.round(pos.x)-10,Math.round(pos.y)-1,21,9);c.fillStyle='#fff8d9';const bob=this.reduceMotion?0:Math.sin(time/300)*2;c.beginPath();c.moveTo(pos.x-4,pos.y-34+bob);c.lineTo(pos.x+4,pos.y-34+bob);c.lineTo(pos.x,pos.y-29+bob);c.fill();}
        const moving=p.moving&&time-p.t<930;drawPerson(c,v,pos.x,pos.y,1.07,this.reduceMotion?0:time/90,moving&&!this.reduceMotion,p.facing);
        let effect='';if(/flirt|kiss|marry|romance|intimacy|date|love/.test(v.action||''))effect='♥';if(/fight|brawl|attack|argue|revolt/.test(v.action||''))effect='!';if(/think|reflect|plan|worry/.test(v.action||''))effect='···';if(/sleep|rest/.test(v.action||''))effect='z';
        if(effect){c.font=effect==='♥'?'13px serif':'bold 12px monospace';c.textAlign='center';c.fillStyle=effect==='♥'?'#be7384':effect==='!'?'#b45b3a':'#f5f0d1';c.fillText(effect,pos.x+11,pos.y-25-(this.reduceMotion?0:Math.sin(time/350)*2));c.textAlign='left';}
        this.hits.push({id:v.id,x:pos.x*this.scale+ox,y:(pos.y-10)*this.scale+oy,radius:13*this.scale});
      }
      // Names are screen-sized to stay legible at every zoom level.
      c.restore();c.save();c.setTransform(this.dpr,0,0,this.dpr,0,0);
      for(const {v,pos} of drawList){const sx=pos.x*this.scale+ox,sy=pos.y*this.scale+oy;if(sx<-40||sx>this.w+40||sy<-40||sy>this.h+40)continue;
        if(this.labels||v.id===this.selected){const name=v.name.split(' ')[0];c.font=`${v.id===this.selected?'600':'500'} ${this.zoom>1.5?10:8}px 'DM Sans', sans-serif`;const tw=c.measureText(name).width+8;c.fillStyle=v.id===this.selected?'#294c3cf0':'#f6f2d9d9';c.fillRect(Math.round(sx-tw/2),Math.round(sy+6*this.scale),tw,13);c.fillStyle=v.id===this.selected?'#f5f2d7':'#546745';c.textAlign='center';c.fillText(name,Math.round(sx),Math.round(sy+6*this.scale+9));}
        const idx=this.state.villagers.findIndex(k=>k.id===v.id);const canSpeak=v.speech&&(v.id===this.selected||this.zoom>1.3||idx%6===Math.floor(time/6500)%6);if(canSpeak){let message=String(v.speech).replace(/^['“"]|['”"]$/g,'');const max=v.id===this.selected?42:23;if(message.length>max)message=message.slice(0,max-1)+'…';c.font='9px "DM Sans", sans-serif';let bw=c.measureText(message).width+15;const bx=clamp(sx-bw/2,8,this.w-bw-8),by=sy-30*this.scale-20;c.fillStyle='#fffbee';c.strokeStyle='#a5b48c';c.lineWidth=1;c.beginPath();c.roundRect(bx,by,bw,21,4);c.fill();c.stroke();c.beginPath();c.moveTo(sx-3,by+20);c.lineTo(sx+1,by+25);c.lineTo(sx+5,by+20);c.fill();c.fillStyle='#58664c';c.textAlign='center';c.fillText(message,bx+bw/2,by+14);this.hits.push({id:v.id,rect:true,x:bx,y:by,w:bw,h:24});}
      }c.textAlign='left';
      const minute=this.state.minute??480;let darkness=0;if(minute<360)darkness=.30;else if(minute<420)darkness=.14;else if(minute>1200)darkness=.29;else if(minute>1080)darkness=.13;if(darkness){c.fillStyle=`rgba(29,47,81,${darkness})`;c.fillRect(0,0,this.w,this.h);}
      const weather=String(this.state.weather||'').toLowerCase();if(/rain|storm/.test(weather)){c.fillStyle='#344d6220';c.fillRect(0,0,this.w,this.h);c.strokeStyle='#ebf2df55';c.lineWidth=1;c.beginPath();for(let i=0;i<95;i++){const rx=(i*79+time/12)%this.w,ry=(i*53+time/3)%this.h;c.moveTo(rx,ry);c.lineTo(rx-3,ry+9);}c.stroke();}if(/snow/.test(weather)){c.fillStyle='#fffdf2c9';for(let i=0;i<60;i++)c.fillRect((i*71+time/65)%this.w,(i*47+time/35)%this.h,2,2);}
    }c.restore();
  }
}
