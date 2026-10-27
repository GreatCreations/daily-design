/* Daily Design index: vanilla JS, no build step.
   data/index.json  -> editions, calendar, facets, totals, shard manifest
   data/items/<YYYY-MM>.json -> items for that month, fetched lazily */
(function(){
"use strict";
var D, EDS=[], EDBY={}, CAL=[], SHARDS=[], ITEMS=[], LOADED={}, LOADING={};
var PAGE=40, EPAGE=12, MPAGE=6;
var shown=PAGE, eshown=EPAGE, mshown=MPAGE, openKey=null, renderT=0;
var GROUPS=["slot","medium","type"], SLOTS=["morning","noon","best","hottest"];
var SLOTCOL={morning:"var(--amber)",noon:"var(--aqua)",best:"var(--violet)",hottest:"var(--flame)"};
var MLABEL={}, SLABEL={}, SINFO={}, TLABEL={"repo/tool":"Repo / tool","case study":"Case study"};
var state=blank();
function blank(){return {q:"",slot:[],medium:[],type:[],tag:[],from:"",to:"",sort:"new",report:""}}
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
  D=data; EDS=D.editions; CAL=D.calendar.slice(); readyToday(); SHARDS=D.shards;
  D.facets.medium.forEach(function(m){MLABEL[m.key]=m.label});
  D.facets.slot.forEach(function(s){SLABEL[s.key]=s.label;SINFO[s.key]=s});
  EDS.forEach(function(e){EDBY[e.date+"/"+e.slot]=e;e._hay=norm([e.title,e.headline,e.summary,e.date,niceDate(e.date),e.slot,e.time,e.kind==="report"?"report":""].join(" "))});
  var t=D.totals;
  $('[data-k="editions"]').textContent=n(t.editions);$('[data-k="items"]').textContent=n(t.items);$('[data-k="tags"]').textContent=n(t.tags);
  $("#totals-note").textContent=n(t.days)+" day"+(t.days==1?"":"s")+" · "+n(t.months)+" month"+(t.months==1?"":"s")+" · latest "+niceDate(t.last);
  $("#updated").textContent="Updated "+niceDate(t.last);
  buildFilters(); buildJump(); readHash(); bind(); renderLatest(); render();
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
    html+='<div class="fgroup"><span class="lab">'+d[1]+'</span><div class="chips">';
    d[2].forEach(function(k){var c=d[0]==="slot"?' style="--c:'+SLOTCOL[k]+'"':"";
      html+='<button class="chip" type="button" data-g="'+d[0]+'" data-k="'+esc(k)+'" aria-pressed="false"'+c+'>'+(d[0]==="slot"?'<span class="sw"></span>':"")+esc(label(d[0],k))+' <span class="n"></span></button>'});
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
    else if(k==="date"&&v){var ds=v.split(",").sort();state.from=ds[0];state.to=ds[ds.length-1]}
    else if(Array.isArray(state[k])&&v)state[k]=v.split(",").filter(Boolean)});
  $("#q").value=state.q;$("#from").value=state.from;$("#to").value=state.to;
}
function writeHash(){
  var parts=[];if(state.q)parts.push("q="+encodeURIComponent(state.q));
  GROUPS.concat(["tag"]).forEach(function(g){if(state[g].length)parts.push(g+"="+state[g].map(encodeURIComponent).join(","))});
  if(state.from)parts.push("from="+state.from);if(state.to)parts.push("to="+state.to);
  if(state.sort==="old")parts.push("sort=old");
  if(state.report)parts.push("report="+state.report.split("/").map(encodeURIComponent).join("/"));
  var h=parts.length?"#"+parts.join("&"):"";
  if(h!==location.hash)history.replaceState(null,"",h||location.pathname+location.search);
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
  var eb=$("#eds-block");
  if(act){
    var eds=EDS.filter(function(e){if(!edMatchBasic(e))return false;if(counts[e.path]||counts[e.url])return true;if(itemFilters())return false;
      return toks.every(function(t){return e._hay.indexOf(t)>=0})});
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
    '<div class="bd"><div class="k"><span>'+esc(e.time)+' · '+esc(e.title)+'</span><span>'+esc(niceDate(e.date))+'</span></div>'+
    '<h3>'+esc(e.headline)+'</h3><p>'+esc(e.summary)+'</p>'+
    '<div class="ft"><span><b>'+n(e.item_count)+'</b> items</span>'+(matches!=null?'<span><b>'+n(matches)+'</b> match'+(matches==1?'':'es')+'</span>':'')+'</div></div></a>';
}
// Dee mascot in empty ('Not published') slots: animated SVG, static PNG pose when reduced motion is on
function deeArt(slot){var u='assets/dee/dee-'+slot;return '<div class="cdee" aria-hidden="true"><picture><source media="(prefers-reduced-motion: reduce)" srcset="'+u+'.png"><img src="'+u+'.svg" alt="" width="128" height="96" loading="lazy" decoding="async"></picture></div>'}
function slotCell(date,slot,big){
  var e=EDBY[date+"/"+slot], s=SINFO[slot];
  if(!e)return '<div class="cell miss" style="--c:'+SLOTCOL[slot]+'"><div class="ck"><span>'+esc(s.label.split(" · ")[0])+'</span><span>'+esc(s.label.split(" · ")[1])+'</span></div>'+deeArt(slot)+'<div class="cm">Not published</div></div>';
  var th=big&&(e.thumb||e.header);
  return '<a class="cell'+(e.kind==="report"?" report":"")+'" style="--c:'+SLOTCOL[slot]+'" href="'+esc(edHref(e))+'"'+edAttrs(e)+'>'+
    (th?'<div class="cth"><img src="'+esc(th)+'" alt="" loading="lazy" decoding="async"></div>':'')+
    '<div class="ck"><span>'+esc(e.time)+'</span><span>'+esc(e.title)+'</span>'+(e.kind==="report"?'<em>Report</em>':'')+'</div>'+
    '<div class="ch">'+esc(e.headline)+'</div><div class="cf"><b>'+n(e.item_count)+'</b> items <span>'+(e.kind==="report"?"Read report ↓":"Open edition →")+'</span></div></a>';
}
/* from 5 AM Pacific the new day's archive row is ready before anything publishes: an empty day (four 'Not published' Dee slots)
   at the top of the archive. The Latest strip skips it and keeps the last day that has an edition. Only the page's copy of the calendar changes; it is never counted as published. */
function ptNow(){try{var p={};new Intl.DateTimeFormat("en-CA",{timeZone:"America/Vancouver",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",hourCycle:"h23"})
  .formatToParts(new Date()).forEach(function(x){p[x.type]=x.value});return {date:p.year+"-"+p.month+"-"+p.day,h:(+p.hour)%24}}catch(e){return null}}
function readyToday(){var t=ptNow();if(!t||!/^\d{4}-\d\d-\d\d$/.test(t.date)||t.h<5)return;
  if(CAL.some(function(c){return c.date===t.date})||(CAL[0]&&t.date<CAL[0].date))return;
  CAL.unshift({date:t.date,slots:[],ready:true})}
function renderLatest(){
  // the most recent day with at least one edition: the 5 AM empty day row is archive-only
  var L=CAL.filter(function(c){return c.slots.length})[0], d=L?L.date:null; if(!d)return;
  $("#latest-h").innerHTML='Latest · '+esc(niceDate(d))+' <span class="lnote">'+L.slots.length+' of 4 editions published</span>';
  $("#latest").innerHTML=SLOTS.map(function(s){return slotCell(d,s,true)}).join("");
}
/* archive: months -> days -> 4 slots; months render lazily when opened */
var openMonths={};
function archiveDays(){
  return CAL.filter(function(c){if(!inRange(c.date))return false;if(state.slot.length&&!c.slots.some(function(s){return state.slot.indexOf(s)>=0}))return false;return true});
}
function renderArchive(){
  var days=archiveDays(), months=[], by={};
  days.forEach(function(c){var m=c.date.slice(0,7);if(!by[m]){by[m]=[];months.push(m)}by[m].push(c)});
  if(state.sort==="old"){months.reverse();months.forEach(function(m){by[m].reverse()})}
  document.querySelectorAll(".segb").forEach(function(b){b.setAttribute("aria-pressed",b.dataset.sort===state.sort)});
  var pubDays=days.filter(function(c){return c.slots.length}).length, pubMonths=months.filter(function(m){return by[m].some(function(c){return c.slots.length})}).length;
  $("#arch-note").textContent=months.length?n(pubDays)+" published day"+(pubDays==1?"":"s")+" in "+pubMonths+" month"+(pubMonths==1?"":"s")+(filtered()?" match the current edition/date filters":"")+". Click a day in a calendar to jump to it.":"No published days in this range.";
  var vis=months.slice(0,mshown);
  if(Object.keys(openMonths).length===0)vis.slice(0,2).forEach(function(m){openMonths[m]=true});
  $("#archive").innerHTML=vis.map(function(m){
    var cnt=by[m].reduce(function(a,c){return a+c.slots.length},0), sh=SHARDS.filter(function(s){return s.month===m})[0];
    return '<details class="month" id="m-'+m+'" data-m="'+m+'"'+(openMonths[m]?" open":"")+'><summary><div class="mt"><h3>'+esc(monthName(m))+'</h3>'+
      '<span>'+pd_(by[m])+' day'+(pd_(by[m])==1?'':'s')+' · '+cnt+' edition'+(cnt==1?'':'s')+(sh?' · '+n(sh.items)+' links':'')+'</span></div>'+heat(m)+'</summary>'+
      '<div class="days" data-days="'+m+'">'+(openMonths[m]?daysHtml(by[m]):'')+'</div></details>'}).join("");
  $("#arch-more").hidden=months.length<=mshown;$("#arch-more").textContent=state.sort==="old"?"Later months ("+(months.length-mshown)+")":"Older months ("+(months.length-mshown)+")";
  ARCH_BY=by;
}
var ARCH_BY={};
function pd_(list){return list.filter(function(c){return c.slots.length}).length}
function daysHtml(list){return list.map(function(c){
  return '<div class="day" id="d-'+c.date+'"><div class="dl"><b>'+esc(fmt(c.date,{day:"numeric"}))+'</b><span>'+esc(fmt(c.date,{weekday:"short"}))+'</span><small>'+c.slots.length+'/4</small></div>'+
    '<div class="daygrid'+(c.slots.length?'':' allmiss')+'">'+SLOTS.map(function(s){return slotCell(c.date,s,false)}).join("")+'</div></div>'}).join("")}
function heat(m){
  var first=pd(m+"-01"), dow=(first.getUTCDay()+6)%7, last=new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+1,0)).getUTCDate(), cells="";
  var pub={};CAL.forEach(function(c){if(c.date.slice(0,7)===m)pub[c.date]=c.slots.length});
  for(var i=0;i<dow;i++)cells+='<i class="pad"></i>';
  for(var d=1;d<=last;d++){var ds=m+"-"+(d<10?"0":"")+d, k=pub[ds]||0;
    cells+=k?'<button type="button" class="hd l'+k+(inRange(ds)?'':' out')+'" data-day="'+ds+'" title="'+esc(niceDate(ds))+': '+k+' of 4 editions">'+d+'</button>':'<i class="hd l0" title="'+esc(niceDate(ds))+': nothing published">'+d+'</i>'}
  return '<div class="heat" aria-label="Calendar of published days"><div class="hw"><i>M</i><i>T</i><i>W</i><i>T</i><i>F</i><i>S</i><i>S</i></div><div class="hg">'+cells+'</div></div>';
}
function jumpTo(m,day){
  var idx=-1, months=Object.keys(ARCH_BY);
  if(!ARCH_BY[m]){state.from="";state.to="";$("#from").value="";$("#to").value="";}
  openMonths[m]=true; render();
  var keys=[].slice.call(document.querySelectorAll("#archive .month")).map(function(x){return x.dataset.m});
  while(keys.indexOf(m)<0&&mshown<1e4){mshown+=MPAGE;renderArchive();keys=[].slice.call(document.querySelectorAll("#archive .month")).map(function(x){return x.dataset.m})}
  var target=day?document.getElementById("d-"+day):document.getElementById("m-"+m);
  if(target){target.scrollIntoView({behavior:"smooth",block:"start"});if(day){target.classList.add("flash");setTimeout(function(){target.classList.remove("flash")},1800)}}
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
  meta.push('<span>'+esc(s.label)+' · '+esc(niceDate(it.date))+'</span>');
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
function reset(){shown=PAGE;eshown=EPAGE}
function toggle(g,k){var a=state[g],i=a.indexOf(k);if(i>=0)a.splice(i,1);else a.push(k);reset();render()}

/* ---------------- inline report reader ---------------- */
var markedP=null;
function loadMarked(){if(window.marked)return Promise.resolve(window.marked);if(markedP)return markedP;
  markedP=new Promise(function(res,rej){var s=document.createElement("script");s.src="assets/vendor/marked.min.js";s.onload=function(){res(window.marked)};s.onerror=function(){markedP=null;rej()};document.head.appendChild(s)});return markedP}
function openFromClick(key){state.report=key;openKey=null;writeHash();syncReader(true)}
function ttsStop(){if(window.DDTTS)window.DDTTS.stop()}
function closeReport(){ttsStop();$("#reader").hidden=true;openKey=null;state.report="";writeHash()}
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
  if(openKey===state.report)return;
  ttsStop();var e=EDBY[state.report]; openKey=state.report; r.hidden=false;
  if(!e||e.kind!=="report"){$("#rd-kick").textContent="Report";$("#rd-gh").removeAttribute("href");$("#rd-body").innerHTML='<div class="empty"><b>Report not found</b>It may not be published yet.</div>';return}
  r.style.setProperty("--c",SLOTCOL[e.slot]);
  $("#rd-kick").innerHTML='<span class="dot"></span>'+esc(e.time)+" · "+esc(e.title)+" · "+esc(niceDate(e.date))+' <b>Report</b>';
  $("#rd-gh").href=e.url;
  var body=$("#rd-body");body.innerHTML='<div class="empty">Loading report…</div>';
  var base=e.path.replace(/[^\/]+$/,""), hdrName=e.header?e.header.split("/").pop():"";
  setTimeout(function(){r.scrollIntoView({behavior:"smooth",block:"start"})},30);
  Promise.all([loadMarked(),fetch(e.path).then(function(x){if(!x.ok)throw new Error(x.status);return x.text()})]).then(function(v){
    if(openKey!==e.date+"/"+e.slot)return;
    var tpl=document.createElement("template");tpl.innerHTML=v[0].parse(v[1],{gfm:true});var tmp=tpl.content;  // inert: images don't load before paths are fixed
    if(hdrName)tmp.querySelectorAll("img").forEach(function(i){if((i.getAttribute("src")||"").split("/").pop()===hdrName){var p=i.parentNode;i.remove();if(p&&p.tagName==="P"&&!p.textContent.trim())p.remove()}});
    clean(tmp,base);
    var box=document.createElement("div");box.appendChild(tmp);
    body.innerHTML=(e.header?'<img class="rd-hdr" src="'+esc(e.header)+'" alt="'+esc(e.title)+' header image">':'')+box.innerHTML;
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
    var s=e.target.closest(".segb");if(s){if(state.sort!==s.dataset.sort){state.sort=s.dataset.sort;openMonths={};mshown=MPAGE}reset();render();return}
  });
  $("#archive").addEventListener("toggle",function(e){var d=e.target;if(!d.dataset||!d.dataset.m)return;openMonths[d.dataset.m]=d.open;
    var box=d.querySelector(".days");if(d.open&&!box.innerHTML)box.innerHTML=daysHtml(ARCH_BY[d.dataset.m]||[])},true);
  $("#jump").addEventListener("change",function(e){if(e.target.value)jumpTo(e.target.value);e.target.value=""});
  $("#arch-more").addEventListener("click",function(){mshown+=MPAGE;renderArchive()});
  if(window.DDTTS)window.DDTTS.attach($("#rd-tts-play"),$("#rd-tts-stop"),function(){var b=$("#rd-body");return b.querySelector(".empty")?null:b});
  $("#rd-close").addEventListener("click",closeReport);$("#rd-close2").addEventListener("click",closeReport);
  $("#clear").addEventListener("click",function(){var keep=state.report,srt=state.sort;state=blank();state.report=keep;state.sort=srt;$("#q").value="";$("#from").value="";$("#to").value="";reset();render()});
  $("#more").addEventListener("click",function(){shown+=PAGE;render()});
  $("#eds-more").addEventListener("click",function(){eshown+=EPAGE;render()});
  $("#ftoggle").addEventListener("click",function(){var f=$("#filters"),o=f.classList.toggle("open");this.setAttribute("aria-expanded",o)});
  window.addEventListener("hashchange",function(){readHash();reset();render()});
  document.addEventListener("keydown",function(e){if(e.key==="/"&&document.activeElement!==$("#q")&&!/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)){e.preventDefault();$("#q").focus()}
    if(e.key==="Escape"){if(document.activeElement===$("#q")){$("#q").value="";state.q="";render()}else if(!$("#reader").hidden)closeReport()}});
}
})();
