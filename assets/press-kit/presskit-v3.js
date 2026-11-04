/* Daily Design press kit modal (about.html). Opens from [data-presskit] buttons and #press-kit. */
(function(){
if(window.__ddPK)return;window.__ddPK=1;
var B="assets/press-kit/",PKU="https://studios.greatcreations.art/daily-design/pk/";
var LOGOS=[
 ["Primary logo","DD icon + wordmark, for dark backgrounds","dd-logo-primary-transparent.png","dd-logo-primary.svg","d","primary"],
 ["Primary logo, on light","Dark ink, for light backgrounds","dd-logo-primary-on-light-transparent.png","dd-logo-primary-on-light.svg","l","primary-light"],
 ["DD icon","Official standalone mark","dd-icon-2048-transparent.png","dd-icon.svg","d","icon"],
 ["Original site wordmark","The header title, for dark backgrounds","dd-wordmark-original-site-transparent.png",null,"d","wordmark"],
 ["Original site wordmark, on light","Dark ink, for light backgrounds","dd-wordmark-original-site-on-light-transparent.png",null,"l","wordmark-light"],
 ["Title lockup","Secondary, for dark backgrounds","dd-title-lockup-transparent.png","dd-title-lockup.svg","d","title"],
 ["Title lockup, on light","Secondary, for light backgrounds","dd-title-lockup-on-light-transparent.png","dd-title-lockup-on-light.svg","l","title-light"]];
var DEE=[["plain","Plain"],["morning","AI Design Daily (7 AM)"],["noon","AI Design in Use (noon)"],["best","Best of the Day (6 PM)"],["hottest","Hottest Right Now (8 PM)"]];
var COLS=[["Amber","#f5a524"],["Aqua","#22e0cf"],["Violet","#9b6bff"],["Flame","#ff5a2e"],["Gold","#ffcf5a"],["Pill","#0b0b0e"]];
var GRADS=[["Title gradient","linear-gradient(90deg,#f5a524,#22e0cf 35%,#9b6bff 68%,#ff5a2e)"],["Icon gradient","linear-gradient(135deg,#f5a524,#ff5a2e 55%,#9b6bff)"],["Save badge gradient","linear-gradient(110deg,#f5a524 0%,#ffcf5a 30%,#fff3cf 45%,#ffcf5a 55%,#22e0cf 100%)"]];
var FONTS=[["Display (headings, title)",'font-family:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;',"serif"]];
var BOIL="Daily Design is a public archive of AI design research digests: four editions a day on how AI is changing creative work, across image, video, 3D, code/UI, sound, games and mashups. Every edition links straight to the original creators and sources, and the whole archive is searchable by medium, type, edition and date.";
var EMAIL="dailydesign@greatcreations.ca",SITE="https://studios.greatcreations.art/daily-design/",X="https://x.com/GreatCreations_";
function e(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
function cp(t,l){return '<button type="button" class="btn" data-copy="'+e(t)+'">'+e(l||"Copy link")+'</button>'}
function dl(f,l){return '<a class="btn" href="'+B+f+'" download>'+l+'</a>'}
var css='#pk-ov{position:fixed;inset:0;z-index:9999;background:rgba(5,5,8,.78);backdrop-filter:blur(6px);display:flex;align-items:flex-start;justify-content:center;padding:4vh 14px;overflow:auto}#pk-ov[hidden]{display:none}'
+'#pk-dlg{position:relative;width:min(1100px,100%);background:var(--bg2,#111117);color:var(--ink,#f1efe9);border:1px solid var(--line2,rgba(255,255,255,.16));border-top:3px solid var(--amber,#f5a524);border-radius:18px;padding:26px clamp(16px,3vw,32px) 30px;font:15px/1.5 var(--sans)}'
+'#pk-dlg h2{font:400 34px/1.1 var(--serif);margin:0 40px 4px 0}#pk-dlg h2 em{background:linear-gradient(90deg,#f5a524,#22e0cf 35%,#9b6bff 68%,#ff5a2e);-webkit-background-clip:text;background-clip:text;color:transparent;padding-right:.06em}#pk-dlg h3{font:700 11px/1 var(--sans);letter-spacing:.18em;text-transform:uppercase;color:var(--mut,#a7a39a);margin:28px 0 12px}'
+'.pk-x{position:absolute;top:14px;right:14px}'
+'.pk-g{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}.pk-t{background:var(--card,#15151c);border:1px solid var(--line,rgba(255,255,255,.08));border-radius:14px;padding:12px;display:flex;flex-direction:column;gap:8px}'
+'.pk-pv{height:130px;border-radius:10px;display:flex;align-items:center;justify-content:center;padding:12px;background:#09090c}.pk-pv.l{background:#fff}.pk-pv img{max-width:100%;max-height:100%}.pk-t b{font-size:14px}.pk-t small{color:var(--mut,#a7a39a);font-size:12px;line-height:1.35}'
+'.pk-bs{display:flex;flex-wrap:wrap;gap:6px;margin-top:auto}'
+'.pk-sw{height:64px;border-radius:10px;border:1px solid rgba(255,255,255,.12)}.pk-g.c{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}.pk-mono{font:12px var(--mono);color:var(--mut,#a7a39a);word-break:break-all}'
+'.pk-zip{margin-top:14px}#pk-dlg .btn{display:inline-flex;align-items:center;gap:8px;text-decoration:none;font-size:14px;padding:13px 16px}#pk-dlg .btn.pri{background:var(--amber);border-color:transparent;color:#0b0b0e;font-weight:800}#pk-dlg .btn.pri:hover{background:#ffb94a}'
+'@media(max-width:560px){#pk-ov{padding:0}#pk-dlg{border-radius:0;min-height:100%}.pk-g{grid-template-columns:1fr 1fr}.pk-pv{height:96px}.pk-g.c{grid-template-columns:1fr 1fr}}@media(max-width:380px){.pk-g{grid-template-columns:1fr}}';
var h='<div id="pk-dlg" role="dialog" aria-modal="true" aria-labelledby="pk-h" tabindex="-1"><button type="button" class="btn pk-x" aria-label="Close press kit">×</button>'
+'<h2 id="pk-h">Press <em>kit</em></h2><p style="color:var(--mut);margin:0">Logos, Dee Dee, colours and fonts for press and sponsors. Everything is free to use when writing about Daily Design.</p>'
+'<a class="btn pri pk-zip" href="'+B+'daily-design-press-kit.zip" download>Download the whole kit (.zip)</a>'
+'<h3>Logos and marks</h3><div class="pk-g">'+LOGOS.map(function(x){return '<div class="pk-t"><div class="pk-pv '+x[4]+'"><img loading="lazy" src="'+B+'thumbs/'+x[2]+'" alt="'+e(x[0])+'"></div><b>'+e(x[0])+'</b><small>'+e(x[1])+'</small><div class="pk-bs">'+dl(x[2],"PNG")+(x[3]?dl(x[3],"SVG"):"")+cp(PKU+x[5]+".png","Copy PNG link")+(x[3]?cp(PKU+x[5]+".svg","Copy SVG link"):"")+'</div></div>'}).join("")+'</div>'
+'<h3>Dee Dee, the mascot</h3><div class="pk-g">'+DEE.map(function(x){var p="deedee-"+x[0]+"-2048-transparent.png";return '<div class="pk-t"><div class="pk-pv"><img loading="lazy" src="'+B+'thumbs/'+p+'" alt="Dee Dee, '+e(x[1])+'"></div><b>Dee Dee · '+e(x[1])+'</b><div class="pk-bs">'+dl(p,"PNG")+dl("deedee-"+x[0]+".svg","SVG")+cp(PKU+"deedee-"+x[0]+".png","Copy PNG link")+cp(PKU+"deedee-"+x[0]+".svg","Copy SVG link")+'</div></div>'}).join("")+'</div>'
+'<h3>Colours</h3><div class="pk-g c">'+COLS.map(function(x){return '<div class="pk-t"><div class="pk-sw" style="background:'+x[1]+'"></div><b>'+x[0]+'</b><span class="pk-mono">'+x[1]+'</span><div class="pk-bs">'+cp(x[1],"Copy HEX")+'</div></div>'}).join("")+'</div>'
+'<div class="pk-g" style="margin-top:14px">'+GRADS.map(function(x){return '<div class="pk-t"><div class="pk-sw" style="background:'+x[1]+'"></div><b>'+x[0]+'</b><span class="pk-mono">'+x[1]+'</span><div class="pk-bs">'+cp("background:"+x[1]+";","Copy CSS")+'</div></div>'}).join("")+'</div>'
+'<h3>Fonts</h3><div class="pk-g">'+FONTS.map(function(x){return '<div class="pk-t"><div style="font:'+(x[2]=="serif"?'400 34px/1 var(--serif)':x[2]=="sans"?'700 30px/1 var(--sans)':'400 22px/1 var(--mono)')+'">Daily Design</div><b>'+x[0]+'</b><span class="pk-mono">'+e(x[1])+'</span><div class="pk-bs">'+cp(x[1],"Copy CSS")+'</div></div>'}).join("")+'</div>'
+'<small style="display:block;color:var(--dim,#76736c);margin-top:8px">The site uses system fonts, so no font files are needed. The logos are supplied as artwork.</small>'
+'<h3>About Daily Design</h3><div class="pk-t"><p style="margin:0">'+e(BOIL)+'</p><div class="pk-bs">'+cp(BOIL,"Copy text")+'</div></div>'
+'<h3>Contact and links</h3><div class="pk-g">'
+'<div class="pk-t"><b>Press and sponsors</b><span class="pk-mono">'+EMAIL+'</span><div class="pk-bs">'+cp(EMAIL,"Copy email")+'<a class="btn" href="mailto:'+EMAIL+'?subject=Daily%20Design%20press">Email</a></div></div>'
+'<div class="pk-t"><b>Website</b><span class="pk-mono">'+SITE+'</span><div class="pk-bs">'+cp(SITE)+'<a class="btn" href="'+SITE+'">Open</a></div></div>'
+'<div class="pk-t"><b>X · @GreatCreations_</b><span class="pk-mono">'+X+'</span><div class="pk-bs">'+cp(X)+'<a class="btn" href="'+X+'" target="_blank" rel="noopener">Open ↗</a></div></div>'
+'</div></div>';
var ov,dlg,last;
function build(){if(ov)return;var st=document.createElement("style");st.textContent=css;document.head.appendChild(st);ov=document.createElement("div");ov.id="pk-ov";ov.hidden=true;ov.innerHTML=h;document.body.appendChild(ov);dlg=ov.firstChild;
 ov.addEventListener("click",function(ev){if(ev.target===ov||ev.target.closest(".pk-x"))close();var b=ev.target.closest("[data-copy]");if(b)copy(b)});
 ov.addEventListener("keydown",function(ev){if(ev.key==="Escape"){ev.preventDefault();close()}if(ev.key==="Tab"){var f=[].slice.call(dlg.querySelectorAll('a[href],button')).filter(function(n){return n.offsetParent!==null});if(!f.length)return;var a=f[0],z=f[f.length-1];if(ev.shiftKey&&document.activeElement===a||document.activeElement===dlg&&ev.shiftKey){ev.preventDefault();z.focus()}else if(!ev.shiftKey&&document.activeElement===z){ev.preventDefault();a.focus()}}})}
function copy(b){var t=b.getAttribute("data-copy"),l=b.textContent;function ok(){b.textContent="Copied";b.classList.add("ok");setTimeout(function(){b.textContent=l;b.classList.remove("ok")},1600)}
 if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(ok,function(){fb(t);ok()})}else{fb(t);ok()}}
function fb(t){var a=document.createElement("textarea");a.value=t;a.style.position="fixed";a.style.opacity="0";document.body.appendChild(a);a.select();try{document.execCommand("copy")}catch(_){}a.remove()}
function open(){build();last=document.activeElement;ov.hidden=false;document.documentElement.style.overflow="hidden";dlg.focus({preventScroll:true});ov.scrollTop=0;if(location.hash!=="#press-kit")history.replaceState(null,"","#press-kit")}
function close(){if(!ov||ov.hidden)return;ov.hidden=true;document.documentElement.style.overflow="";if(location.hash==="#press-kit")history.replaceState(null,"",location.pathname+location.search);if(last&&last.focus)last.focus()}
document.addEventListener("click",function(ev){var t=ev.target.closest("[data-presskit],a[href$='#press-kit']");if(t&&!(ov&&ov.contains(t))){ev.preventDefault();open()}});
function chk(){if(location.hash==="#press-kit")open()}
window.addEventListener("hashchange",chk);if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",chk);else chk();
window.ddPressKit={open:open,close:close};
})();
