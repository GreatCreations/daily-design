/* Daily Design: 3D "DD" logo, scrubbed by scroll.
   Progress p = scroll / (scroll at which the search bar sticks), 0..1. The logo's place on a swirling path
   from the hero spot to the dock beside the sticky search bar, its turn, scale, light sweep and trails are all
   functions of the (lightly smoothed) scroll position. Nothing moves unless the page scrolls. Decorative only. */
(function(){
"use strict";
var spot=document.getElementById("logo-spot"),dock=document.getElementById("logo-dock"),bar=document.querySelector(".searchbox");
if(!spot||!dock||!bar)return;
var RM=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
var COLORS=["#f5a524","#22e0cf","#9b6bff","#ff5a2e"];
var D="M8.5 16H14.5A16 16 0 0 1 14.5 48H8.5ZM14.5 23.5A8.5 8.5 0 0 1 14.5 40.5ZM33.5 16H39.5A16 16 0 0 1 39.5 48H33.5ZM39.5 23.5A8.5 8.5 0 0 1 39.5 40.5Z";
function build(extra,asButton){
  var el=document.createElement(asButton?"button":"div");el.className="ddl"+(extra?" "+extra:"");
  if(asButton){el.type="button";el.setAttribute("aria-label","Back to top");el.title="Back to top"}else el.setAttribute("aria-hidden","true");
  var h='<div class="ddl-floor"></div><div class="ddl-rot">',N=12,svg='<svg viewBox="0 0 64 64" aria-hidden="true" focusable="false"><path fill="#0b0b0e" fill-rule="evenodd" d="'+D+'"/></svg>';
  for(var i=N;i>=1;i--)h+='<div class="ddl-l'+(i===N?" b":i===1?" e":"")+'" style="transform:translateZ('+(-i*1.35).toFixed(2)+'px)"></div>';
  h+='<div class="ddl-face ddl-back" style="transform:translateZ('+(-(N+1)*1.35).toFixed(2)+'px) rotateY(180deg)">'+svg+'</div>';
  h+='<div class="ddl-face">'+svg+'<i class="ddl-sweep"></i></div></div>';
  h=h.replace(/<div/g,'<span').replace(/<\/div>/g,'</span>');   // valid inside a <button>
  el.innerHTML=h;return el;
}
function clamp(x){return x<0?0:x>1?1:x}
function ease(x){return x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2}
function kOf(el){return parseFloat(getComputedStyle(el).getPropertyValue("--k"))||1}

/* ---- layout (document coordinates), refreshed on resize / content changes ---- */
var L={};
function measure(){
  var sy=scrollY,sr=spot.getBoundingClientRect(),br=bar.getBoundingClientRect(),dr=dock.getBoundingClientRect();
  L.mob=innerWidth<=640;
  L.S1=Math.max(1,bar.offsetTop);                                   // scroll at which the search bar sticks
  L.ax=sr.left+sr.width/2;L.ay=sr.top+sy+sr.height/2;               // hero spot centre
  L.bx=dr.left+dr.width/2;L.by=bar.offsetTop+(dr.top-br.top)+dr.height/2; // dock centre while the bar is unstuck
  L.k0=kOf(spot);L.k1=kOf(dock);L.R=L.mob?46:110;
}
/* the path: straight interpolation plus a swirl loop (swinging toward the page centre) that peaks mid-way; q in 0..1, doc coordinates */
function path(q){
  var e=ease(q),R=L.R*Math.sin(Math.PI*e),a=Math.PI*2*1.15*e+Math.PI*.75;
  return {x:L.ax+(L.bx-L.ax)*e-(Math.cos(a)-Math.cos(Math.PI*.75))*R, y:L.ay+(L.by-L.ay)*e+Math.sin(a)*R*.6, e:e};
}

/* ---- reduced motion: two static logos, crossfaded by progress ---- */
if(RM){
  var h=build("",true),d=build("",true);spot.appendChild(h);dock.appendChild(d);
  [h,d].forEach(function(b){b.addEventListener("click",function(){
    if(scrollY>4){scrollTo(0,0);return}
    b.classList.remove("pulse");void b.offsetWidth;b.classList.add("pulse");setTimeout(function(){b.classList.remove("pulse")},700)})});
  var upd=function(){measure();var p=clamp(scrollY/L.S1);h.style.opacity=(1-p).toFixed(3);d.style.opacity=p.toFixed(3);
    // only the more visible copy is interactive
    var hOn=p<.5;h.tabIndex=hOn?0:-1;d.tabIndex=hOn?-1:0;h.style.pointerEvents=hOn?"auto":"none";d.style.pointerEvents=hOn?"none":"auto";
    if(hOn){h.removeAttribute("aria-hidden");d.setAttribute("aria-hidden","true")}else{d.removeAttribute("aria-hidden");h.setAttribute("aria-hidden","true")}};
  upd();addEventListener("scroll",upd,{passive:true});addEventListener("resize",upd);
  return;
}

var fly=build("fly",true);bar.parentNode.insertBefore(fly,bar);
var rot=fly.querySelector(".ddl-rot"),sweep=fly.querySelector(".ddl-sweep"),floor=fly.querySelector(".ddl-floor");
var canvas=document.createElement("canvas");canvas.className="ddl-trail";canvas.setAttribute("aria-hidden","true");canvas.style.display="none";
document.body.appendChild(canvas);var ctx=canvas.getContext("2d"),dpr=1;
function sizeCanvas(){dpr=Math.min(devicePixelRatio||1,2);canvas.width=innerWidth*dpr;canvas.height=innerHeight*dpr;ctx.setTransform(dpr,0,0,dpr,0,0)}

var ys=scrollY,vel=0,raf=0,last=0,drawn=false,fxT=-1,fxStart=0,FX_MS=1000;
function render(){
  var p=clamp(ys/L.S1),P=path(p),e=P.e;
  var fe=fxT>=0?ease(fxT):0;   // click effect (the one non-scroll animation), 0 when idle
  var s=(L.k0+(L.k1-L.k0)*e)*(1+.16*Math.sin(Math.PI*e))*(1+.14*Math.sin(Math.PI*fe));
  fly.style.setProperty("--s",s.toFixed(4));
  // viewport position = document position - (smoothed) scroll; at p=1 this equals the stuck dock slot
  var half=60*s+6,vx=Math.min(Math.max(P.x,half),innerWidth-half),vy=P.y-Math.min(ys,L.S1);  // never leave the viewport sideways
  fly.style.transform="translate3d("+(vx-60*s).toFixed(2)+"px,"+(vy-60*s).toFixed(2)+"px,0) scale("+s.toFixed(4)+")";
  // turn: one full spin across the path, plus a subtle tilt tied to scroll position
  var ry=-22+360*e+360*fe+Math.sin(ys/260)*12,rx=10+Math.cos(ys/380)*5-8*Math.sin(Math.PI*fe);
  rot.style.transform="rotateX("+rx.toFixed(2)+"deg) rotateY("+ry.toFixed(2)+"deg)";
  var sw=((ys/520)%1+1)%1;sweep.style.transform="translateX("+(-160+520*sw).toFixed(1)+"%) skewX(-18deg)";
  floor.style.opacity=Math.max(0,1-p*5).toFixed(3);
  drawTrails(p);
  if(fxT>=0)drawFx(vx,vy,s);
}
/* trails: four ribbons spiralling around the path history [p-span, p] plus seeded sparks, all from progress;
   their brightness follows scroll speed, so they fade out when scrolling stops */
var SPARKS=[];(function(){var r=7;function rnd(){r=(r*16807)%2147483647;return r/2147483647}
  for(var i=0;i<140;i++)SPARKS.push({q:rnd(),a:rnd()*6.283,d:.3+rnd()*1.2,s:.6+rnd(),c:i%4});})();
function drawTrails(p){
  var alpha=Math.min(1,vel*1.6);
  if(alpha<.01||p<=0){if(drawn&&fxT<0){ctx.clearRect(0,0,innerWidth,innerHeight);canvas.style.display="none";drawn=false}else if(fxT>=0)ctx.clearRect(0,0,innerWidth,innerHeight);return}
  if(!drawn){canvas.style.display="block";drawn=true}
  ctx.clearRect(0,0,innerWidth,innerHeight);ctx.globalCompositeOperation="lighter";ctx.lineCap="round";
  var span=L.mob?.22:.3,steps=L.mob?18:30,q0=Math.max(0,p-span),off=Math.min(ys,L.S1),R=L.mob?30:62,lw=L.mob?1.8:3;
  for(var c=0;c<4;c++){
    ctx.strokeStyle=COLORS[c];var prev=null;
    for(var j=0;j<=steps;j++){
      var q=q0+(p-q0)*j/steps,P=path(q),f=(q-q0)/Math.max(1e-6,p-q0);
      var sc=(L.k0+(L.k1-L.k0)*P.e),ang=q*40+c*Math.PI/2,rr=R*sc*(.55+.45*f);
      var x=P.x+Math.cos(ang)*rr,y=P.y-off+Math.sin(ang)*rr*.7;
      if(prev){ctx.globalAlpha=alpha*f*.6;ctx.lineWidth=lw*f+.3;ctx.beginPath();ctx.moveTo(prev[0],prev[1]);ctx.lineTo(x,y);ctx.stroke()}
      prev=[x,y];
    }
  }
  var n=L.mob?50:140;
  for(var i=0;i<n;i++){var k=SPARKS[i],age=(p-k.q)/span;if(age<0||age>1||k.q<=0)continue;
    var P2=path(k.q),dist=(L.mob?30:70)*k.d*age,a2=k.a+age*2.4;   // drift outward and swirl as you keep scrolling
    ctx.globalAlpha=alpha*(1-age)*.9;ctx.fillStyle=COLORS[k.c];ctx.beginPath();
    ctx.arc(P2.x+Math.cos(a2)*dist,P2.y-off+Math.sin(a2)*dist,(L.mob?1.3:1.9)*k.s*(1-age*.5),0,6.2832);ctx.fill()}
  // landing ring, scrubbed: grows over the last stretch of the path and is gone exactly at p=1
  if(p>.86&&p<1){var t=(p-.86)/.14,B=path(1),rad=(L.mob?10:22)+(L.mob?22:46)*t,m=L.mob?10:20;
    for(var b=0;b<m;b++){var a3=b/m*6.283+t*1.5;ctx.globalAlpha=alpha*Math.sin(Math.PI*t)*.85;ctx.fillStyle=COLORS[b%4];
      ctx.beginPath();ctx.arc(B.x+Math.cos(a3)*rad,B.y-off+Math.sin(a3)*rad*.8,L.mob?1.3:1.9,0,6.2832);ctx.fill()}}
  ctx.globalAlpha=1;ctx.globalCompositeOperation="source-over";
}
/* click-at-top effect: ring burst and a swirl of sparks around the logo, time-based, ~1 s */
function drawFx(x,y,s){
  if(!drawn){canvas.style.display="block";drawn=true}
  var t=fxT,r0=60*s,mob=L.mob;ctx.globalCompositeOperation="lighter";
  for(var ring=0;ring<2;ring++){var tt=clamp(t*1.25-ring*.18);if(tt<=0||tt>=1)continue;
    ctx.globalAlpha=(1-tt)*.85;ctx.lineWidth=(mob?2:3)*(1-tt)+.5;
    var g=ctx.createLinearGradient(x-r0,y-r0,x+r0,y+r0);g.addColorStop(0,"#f5a524");g.addColorStop(.35,"#22e0cf");g.addColorStop(.68,"#9b6bff");g.addColorStop(1,"#ff5a2e");
    ctx.strokeStyle=g;ctx.beginPath();ctx.ellipse(x,y,r0*(.8+1.3*ease(tt)),r0*(.8+1.3*ease(tt))*.86,0,0,6.2832);ctx.stroke()}
  var n=mob?18:32;
  for(var i=0;i<n;i++){var a=i/n*6.2832+t*3.2+(i%2)*.4,rr=r0*(.6+1.6*ease(t))*(.75+.25*((i*7)%5)/4);
    ctx.globalAlpha=Math.sin(Math.PI*t)*.95;ctx.fillStyle=COLORS[i%4];ctx.beginPath();
    ctx.arc(x+Math.cos(a)*rr,y+Math.sin(a)*rr*.86,(mob?1.4:2)*(1.2-t*.6),0,6.2832);ctx.fill()}
  ctx.globalAlpha=1;ctx.globalCompositeOperation="source-over";
}
fly.addEventListener("click",function(){
  if(scrollY>4){interacted=true;scrollTo({top:0,behavior:"smooth"});return}   // scroll-scrubbed rewind
  fxStart=performance.now();fxT=0;interacted=true;kick();
});
/* light smoothing toward the real scroll position; the loop stops as soon as everything has settled */
function frame(now){
  var dt=Math.min(now-last,64);last=now;
  if(fxT>=0){fxT=(now-fxStart)/FX_MS;if(fxT>=1)fxT=1}
  var target=scrollY,prevYs=ys,kk=1-Math.exp(-dt/55);       // settles in ~0.2 s
  ys+=(target-ys)*kk;if(Math.abs(target-ys)<.25)ys=target;
  var dpdt=Math.abs(ys-prevYs)/L.S1/Math.max(dt,1)*1000;     // progress per second
  var inRange=ys<L.S1+1||prevYs<L.S1+1;
  vel=Math.max(inRange?Math.min(1,dpdt*.9):0,vel*Math.exp(-dt/140));
  if(vel<.01)vel=0;
  render();
  if(fxT>=1){fxT=-1;render();if(vel<=0){ctx.clearRect(0,0,innerWidth,innerHeight);canvas.style.display="none";drawn=false}}   // ends exactly on the resting pose
  if(ys!==target||vel>0||fxT>=0)raf=requestAnimationFrame(frame);else raf=0;
}
/* until the visitor interacts, scroll changes (scroll restoration on refresh, hash links) are applied
   directly at the matching progress: no animated catch-up, no trails */
var interacted=false;
["wheel","touchstart","pointerdown","keydown"].forEach(function(t){addEventListener(t,function(){interacted=true},{passive:true,capture:true})});
function kick(){
  if(!interacted&&fxT<0){if(raf){cancelAnimationFrame(raf);raf=0}ys=scrollY;vel=0;render();return}
  if(!raf){last=performance.now();raf=requestAnimationFrame(frame)}
}
function relayout(){measure();sizeCanvas();ys=scrollY;vel=0;render()}
relayout();
addEventListener("scroll",kick,{passive:true});
addEventListener("resize",relayout);
addEventListener("load",relayout);
if(window.ResizeObserver)new ResizeObserver(function(){measure();render()}).observe(document.querySelector(".masthead")||document.body);
window.DDLogo={progress:function(){return clamp(ys/L.S1)},range:function(){return L.S1},settled:function(){return !raf}};
})();
