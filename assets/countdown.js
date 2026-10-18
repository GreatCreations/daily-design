/* Daily Design: countdown to the next scheduled edition.
   Schedule is wall-clock time in America/Vancouver (DST-aware via Intl), shown in the visitor's own zone. */
(function(){
"use strict";
var el=document.getElementById("cd");
if(!el||!window.Intl||!Intl.DateTimeFormat)return;
var TZ="America/Vancouver", ARRIVING_MS=10*60*1000;
var SLOTS=[{h:7,name:"AI Design Daily",c:"var(--amber)"},{h:12,name:"AI Design in Use",c:"var(--aqua)"},
           {h:18,name:"Best of the Day",c:"var(--violet)"},{h:20,name:"Hottest Right Now",c:"var(--flame)"}];
var partsFmt;
try{partsFmt=new Intl.DateTimeFormat("en-US",{timeZone:TZ,hourCycle:"h23",year:"numeric",month:"numeric",day:"numeric",hour:"numeric",minute:"numeric",second:"numeric"})}catch(e){return}
function wall(t){var o={};partsFmt.formatToParts(new Date(t)).forEach(function(p){o[p.type]=+p.value});if(o.hour===24)o.hour=0;return o}
function offsetAt(t){var w=wall(t);return Date.UTC(w.year,w.month-1,w.day,w.hour,w.minute,w.second)-Math.floor(t/1000)*1000}
/* UTC instant of a Vancouver wall-clock time */
function instant(y,m,d,h){var g=Date.UTC(y,m-1,d,h,0,0),t=g-offsetAt(g);return g-offsetAt(t)}
function upcoming(now){
  var w=wall(now);
  for(var k=-1;k<3;k++){
    var base=new Date(Date.UTC(w.year,w.month-1,w.day+k));
    for(var i=0;i<SLOTS.length;i++){
      var t=instant(base.getUTCFullYear(),base.getUTCMonth()+1,base.getUTCDate(),SLOTS[i].h);
      if(t+ARRIVING_MS>now)return {slot:SLOTS[i],t:t};
    }
  }
}
var loc=undefined;try{loc=navigator.language||undefined}catch(e){}
var tFmt=new Intl.DateTimeFormat(loc,{hour:"numeric",minute:"2-digit",timeZoneName:"short"});
var dFmt=new Intl.DateTimeFormat(loc,{weekday:"short"});
var dayKey=new Intl.DateTimeFormat("en-CA",{year:"numeric",month:"2-digit",day:"2-digit"});
function two(n){return(n<10?"0":"")+n}
var $=function(s){return el.querySelector(s)}, cur=null;
el.innerHTML='<span class="cd-dot" aria-hidden="true"></span><span class="cd-k" aria-hidden="true">Next</span>'+
  '<span class="cd-n" aria-hidden="true"></span><span class="cd-s" aria-hidden="true">·</span><span class="cd-t" aria-hidden="true"></span>'+
  '<span class="cd-s" aria-hidden="true">·</span><span class="cd-c" role="timer" aria-live="off" aria-atomic="true"></span><span class="sr cd-sr"></span>';
function tick(){
  var now=Date.now(),u=upcoming(now);if(!u)return;
  var key=u.t+"|"+u.slot.name;
  if(key!==cur){cur=key;
    var when=tFmt.format(new Date(u.t));
    if(dayKey.format(new Date(u.t))!==dayKey.format(new Date(now)))when=dFmt.format(new Date(u.t))+" "+when;
    el.style.setProperty("--c",u.slot.c);
    $(".cd-n").textContent=u.slot.name;$(".cd-t").textContent=when;
    $(".cd-sr").textContent="Next scheduled edition: "+u.slot.name+" at "+when+".";
    el.title="Scheduled time (editions can land a few minutes late)";
  }
  var left=u.t-now;
  if(left<=0){el.classList.add("arriving");$(".cd-c").textContent="arriving now"}
  else{el.classList.remove("arriving");var s=Math.ceil(left/1000);
    $(".cd-c").textContent="in "+two(Math.floor(s/3600))+":"+two(Math.floor(s%3600/60))+":"+two(s%60)}
  el.hidden=false;document.documentElement.classList.add("has-cd");
}
tick();
var timer=null;
function start(){clearTimeout(timer);(function loop(){tick();timer=setTimeout(loop,1000-(Date.now()%1000)+15)})()}
start();
document.addEventListener("visibilitychange",function(){if(!document.hidden)start()});
window.DDCountdown={upcoming:upcoming,instant:instant};
})();
