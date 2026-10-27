/* Daily Design read-aloud: uses the browser's built-in speech (Web Speech API).
   No external services, no keys, nothing leaves the browser. */
(function(){
"use strict";
var S=window.speechSynthesis, OK=!!(S&&window.SpeechSynthesisUtterance);

/* ---- voice: prefer well-known female English voices, else the first English voice ---- */
var PREF=[/Google UK English Female/i,/^Google US English$/i,
  /Microsoft (Aria|Jenny|Sonia|Libby|Natasha|Clara|Emma|Ava|Michelle|Molly|Neerja).*Natural/i,
  /^(Samantha|Karen|Moira|Tessa|Serena|Victoria|Fiona|Allison|Ava|Susan|Zoe|Kate)\b/i,
  /Zira/i,/female/i,/Microsoft (Hazel|Susan|Catherine|Heera|Linda)/i];
var voice=null, voicesReady=false;
function isEn(v){return /^en([-_]|$)/i.test(v.lang||"")}
function pickVoice(){
  var vs=OK?S.getVoices():[]; if(!vs.length)return null;
  var en=vs.filter(isEn);
  for(var i=0;i<PREF.length;i++)for(var j=0;j<en.length;j++)if(PREF[i].test(en[j].name))return en[j];
  return en.filter(function(v){return /^en[-_]US/i.test(v.lang)})[0]||en[0]||null;
}
function refreshVoice(){var v=pickVoice();if(v){voice=v;voicesReady=true}}
function whenVoices(cb){
  refreshVoice(); if(voicesReady){cb();return}
  var done=false;function go(){if(done)return;done=true;refreshVoice();cb()}
  S.addEventListener&&S.addEventListener("voiceschanged",go,{once:true});
  setTimeout(go,1200);  // some browsers never fire the event; speak with the default voice
}
if(OK){refreshVoice();if(S.addEventListener)S.addEventListener("voiceschanged",refreshVoice);else S.onvoiceschanged=refreshVoice}

/* ---- text extraction ---- */
var SKIP="script,style,noscript,template,svg,canvas,img,picture,video,audio,iframe,object,figure,pre,code,button,nav,select,input,textarea,label,kbd,footer,#dd-nav,#dd-foot,.dd-credit,.dd-contactln,.dd-spon,.dd-fill,.dd-tts,.rd-tts,[aria-hidden='true'],[hidden]";
var BLOCK=/^(P|LI|H[1-6]|BLOCKQUOTE|DIV|SECTION|ARTICLE|HEADER|MAIN|ASIDE|UL|OL|DL|DT|DD|TABLE|TR|TD|TH|CAPTION|FIGCAPTION|HR|BR|SUMMARY|DETAILS)$/;
var EMOJI=/[\u2190-\u21FF\u2300-\u23FF\u2460-\u27BF\u2B00-\u2BFF\uFE0F\u200D]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|\uD83E[\uDC00-\uDFFF]/g;
function norm(t){
  return t.replace(/https?:\/\/\S+/g," ").replace(/www\.\S+/g," ").replace(EMOJI," ")
    .replace(/[*_#`|>~]+/g," ").replace(/\s*·\s*/g,", ").replace(/\s+/g," ")
    .replace(/\s+([,.;:!?])/g,"$1").replace(/([,;:])\1+/g,"$1").replace(/^[\s,.;:]+/,"").trim();
}
function hiddenEl(el){if(el.hidden)return true;var cs=window.getComputedStyle?getComputedStyle(el):null;return !!cs&&(cs.display==="none"||cs.visibility==="hidden")}
function collect(root){
  var out=[],buf="";
  function flush(){var t=norm(buf);buf="";if(t&&/[A-Za-z0-9]/.test(t))out.push(/[.!?…:;]["'”’)]*$/.test(t)?t:t+".")}
  function walk(n){
    if(n.nodeType===3){buf+=n.nodeValue;return}
    if(n.nodeType!==1||n.matches(SKIP)||hiddenEl(n))return;
    var blk=BLOCK.test(n.tagName);if(blk)flush();
    for(var c=n.firstChild;c;c=c.nextSibling)walk(c);
    if(blk)flush();else buf+=" ";
  }
  walk(root);flush();return out;
}
/* split paragraphs into short pieces: long utterances stall in Chrome */
function chunk(paras,max){
  max=max||200;var out=[];
  paras.forEach(function(p){
    var sents=p.replace(/([.!?…]+["'”’)]*)\s+/g,"$1\u0001").split("\u0001"),cur="";
    sents.forEach(function(s){s=s.trim();if(!s)return;
      while(s.length>max){var cut=s.lastIndexOf(", ",max);if(cut<max/2)cut=s.lastIndexOf(" ",max);if(cut<1)cut=max;
        if(cur){out.push(cur);cur=""}out.push(s.slice(0,cut+1).trim());s=s.slice(cut+1).trim()}
      if(cur&&(cur+" "+s).length>max){out.push(cur);cur=s}else cur=cur?cur+" "+s:s});
    if(cur)out.push(cur);
  });
  return out;
}

/* ---- player (one at a time per page) ---- */
var players=[];
function Player(play,stop,getRoot){
  this.play=play;this.stop=stop;this.getRoot=getRoot;this.chunks=[];this.i=0;this.state="idle";this.gen=0;
  var me=this;
  play.addEventListener("click",function(){me.toggle()});
  stop.addEventListener("click",function(){me.reset();play.focus()});
  players.push(this);this.ui();
}
Player.prototype.ui=function(){
  var st=this.state,p=this.play,lab=p.querySelector(".tts-l"),ic=p.querySelector(".tts-i");
  var t=st==="playing"?"Pause":st==="paused"?"Resume":"Listen";
  if(lab)lab.textContent=t; if(ic)ic.textContent=st==="playing"?"❚❚":"▶";
  p.setAttribute("aria-label",st==="playing"?"Pause reading":st==="paused"?"Resume reading aloud":"Listen: read this page aloud");
  p.setAttribute("aria-pressed",st==="playing"?"true":"false");
  p.classList.toggle("on",st!=="idle");
  this.stop.hidden=st==="idle";
};
Player.prototype.toggle=function(){
  if(this.state==="playing"){this.pause();return}
  if(this.state==="paused"){this.resume();return}
  this.start();
};
Player.prototype.start=function(){
  players.forEach(function(o){if(o.state!=="idle")o.reset()});
  var root=this.getRoot();if(!root)return;
  this.chunks=chunk(collect(root));this.i=0;
  if(!this.chunks.length)return;
  this.state="playing";this.ui();S.cancel();
  var me=this,g=++this.gen;
  // speak the first piece inside the click (needed on iPhone), then keep going
  if(voicesReady||S.getVoices().length){refreshVoice();this.next()}else whenVoices(function(){if(g===me.gen&&me.state==="playing")me.next()});
};
Player.prototype.next=function(){
  if(this.state!=="playing")return;
  if(this.i>=this.chunks.length){this.reset();return}
  var me=this,g=this.gen,u=new SpeechSynthesisUtterance(this.chunks[this.i]);
  if(voice){u.voice=voice;u.lang=voice.lang}else u.lang="en-US";
  u.rate=1;u.pitch=1;
  u.onend=function(){if(g!==me.gen||me.state!=="playing")return;me.i++;me.next()};
  u.onerror=function(e){if(g!==me.gen||me.state!=="playing")return;if(e&&(e.error==="interrupted"||e.error==="canceled"))return;me.i++;me.next()};
  S.speak(u);
};
/* pause = cancel and remember the piece; resume restarts it. Native pause() is unreliable on Android. */
Player.prototype.pause=function(){this.gen++;this.state="paused";S.cancel();this.ui()};
Player.prototype.resume=function(){this.gen++;this.state="playing";this.ui();S.cancel();this.next()};
Player.prototype.reset=function(){this.gen++;var was=this.state;this.state="idle";this.i=0;if(was!=="idle")S.cancel();this.ui()};

var api={supported:OK,
  attach:function(play,stop,getRoot){if(!OK||!play||!stop)return null;play.hidden=false;return new Player(play,stop,getRoot)},
  stop:function(){players.forEach(function(p){p.reset()})},
  _collect:collect,_chunk:chunk,_voice:function(){return voice}};
window.DDTTS=api;
if(OK)window.addEventListener("pagehide",api.stop);

/* edition pages: auto-wire the button in the Daily Design nav bar */
function auto(){var p=document.getElementById("dd-tts-play"),s=document.getElementById("dd-tts-stop");
  if(p&&s)api.attach(p,s,function(){return document.querySelector("[data-tts-root]")||document.body})}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",auto);else auto();
})();
