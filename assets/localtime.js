/* Daily Design: show marked Pacific times in the visitor's own time zone (PT text is the no-JS fallback and the tooltip).
   <time datetime="2026-10-30T09:00" data-local data-pt="2026-10-30T09:00">9 AM PT</time> -> "10 AM MDT". Pacific offset follows the
   site's rule (publish.py tz_auto/pt_iso: PDT/PST before 2026-11-01, permanent PT = UTC-7 from then), same as assets/tzlocal.js. */
(function(){"use strict";
function ptOff(ds){if(ds>="2026-11-01")return-7;var y=+ds.slice(0,4),m=+ds.slice(5,7),d=+ds.slice(8,10);
 function sun(mo,n){var f=new Date(Date.UTC(y,mo-1,1)).getUTCDay();return 1+(7-f)%7+7*(n-1)}
 var k=m*100+d;return(k>=300+sun(3,2)&&k<1100+sun(11,1))?-7:-8}
function inst(w){var m=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(w||"");if(!m)return null;
 return Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5])-ptOff(w.slice(0,10))*3600000}
function run(root){try{
 var me=Intl.DateTimeFormat().resolvedOptions().timeZone;if(me==="America/Vancouver")return;
 var ts=(root||document).querySelectorAll("time[data-local]:not([data-done])"),dk=new Intl.DateTimeFormat("en-CA",{year:"numeric",month:"2-digit",day:"2-digit"});
 for(var i=0;i<ts.length;i++){var t=ts[i],w=t.getAttribute("data-pt"),u=inst(w);if(u==null)continue;t.setAttribute("data-done","");
  var dd=new Date(u);if(-dd.getTimezoneOffset()===ptOff(w.slice(0,10))*60)continue;
  var s=dd.toLocaleTimeString("en-US",{hour:"numeric",minute:"2-digit",timeZoneName:"short"}).replace(":00 "," ");
  if(dk.format(dd)!==w.slice(0,10))s+=" ("+dd.toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"})+")";
  if(!t.title)t.title=t.textContent;t.setAttribute("datetime",dd.toISOString());t.textContent=s}
}catch(e){}}
window.ddLocalTime=run;
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",function(){run()});else run();
})();
