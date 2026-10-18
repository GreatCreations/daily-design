(function(){
"use strict";
var D, ITEMS=[], EDS=[], state={q:"",slot:[],medium:[],type:[],date:[],tag:[]}, shown=40, PAGE=60;
var GROUPS=["slot","medium","type","date"];
var $=function(s){return document.querySelector(s)};
var SLOTCOL={morning:"var(--amber)",noon:"var(--aqua)",best:"var(--violet)",hottest:"var(--flame)"};
var MLABEL={}, SLABEL={}, TLABEL={"repo/tool":"Repo / tool","case study":"Case study"};
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function norm(s){return String(s||"").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"")}
function cap(s){return s.charAt(0).toUpperCase()+s.slice(1)}
function niceDate(d){var p=d.split("-");var dt=new Date(Date.UTC(+p[0],+p[1]-1,+p[2]));return dt.toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric",year:"numeric",timeZone:"UTC"})}
function label(g,k){return g==="medium"?(MLABEL[k]||k):g==="slot"?(SLABEL[k]||k):g==="date"?niceDate(k):(TLABEL[k]||cap(k))}
function host(u){try{return new URL(u).hostname.replace(/^www\./,"")}catch(e){return ""}}

function init(data){
  D=data; EDS=D.editions; ITEMS=D.items;
  D.facets.medium.forEach(function(m){MLABEL[m.key]=m.label});
  D.facets.slot.forEach(function(s){SLABEL[s.key]=s.label});
  var edBy={}; EDS.forEach(function(e){edBy[e.path]=e;
    e._hay=norm([e.title,e.headline,e.summary,e.date,niceDate(e.date),e.slot,e.time].join(" "))});
  ITEMS.forEach(function(it){var e=edBy[it.edition]||{};it._ed=e;
    it._hay=norm([it.title,it.note,it.source,it.author,it.medium,MLABEL[it.medium],it.type,it.kind,(it.tags||[]).join(" "),
      (it.links||[]).map(function(l){return l.label}).join(" "),host(it.url),it.engagement,e.title,it.slot,it.date].join(" "))});
  // totals
  var t=D.totals;["editions","items","tags"].forEach(function(k){countUp(document.querySelector('[data-k="'+k+'"]'),t[k])});
  var dates=D.facets.date; $("#totals-note").textContent=t.days+" day"+(t.days==1?"":"s")+" of editions · latest "+(dates[0]?niceDate(dates[0]):"–");
  $("#updated").textContent=dates[0]?"Updated "+niceDate(dates[0]):"";
  buildFilters(); readHash(); bind(); render();
}
function countUp(el,n){if(el)el.textContent=Number(n).toLocaleString()}

function buildFilters(){
  var f=$("#filters"), html="";
  var defs=[["slot","Edition",D.facets.slot.map(function(s){return s.key})],["medium","Medium",D.facets.medium.map(function(m){return m.key})],
            ["type","Type",D.facets.type],["date","Date",D.facets.date]];
  defs.forEach(function(d){
    html+='<div class="fgroup"><span class="lab">'+d[1]+'</span><div class="chips" data-g="'+d[0]+'">';
    d[2].forEach(function(k){var c=d[0]==="slot"?' style="--c:'+SLOTCOL[k]+'"':"";
      html+='<button class="chip" type="button" data-g="'+d[0]+'" data-k="'+esc(k)+'" aria-pressed="false"'+c+'>'+(d[0]==="slot"?'<span class="sw"></span>':"")+esc(label(d[0],k))+' <span class="n"></span></button>'});
    html+='</div></div>';
  });
  html+='<div class="fgroup" id="tagrow" hidden><span class="lab">Tag</span><div class="chips" id="tagchips"></div></div>';
  f.innerHTML=html;
}
function readHash(){
  var h=location.hash.replace(/^#/,""); state={q:"",slot:[],medium:[],type:[],date:[],tag:[]};
  h.split("&").forEach(function(p){if(!p)return;var i=p.indexOf("=");var k=decodeURIComponent(i<0?p:p.slice(0,i)),v=i<0?"":decodeURIComponent(p.slice(i+1).replace(/\+/g," "));
    if(k==="q")state.q=v;else if(state[k]&&v)state[k]=v.split(",").filter(Boolean)});
  $("#q").value=state.q;
}
function writeHash(){
  var parts=[];if(state.q)parts.push("q="+encodeURIComponent(state.q));
  GROUPS.concat(["tag"]).forEach(function(g){if(state[g].length)parts.push(g+"="+state[g].map(encodeURIComponent).join(","))});
  var h=parts.length?"#"+parts.join("&"):"";
  if(h!==location.hash)history.replaceState(null,"",h||location.pathname+location.search);
}
function tokens(){return norm(state.q).split(/\s+/).filter(Boolean)}
function itemMatch(it,skip,toks){
  for(var i=0;i<toks.length;i++)if(it._hay.indexOf(toks[i])<0)return false;
  for(var g=0;g<GROUPS.length;g++){var G=GROUPS[g];if(G===skip||!state[G].length)continue;
    var v=G==="slot"?it.slot:G==="date"?it.date:it[G];if(state[G].indexOf(v)<0)return false}
  for(var j=0;j<state.tag.length;j++)if((it.tags||[]).indexOf(state.tag[j])<0)return false;
  return true;
}
function active(){return !!(state.q||state.tag.length||GROUPS.some(function(g){return state[g].length}))}

function render(){
  var toks=tokens(), act=active();
  var res=ITEMS.filter(function(it){return itemMatch(it,null,toks)});
  // chip counts (faceted)
  document.querySelectorAll(".chip[data-g]").forEach(function(c){var g=c.dataset.g,k=c.dataset.k;
    var n=ITEMS.reduce(function(a,it){var v=g==="slot"?it.slot:g==="date"?it.date:it[g];return a+(v===k&&itemMatch(it,g,toks)?1:0)},0);
    var on=state[g].indexOf(k)>=0;c.setAttribute("aria-pressed",on);c.querySelector(".n").textContent=n;c.classList.toggle("zero",!n&&!on)});
  var tr=$("#tagrow");tr.hidden=!state.tag.length;
  $("#tagchips").innerHTML=state.tag.map(function(t){return '<button class="chip" type="button" aria-pressed="true" data-tag="'+esc(t)+'">'+esc(cap(t))+' ✕</button>'}).join("");
  $("#clear").hidden=!act;
  // editions
  var counts={};res.forEach(function(it){counts[it.edition]=(counts[it.edition]||0)+1});
  var itemFilters=state.medium.length||state.type.length||state.tag.length;
  var eds=EDS.filter(function(e){
    if(state.slot.length&&state.slot.indexOf(e.slot)<0)return false;
    if(state.date.length&&state.date.indexOf(e.date)<0)return false;
    if(!toks.length&&!itemFilters)return true;
    if(counts[e.path])return true;
    if(itemFilters)return false;
    return toks.every(function(t){return e._hay.indexOf(t)>=0});
  });
  $("#eds").innerHTML=eds.map(function(e,i){return edCard(e,!act&&i===0,act?counts[e.path]||0:null)}).join("")||'<div class="empty">No editions match.</div>';
  $("#eds-eyebrow").textContent=(act?"Matching editions · ":"Editions · ")+eds.length;
  // items
  var list=res.slice().sort(function(a,b){return a.date<b.date?1:a.date>b.date?-1:0});
  $("#items").innerHTML=list.slice(0,shown).map(function(it){return itemRow(it,toks)}).join("")||
    '<div class="empty"><b>Nothing found</b>Try fewer words or clear a filter.</div>';
  $("#more").hidden=list.length<=shown; $("#more").textContent="Show more ("+(list.length-shown)+" left)";
  $("#items-eyebrow").textContent=(act?"Matching links · ":"Every link · ")+list.length;
  $("#status-title").textContent=act?(state.q?"Results for “"+state.q+"”":"Filtered view"):"All editions";
  $("#status-line").innerHTML="<b>"+list.length+"</b> link"+(list.length==1?"":"s")+" in <b>"+eds.length+"</b> edition"+(eds.length==1?"":"s")+(act?" · share this view by copying the URL":"");
  writeHash();
}
function edCard(e,feature,matches){
  var th=e.thumb||e.header;
  return '<a class="ed'+(feature?' feature':'')+'" style="--c:'+SLOTCOL[e.slot]+'" href="'+esc(e.path)+'">'+
    '<div class="th">'+(th?'<img src="'+esc(th)+'" alt="" loading="'+(feature?'eager':'lazy')+'" decoding="async">':'')+'</div>'+
    (feature?'<span class="new">Latest</span>':'')+
    '<div class="bd"><div class="k"><span>'+esc(e.time)+' · '+esc(e.title)+'</span><span>'+esc(niceDate(e.date))+'</span></div>'+
    '<h3>'+esc(e.headline)+'</h3><p>'+esc(e.summary)+'</p>'+
    '<div class="ft"><span><b>'+e.item_count+'</b> items</span>'+(matches!=null?'<span><b>'+matches+'</b> match'+(matches==1?'':'es')+'</span>':'<span>Read edition →</span>')+'</div></div></a>';
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
  var e=it._ed||{};
  var meta=['<span class="src">'+hl(it.author||it.source,toks)+'</span>'];
  if(it.author&&it.source)meta.push('<span>'+hl(it.source,toks)+'</span>');
  if(it.item_date)meta.push('<span>'+esc(it.item_date)+'</span>');
  if(it.engagement)meta.push('<span class="eng">'+esc(it.engagement)+'</span>');
  meta.push('<span>'+esc(e.time||"")+' '+esc(e.title||"")+' · '+esc(niceDate(it.date))+'</span>');
  var tags=(it.tags||[]).map(function(t){return '<button type="button" data-tagclick="'+esc(t)+'">'+esc(tagLabel(t))+'</button>'}).join("");
  var xl=(it.links||[]).map(function(l){return '<a href="'+esc(l.url)+'" target="_blank" rel="noopener">'+hl(l.label,toks)+' ↗</a>'}).join("");
  return '<article class="it" style="--c:'+SLOTCOL[it.slot]+'"><span class="bar"></span><div>'+
    '<div class="meta">'+meta.join("<span>·</span>")+'</div>'+
    '<h4><a href="'+esc(it.url)+'" target="_blank" rel="noopener">'+hl(it.title,toks)+'</a></h4>'+
    (it.note?'<p>'+hl(it.note,toks)+'</p>':'')+(xl?'<div class="xl">'+xl+'</div>':'')+'<div class="tags">'+tags+'</div></div>'+
    '<div class="acts"><a class="go" href="'+esc(it.url)+'" target="_blank" rel="noopener">Open source ↗</a><a href="'+esc(it.edition+frag(it.title))+'">In edition →</a></div></article>';
}
function tagLabel(t){if(MLABEL[t])return MLABEL[t];if(SLABEL[t])return SLABEL[t].split(" · ")[0];if(/^\d{4}-\d\d-\d\d$/.test(t))return niceDate(t);return TLABEL[t]||cap(t)}
function groupOf(t){if(MLABEL[t])return"medium";if(SLABEL[t])return"slot";if(/^\d{4}-\d\d-\d\d$/.test(t))return"date";if(D.facets.type.indexOf(t)>=0)return"type";return"tag"}
function toggle(g,k){var a=state[g],i=a.indexOf(k);if(i>=0)a.splice(i,1);else a.push(k);shown=40;render()}
function bind(){
  var timer;$("#q").addEventListener("input",function(e){clearTimeout(timer);timer=setTimeout(function(){state.q=e.target.value.trim();shown=40;render()},90)});
  $("#filters").addEventListener("click",function(e){var c=e.target.closest(".chip");if(!c)return;if(c.dataset.tag){toggle("tag",c.dataset.tag);return}toggle(c.dataset.g,c.dataset.k)});
  $("#items").addEventListener("click",function(e){var b=e.target.closest("[data-tagclick]");if(!b)return;var t=b.dataset.tagclick,g=groupOf(t);
    if(state[g].indexOf(t)<0)toggle(g,t);window.scrollTo({top:$("#results").offsetTop-120,behavior:"smooth"})});
  $("#clear").addEventListener("click",function(){state={q:"",slot:[],medium:[],type:[],date:[],tag:[]};$("#q").value="";shown=40;render()});
  $("#more").addEventListener("click",function(){shown+=PAGE;render()});
  $("#ftoggle").addEventListener("click",function(){var f=$("#filters"),o=f.classList.toggle("open");this.setAttribute("aria-expanded",o)});
  window.addEventListener("hashchange",function(){readHash();render()});
  document.addEventListener("keydown",function(e){if(e.key==="/"&&document.activeElement!==$("#q")){e.preventDefault();$("#q").focus()}
    if(e.key==="Escape"&&document.activeElement===$("#q")){$("#q").value="";state.q="";render()}});
}
if(window.DD_DATA)init(window.DD_DATA);
else fetch("data/index.json").then(function(r){return r.json()}).then(init).catch(function(){$("#items").innerHTML='<div class="empty"><b>Could not load the index</b></div>'});
})();
