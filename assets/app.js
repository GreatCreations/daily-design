/* Daily Design index: vanilla JS, no build step.
   data/index.json  -> editions, calendar, facets, totals, shard manifest
   data/items/<YYYY-MM>.json -> items for that month, fetched lazily */
(function(){
"use strict";
var D, EDS=[], EDBY={}, CAL=[], SHARDS=[], ITEMS=[], LOADED={}, LOADING={};
var PAGE=40, EPAGE=12;
var shown=PAGE, eshown=EPAGE, openKey=null, renderT=0;
var GROUPS=["slot","medium","type"], SLOTS=["morning","noon","best","hottest"];
var SLOTCOL={morning:"var(--amber)",noon:"var(--aqua)",best:"var(--violet)",hottest:"var(--flame)"};
var MLABEL={}, SLABEL={}, SINFO={}, TLABEL={"repo/tool":"Repo / tool","case study":"Case study"};
var state=blank();
function blank(){return {q:"",slot:[],medium:[],type:[],tag:[],from:"",to:"",sort:"new",report:"",part:"",archive:""}}
var $=function(s){return document.querySelector(s)};
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function norm(s){return String(s||"").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"")}
function cap(s){return s?s.charAt(0).toUpperCase()+s.slice(1):s}
function pd(d){var p=d.split("-");return new Date(Date.UTC(+p[0],+p[1]-1,+(p[2]||1)))}
function fmt(d,o){return pd(d).toLocaleDateString("en-US",Object.assign({timeZone:"UTC"},o))}
function niceDate(d){return fmt(d,{weekday:"short",month:"short",day:"numeric",year:"numeric"})}
function monthName(m){return fmt(m+"-01",{month:"long",year:"numeric"})}
function host(u){try{return new URL(u).hostname.replace(/^www\./,"")}catch(e){return ""}}
function label(g,k){return g==="medium"?(MLABEL[k]||k):g==="slot"?(SLABEL[k]||k):(TLABEL[k]||cap(k))}
function inRange(d){return (!state.from||d>=state.from)&&(!state.to||d<=state.to)}
function monthInRange(m){return (!state.from||m>=state.from.slice(0,7))&&(!state.to||m<=state.to.slice(0,7))}
function n(x){return Number(x).toLocaleString()}

/* ---------------- boot ---------------- */
fetch("data/index.json").then(function(r){if(!r.ok)throw new Error(r.status);return r.json()}).then(init).catch(function(){
  $("#items").innerHTML='<div class="empty"><b>Could not load the index</b>Please reload the page.</div>'});

function init(data){
  D=data; EDS=D.editions; CAL=D.calendar.slice(); MAINT={}; LAUNCH={}; if(D.special)D.special.forEach(function(x){(x.type==="launch"?LAUNCH:MAINT)[x.date]=1}); else (D.maintenance||[]).forEach(function(d){MAINT[d]=1}); readyToday(); SHARDS=D.shards;
  D.facets.medium.forEach(function(m){MLABEL[m.key]=m.label});
  D.facets.slot.forEach(function(s){SLABEL[s.key]=s.label;SINFO[s.key]=s});
  EDS.forEach(function(e){EDBY[e.date+"/"+e.slot]=e;e._hay=norm([e.title,e.headline,e.summary,e.date,niceDate(e.date),e.slot,e.time,e.kind==="report"?"report":""].join(" "))});
  var t=D.totals;
  $('[data-k="editions"]').textContent=n(t.editions);$('[data-k="items"]').textContent=n(t.items);$('[data-k="tags"]').textContent=n(t.tags);
  $("#totals-note").textContent=n(t.days)+" day"+(t.days==1?"":"s")+" · "+n(t.months)+" month"+(t.months==1?"":"s")+" · latest "+niceDate(t.last);
  $("#updated").textContent="Updated "+niceDate(t.last);
  buildFilters(); buildJump(); readHash(); bind(); renderLatest(); render(); if(state.archive)setTimeout(archTop,80);
  var an=anchorEl();if(an)setTimeout(function(){an.scrollIntoView()},120);
}

/* ---------------- shards ---------------- */
function prepItem(it){it._hay=norm([it.title,it.note,it.source,it.author,it.medium,MLABEL[it.medium],it.type,it.kind,(it.tags||[]).join(" "),
  (it.links||[]).map(function(l){return l.label}).join(" "),host(it.url),it.engagement,SINFO[it.slot]?SINFO[it.slot].label:"",it.date,it.edition_kind==="report"?"report":""].join(" "));return it}
function loadShard(s){
  if(LOADED[s.month])return Promise.resolve();
  if(LOADING[s.month])return LOADING[s.month];
  return LOADING[s.month]=fetch(s.path).then(function(r){if(!r.ok)throw new Error(r.status);return r.json()}).then(function(j){
    j.items.forEach(prepItem); LOADED[s.month]=j.items; rebuildItems(); delete LOADING[s.month];
  }).catch(function(){delete LOADING[s.month]});
}
function rebuildItems(){var a=[];SHARDS.forEach(function(s){if(LOADED[s.month])a=a.concat(LOADED[s.month])});ITEMS=a}
function neededShards(){return SHARDS.filter(function(s){return monthInRange(s.month)})}
function ensureShards(all){
  var need=neededShards(), todo=need.filter(function(s){return !LOADED[s.month]});
  if(!all){ // browsing: load only as many months as the visible list needs
    var have=0;need.forEach(function(s){if(LOADED[s.month])have+=s.items});
    var order=state.sort==="old"?need.slice().reverse():need; todo=[];
    for(var i=0;i<order.length&&have<shown+PAGE;i++){if(!LOADED[order[i].month]){todo.push(order[i]);have+=order[i].items}}
  }
  if(!todo.length){progress(need);return}
  progress(need);
  var q=todo.slice(), run=function(){var s=q.shift();if(!s)return Promise.resolve();return loadShard(s).then(function(){progress(need);schedule();return run()})};
  Promise.all([run(),run(),run()]);
}
function progress(need){
  var tot=need.length, done=need.filter(function(s){return LOADED[s.month]}).length, p=$("#progress");
  if(!active()||done>=tot){p.hidden=true;return}
  p.hidden=false;$("#progress-bar").style.width=Math.round(100*done/Math.max(1,tot))+"%";
}
function schedule(){clearTimeout(renderT);renderT=setTimeout(function(){render(true)},60)}

/* ---------------- filters + hash ---------------- */
function buildFilters(){
  var html="";
  [["slot","Edition",SLOTS],["medium","Medium",D.facets.medium.map(function(m){return m.key})],["type","Type",D.facets.type]].forEach(function(d){
    html+='<div class="fgroup"><span class="lab">'+d[1]+(d[0]==="slot"?' · <span class="dd-tz">'+tzLabel()+'</span>':'')+'</span><div class="chips">';
    d[2].forEach(function(k){var c=d[0]==="slot"?' style="--c:'+SLOTCOL[k]+'"':"";
      html+='<button class="chip" type="button" data-g="'+d[0]+'" data-k="'+esc(k)+'" aria-pressed="false"'+c+(d[0]==="slot"?' title="'+esc(tzTip((ptNow()||{}).date,k))+'"':'')+'>'+(d[0]==="slot"?'<span class="sw"></span>':"")+esc(label(d[0],k))+' <span class="n"></span></button>'});
    html+='</div></div>';
  });
  var t=D.totals;
  html+='<div class="fgroup"><span class="lab">Dates</span><div class="chips dates">'+
    '<label class="dt"><span>From</span><input type="date" id="from" min="'+t.first+'" max="'+t.last+'"></label>'+
    '<label class="dt"><span>To</span><input type="date" id="to" min="'+t.first+'" max="'+t.last+'"></label>'+
    '<button class="chip" type="button" data-range="day">Latest day</button><button class="chip" type="button" data-range="7">Last 7 days</button>'+
    '<button class="chip" type="button" data-range="30">Last 30 days</button><button class="chip" type="button" data-range="month">This month</button>'+
    '<button class="chip" type="button" data-range="all">All time</button></div></div>';
  html+='<div class="fgroup" id="tagrow" hidden><span class="lab">Tag</span><div class="chips" id="tagchips"></div></div>';
  $("#filters").innerHTML=html;
}
function buildJump(){
  var months=SHARDS.map(function(s){return s.month});
  $("#jump").innerHTML='<option value="">Month…</option>'+months.map(function(m){var s=SHARDS.filter(function(x){return x.month===m})[0];
    return '<option value="'+m+'">'+esc(monthName(m))+' ('+s.editions+')</option>'}).join("");
}
function readHash(){
  var h=location.hash.replace(/^#/,""); state=blank();
  h.split("&").forEach(function(p){if(!p)return;var i=p.indexOf("=");var k=decodeURIComponent(i<0?p:p.slice(0,i)),v=i<0?"":decodeURIComponent(p.slice(i+1).replace(/\+/g," "));
    if(k==="q"||k==="from"||k==="to"||k==="report")state[k]=v;else if(k==="sort")state.sort=v==="old"?"old":"new";
    else if(k==="archive"&&/^\d{4}-\d\d-\d\d$/.test(v))state.archive=v;
    else if(k==="part"&&/^[a-z0-9-]{1,80}$/.test(v))state.part=v;
    else if(k==="date"&&v){var ds=v.split(",").sort();state.from=ds[0];state.to=ds[ds.length-1]}
    else if(Array.isArray(state[k])&&v)state[k]=v.split(",").filter(Boolean)});
  $("#q").value=state.q;$("#from").value=state.from;$("#to").value=state.to;
}
// plain in-page anchors (#latest-block, #search, #archive-block from the About site map) are kept, not treated as filter state
function anchorEl(){var h=location.hash;return /^#[A-Za-z][\w-]*$/.test(h)?document.getElementById(h.slice(1)):null}
function writeHash(){
  var parts=[];if(state.q)parts.push("q="+encodeURIComponent(state.q));
  GROUPS.concat(["tag"]).forEach(function(g){if(state[g].length)parts.push(g+"="+state[g].map(encodeURIComponent).join(","))});
  if(state.from)parts.push("from="+state.from);if(state.to)parts.push("to="+state.to);
  if(state.sort==="old")parts.push("sort=old");
  if(state.archive)parts.push("archive="+state.archive);
  if(state.report)parts.push("report="+state.report.split("/").map(encodeURIComponent).join("/"));
  if(state.report&&state.part)parts.push("part="+state.part);
  var h=parts.length?"#"+parts.join("&"):"";if(!h&&anchorEl())return;
  var push=PUSH;PUSH=false;
  if(h!==location.hash)history[push?"pushState":"replaceState"](null,"",h||location.pathname+location.search);
}
function tokens(){return norm(state.q).split(/\s+/).filter(Boolean)}
function itemFilters(){return state.medium.length||state.type.length||state.tag.length}
function active(){return !!(state.q||itemFilters())}
function filtered(){return active()||state.slot.length||state.from||state.to}
function itemMatch(it,skip,toks){
  if(!inRange(it.date))return false;
  for(var i=0;i<toks.length;i++)if(it._hay.indexOf(toks[i])<0)return false;
  for(var g=0;g<GROUPS.length;g++){var G=GROUPS[g];if(G===skip||!state[G].length)continue;if(state[G].indexOf(it[G])<0)return false}
  for(var j=0;j<state.tag.length;j++)if((it.tags||[]).indexOf(state.tag[j])<0)return false;
  return true;
}
function edMatchBasic(e){return (!state.slot.length||state.slot.indexOf(e.slot)>=0)&&inRange(e.date)}

/* ---------------- render ---------------- */
function render(fromShard){
  var toks=tokens(), act=active();
  if(!fromShard)ensureShards(act);
  var res=[], counts={}, chip={}, i, it;
  for(i=0;i<ITEMS.length;i++){it=ITEMS[i];
    if(itemMatch(it,null,toks)){res.push(it);counts[it.edition]=(counts[it.edition]||0)+1}
    for(var g=0;g<GROUPS.length;g++){var G=GROUPS[g];if(itemMatch(it,G,toks)){var key=G+"|"+it[G];chip[key]=(chip[key]||0)+1}}}
  document.querySelectorAll(".chip[data-g]").forEach(function(c){var g=c.dataset.g,k=c.dataset.k,v=chip[g+"|"+k]||0,on=state[g].indexOf(k)>=0;
    c.setAttribute("aria-pressed",on);c.querySelector(".n").textContent=v?n(v):"0";c.classList.toggle("zero",!v&&!on)});
  document.querySelectorAll(".chip[data-range]").forEach(function(c){c.setAttribute("aria-pressed",rangeIs(c.dataset.range))});
  $("#tagrow").hidden=!state.tag.length;
  $("#tagchips").innerHTML=state.tag.map(function(t){return '<button class="chip" type="button" aria-pressed="true" data-tag="'+esc(t)+'">'+esc(cap(t))+' ✕</button>'}).join("");
  $("#clear").hidden=!filtered();
  if(state.sort==="old")res.reverse();
  // editions (only when searching/filtering by item fields)
  var eb=$("#eds-block"); ARCH_MATCH=null;
  if(act){
    var eds=EDS.filter(function(e){if(!edMatchBasic(e))return false;if(counts[e.path]||counts[e.url])return true;if(itemFilters())return false;
      return toks.every(function(t){return e._hay.indexOf(t)>=0})});
    ARCH_MATCH={};eds.forEach(function(e){ARCH_MATCH[e.date]=1});
    if(state.sort==="old")eds=eds.slice().reverse();
    eb.hidden=false;
    $("#eds").innerHTML=eds.slice(0,eshown).map(function(e){return edCard(e,counts[e.url]||counts[e.path]||0)}).join("")||'<div class="empty">No editions match.</div>';
    $("#eds-more").hidden=eds.length<=eshown;$("#eds-more").textContent="More editions ("+n(eds.length-eshown)+" left)";
    $("#eds-eyebrow").textContent="Matching editions · "+n(eds.length);
  } else eb.hidden=true;
  // items
  var need=neededShards(), loadedN=need.filter(function(s){return LOADED[s.month]}).length, totalInRange=need.reduce(function(a,s){return a+s.items},0);
  $("#items").innerHTML=res.slice(0,shown).map(function(x){return itemRow(x,toks)}).join("")||
    (loadedN<need.length?'<div class="empty">Loading…</div>':'<div class="empty"><b>Nothing found</b>Try fewer words, a wider date range, or clear a filter.</div>');
  var more=res.length>shown||(!act&&loadedN<need.length);
  $("#more").hidden=!more;$("#more").textContent=res.length>shown?"Show more ("+n(res.length-shown)+" loaded)":"Load older links";
  var partial=act&&loadedN<need.length;
  $("#items-eyebrow").textContent=(act?"Matching links · ":filtered()?"Links in this view · ":"Recent links · ")+(act?n(res.length)+(partial?"+":""):n(filtered()?Math.max(res.length,0):totalInRange));
  $("#status-title").textContent=act?(state.q?"Results for “"+state.q+"”":"Filtered view"):filtered()?"Filtered archive":"Browse";
  $("#status-line").innerHTML=act?"<b>"+n(res.length)+"</b> link"+(res.length==1?"":"s")+(partial?" so far · searching "+loadedN+" of "+need.length+" months":" · all "+need.length+" month"+(need.length==1?"":"s")+" searched")+" · share this view by copying the URL"
    :(filtered()?rangeText()+" · ":"")+"<b>"+n(D.totals.editions)+"</b> editions · <b>"+n(D.totals.items)+"</b> links";
  // browsing: archive sits right under Latest; searching: results first, archive below
  var ab=$("#archive-block"), ib=$("#items-block");
  if(!act&&ab.nextElementSibling!==ib)ib.parentNode.insertBefore(ab,ib);
  else if(act&&ib.nextElementSibling!==ab)ib.parentNode.insertBefore(ab,ib.nextElementSibling);
  renderArchive(); writeHash(); syncReader();
}
function rangeText(){if(state.from&&state.to&&state.from===state.to)return niceDate(state.from);if(state.from||state.to)return (state.from?niceDate(state.from):"start")+" → "+(state.to?niceDate(state.to):"latest");return ""}
function addDays(d,k){var x=pd(d);x.setUTCDate(x.getUTCDate()+k);return x.toISOString().slice(0,10)}
function rangeFor(r){var L=D.totals.last;if(r==="day")return [L,L];if(r==="7")return [addDays(L,-6),L];if(r==="30")return [addDays(L,-29),L];if(r==="month")return [L.slice(0,7)+"-01",L];return ["",""]}
function rangeIs(r){var a=rangeFor(r);return r==="all"?(!state.from&&!state.to):(state.from===a[0]&&state.to===a[1])}

function edHref(e){return e.kind==="report"?"#report="+e.date+"/"+e.slot:e.path}
function edAttrs(e){return e.kind==="report"?' data-report="'+esc(e.date+"/"+e.slot)+'"':""}
function edCard(e,matches){
  var th=e.thumb||e.header, rep=e.kind==="report";
  return '<a class="ed'+(rep?' report':'')+'" style="--c:'+SLOTCOL[e.slot]+'" href="'+esc(edHref(e))+'"'+edAttrs(e)+'>'+
    '<div class="th">'+(th?'<img src="'+esc(th)+'" alt="" loading="lazy" decoding="async">':'')+'</div>'+(rep?'<span class="rtag">Report</span>':'')+
    '<div class="bd"><div class="k"><span>'+esc(e.time)+tzs(e.date,e.slot,true)+' · '+esc(e.title)+'</span><span>'+esc(niceDate(e.date))+'</span></div>'+
    '<h3>'+esc(e.headline)+'</h3><p>'+esc(e.summary)+'</p>'+
    '<div class="ft"><span><b>'+n(e.item_count)+'</b> items</span>'+(matches!=null?'<span><b>'+n(matches)+'</b> match'+(matches==1?'':'es')+'</span>':'')+'</div></div></a>';
}
/* ---- time zones. Editions are filed and timed in Pacific time (America/Vancouver).
   TZ_LABEL: "auto", or one fixed label ("PST", "PT", ...) shown after every Pacific clock time. auto = PDT/PST by the old daylight rule for
   the date shown until B.C.'s permanent UTC-7 starts on TZ_PERM_FROM (no fall-back on 2026-11-01; B.C. calls it "Pacific time"), then
   TZ_PERMANENT. Rule-based on purpose (browsers with tzdata 2026b+ name that zone "MST"; older ones still apply UTC-8). The UTC offset
   always follows the real rule, whatever the label. Mirrors TZ_LABEL in tools/publish.py and assets/tzlocal.js. */
var TZ_LABEL="auto", TZ_PERMANENT="PT", TZ_PERM_FROM="2026-11-01";
function tzAuto(ds){if(!/^\d{4}-\d\d-\d\d$/.test(ds||""))return "PT";if(ds>=TZ_PERM_FROM)return TZ_PERMANENT;
  var y=+ds.slice(0,4),k=+ds.slice(5,7)*100+(+ds.slice(8,10));function sun(mo,n){var f=new Date(Date.UTC(y,mo-1,1)).getUTCDay();return 1+(7-f)%7+7*(n-1)}
  return k>=300+sun(3,2)&&k<1100+sun(11,1)?"PDT":"PST"}
function tzLabel(ds){return TZ_LABEL!=="auto"?TZ_LABEL:tzAuto(ds||(ptNow()||{}).date)}
var SLOTH={morning:7,noon:12,best:18,hottest:20}, SLOTWHEN={morning:"morning",noon:"noon",best:"evening",hottest:"late evening"};
function slotMs(ds,slot){return Date.UTC(+ds.slice(0,4),+ds.slice(5,7)-1,+ds.slice(8,10),SLOTH[slot])+(tzAuto(ds)==="PST"?8:7)*3600e3}
/* the visitor's own clock for a Pacific slot time; "" when it reads the same as Pacific (Vancouver visitors see Pacific only) */
var LOCF=null,LOCD=null,LOC12=true;try{LOCF=new Intl.DateTimeFormat(undefined,{hour:"numeric",minute:"2-digit",timeZoneName:"short"});
  LOC12=/h1[12]/.test(LOCF.resolvedOptions().hourCycle||"h12");LOCD=new Intl.DateTimeFormat("en-CA",{year:"numeric",month:"2-digit",day:"2-digit"})}catch(e){}
function locHint(ds,slot){if(!LOCF||!SLOTH[slot]||!/^\d{4}-\d\d-\d\d$/.test(ds||""))return "";var t=slotMs(ds,slot),d=new Date(t);
  if(-d.getTimezoneOffset()===(tzAuto(ds)==="PST"?-480:-420))return "";
  var s=LOCF.format(d);if(LOC12)s=s.replace(/:00(?=\D)/,"");
  if(LOCD.format(d)!==ds)s=new Intl.DateTimeFormat(undefined,{weekday:"short"}).format(d)+" "+s;return s}
/* " PDT" label (+ " (3 PM BST)" visitor time when loc) after a Pacific time */
function tzs(ds,slot,loc){var h=loc&&locHint(ds,slot);return ' <span class="dd-tz">'+tzLabel(ds)+'</span>'+(h?' <span class="dd-loc" title="Your time">('+esc(h)+')</span>':'')}
function tzTip(ds,slot){var s=(SINFO[slot]||{label:""}).label.split(" · ")[0],h=locHint(ds,slot);return s+" "+tzLabel(ds)+(h?" · "+h+" your time":"")}
function slotLab(slot,ds){var s=(SINFO[slot]||{label:""}).label.split(" · ");return esc(s[0])+tzs(ds,slot,true)+(s[1]?' · '+esc(s[1]):'')}
/* empty slot wording: today (Vancouver) before the slot's time -> "Not published until <part of day>"; up to 2 h after it -> "Publishing soon";
   later today -> "Not published yet"; past days -> "Not published" */
function missText(ds,slot){var t=ptNow();if(!t||ds!==t.date||!SLOTH[slot])return "Not published";
  return t.h<SLOTH[slot]?"Not published until "+SLOTWHEN[slot]:t.h<SLOTH[slot]+2?"Publishing soon":"Not published yet"}
function missLoc(ds,slot){var t=ptNow();if(!t||ds!==t.date||t.h>=SLOTH[slot])return "";var h=locHint(ds,slot);return h?h+" your time":""}
function fillTz(){var t=(ptNow()||{}).date,L=tzLabel(t);[].forEach.call(document.querySelectorAll("[data-tz]"),function(x){x.textContent=L});
  var n=document.getElementById("tznote"),h=locHint(t,"noon");
  if(n)n.textContent="Editions are dated and timed in Pacific time ("+L+")."+(h?" Times in brackets are your local time ("+(h.split(" ").pop())+").":"")}
// Dee mascot in empty ('Not published') slots: animated SVG, static PNG pose when reduced motion is on
function deeArt(slot){var u='assets/dee/dee-'+slot;return '<div class="cdee" aria-hidden="true"><picture><source media="(prefers-reduced-motion: reduce)" srcset="'+u+'.png"><img src="'+u+'.svg" alt="" width="128" height="96" loading="lazy" decoding="async"></picture></div>'}
function slotCell(date,slot,big){
  var e=EDBY[date+"/"+slot], s=SINFO[slot];
  if(!e)return '<div class="cell miss" style="--c:'+SLOTCOL[slot]+'" title="'+esc(tzTip(date,slot))+'"><div class="ck"><span>'+esc(s.label.split(" · ")[0])+tzs(date,slot,false)+'</span><span>'+esc(s.label.split(" · ")[1])+'</span></div>'+deeArt(slot)+'<div class="cm">'+missText(date,slot)+(big&&missLoc(date,slot)?'<small class="cm-loc">'+esc(missLoc(date,slot))+'</small>':'')+'</div></div>';
  var th=big&&(e.thumb||e.header);
  return '<a class="cell'+(e.kind==="report"?" report":"")+'" style="--c:'+SLOTCOL[slot]+'" href="'+esc(edHref(e))+'"'+edAttrs(e)+'>'+
    (th?'<div class="cth"><img src="'+esc(th)+'" alt="" loading="lazy" decoding="async"></div>':'')+
    '<div class="ck" title="'+esc(tzTip(e.date,e.slot))+'"><span>'+esc(e.time)+tzs(e.date,e.slot,big)+'</span><span>'+esc(e.title)+'</span>'+(e.kind==="report"?'<em>Report</em>':'')+'</div>'+
    '<div class="ch">'+esc(e.headline)+'</div><div class="cf"><b>'+n(e.item_count)+'</b> items <span>'+(e.kind==="report"?"Read report ↓":"Open edition →")+'</span></div></a>';
}
/* from 5 AM Pacific the new day's archive row is ready before anything publishes: an empty day (four 'Not published' Dee slots)
   at the top of the archive. The Latest strip skips it and keeps the last day that has an edition. Only the page's copy of the calendar changes; it is never counted as published. */
function ptNow(){try{var p={};new Intl.DateTimeFormat("en-CA",{timeZone:"America/Vancouver",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",hourCycle:"h23"})
  .formatToParts(new Date()).forEach(function(x){p[x.type]=x.value});return {date:p.year+"-"+p.month+"-"+p.day,h:(+p.hour)%24}}catch(e){return null}}
function readyToday(){var t=ptNow();if(!t||!/^\d{4}-\d\d-\d\d$/.test(t.date)||t.h<5)return;
  if(CAL.some(function(c){return c.date===t.date})||(CAL[0]&&t.date<CAL[0].date))return;
  CAL.unshift({date:t.date,slots:[],ready:true})}
function renderLatest(){fillTz();
  // the most recent day with at least one edition: the 5 AM empty day row is archive-only
  var L=CAL.filter(function(c){return c.slots.length})[0], d=L?L.date:null; if(!d)return;
  $("#latest-h").innerHTML='Latest · '+esc(niceDate(d))+' <span class="lnote">'+L.slots.length+' of 4 editions published</span>';
  $("#latest").innerHTML=SLOTS.map(function(s){return slotCell(d,s,true)}).join("");
}
/* archive: paged in place. The default view is the newest 8 days (the 5 AM empty row counts as today); each Older step
   replaces it with the 14 days before. Unfiltered pages are fixed calendar windows counted back from the newest day (forward
   from the oldest when sorted oldest first), so #archive=<first date of the page> always opens the same days. With a search or
   filter, pages count matching days instead: the first 8, then 14 each. Only the current page's rows are rendered. */
var MAINT={}, LAUNCH={}; // special days (index.json 'special', from tools/special-days.json): maintenance = red, no row, never published; launch = aqua-green, clickable only if it has editions
var AFIRST=8, ASTEP=14, ARCH={blocks:[],i:0,list:[]}, ARCH_MATCH=null, PUSH=false;
function archiveDays(){
  return CAL.filter(function(c){if(!inRange(c.date))return false;if(state.slot.length&&!c.slots.some(function(s){return state.slot.indexOf(s)>=0}))return false;
    if(ARCH_MATCH&&!ARCH_MATCH[c.date])return false;return true});
}
function archBlocks(list){
  var old=state.sort==="old", out=[], i, fr, to;
  function win(a,b,rows){out.push({from:a,to:b,rows:rows.filter(function(c){return c.date>=a&&c.date<=b})})}
  if(!list.length)return out;
  if(!filtered()){
    var N=list[0].date, M=list[list.length-1].date;
    if(!old){for(i=0;;i++){to=i?addDays(N,-AFIRST-ASTEP*(i-1)):N;fr=addDays(to,-((i?ASTEP:AFIRST)-1));if(to<M)break;win(fr,to,list)}}
    else{var asc=list.slice().reverse();for(i=0;;i++){fr=i?addDays(M,AFIRST+ASTEP*(i-1)):M;to=addDays(fr,(i?ASTEP:AFIRST)-1);if(fr>N)break;win(fr,to,asc)}}
  } else {
    var L=old?list.slice().reverse():list;
    for(i=0;i<L.length;){var r=L.slice(i,i+(out.length?ASTEP:AFIRST));i+=r.length;
      var ds=r.map(function(c){return c.date}).sort();out.push({from:ds[0],to:ds[ds.length-1],rows:r})}
  }
  return out;
}
function archIndex(blocks,d){if(!d||!blocks.length)return 0;var best=0,bd=Infinity;
  for(var i=0;i<blocks.length;i++){var b=blocks[i];if(d>=b.from&&d<=b.to)return i;var x=Math.min(Math.abs(pd(d)-pd(b.from)),Math.abs(pd(d)-pd(b.to)));if(x<bd){bd=x;best=i}}
  return best}
function archRange(b){var l=ARCH.list, lo=b.from, hi=b.to;if(l.length){if(lo<l[l.length-1].date)lo=l[l.length-1].date;if(hi>l[0].date)hi=l[0].date}
  if(lo>hi){lo=b.from;hi=b.to}
  var y=String(ptNow()?ptNow().date:"").slice(0,4), o=function(d){return fmt(d,d.slice(0,4)===y?{month:"short",day:"numeric"}:{month:"short",day:"numeric",year:"numeric"})};
  return lo===hi?o(lo):o(lo)+" – "+o(hi)}
function archPager(pos){
  var b=ARCH.blocks, i=ARCH.i, old=state.sort==="old", f=filtered();if(b.length<2)return "";
  function btn(j,l,cls){return j<0||j>=b.length?'<button type="button" class="btn apg '+cls+'" disabled>'+l+'</button>':'<button type="button" class="btn apg '+cls+'" data-apage="'+j+'">'+l+'</button>'}
  return '<nav class="apager apager-'+pos+'" aria-label="Archive pages">'+btn(i-1,old?"← Earlier":"← Newer","apg-prev")+
    '<span class="arange"><b>'+esc(archRange(b[i]))+'</b><small>Page '+(i+1)+' of '+b.length+'</small></span>'+
    btn(i+1,(old?"Later ":"Older ")+(f?"14 days":"2 weeks")+" →","apg-next")+'</nav>'}
function archNote(pubDays,pubMonths,list){return n(pubDays)+" published day"+(pubDays==1?"":"s")+" in "+pubMonths+" month"+(pubMonths==1?"":"s")+(filtered()?" match the current search and filters":"")+". Click a day in a calendar to jump to it."}
function renderArchive(){
  var list=archiveDays(), by={}, months=[];
  ARCH.list=list;
  var blocks=archBlocks(list), bi=archIndex(blocks,state.archive), B=blocks[bi];
  state.archive=bi?B.from:""; ARCH.blocks=blocks; ARCH.i=bi;
  list.forEach(function(c){var m=c.date.slice(0,7);if(!by[m]){by[m]=[];months.push(m)}by[m].push(c)});
  document.querySelectorAll(".segb").forEach(function(b){b.setAttribute("aria-pressed",b.dataset.sort===state.sort)});
  var pubDays=pd_(list), pubMonths=months.filter(function(m){return by[m].some(function(c){return c.slots.length})}).length;
  $("#arch-note").innerHTML=months.length?archNote(pubDays,pubMonths,list):"No published days in this range.";
  var rows=B?B.rows:[], gm=[], g={};
  rows.forEach(function(c){var m=c.date.slice(0,7);if(!g[m]){g[m]=[];gm.push(m)}g[m].push(c)});
  var body=gm.map(function(m){
    var cnt=by[m].reduce(function(a,c){return a+c.slots.length},0), sh=SHARDS.filter(function(s){return s.month===m})[0];
    return '<details class="month" id="m-'+m+'" data-m="'+m+'" open><summary><div class="mt"><h3>'+esc(monthName(m))+'</h3>'+
      '<span>'+pd_(by[m])+' day'+(pd_(by[m])==1?'':'s')+' · '+cnt+' edition'+(cnt==1?'':'s')+(sh?' · '+n(sh.items)+' links':'')+'</span></div>'+heat(m)+'</summary>'+
      '<div class="days" data-days="'+m+'">'+daysHtml(g[m])+'</div></details>'}).join("");
  if(B&&!rows.length)body='<div class="empty arch-gap"><b>Nothing published '+esc(archRange(B))+'</b>Use the buttons to keep going.</div>';
  $("#archive").innerHTML=B?archPager("top")+body+archPager("bot"):"";
  $("#arch-more").hidden=true;
}
// scroll an element to just under the sticky search bar (taller on desktop, where the filters sit inside it)
function scrollUnder(el){if(!el)return;var sb=$(".searchbox"), off=(sb?sb.getBoundingClientRect().height:0)+14;
  window.scrollTo({top:Math.max(0,el.getBoundingClientRect().top+window.scrollY-off),behavior:"smooth"})}
function archTop(){scrollUnder($("#archive-block"))}
function goPage(j){var b=ARCH.blocks[j];if(!b)return;state.archive=j?b.from:"";PUSH=true;render();archTop()}
function pd_(list){return list.filter(function(c){return c.slots.length}).length}
function daysHtml(list){return list.map(function(c){
  return '<div class="day" id="d-'+c.date+'"><div class="dl"><b>'+esc(fmt(c.date,{day:"numeric"}))+'</b><span>'+esc(fmt(c.date,{weekday:"short"}))+'</span><small>'+c.slots.length+'/4</small></div>'+
    '<div class="daygrid'+(c.slots.length?'':' allmiss')+'">'+SLOTS.map(function(s){return slotCell(c.date,s,false)}).join("")+'</div></div>'}).join("")}
function heat(m){
  var first=pd(m+"-01"), dow=(first.getUTCDay()+6)%7, last=new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+1,0)).getUTCDate(), cells="";
  var pub={};CAL.forEach(function(c){if(c.date.slice(0,7)===m)pub[c.date]=c.slots.length});
  for(var i=0;i<dow;i++)cells+='<i class="pad"></i>';
  for(var d=1;d<=last;d++){var ds=m+"-"+(d<10?"0":"")+d, k=pub[ds]||0;
    cells+=k?'<button type="button" class="hd l'+k+(LAUNCH[ds]?' lch':'')+(inRange(ds)?'':' out')+'" data-day="'+ds+'" title="'+esc(niceDate(ds))+': '+(LAUNCH[ds]?'Launch day · ':'')+k+' of 4 editions">'+d+'</button>':LAUNCH[ds]?'<i class="hd lnch" role="img" title="'+esc(niceDate(ds))+': Launch day" aria-label="'+esc(niceDate(ds))+': Launch day">'+d+'</i>':MAINT[ds]?'<i class="hd mnt" role="img" title="'+esc(niceDate(ds))+': Maintenance · nothing published" aria-label="'+esc(niceDate(ds))+': Maintenance · nothing published">'+d+'</i>'
      :'<i class="hd l0" title="'+esc(niceDate(ds))+': nothing published">'+d+'</i>'}
  return '<div class="heat" aria-label="Calendar of published days"><div class="hw"><i>M</i><i>T</i><i>W</i><i>T</i><i>F</i><i>S</i><i>S</i></div><div class="hg">'+cells+'</div></div>';
}
function jumpTo(m,day){
  function has(){return ARCH.list.some(function(c){return day?c.date===day:c.date.slice(0,7)===m})}
  if(!has()){state.from="";state.to="";$("#from").value="";$("#to").value="";state.slot=[];render();
    if(!has()){state.q="";$("#q").value="";state.medium=[];state.type=[];state.tag=[];render()}}
  var pick=day;
  if(!pick){var hit=ARCH.list.filter(function(c){return c.date.slice(0,7)===m});if(!hit.length)return;pick=(state.sort==="old"?hit[hit.length-1]:hit[0]).date}
  state.archive=pick;PUSH=true;render();
  var target=day?document.getElementById("d-"+day):document.getElementById("m-"+m);
  if(target){scrollUnder(target);if(day){target.classList.add("flash");setTimeout(function(){target.classList.remove("flash")},1800)}}
}
function hl(text,toks){
  text=String(text||""); if(!toks.length)return esc(text);
  var low=text.toLowerCase(), marks=[];
  toks.forEach(function(t){var i=0;while(t&&(i=low.indexOf(t,i))>=0){marks.push([i,i+t.length]);i+=t.length}});
  if(!marks.length)return esc(text);
  marks.sort(function(a,b){return a[0]-b[0]});var out="",pos=0;
  marks.forEach(function(m){if(m[0]<pos)return;out+=esc(text.slice(pos,m[0]))+"<mark>"+esc(text.slice(m[0],m[1]))+"</mark>";pos=m[1]});
  return out+esc(text.slice(pos));
}
function frag(t){return "#:~:text="+encodeURIComponent(t.split(/\s+/).slice(0,7).join(" ")).replace(/-/g,"%2D").replace(/,/g,"%2C")}
function itemRow(it,toks){
  var s=SINFO[it.slot]||{label:""};
  var meta=['<span class="src">'+hl(it.author||it.source,toks)+'</span>'];
  if(it.author&&it.source)meta.push('<span>'+hl(it.source,toks)+'</span>');
  if(it.item_date)meta.push('<span>'+esc(it.item_date)+'</span>');
  if(it.engagement)meta.push('<span class="eng">'+esc(it.engagement)+'</span>');
  meta.push('<span>'+slotLab(it.slot,it.date)+' · '+esc(niceDate(it.date))+'</span>');
  var tags=(it.tags||[]).map(function(t){return '<button type="button" data-tagclick="'+esc(t)+'">'+esc(tagLabel(t))+'</button>'}).join("");
  var xl=(it.links||[]).map(function(l){return '<a href="'+esc(l.url)+'" target="_blank" rel="noopener">'+hl(l.label,toks)+' ↗</a>'}).join("");
  var ed=it.edition_kind==="report"?'<a href="#report='+esc(it.date+"/"+it.slot)+'" data-report="'+esc(it.date+"/"+it.slot)+'">Read report ↓</a>':'<a href="'+esc(it.edition+frag(it.title))+'">In edition →</a>';
  return '<article class="it" style="--c:'+SLOTCOL[it.slot]+'"><span class="bar"></span><div>'+
    '<div class="meta">'+meta.join("<span>·</span>")+'</div>'+
    '<h4><a href="'+esc(it.url)+'" target="_blank" rel="noopener">'+hl(it.title,toks)+'</a></h4>'+
    (it.note?'<p>'+hl(it.note,toks)+'</p>':'')+(xl?'<div class="xl">'+xl+'</div>':'')+'<div class="tags">'+tags+'</div></div>'+
    '<div class="acts"><a class="go" href="'+esc(it.url)+'" target="_blank" rel="noopener">Open source ↗</a>'+ed+'</div></article>';
}
function tagLabel(t){if(MLABEL[t])return MLABEL[t];if(SLABEL[t])return SLABEL[t].split(" · ")[0];if(/^\d{4}-\d\d-\d\d$/.test(t))return niceDate(t);return TLABEL[t]||cap(t)}
function groupOf(t){if(MLABEL[t])return"medium";if(SLABEL[t])return"slot";if(/^\d{4}-\d\d-\d\d$/.test(t))return"date";if(D.facets.type.indexOf(t)>=0)return"type";return"tag"}
function reset(keep){shown=PAGE;eshown=EPAGE;if(!keep)state.archive=""}
function toggle(g,k){var a=state[g],i=a.indexOf(k);if(i>=0)a.splice(i,1);else a.push(k);reset();render()}

/* ---------------- inline report reader ---------------- */
var markedP=null;
function loadMarked(){if(window.marked)return Promise.resolve(window.marked);if(markedP)return markedP;
  markedP=new Promise(function(res,rej){var s=document.createElement("script");s.src="assets/vendor/marked.min.js";s.onload=function(){res(window.marked)};s.onerror=function(){markedP=null;rej()};document.head.appendChild(s)});return markedP}
function openFromClick(key){state.report=key;state.part="";openKey=null;writeHash();syncReader(true)}
function ttsStop(){if(window.DDTTS)window.DDTTS.stop()}
function closeReport(){ttsStop();$("#reader").hidden=true;openKey=null;state.report="";state.part="";writeHash()}
/* marker anchors: reports/<date>/<slot>.parts.json lists every part's permanent id in document order (the static report page
   carries the same ids). The reader renders the Markdown itself, so ids are put on the matching elements here, checked by text. */
var partShown="";
function ptxt(s){return String(s||"").toLowerCase().normalize("NFD").replace(/[^a-z0-9]+/g,"").slice(0,40)}
function applyParts(root,doc){if(!doc||!doc.parts)return;var els=[];
  [].forEach.call(root.children,function(c){var t=c.tagName;if(t==="H1"||t==="HR"||t==="IMG")return;
    if(t==="UL"||t==="OL"){[].forEach.call(c.children,function(li){if(li.tagName==="LI")els.push(li)});return}
    if(t==="P"&&!c.textContent.trim())return;els.push(c)});
  var j=0;doc.parts.forEach(function(p){var want=ptxt(p.text);
    for(var k=j;k<Math.min(els.length,j+4);k++){if(ptxt(els[k].textContent)===want){els[k].id=p.id;j=k+1;return}}})}
function showPart(){var id=state.part;if(!id||!state.report){partShown="";return}
  var b=$("#rd-body"),el=document.getElementById(id);if(!el||!b.contains(el))return;
  [].forEach.call(b.querySelectorAll(".dd-part-hit"),function(x){x.classList.remove("dd-part-hit")});
  partShown=id;el.classList.add("dd-part-hit");scrollUnder(el);
  // the header image can finish loading after the jump and push the part down: aim again once it has
  var h=b.querySelector(".rd-hdr");if(h&&!h.complete)h.addEventListener("load",function(){if(partShown===id)scrollUnder(el)},{once:true})}
function clean(root,base){
  root.querySelectorAll("script,iframe,object,embed,style,link,meta,form,input,button").forEach(function(x){x.remove()});
  root.querySelectorAll("*").forEach(function(x){[].slice.call(x.attributes).forEach(function(a){
    if(/^on/i.test(a.name)||/^\s*(javascript|vbscript|data):/i.test(a.value)&&/^(href|src|xlink:href|action)$/i.test(a.name))x.removeAttribute(a.name)})});
  root.querySelectorAll("img").forEach(function(i){var s=i.getAttribute("src")||"";if(s&&!/^(https?:|\/)/i.test(s))i.setAttribute("src",base+s);i.loading="lazy"});
  root.querySelectorAll("a[href]").forEach(function(a){var h=a.getAttribute("href");if(/^https?:/i.test(h)){a.target="_blank";a.rel="noopener"}else if(h&&h.charAt(0)!=="#")a.setAttribute("href",base+h)});
}
function syncReader(scroll){
  var r=$("#reader");
  if(!state.report){if(!r.hidden){ttsStop();r.hidden=true;openKey=null}return}
  if(openKey===state.report){if(state.part!==partShown)showPart();return}
  ttsStop();var e=EDBY[state.report]; openKey=state.report; r.hidden=false;
  if(!e||e.kind!=="report"){$("#rd-kick").textContent="Report";$("#rd-gh").removeAttribute("href");$("#rd-body").innerHTML='<div class="empty"><b>Report not found</b>It may not be published yet.</div>';return}
  r.style.setProperty("--c",SLOTCOL[e.slot]);
  $("#rd-kick").innerHTML='<span class="dot"></span>'+esc(e.time)+tzs(e.date,e.slot,true)+" · "+esc(e.title)+" · "+esc(niceDate(e.date))+' <b>Report</b>';
  $("#rd-gh").href=e.url;
  var body=$("#rd-body");body.innerHTML='<div class="empty">Loading report…</div>';
  var base=e.path.replace(/[^\/]+$/,""), hdrName=e.header?e.header.split("/").pop():"";
  setTimeout(function(){r.scrollIntoView({behavior:"smooth",block:"start"})},30);
  var pj=e.path.replace(/\.md$/,".parts.json");partShown="";
  Promise.all([loadMarked(),fetch(e.path).then(function(x){if(!x.ok)throw new Error(x.status);return x.text()}),
    fetch(pj).then(function(x){return x.ok?x.json():null}).catch(function(){return null})]).then(function(v){
    if(openKey!==e.date+"/"+e.slot)return;
    var tpl=document.createElement("template");tpl.innerHTML=v[0].parse(v[1],{gfm:true});var tmp=tpl.content;  // inert: images don't load before paths are fixed
    if(hdrName)tmp.querySelectorAll("img").forEach(function(i){if((i.getAttribute("src")||"").split("/").pop()===hdrName){var p=i.parentNode;i.remove();if(p&&p.tagName==="P"&&!p.textContent.trim())p.remove()}});
    clean(tmp,base);
    var box=document.createElement("div");box.appendChild(tmp);
    body.innerHTML=(e.header?'<img class="rd-hdr" src="'+esc(e.header)+'" alt="'+esc(e.title)+' header image">':'')+box.innerHTML;
    applyParts(body,v[2]);if(state.part)setTimeout(showPart,80);
  }).catch(function(){body.innerHTML='<div class="empty"><b>Could not load this report here</b><a href="'+esc(e.url)+'" target="_blank" rel="noopener">Read it on GitHub ↗</a></div>'});
}

/* ---------------- events ---------------- */
function bind(){
  var timer;$("#q").addEventListener("input",function(e){clearTimeout(timer);timer=setTimeout(function(){state.q=e.target.value.trim();reset();render()},120)});
  $("#filters").addEventListener("click",function(e){var c=e.target.closest(".chip");if(!c)return;
    if(c.dataset.tag){toggle("tag",c.dataset.tag);return}
    if(c.dataset.range){var r=rangeFor(c.dataset.range);state.from=r[0];state.to=r[1];$("#from").value=r[0];$("#to").value=r[1];reset();render();return}
    if(c.dataset.g)toggle(c.dataset.g,c.dataset.k)});
  ["from","to"].forEach(function(k){$("#"+k).addEventListener("change",function(e){state[k]=e.target.value||"";if(state.from&&state.to&&state.from>state.to){var t=state.from;state.from=state.to;state.to=t;$("#from").value=state.from;$("#to").value=state.to}reset();render()})});
  document.addEventListener("click",function(e){
    var a=e.target.closest("[data-report]");if(a&&!e.metaKey&&!e.ctrlKey){e.preventDefault();openFromClick(a.dataset.report);return}
    var b=e.target.closest("[data-tagclick]");if(b){var t=b.dataset.tagclick,g=groupOf(t);
      if(g==="date"){state.from=t;state.to=t;$("#from").value=t;$("#to").value=t;reset();render()}else if(state[g].indexOf(t)<0)toggle(g,t);
      window.scrollTo({top:$("#results").offsetTop-120,behavior:"smooth"});return}
    var h=e.target.closest("[data-day]");if(h){e.preventDefault();jumpTo(h.dataset.day.slice(0,7),h.dataset.day);return}
    var s=e.target.closest(".segb");if(s){if(state.sort!==s.dataset.sort){state.sort=s.dataset.sort;reset()}render();return}
    var pg=e.target.closest("[data-apage]");if(pg){goPage(+pg.dataset.apage);return}
  });
  $("#jump").addEventListener("change",function(e){if(e.target.value)jumpTo(e.target.value);e.target.value=""});
  if(window.DDTTS)window.DDTTS.attach($("#rd-tts-play"),$("#rd-tts-stop"),function(){var b=$("#rd-body");return b.querySelector(".empty")?null:b});
  $("#rd-close").addEventListener("click",closeReport);$("#rd-close2").addEventListener("click",closeReport);
  $("#clear").addEventListener("click",function(){var keep=state.report,srt=state.sort;state=blank();state.report=keep;state.sort=srt;$("#q").value="";$("#from").value="";$("#to").value="";reset();render()});
  $("#more").addEventListener("click",function(){shown+=PAGE;render()});
  $("#eds-more").addEventListener("click",function(){eshown+=EPAGE;render()});
  $("#ftoggle").addEventListener("click",function(){var f=$("#filters"),o=f.classList.toggle("open");this.setAttribute("aria-expanded",o)});
  window.addEventListener("hashchange",function(){var pa=state.archive;readHash();reset(true);render();if(state.archive!==pa)archTop()});
  document.addEventListener("keydown",function(e){if(e.key==="/"&&document.activeElement!==$("#q")&&!/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)){e.preventDefault();$("#q").focus()}
    if(e.key==="Escape"){if(document.activeElement===$("#q")){$("#q").value="";state.q="";render()}else if(!$("#reader").hidden)closeReport()}});
}
})();
