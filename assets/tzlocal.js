/* Daily Design: the visitor's own clock next to a Pacific time on static pages (edition and report headers).
   <span class="dd-loc" data-pt="2026-10-26T07:00:00-07:00" data-ptd="2026-10-26" hidden></span> -> "(3 PM GMT+1)", with the weekday when the
   visitor's date differs from the Pacific date. Stays hidden for visitors whose clock reads the same as Pacific, and without JS. */
(function(){try{
  var f=new Intl.DateTimeFormat(undefined,{hour:"numeric",minute:"2-digit",timeZoneName:"short"}),h12=/h1[12]/.test(f.resolvedOptions().hourCycle||"h12"),
      dk=new Intl.DateTimeFormat("en-CA",{year:"numeric",month:"2-digit",day:"2-digit"}),wd=new Intl.DateTimeFormat(undefined,{weekday:"short"});
  [].forEach.call(document.querySelectorAll(".dd-loc[data-pt]"),function(x){
    var v=x.getAttribute("data-pt"),m=v.match(/([+-])(\d\d):(\d\d)$/),d=new Date(v);if(!m||isNaN(d))return;
    if(-d.getTimezoneOffset()===(m[1]==="-"?-1:1)*(+m[2]*60+(+m[3])))return;
    var s=f.format(d);if(h12)s=s.replace(/:00(?=\D)/,"");if(dk.format(d)!==x.getAttribute("data-ptd"))s=wd.format(d)+" "+s;
    x.textContent="("+s+")";x.title="Your time";x.hidden=false});
}catch(e){}})();
