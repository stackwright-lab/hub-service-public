"""Interface du tableau de bord : une page HTML autonome (CSS + JS inclus, aucune dépendance externe)."""
from __future__ import annotations

import json

TEMPLATE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hub Service Public – santé des données</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap">
<style>
:root{color-scheme:light;--plane:#f5f6fa;--surface:#ffffff;--raise:#ffffff;--ink:#161616;--ink2:#3a3a3a;--muted:#666666;--line:#dddddd;
--blue:#16348f;--violet:#16348f;--good:#18753c;--warn:#b34000;--serious:#b34000;--crit:#c8102e;--neutral:#666666;--glow:transparent;--red:#c8102e;--blue-bg:#16348f}
:root[data-theme=dark]{color-scheme:dark;--plane:#121212;--surface:#1b1b1f;--raise:#242428;--ink:#eeeeee;--ink2:#cecece;--muted:#a6a6a6;--line:#353535;--blue:#8aa4ff;--violet:#8aa4ff;--good:#4fd07f;--warn:#ff9a5c;--serious:#ff9a5c;--crit:#ff6b7a;--red:#ff6b7a;--blue-bg:#2b48a8}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){color-scheme:dark;--plane:#121212;--surface:#1b1b1f;--raise:#242428;--ink:#eeeeee;--ink2:#cecece;--muted:#a6a6a6;--line:#353535;--blue:#8aa4ff;--violet:#8aa4ff;--good:#4fd07f;--warn:#ff9a5c;--serious:#ff9a5c;--crit:#ff6b7a;--red:#ff6b7a;--blue-bg:#2b48a8}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--plane);color:var(--ink);font:16px/1.5 "Source Sans 3",system-ui,-apple-system,"Segoe UI",sans-serif}
header.top{position:sticky;top:0;z-index:5;background:var(--surface);border-bottom:1px solid var(--line);box-shadow:0 2px 6px rgba(0,0,18,.06)}
.bar{max-width:1180px;margin:0 auto;padding:12px 20px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.logo{width:44px;height:44px;background:var(--blue-bg);display:grid;place-items:center;color:#fff;font-weight:700;font-size:15px;letter-spacing:.04em;border-bottom:4px solid var(--red)}
.bar h1{font-size:17px;margin:0;letter-spacing:.2px}.bar .sp{flex:1}
.pill{display:inline-flex;align-items:center;gap:7px;padding:5px 12px;border-radius:999px;border:1px solid var(--line);background:var(--surface);font-size:12.5px;color:var(--ink2)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--neutral)}.dot.on{background:var(--good);box-shadow:0 0 0 0 rgba(12,163,12,.6);animation:pulse 2s infinite}
@keyframes pulse{70%{box-shadow:0 0 0 8px rgba(12,163,12,0)}100%{box-shadow:0 0 0 0 rgba(12,163,12,0)}}
button,.btn{font:inherit;font-weight:600;font-size:13.5px;padding:7px 15px;border-radius:4px;border:1px solid var(--line);background:var(--surface);color:var(--ink);cursor:pointer}
button:hover{border-color:var(--blue)}button.primary{border:0;color:#fff;background:var(--blue-bg)}
button:disabled{opacity:.5;cursor:progress}
main{max-width:1180px;margin:0 auto;padding:22px 20px 60px}
.hero{margin:6px 0 20px}.hero h2{font-size:30px;line-height:1.15;margin:0 0 6px;font-weight:800}
.hero h2 span{color:var(--blue)}
.hero p{margin:0;color:var(--ink2);max-width:760px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin:18px 0 8px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:4px;padding:16px 18px}
.kpi{position:relative;overflow:hidden}.kpi:before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:var(--blue);opacity:.85}
.kpi b{display:block;font-size:30px;line-height:1.2;font-weight:800;margin-top:4px}.kpi span{color:var(--ink2);font-size:13px}
.delta{display:inline-block;margin-top:6px;font-size:12px;padding:1px 8px;border-radius:999px;border:1px solid var(--line);color:var(--ink2)}
.delta[hidden]{display:none}.delta.up{color:var(--warn);border-color:var(--warn)}.delta.ok{color:var(--good);border-color:var(--good)}
nav.tabs{display:flex;gap:6px;margin:26px 0 16px;overflow-x:auto;padding-bottom:4px}
nav.tabs button{border-radius:999px;white-space:nowrap}nav.tabs button[aria-selected=true]{background:var(--blue-bg);color:#fff;border-color:transparent}
section.panel{display:none}section.panel.on{display:block;animation:in .25s ease}@keyframes in{from{opacity:0;transform:translateY(6px)}}
.g2{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}
h3{font-size:15px;margin:0 0 4px}.sub{color:var(--ink2);font-size:13px;margin:0 0 10px}.note{color:var(--muted);font-size:12.5px}
.stack{display:flex;height:26px;gap:2px;border-radius:4px;overflow:hidden;margin:10px 0}.stack i{display:block;min-width:3px;transition:flex .5s}
.stack i:hover{filter:brightness(1.2)}
.leg{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--ink2)}.leg b{margin-right:4px}
.row{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(70px,1fr) 62px;gap:10px;align-items:center;font-size:13.5px;margin:7px 0}
.row .t{display:block;height:10px;background:var(--line);border-radius:5px;overflow:hidden}.row .t i{display:block;height:100%;border-radius:5px;background:var(--blue);transition:width .6s}
.row .v{text-align:right;font-variant-numeric:tabular-nums}
table{width:100%;border-collapse:collapse;font-size:13.5px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
th{color:var(--ink2);font-weight:600;cursor:pointer;user-select:none;white-space:nowrap}th:hover{color:var(--ink)}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.scroll{max-height:430px;overflow:auto;border-radius:4px}
input,select{font:inherit;font-size:13.5px;padding:7px 12px;border-radius:4px;border:1px solid var(--line);background:var(--raise);color:var(--ink)}
.tools{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 10px}.tools[hidden]{display:none}
.feed a{color:var(--ink);text-decoration:none}.feed a:hover{color:var(--blue)}.feed li{padding:8px 0;border-bottom:1px solid var(--line);list-style:none}
.feed ul{margin:0;padding:0}.feed small{display:block;color:var(--muted)}
.chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;font-size:12.5px;font-weight:600;border:1px solid currentColor}
.alert{display:flex;gap:10px;padding:10px 0;border-bottom:1px solid var(--line)}.alert:last-child{border:0}.alert i{font-style:normal;font-weight:800;width:20px}
.sgrid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:14px;align-items:start}@media(max-width:900px){.sgrid{grid-template-columns:1fr}}
.search{display:flex;gap:10px;flex-wrap:wrap}.search input[type=search]{flex:1;min-width:240px;font-size:16px;padding:12px 16px;border-radius:4px}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}.chips button{border-radius:999px;padding:5px 13px}.chips button[aria-pressed=true]{background:var(--blue-bg);color:#fff;border-color:transparent}
.res{padding:12px 14px;border:1px solid var(--line);border-radius:4px;margin:8px 0;cursor:pointer;background:var(--raise)}.res:hover,.res.sel{border-color:var(--blue)}
.res b{display:block}.res small{color:var(--ink2)}.res p{margin:4px 0 0;color:var(--ink2);font-size:13px}
.badge{display:inline-block;padding:1px 8px;margin:4px 6px 0 0;border-radius:999px;border:1px solid var(--line);font-size:12px;color:var(--ink2)}
.badge.ok{color:var(--good);border-color:var(--good)}.badge.w{color:var(--warn);border-color:var(--warn)}.badge.k{color:var(--crit);border-color:var(--crit)}
.detail{position:sticky;top:76px;max-height:calc(100vh - 96px);overflow:auto}.detail pre{white-space:pre-wrap;font:inherit;color:var(--ink2);margin:6px 0}
.kv{display:grid;grid-template-columns:130px 1fr;gap:4px 10px;font-size:13.5px;margin:8px 0}.kv dt{color:var(--muted)}.kv dd{margin:0;overflow-wrap:anywhere}
.dpe{display:flex;gap:14px;align-items:flex-start}.lab{min-width:52px;height:52px;border-radius:4px;display:grid;place-items:center;font-size:28px;font-weight:800;color:#0b0b0b}
.ex{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}.ex button{font-weight:500;font-size:12.5px;padding:3px 11px;border-radius:999px}
.grp{font-size:12.5px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);margin:14px 0 2px}
a.lnk{color:var(--blue);text-decoration:none}a.lnk:hover{text-decoration:underline}
#tip{position:fixed;z-index:20;pointer-events:none;background:var(--raise);border:1px solid var(--line);border-radius:4px;padding:6px 10px;font-size:12.5px;box-shadow:0 8px 24px rgba(0,0,0,.35);display:none;max-width:280px}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style></head><body>
<header class="top"><div class="bar">
<div class="logo" aria-hidden="true">HSP</div><h1>Hub Service Public</h1><span class="sp"></span>
<span class="pill" id="live"><span class="dot" id="dot"></span><span id="livetxt">Mode statique</span></span>
<button id="theme" type="button" aria-label="Changer de thème">Thème</button>
<button id="upd" type="button" class="primary" hidden>Mettre à jour</button>
</div></header>
<main>
<div class="hero"><h2>La santé des données du <span>service public</span></h2>
<p id="asof"></p></div>
<div class="kpis" id="kpis"></div>
<nav class="tabs" role="tablist" id="tabs"></nav>
<section class="panel" id="p-search"></section>
<section class="panel" id="p-overview"></section>
<section class="panel" id="p-datasets"></section>
<section class="panel" id="p-apis"></section>
<section class="panel" id="p-eco"></section>
<section class="panel" id="p-services"></section>
<noscript><p>Ce tableau de bord nécessite JavaScript.</p></noscript>
<p class="note" style="margin-top:34px">Projet indépendant et open source, non affilié à l’administration. La fraîcheur dépend de la périodicité déclarée par le producteur. La complétude décrit les métadonnées, pas la qualité des valeurs. Ce tableau de bord n'est pas un contrôle officiel.</p>
</main>
<div id="tip" role="tooltip"></div>
<script type="application/json" id="data">__DATA__</script>
<script>
(function(){
"use strict";
var D=JSON.parse(document.getElementById('data').textContent), TOKEN=__TOKEN__, LIVE=null;
var $=function(s,r){return (r||document).querySelector(s)};
var nf=new Intl.NumberFormat('fr-FR');
function n(v){return v==null?'–':nf.format(v)}
function pct(a,b){return b?(100*a/b).toFixed(1).replace('.',','):'0'}
function el(tag,attrs,kids){var e=document.createElement(tag);for(var k in (attrs||{})){if(k==='class')e.className=attrs[k];else if(k==='html')e.innerHTML=attrs[k];else e.setAttribute(k,attrs[k]);}
 (kids||[]).forEach(function(c){e.appendChild(typeof c==='string'?document.createTextNode(c):c)});return e}
var ST={a_jour:['À jour','var(--good)','✓'],en_retard:['En retard','var(--warn)','!'],perime:['Périmé','var(--crit)','✕'],sans_engagement:['Sans engagement','var(--neutral)','–']};
var FREQ={continuous:'Continu',severalTimesADay:'Plusieurs fois/jour',daily:'Quotidien',threeTimesAWeek:'3 fois/semaine',weekly:'Hebdomadaire',biweekly:'Bimensuel',threeTimesAMonth:'3 fois/mois',monthly:'Mensuel',bimonthly:'Tous les 2 mois',quarterly:'Trimestriel',threeTimesAYear:'3 fois/an',semiannual:'Semestriel',annual:'Annuel',biennial:'Tous les 2 ans',triennial:'Tous les 3 ans',quinquennial:'Tous les 5 ans'};

/* ---------- infobulle ---------- */
var tip=$('#tip');
document.addEventListener('mousemove',function(e){var t=e.target.closest&&e.target.closest('[data-tip]');
 if(!t){tip.style.display='none';return}tip.textContent=t.getAttribute('data-tip');tip.style.display='block';
 var x=Math.min(e.clientX+14,innerWidth-tip.offsetWidth-8),y=Math.min(e.clientY+16,innerHeight-tip.offsetHeight-8);tip.style.left=x+'px';tip.style.top=y+'px'});

/* ---------- briques ---------- */
function stack(parts){var tot=parts.reduce(function(a,p){return a+p.v},0)||1;
 var bar=el('div',{class:'stack',role:'img','aria-label':'répartition'});
 parts.forEach(function(p){if(!p.v)return;var i=el('i',{'data-tip':p.l+' : '+n(p.v)+' ('+pct(p.v,tot)+' %)'});i.style.flex=p.v;i.style.background=p.c;bar.appendChild(i)});
 var leg=el('div',{class:'leg'});parts.forEach(function(p){var b=el('b',{},[p.i]);b.style.color=p.c;leg.appendChild(el('span',{},[b,p.l+' · '+n(p.v)+' ('+pct(p.v,tot)+' %)']))});
 return el('div',{},[bar,leg])}
function bars(rows,suffix){var mx=Math.max.apply(null,rows.map(function(r){return r[1]}).concat([1]));
 var w=el('div');rows.forEach(function(r){var t=el('span',{class:'t'});var i=el('i');i.style.width=(100*r[1]/mx)+'%';t.appendChild(i);
 w.appendChild(el('div',{class:'row','data-tip':r[0]+' : '+n(r[1])},[el('span',{},[r[0]]),t,el('span',{class:'v'},[n(r[1])+(suffix||'')])]))});return w}
function card(title,sub,body,wide){var c=el('div',{class:'card'},[el('h3',{},[title])]);if(sub)c.appendChild(el('p',{class:'sub'},[sub]));(body||[]).forEach(function(b){c.appendChild(b)});if(wide)c.style.gridColumn='1/-1';return c}
function table(head,rows,opts){opts=opts||{};var state={col:opts.sort==null?-1:opts.sort,dir:-1,q:''};
 var wrap=el('div'),tools=el('div',{class:'tools'}),inp=el('input',{type:'search',placeholder:'Filtrer…','aria-label':'Filtrer le tableau'});
 if(opts.search)tools.appendChild(inp);wrap.appendChild(tools);
 var sc=el('div',{class:'scroll'}),tb=el('table'),thead=el('thead'),tr=el('tr');
 head.forEach(function(h,i){var th=el('th',{class:(opts.num||[]).indexOf(i)>=0?'n':''},[h]);th.addEventListener('click',function(){state.dir=state.col===i?-state.dir:-1;state.col=i;draw()});tr.appendChild(th)});
 thead.appendChild(tr);var tbody=el('tbody');tb.appendChild(thead);tb.appendChild(tbody);sc.appendChild(tb);wrap.appendChild(sc);
 function draw(){var r=rows.filter(function(x){return !state.q||x.join(' ').toLowerCase().indexOf(state.q)>=0});
  if(state.col>=0)r=r.slice().sort(function(a,b){var u=a[state.col],v=b[state.col];return (typeof u==='number'&&typeof v==='number'?u-v:String(u).localeCompare(String(v),'fr'))*state.dir});
  tbody.textContent='';r.slice(0,opts.limit||300).forEach(function(row){var t=el('tr');row.forEach(function(c,i){var num=(opts.num||[]).indexOf(i)>=0;
   var td=el('td',{class:num?'n':''},[typeof c==='number'?n(c):String(c)]);t.appendChild(td)});tbody.appendChild(t)});
  if(!r.length)tbody.appendChild(el('tr',{},[el('td',{colspan:head.length},['Aucun résultat'])]))}
 inp.addEventListener('input',function(){state.q=inp.value.toLowerCase();draw()});draw();return wrap}
function grid(items){return el('div',{class:'g2'},items)}
function chip(ok,label){var c=el('span',{class:'chip'},[(ok?'✓ ':'✕ ')+label]);c.style.color=ok?'var(--good)':'var(--crit)';return c}
function ago(iso){if(!iso)return 'jamais';var s=Math.max(0,(Date.now()-new Date(iso).getTime())/1000);
 if(s<90)return 'il y a '+Math.round(s)+' s';if(s<5400)return 'il y a '+Math.round(s/60)+' min';if(s<129600)return 'il y a '+Math.round(s/3600)+' h';return 'il y a '+Math.round(s/86400)+' j'}

/* ---------- KPI ---------- */
var KP=[['datasets','jeux de données','datasets'],['resources','fichiers',null],['dataservices','API','dataservices'],['organizations','organisations','organizations'],['reuses','réutilisations','reuses'],['discussions','discussions','discussions']];
function countUp(node,target){var t0=performance.now(),d=700;function f(t){var k=Math.min(1,(t-t0)/d);node.textContent=nf.format(Math.round(target*(1-Math.pow(1-k,3))));if(k<1)requestAnimationFrame(f)}requestAnimationFrame(f)}
var kpiNodes={};
function buildKpis(){var box=$('#kpis');box.textContent='';KP.forEach(function(k){var b=el('b'),dl=el('span',{class:'delta'});dl.hidden=true;
 box.appendChild(el('div',{class:'card kpi'},[el('span',{},[k[1]]),b,dl]));kpiNodes[k[0]]={b:b,d:dl};countUp(b,D.counts[k[0]]||0)})}
function updateDeltas(){if(!LIVE)return;KP.forEach(function(k){var liveV=k[2]?LIVE.totals[k[2]]:null,node=kpiNodes[k[0]];if(liveV==null){node.d.hidden=true;return}
 var diff=liveV-(D.counts[k[0]]||0);node.d.hidden=false;node.d.className='delta '+(diff>0?'up':'ok');
 node.d.textContent=diff>0?'+'+n(diff)+' sur le site depuis l’index':diff<0?n(diff)+' (retraits depuis l’index)':'index à jour'})}

/* ---------- panneaux ---------- */
function freshParts(f){return ['a_jour','en_retard','perime','sans_engagement'].map(function(k){return {l:ST[k][0],v:f[k]||0,c:ST[k][1],i:ST[k][2]}})}
function insights(){var out=[],f=D.datasets.fresh,fl=D.datasets.flags,tot=fl.total,commit=f.a_jour+f.en_retard+f.perime;
 out.push(['crit',pct(f.sans_engagement,tot)+' % des jeux ('+n(f.sans_engagement)+') n’ont aucune périodicité exploitable : leur fraîcheur ne peut pas être pilotée.']);
 if(commit)out.push([f.perime/commit>.3?'crit':'warn','Parmi les jeux avec engagement, '+pct(f.perime,commit)+' % sont périmés (plus de 3 périodes sans mise à jour).']);
 if(D.orgs_late.length)out.push(['warn','Producteur le plus en retard (≥ 20 jeux) : '+D.orgs_late[0][0]+' ('+n(D.orgs_late[0][1])+' jeux sur '+n(D.orgs_late[0][2])+').']);
 out.push(['warn',pct(D.apis.no_machine_doc,D.apis.total)+' % des API n’ont pas de documentation machine (OpenAPI) : elles ne sont pas exploitables automatiquement.']);
 out.push(['warn',n(D.discussions.unanswered_30d)+' discussions ouvertes restent sans réponse depuis plus de 30 jours.']);
 if(LIVE&&LIVE.services){var ko=LIVE.services.filter(function(s){return !s.ok});if(ko.length)out.unshift(['crit','Service en échec en ce moment : '+ko.map(function(s){return s.nom}).join(', ')+'.'])}
 return out}
function renderOverview(){var p=$('#p-overview');p.textContent='';
 var f=D.datasets.fresh,commit=f.a_jour+f.en_retard+f.perime;
 var fr=card('Fraîcheur des jeux de données','Date de dernière mise à jour comparée à la périodicité déclarée.',[stack(freshParts(f)),el('p',{class:'note'},['Avec engagement de mise à jour : '+pct(f.a_jour,commit)+' % à jour.'])]);
 var al=el('div');insights().forEach(function(a){var i=el('i',{},[a[0]==='crit'?'✕':'!']);i.style.color=a[0]==='crit'?'var(--crit)':'var(--warn)';al.appendChild(el('div',{class:'alert'},[i,el('span',{},[a[1]])]))});
 var feed=el('div',{class:'feed'});
 if(LIVE&&LIVE.latest&&LIVE.latest.length){var ul=el('ul');LIVE.latest.forEach(function(d){var a=el('a',{href:d.page||'#',target:'_blank',rel:'noopener noreferrer'},[d.title||'(sans titre)']);ul.appendChild(el('li',{},[a,el('small',{},[d.organization+' · publié '+ago(d.created_at)])]))});feed.appendChild(ul)}
 else feed.appendChild(el('p',{class:'note'},[TOKEN?'Chargement des derniers jeux publiés…':'Disponible en mode serveur : uv run hub-dashboard --serve']));
 var sv=el('div',{class:'leg'});if(LIVE&&LIVE.services)LIVE.services.forEach(function(s){sv.appendChild(chip(s.ok,s.nom))});else (D.services||[]).forEach(function(s){sv.appendChild(chip(s.ok,s.nom))});
 if(!sv.childNodes.length)sv.appendChild(el('span',{class:'note'},['Services non mesurés.']));
 p.appendChild(grid([fr,card('Points d’attention','Calculés sur l’index et le direct.',[al]),card('Derniers jeux publiés (en direct)','Source : data.gouv.fr, rafraîchi toutes les 30 s.',[feed]),card('Services','Joignabilité : toute réponse HTTP < 500.',[sv])]))}
function renderDatasets(){var p=$('#p-datasets');p.textContent='';
 var sel=el('select',{'aria-label':'Périodicité'},[el('option',{value:''},['Toutes les périodicités'])]);
 Object.keys(D.datasets.by_freq).sort(function(a,b){return (D.datasets.by_freq[b].total||0)-(D.datasets.by_freq[a].total||0)}).forEach(function(k){sel.appendChild(el('option',{value:k},[(FREQ[k]||k)+' ('+n(D.datasets.by_freq[k].total)+')']))});
 var holder=el('div');function drawF(){holder.textContent='';var f=sel.value?D.datasets.by_freq[sel.value]:D.datasets.fresh;holder.appendChild(stack(freshParts(f)))}
 sel.addEventListener('change',drawF);drawF();
 var fl=D.datasets.flags;
 p.appendChild(grid([
  card('Fraîcheur par périodicité','Choisissez une périodicité pour isoler ses jeux.',[el('div',{class:'tools'},[sel]),holder]),
  card('Complétude des métadonnées','Base : '+n(fl.total)+' jeux publics.',[bars([['Description < 30 caractères',fl.short_desc],['Licence non précisée',fl.no_license],['Sans mots-clés',fl.no_tags],['Sans fichier',fl.no_resource],['Sans producteur',fl.no_org]])]),
  card('Formats de fichiers',pct(D.resources.tabular,D.resources.total)+' % des fichiers sont interrogeables par l’API tabulaire.',[bars(D.resources.formats)]),
  card('Producteurs les plus en retard','≥ 20 jeux ; part en retard ou périmés.',[table(['Producteur','Retard/périmés','Jeux','Part'],D.orgs_late.map(function(r){return [r[0],r[1],r[2],pct(r[1],r[2])+' %']}),{num:[1,2,3],sort:1})],true)]));
 var late=el('div',{class:'card',style:'margin-top:14px'},[el('h3',{},['Jeux en retard ou périmés les plus consultés']),el('p',{class:'sub'},['Uniquement les jeux avec une périodicité déclarée. Cliquez sur un en-tête pour trier.']),
  table(['Jeu','Producteur','Périodicité','Dernière MAJ','État','Vues'],D.datasets.late_rows.map(function(r){return [r[0],r[1],FREQ[r[2]]||r[2],r[3],ST[r[4]][0],r[5]]}),{num:[5],search:true,sort:5,limit:200})]);
 p.appendChild(late)}
function renderApis(){var p=$('#p-apis');p.textContent='';var a=D.apis,lv=a.live;
 var parts=[card('Accès','Répartition par type d’accès.',[bars([['Ouvert',a.open],['Ouvert avec compte',a.account],['Restreint',a.restricted]])]),
  card('Documentation et exploitabilité','Base : '+n(a.total)+' API.',[bars([['Sans URL de base',a.no_base],['Sans documentation machine',a.no_machine_doc],['Sans documentation technique',a.no_tech_doc],['Sans limite de débit renseignée',a.no_rate]])])];
 if(lv.tested)parts.push(card('Joignabilité (échantillon de '+n(lv.tested)+')','Contrôlé '+ago(lv.last_check)+'. OpenAPI valide : '+n(lv.openapi)+'/'+n(lv.tested)+' · latence médiane '+(lv.median_ms==null?'–':lv.median_ms+' ms'),[stack([{l:'Joignable',v:lv.reachable,c:ST.a_jour[1],i:'✓'},{l:'Erreur serveur',v:lv.server_error,c:'var(--serious)',i:'!'},{l:'Injoignable',v:lv.down,c:ST.perime[1],i:'✕'}])]));
 else parts.push(card('Joignabilité','Non mesurée.',[el('p',{class:'note'},['Utilisez « Mettre à jour » (mode serveur) ou : uv run hub-health --sample 300'])]));
 p.appendChild(grid(parts))}
function renderEco(){var p=$('#p-eco');p.textContent='';var o=D.orgs,r=D.reuses,di=D.discussions;
 p.appendChild(grid([card('Organisations','Base : '+n(o.total),[bars([['Sans aucun jeu ni API',o.empty],['Sans description',o.no_desc],['Sans site web',o.no_url]])]),
  card('Réutilisations','Base : '+n(r.total),[bars([['Sans jeu rattaché',r.no_dataset],['Sans lien',r.no_url],['Sans description',r.no_desc]])]),
  card('Types de réutilisation',null,[bars(D.reuse_types)]),
  card('Discussions','Base : '+n(di.total),[bars([['Ouvertes',di.open],['Ouvertes sans réponse > 30 j',di.unanswered_30d]])])]))}
function renderServices(){var p=$('#p-services');p.textContent='';var list=(LIVE&&LIVE.services)||D.services||[];
 var c=card('Services de la plateforme',LIVE?'Mesure en direct '+ago(LIVE.at)+'.':(D.services_at?'Dernière mesure '+ago(D.services_at)+'.':'Non mesuré : lancez le mode serveur.'),[]);
 if(list.length)c.appendChild(table(['État','Type','Service','HTTP','Latence (ms)'],list.map(function(s){return [s.ok?'✓ joignable':'✕ en échec',s.type,s.nom,s.status,s.latency_ms==null?0:s.latency_ms]}),{num:[3,4]}));
 p.appendChild(c)}

/* ---------- recherche (mode serveur) ---------- */
var KIND_LABEL={tout:'Tout',jeux_de_donnees:'Jeux de données',api:'API',organisations:'Organisations',reutilisations:'Réutilisations',discussions:'Discussions'};
var TBL={datasets:'datasets',dataservices:'dataservices',organizations:'organizations',reuses:'reuses',discussions:'discussions'};
var SEARCH=null;
function qget(path,params){var u=new URLSearchParams();for(var k in params){if(params[k]!==''&&params[k]!=null)u.set(k,params[k])}
 return fetch(path+'?'+u.toString()).then(function(r){return r.json()})}
function badge(t,c){return el('span',{class:'badge'+(c?' '+c:'')},[t])}
function sizeOf(b){if(!b)return '';return b>1e6?(b/1e6).toFixed(1).replace('.',',')+' Mo':Math.max(1,Math.round(b/1e3))+' Ko'}
function resultCard(tbl,r,onPick){var title=r.title||r.name||'(sans titre)',c=el('div',{class:'res',tabindex:'0',role:'button'});
 c.appendChild(el('b',{},[title+(r.acronym?' ('+r.acronym+')':'')]));
 var meta=[];
 if(tbl==='datasets'){meta.push(badge(r.organization_name||'Producteur individuel'));if(r.frequency&&FREQ[r.frequency])meta.push(badge(FREQ[r.frequency]));if(r.license&&r.license!=='notspecified')meta.push(badge(r.license));
  meta.push(badge(n(r.resource_count)+' fichier(s)'));if(r.tabular_count)meta.push(badge(n(r.tabular_count)+' interrogeable(s)','ok'));meta.push(badge(n(r.views)+' vues'))}
 else if(tbl==='dataservices'){meta.push(badge(r.organization_name||'—'));meta.push(badge({open:'Accès ouvert',open_with_account:'Compte requis',restricted:'Restreint'}[r.access_type]||'Accès inconnu',r.access_type==='open'?'ok':r.access_type==='restricted'?'k':'w'))}
 else if(tbl==='organizations'){meta.push(badge(n(r.datasets_count)+' jeux'));meta.push(badge(n(r.dataservices_count)+' API'));meta.push(badge(n(r.reuses_count)+' réutilisations'))}
 else if(tbl==='reuses'){meta.push(badge(r.type||'réutilisation'));if(r.organization_name)meta.push(badge(r.organization_name))}
 else{meta.push(badge(r.subject_class||'Discussion'));meta.push(badge(n(r.messages_count)+' message(s)',r.closed?'ok':'w'));meta.push(badge(r.closed?'Fermée':'Ouverte'))}
 var m=el('div');meta.forEach(function(x){m.appendChild(x)});c.appendChild(m);
 if(r.extrait)c.appendChild(el('p',{},[r.extrait]));
 function go(){onPick(tbl,r,c)};c.addEventListener('click',go);c.addEventListener('keydown',function(e){if(e.key==='Enter')go()});return c}
function kvlist(pairs){var dl=el('dl',{class:'kv'});pairs.forEach(function(p){if(p[1]==null||p[1]==='')return;dl.appendChild(el('dt',{},[p[0]]));var dd=el('dd');
 if(/^https?:\/\//.test(String(p[1]))){dd.appendChild(el('a',{class:'lnk',href:p[1],target:'_blank',rel:'noopener noreferrer'},[String(p[1])]))}else dd.textContent=String(p[1]);dl.appendChild(dd)});return dl}
function previewTable(holder,rid){holder.textContent='Chargement…';
 Promise.all([qget('/api/profile',{rid:rid}),qget('/api/rows',{rid:rid})]).then(function(rs){var pr=rs[0],rw=rs[1];holder.textContent='';
  if(rw.erreur){holder.appendChild(el('p',{class:'note'},[rw.erreur]));return}
  var cols=rw.lignes&&rw.lignes[0]?Object.keys(rw.lignes[0]):[];var state={page:1,col:'',val:''};
  var tools=el('div',{class:'tools'}),sel=el('select',{'aria-label':'Colonne'}),inp=el('input',{type:'search',placeholder:'Valeur contenue…'}),go=el('button',{type:'button'},['Filtrer']);
  cols.forEach(function(c){sel.appendChild(el('option',{value:c},[c]))});[sel,inp,go].forEach(function(x){tools.appendChild(x)});holder.appendChild(tools);
  var info=el('p',{class:'note'}),box=el('div',{class:'scroll'}),nav=el('div',{class:'tools'}),prev=el('button',{type:'button'},['Précédent']),next=el('button',{type:'button'},['Suivant']);nav.appendChild(prev);nav.appendChild(next);
  holder.appendChild(info);holder.appendChild(box);holder.appendChild(nav);
  function load(){qget('/api/rows',{rid:rid,page:state.page,col:state.col,val:state.val}).then(function(d){box.textContent='';
   if(d.erreur){info.textContent=d.erreur;return}
   info.textContent=n(d.total)+' ligne(s) · page '+state.page+' · source : API tabulaire (en direct)';
   var cs=d.lignes[0]?Object.keys(d.lignes[0]):cols,t=el('table'),h=el('tr');cs.forEach(function(c){h.appendChild(el('th',{},[c]))});t.appendChild(el('thead',{},[h]));
   var tb=el('tbody');d.lignes.forEach(function(row){var tr=el('tr');cs.forEach(function(c){tr.appendChild(el('td',{},[row[c]==null?'':String(row[c])]))});tb.appendChild(tr)});t.appendChild(tb);box.appendChild(t);
   prev.disabled=state.page<=1;next.disabled=!d.page_suivante})}
  go.addEventListener('click',function(){state.col=sel.value;state.val=inp.value;state.page=1;load()});inp.addEventListener('keydown',function(e){if(e.key==='Enter')go.click()});
  prev.addEventListener('click',function(){state.page--;load()});next.addEventListener('click',function(){state.page++;load()});load();
  if(pr&&pr.profil&&pr.profil.profile&&pr.profil.profile.header){holder.appendChild(el('p',{class:'note'},['Colonnes : '+pr.profil.profile.header.join(', ')]))}})}
function showDetail(box,tbl,r){box.textContent='';box.appendChild(el('p',{class:'note'},['Chargement…']));
 if(tbl==='reuses'||tbl==='discussions'){box.textContent='';var c=card(r.title||'Discussion',null,[kvlist([['Type',r.type||r.subject_class],['Producteur',r.organization_name],['Lien',r.url||r.page]]),el('pre',{},[r.extrait||''])]);box.appendChild(c);return}
 qget('/api/item',{type:tbl,id:r.id}).then(function(it){box.textContent='';if(it.erreur){box.appendChild(el('p',{class:'note'},[it.erreur]));return}
  var c=el('div',{class:'card detail'});c.appendChild(el('h3',{},[it.title||it.name]));
  if(tbl==='datasets'){c.appendChild(kvlist([['Producteur',it.organization_name],['Licence',it.license],['Périodicité',FREQ[it.frequency]||it.frequency],['Dernière MAJ',(it.last_update||'').slice(0,10)],['Couverture',[it.temporal_start,it.temporal_end].filter(Boolean).join(' → ')],['Vues',it.views],['Page',it.page]]));
   c.appendChild(el('pre',{},[it.description||'']));c.appendChild(el('div',{class:'grp'},['Fichiers']));
   (it.ressources||[]).slice(0,60).forEach(function(f){var row=el('div',{class:'res'});row.style.cursor='default';row.appendChild(el('b',{},[f.title||'(sans titre)']));
    var m=el('div');m.appendChild(badge((f.format||'?').toUpperCase()));if(f.filesize)m.appendChild(badge(sizeOf(f.filesize)));
    if(f.tabular){m.appendChild(badge('Interrogeable','ok'));var hold=el('div'),b=el('button',{type:'button'},['Aperçu des données (direct)']);b.style.marginTop='6px';b.addEventListener('click',function(){b.hidden=true;previewTable(hold,f.id)});row.appendChild(m);row.appendChild(b);row.appendChild(hold)}
    else{row.appendChild(m);if(f.latest)row.appendChild(el('a',{class:'lnk',href:f.latest,target:'_blank',rel:'noopener noreferrer'},['Télécharger'])) }
    c.appendChild(row)})}
  else if(tbl==='dataservices'){c.appendChild(kvlist([['Producteur',it.organization_name],['Accès',it.access_type],['URL de base',it.base_api_url],['Doc. machine',it.machine_documentation_url],['Doc. technique',it.technical_documentation_url],['Demande d’accès',it.authorization_request_url],['Limites',it.rate_limiting],['Licence',it.license],['Page',it.page]]));c.appendChild(el('pre',{},[it.description||'']))}
  else{c.appendChild(kvlist([['Site',it.url],['Page',it.page],['Jeux',it.datasets_count],['API',it.dataservices_count]]));c.appendChild(el('pre',{},[it.description||'']));
   c.appendChild(el('div',{class:'grp'},['Jeux les plus consultés']));(it.jeux_de_donnees_populaires||[]).forEach(function(d){var rr=el('div',{class:'res'},[el('b',{},[d.title]),el('small',{},[n(d.views)+' vues'])]);rr.addEventListener('click',function(){showDetail(box,'datasets',{id:d.id})});c.appendChild(rr)});
   if((it.api||[]).length){c.appendChild(el('div',{class:'grp'},['API']));it.api.forEach(function(d){var rr=el('div',{class:'res'},[el('b',{},[d.title])]);rr.addEventListener('click',function(){showDetail(box,'dataservices',{id:d.id})});c.appendChild(rr)})}}
  box.appendChild(c)}).catch(function(){box.textContent='Erreur de chargement'})}

var DPE_COL={A:'#319834',B:'#33cc31',C:'#cbfc34',D:'#fbfe06',E:'#fbcc05',F:'#fc9935',G:'#fc0205'};
function renderDpe(res,d){
 if(d.erreur){res.appendChild(card('DPE par adresse',null,[el('p',{},[d.erreur]),d.adresse_reconnue?el('p',{class:'note'},['Adresse reconnue : '+d.adresse_reconnue]):el('span')]));return}
 var head=card('DPE à l’adresse : '+d.adresse_reconnue,n(d.total)+' diagnostic(s) trouvé(s) · source : ADEME (en direct), géocodage Base Adresse Nationale.',[]);
 if(!d.diagnostics.length)head.appendChild(el('p',{},['Aucun DPE « logements existants » (depuis juillet 2021) à cette adresse exacte. ',d.limites]));
 res.appendChild(head);
 d.diagnostics.forEach(function(x){var lab=el('div',{class:'lab','aria-label':'Étiquette énergie '+x.etiquette_dpe},[x.etiquette_dpe||'?']);lab.style.background=DPE_COL[x.etiquette_dpe]||'var(--line)';
  var body=el('div',{});body.appendChild(el('b',{},[(x.type_batiment||'Logement')+(x.surface_habitable_logement?' · '+n(Math.round(x.surface_habitable_logement))+' m²':'')]));
  var m=el('div');m.appendChild(badge('GES '+(x.etiquette_ges||'?')));if(x.date_etablissement_dpe)m.appendChild(badge('établi le '+x.date_etablissement_dpe));
  if(x.date_fin_validite_dpe){var exp=x.date_fin_validite_dpe<new Date().toISOString().slice(0,10);m.appendChild(badge((exp?'expiré le ':'valide jusqu’au ')+x.date_fin_validite_dpe,exp?'k':'ok'))}
  if(x.annee_construction)m.appendChild(badge('construit en '+x.annee_construction));body.appendChild(m);
  body.appendChild(kvlist([['Conso. énergie primaire',x.conso_5_usages_par_m2_ep!=null?Math.round(x.conso_5_usages_par_m2_ep)+' kWh/m²/an':null],['Émissions GES',x.emission_ges_5_usages_par_m2!=null?Math.round(x.emission_ges_5_usages_par_m2)+' kg CO₂/m²/an':null],['Chauffage',x.type_energie_principale_chauffage],['Installation',x.type_installation_chauffage],['Isolation',x.qualite_isolation_enveloppe],['Coût annuel estimé',x.cout_total_5_usages!=null?Math.round(x.cout_total_5_usages)+' €':null],['N° DPE',x.numero_dpe]]));
  res.appendChild(el('div',{class:'res'},[el('div',{class:'dpe'},[lab,body])]))});
 if(d.limites)res.appendChild(el('p',{class:'note'},[d.limites]))}

function renderPistes(res,d){
 var h=card('Enquête dans le catalogue',(d.lieu_detecte?'Lieu détecté : '+d.lieu_detecte+' · ':'')+'mots-clés : '+(d.mots_cles||'—')+' · lignes lues en direct sur les fichiers interrogeables.',[]);
 h.appendChild(el('p',{class:'note'},[d.limites||'']));res.appendChild(h);
 if(!d.pistes.length)res.appendChild(el('p',{class:'note'},['Aucun fichier interrogeable ne correspond : voir les jeux et API trouvés ci-dessous.']));
 d.pistes.forEach(function(p){var c=el('div',{class:'res'});c.style.cursor='default';c.appendChild(el('b',{},[p.jeu]));
  var m=el('div');m.appendChild(badge(p.producteur||'—'));m.appendChild(badge(p.fichier||'fichier'));if(p.filtre)m.appendChild(badge(p.filtre,'ok'));if(p.total!=null)m.appendChild(badge(n(p.total)+' ligne(s)'));c.appendChild(m);
  if(p.erreur)c.appendChild(el('p',{},['Lecture impossible : '+p.erreur]));
  else if(p.lignes&&p.lignes.length){var cs=Object.keys(p.lignes[0]).slice(0,8),t=el('table'),hr=el('tr');cs.forEach(function(x){hr.appendChild(el('th',{},[x]))});t.appendChild(el('thead',{},[hr]));var tb=el('tbody');
   p.lignes.forEach(function(row){var tr=el('tr');cs.forEach(function(x){tr.appendChild(el('td',{},[row[x]==null?'':String(row[x])]))});tb.appendChild(tr)});t.appendChild(tb);var sc=el('div',{class:'scroll'});sc.appendChild(t);c.appendChild(sc)}
  if(p.page)c.appendChild(el('a',{class:'lnk',href:p.page,target:'_blank',rel:'noopener noreferrer'},['Voir sur data.gouv.fr']));res.appendChild(c)})}
function renderSearch(){var p=$('#p-search');
 if(!TOKEN){p.textContent='';p.appendChild(card('Recherche dans tout data.gouv.fr','Jeux de données, API, organisations, réutilisations, discussions.',[el('p',{class:'note'},['Disponible en mode serveur : uv run hub-dashboard --serve'])]));return}
 if(SEARCH)return;SEARCH={kind:'tout',offset:0};p.textContent='';
 var inp=el('input',{type:'search',placeholder:'Posez une question ou cherchez : « DPE du 10 rue de Rivoli à Paris », valeurs foncières, Insee…','aria-label':'Recherche'}),chips=el('div',{class:'chips'});
 var fprod=el('input',{type:'search',placeholder:'Producteur (ex. Insee)'}),ffmt=el('input',{type:'search',placeholder:'Format (csv, json…)'}),ftab=el('input',{type:'checkbox'}),fl=el('label',{class:'note'},[ftab,' interrogeables seulement']);
 var filters=el('div',{class:'tools'},[fprod,ffmt,fl]);filters.hidden=true;
 var res=el('div'),more=el('button',{type:'button'},['Plus de résultats']);more.hidden=true;var det=el('div'),info=el('p',{class:'note'});
 var ex=el('div',{class:'ex'});['DPE du 10 rue de Rivoli à Paris','valeurs foncières','qualité de l’air','population des communes'].forEach(function(t){var b=el('button',{type:'button'},[t]);b.addEventListener('click',function(){inp.value=t;SEARCH.kind='tout';sched()});ex.appendChild(b)});
 p.appendChild(el('div',{class:'search'},[inp]));p.appendChild(ex);p.appendChild(chips);p.appendChild(filters);p.appendChild(info);p.appendChild(el('div',{class:'sgrid'},[el('div',{},[res,more]),det]));
 Object.keys(KIND_LABEL).forEach(function(k){var b=el('button',{type:'button','aria-pressed':k==='tout'?'true':'false'},[KIND_LABEL[k]]);b.addEventListener('click',function(){SEARCH.kind=k;SEARCH.offset=0;Array.prototype.forEach.call(chips.children,function(x){x.setAttribute('aria-pressed','false')});b.setAttribute('aria-pressed','true');filters.hidden=k!=='jeux_de_donnees';run(true)});chips.appendChild(b)});
 var sel=null;function pick(tbl,r,node){if(sel)sel.classList.remove('sel');sel=node;node.classList.add('sel');showDetail(det,tbl,r)}
 var timer=null,seq=0;
 function run(reset){var my=++seq;if(reset){SEARCH.offset=0;res.textContent=''}
  qget(SEARCH.kind==='tout'&&inp.value?'/api/ask':'/api/search',{q:inp.value,type:SEARCH.kind,producteur:fprod.value,format:ffmt.value,interrogeable:ftab.checked?'1':'',limit:SEARCH.kind==='tout'?6:12,offset:SEARCH.offset}).then(function(d){if(my!==seq)return;
   if(d.intention==='dpe'){more.hidden=true;info.textContent='Question reconnue : DPE d’une adresse (interrogé en direct).';res.textContent='';renderDpe(res,d);return}
   if(d.erreur){info.textContent=d.erreur;return}var total=0;if(d.intention==='general'&&reset){renderPistes(res,d)}
   Object.keys(d.resultats).forEach(function(tbl){var rows=d.resultats[tbl];total+=rows.length;if(!rows.length)return;
    if(SEARCH.kind==='tout')res.appendChild(el('div',{class:'grp'},[KIND_LABEL[{datasets:'jeux_de_donnees',dataservices:'api',organizations:'organisations',reuses:'reutilisations',discussions:'discussions'}[tbl]]]));
    rows.forEach(function(r){res.appendChild(resultCard(tbl,r,pick))})});
   more.hidden=SEARCH.kind==='tout'||total<d.limit;
   info.textContent=(inp.value?'Résultats pour « '+inp.value+' »':'Les plus consultés')+' · index local, rapide, hors ligne ; les aperçus de fichiers sont interrogés en direct.';
   if(!total&&reset)res.appendChild(el('p',{class:'note'},['Aucun résultat. Essayez moins de mots ou un autre type.']))}).catch(function(){info.textContent='Recherche indisponible'})}
 function sched(){clearTimeout(timer);timer=setTimeout(function(){run(true)},250)}
 [inp,fprod,ffmt].forEach(function(x){x.addEventListener('input',sched)});ftab.addEventListener('change',sched);
 more.addEventListener('click',function(){SEARCH.offset+=12;run(false)});run(true);setTimeout(function(){inp.focus()},50)}
var PANELS=[['search','Recherche',renderSearch],['overview','Vue d’ensemble',renderOverview],['datasets','Jeux de données',renderDatasets],['apis','API',renderApis],['eco','Écosystème',renderEco],['services','Services',renderServices]];
function renderAll(){PANELS.forEach(function(x){x[2]()});updateDeltas()}
function buildTabs(){var t=$('#tabs');PANELS.forEach(function(x,i){var b=el('button',{type:'button',role:'tab','aria-selected':'false'},[x[1]]);
 b.addEventListener('click',function(){show(x[0])});t.appendChild(b)});
 function show(id){PANELS.forEach(function(y,j){$('#p-'+y[0]).classList.toggle('on',y[0]===id);t.children[j].setAttribute('aria-selected',y[0]===id?'true':'false')});history.replaceState(null,'','#'+id)}
 var h=(location.hash||'').slice(1);show(PANELS.some(function(x){return x[0]===h})?h:(TOKEN?'search':'overview'))}

/* ---------- direct et mise à jour (mode serveur) ---------- */
function setLive(on,txt){$('#dot').className='dot'+(on?' on':'');$('#livetxt').textContent=txt}
function poll(){fetch('/api/live').then(function(r){return r.json()}).then(function(L){LIVE=L;
 var errs=Object.keys(L.errors||{}).length;setLive(true,'En direct · '+ago(L.at)+(errs?' · '+errs+' source(s) indisponible(s)':''));renderAll()})
 .catch(function(){setLive(false,'Direct indisponible')})}
function initServer(){var b=$('#upd');b.hidden=false;poll();setInterval(poll,30000);
 setInterval(function(){if(LIVE)setLive(true,'En direct · '+ago(LIVE.at))},5000);
 function status(){fetch('/status').then(function(r){return r.json()}).then(function(s){if(s.running){b.textContent='En cours : '+s.step+'…';setTimeout(status,2000)}
  else if(s.error){b.disabled=false;b.textContent='Échec : '+s.error+' (réessayer)'}else{location.reload()}}).catch(function(){setTimeout(status,3000)})}
 b.addEventListener('click',function(){b.disabled=true;b.textContent='Démarrage…';
  fetch('/update',{method:'POST',headers:{'X-Token':TOKEN}}).then(function(r){if(!r.ok&&r.status!==409)throw new Error('HTTP '+r.status);status()}).catch(function(e){b.disabled=false;b.textContent='Échec : '+e.message})})}

/* ---------- thème ---------- */
$('#theme').addEventListener('click',function(){var r=document.documentElement,cur=r.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme:light)').matches?'light':'dark');
 var nx=cur==='dark'?'light':'dark';r.setAttribute('data-theme',nx);try{localStorage.setItem('hub-theme',nx)}catch(e){}});
try{var sv=localStorage.getItem('hub-theme');if(sv)document.documentElement.setAttribute('data-theme',sv)}catch(e){}

$('#asof').textContent='Index du '+D.generated_at.slice(0,16).replace('T',' ')+' UTC · '+(TOKEN?'mode serveur, chiffres du site en direct':'mode statique, sans données en direct')+'.';
buildKpis();buildTabs();renderAll();
if(TOKEN)initServer();
})();
</script></body></html>
"""


def build(data: dict, token: str | None) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/").replace("<!--", "<\\!--")
    return TEMPLATE.replace("__DATA__", payload).replace("__TOKEN__", json.dumps(token))
