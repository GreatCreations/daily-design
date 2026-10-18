/* Daily Design: 3D "DD" logo. Lives in the hero, docks beside the sticky search bar when the hero
   scrolls away, and flies between the two with theme-colour trails. Decorative only (aria-hidden). */
(function(){
"use strict";
var spot=document.getElementById("logo-spot"),dock=document.getElementById("logo-dock"),bar=document.querySelector(".searchbox");
if(!spot||!dock||!bar)return;
var RM=window.matchMedia?matchMedia("(prefers-reduced-motion: reduce)"):{matches:false};
var COLORS=["#f5a524","#22e0cf","#9b6bff","#ff5a2e"];
var D="M8.5 16H14.5A16 16 0 0 1 14.5 48H8.5ZM14.5 23.5A8.5 8.5 0 0 1 14.5 40.5ZM33.5 16H39.5A16 16 0 0 1 39.5 48H33.5ZM39.5 23.5A8.5 8.5 0 0 1 39.5 40.5Z";
function build(){
  var el=document.createElement("div");el.className="ddl";el.setAttribute("aria-hidden","true");
  var h='<div class="ddl-floor"></div><div class="ddl-rot">',N=12;
  for(var i=N;i>=1;i--)h+='<div class="ddl-l'+(i===N?" b":i===1?" e":"")+'" style="transform:translateZ('+(-i*1.35).toFixed(2)+'px)"></div>';
  h+='<div class="ddl-face ddl-back" style="transform:translateZ('+(-(N+1)*1.35).toFixed(2)+'px) rotateY(180deg)"><svg viewBox="0 0 64 64" aria-hidden="true" focusable="false"><path fill="#0b0b0e" fill-rule="evenodd" d="'+D+'"/></svg></div>';
  h+='<div class="ddl-face"><svg viewBox="0 0 64 64" aria-hidden="true" focusable="false"><path fill="#0b0b0e" fill-rule="evenodd" d="'+D+'"/></svg><i class="ddl-sweep"></i></div></div>';
  el.innerHTML=h;return el;
}
var heroL=build(),dockL=build(),fly=null,canvas=null,ctx=null;
spot.appendChild(heroL);dock.appendChild(dockL);
var state="hero",t=0,dir=0,raf=0,last=0,parts=[],ribbons=[[],[],[],[]],tailUntil=0;
function mobile(){return innerWidth<=640}
function center(el){var r=el.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}}
function kOf(el){return parseFloat(getComputedStyle(el).getPropertyValue("--k"))||1}
function show(which,instant){
  heroL.classList.toggle("off",which!=="hero");dockL.classList.toggle("off",which!=="dock");
  if(instant){[heroL,dockL].forEach(function(l){l.style.transition="none";void l.offsetWidth;l.style.transition=""})}
}
function hideBoth(){heroL.classList.add("off");dockL.classList.add("off")}
/* scroll thresholds with hysteresis */
function want(){
  // dock once the hero spot's centre scrolls near the top of the viewport; come back only well below that
  var r=spot.getBoundingClientRect(),mid=r.top+r.height/2,DOCK_AT=110,HERO_AT=190;
  if(state!=="dock"&&mid<DOCK_AT)return "dock";
  if(state!=="hero"&&mid>HERO_AT)return "hero";
  return state;
}
var ticking=false;
function onScroll(){if(ticking)return;ticking=true;requestAnimationFrame(function(){ticking=false;var w=want();if(w!==state)go(w)})}
function go(to){
  state=to;
  if(RM.matches){show(to);return}       // reduced motion: fade between spots, no flight or trails
  dir=to==="dock"?1:-1;
  if(!fly){fly=build();fly.classList.add("fly");document.body.appendChild(fly);hideBoth()}
  if(!canvas){canvas=document.createElement("canvas");canvas.className="ddl-trail";canvas.setAttribute("aria-hidden","true");document.body.appendChild(canvas);ctx=canvas.getContext("2d");sizeCanvas()}
  canvas.style.display="block";fly.style.display="block";
  if(!raf){last=performance.now();raf=requestAnimationFrame(frame)}
}
function sizeCanvas(){if(!canvas)return;var d=Math.min(devicePixelRatio||1,2);canvas.width=innerWidth*d;canvas.height=innerHeight*d;ctx.setTransform(d,0,0,d,0,0)}
function ease(x){return x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2}
function frame(now){
  var dt=Math.min(now-last,50);last=now;
  var mob=mobile(),dur=mob?800:950;
  var flying=dir!==0;
  if(flying){
    t=Math.max(0,Math.min(1,t+dir*dt/dur));
    var e=ease(t),a=center(spot),b=center(dock),k0=kOf(spot),k1=kOf(dock);
    // curved path: straight interpolation plus a swirl loop whose radius peaks mid-flight
    var R=(mob?46:110)*Math.sin(Math.PI*e),ang=Math.PI*2*1.15*e+Math.PI*.75;
    var x=a.x+(b.x-a.x)*e+Math.cos(ang)*R-R*Math.cos(Math.PI*.75)*Math.sin(Math.PI*e),
        y=a.y+(b.y-a.y)*e+Math.sin(ang)*R*.6;
    var s=(k0+(k1-k0)*e)*(1+.18*Math.sin(Math.PI*e));
    fly.style.transform="translate3d("+(x-60).toFixed(1)+"px,"+(y-60).toFixed(1)+"px,0) scale("+s.toFixed(3)+")";
    fly.firstChild.nextSibling.style.transform="rotateX(10deg) rotateY("+(e*360).toFixed(1)+"deg)";
    emit(x,y,s*60,now,mob);
    if((dir>0&&t>=1)||(dir<0&&t<=0)){
      var land=dir>0?b:a;dir=0;fly.style.display="none";show(state,true);burst(land.x,land.y,mob);tailUntil=now+900;
      // the user may have scrolled back during the landing
      var w=want();if(w!==state)go(w);
    }
  }
  draw(dt);
  if(dir!==0||parts.length||now<tailUntil){raf=requestAnimationFrame(frame)}
  else{raf=0;ctx.clearRect(0,0,innerWidth,innerHeight);canvas.style.display="none";ribbons=[[],[],[],[]]}
}
function emit(x,y,r,now,mob){
  var max=mob?90:260,per=mob?1:3;
  for(var i=0;i<4;i++){
    var a=now/140+i*Math.PI/2,rr=r*.95;
    var px=x+Math.cos(a)*rr,py=y+Math.sin(a)*rr*.7;
    var rb=ribbons[i];rb.push({x:px,y:py,life:1});if(rb.length>(mob?12:22))rb.shift();
    if(parts.length<max&&Math.random()<per/4*4/4)for(var j=0;j<per/2+.5;j++){
      var sp=(mob?.04:.06)+Math.random()*.08,dirA=a+Math.PI/2;
      parts.push({x:px,y:py,vx:Math.cos(dirA)*sp,vy:Math.sin(dirA)*sp,spin:(Math.random()<.5?-1:1)*(.004+Math.random()*.006),life:1,decay:1/(500+Math.random()*500),size:(mob?1.2:1.6)+Math.random()*(mob?1.4:2.4),c:COLORS[i]});
    }
  }
}
function burst(x,y,mob){var n=mob?10:22;for(var i=0;i<n;i++){var a=i/n*Math.PI*2,sp=.08+Math.random()*.12;
  parts.push({x:x,y:y,vx:Math.cos(a)*sp,vy:Math.sin(a)*sp,spin:.006,life:1,decay:1/650,size:(mob?1.2:1.8)+Math.random()*1.6,c:COLORS[i%4]})}}
function draw(dt){
  if(!ctx)return;ctx.clearRect(0,0,innerWidth,innerHeight);ctx.globalCompositeOperation="lighter";
  // ribbons: four colour streams spiralling around the logo's path
  for(var i=0;i<4;i++){var rb=ribbons[i];if(dir===0){rb.shift()}
    if(rb.length<2)continue;ctx.strokeStyle=COLORS[i];ctx.lineCap="round";
    for(var j=1;j<rb.length;j++){var f=j/rb.length;ctx.globalAlpha=f*.55;ctx.lineWidth=(mobile()?1.6:2.6)*f+.4;
      ctx.beginPath();ctx.moveTo(rb[j-1].x,rb[j-1].y);ctx.lineTo(rb[j].x,rb[j].y);ctx.stroke()}}
  for(var k=parts.length-1;k>=0;k--){var p=parts[k];
    var c=Math.cos(p.spin*dt),s=Math.sin(p.spin*dt),vx=p.vx*c-p.vy*s;p.vy=p.vx*s+p.vy*c;p.vx=vx;   // swirl
    p.x+=p.vx*dt;p.y+=p.vy*dt;p.life-=p.decay*dt;
    if(p.life<=0){parts.splice(k,1);continue}
    ctx.globalAlpha=p.life*.9;ctx.fillStyle=p.c;ctx.beginPath();ctx.arc(p.x,p.y,p.size*(.4+p.life*.6),0,6.2832);ctx.fill()}
  ctx.globalAlpha=1;ctx.globalCompositeOperation="source-over";
}
/* start in the right place without animating (e.g. page opened scrolled down or on a #report link) */
function init(){var w=want();state=w;show(w,true)}
init();
addEventListener("scroll",onScroll,{passive:true});
addEventListener("resize",function(){sizeCanvas();onScroll()});
document.addEventListener("visibilitychange",function(){document.documentElement.classList.toggle("dd-paused",document.hidden)});
window.DDLogo={state:function(){return state},t:function(){return t}};
})();
