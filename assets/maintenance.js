/* Daily Design: scheduled-maintenance notice on the About page (#ab-maint).
   Reads "maintenance_windows" from data/index.json (tools/special-days.json "windows"). While the America/Vancouver wall clock is inside a
   window it shows "<label>: <about>" ("about" falls back to "text"); outside any window the element stays hidden, and it hides itself again
   when the window ends. Same window shape and time rule as assets/countdown.js (start/end "YYYY-MM-DDTHH:MM" Vancouver time, end inclusive). */
(function(){
"use strict";
var el=document.getElementById("ab-maint");
if(!el||!window.fetch||!window.Intl||!Intl.DateTimeFormat)return;
var fmt,W=[],cur=null;
try{fmt=new Intl.DateTimeFormat("en-US",{timeZone:"America/Vancouver",hourCycle:"h23",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"})}catch(e){return}
function now(){var o={};fmt.formatToParts(new Date()).forEach(function(p){o[p.type]=p.value});
  return o.year+"-"+o.month+"-"+o.day+"T"+(o.hour==="24"?"00":o.hour)+":"+o.minute}
function active(){var k=now();for(var i=0;i<W.length;i++)if(k>=W[i].start&&k<=W[i].end)return W[i];return null}
function render(){
  var w=active();
  if(!w){if(cur!==null){cur=null;el.hidden=true;el.textContent=""}return}
  var id=w.start+"|"+w.label+"|"+(w.about||w.text);
  if(id===cur)return;cur=id;
  el.textContent="";var b=document.createElement("b");b.textContent=w.label+":";
  el.appendChild(b);el.appendChild(document.createTextNode(" "+(w.about||w.text||"")));el.hidden=false}
fetch("data/index.json").then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(j){
  var a=j&&j.maintenance_windows;W=Array.isArray(a)?a.filter(function(w){return w&&w.start&&w.end&&w.label}):[];
  render();setInterval(render,15000);
  document.addEventListener("visibilitychange",function(){if(!document.hidden)render()})}).catch(function(){});
})();
