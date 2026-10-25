<<<<<<< HEAD
const stops=[{name:"Roslyn Harbour",day:"Start",coords:[40.8168,-73.6368],note:"The road trip begins on Long Island."},{name:"Port Jefferson Ferry",day:"Day 1",coords:[40.9465,-73.0693],note:"Evening ferry across Long Island Sound."},{name:"Bridgeport",day:"Day 1",coords:[41.1792,-73.1894],note:"Landing in Connecticut."},{name:"Providence area",day:"Day 1",coords:[41.9212,-71.5495],note:"Overnight near Providence."},{name:"Boston Common",day:"Day 2",coords:[42.3551,-71.0656],note:"Boston Common and Fenway Park."},{name:"Harvard Square",day:"Day 2",coords:[42.3735,-71.1189],note:"Lunch at Santouka in Cambridge."},{name:"Colchester, Vermont",day:"Day 2",coords:[44.5439,-73.1479],note:"Overnight in Vermont."},{name:"Burlington Waterfront",day:"Day 3",coords:[44.4759,-73.2121],note:"Lake Champlain and Spot on the Dock."},{name:"Smugglers' Notch",day:"Day 3",coords:[44.5567,-72.7904],note:"A winding mountain pass."},{name:"Lake George",day:"Day 3–4",coords:[43.4262,-73.7123],note:"A lakeside stop and overnight."},{name:"Carlisle, Pennsylvania",day:"Day 4",coords:[40.2010,-77.2003],note:"Overnight before Gettysburg."},{name:"Gettysburg",day:"Day 5",coords:[39.7893,-77.2375],note:"Civil War battlefield and Little Round Top."},{name:"Washington, DC",day:"Day 5",coords:[38.8895,-77.0353],note:"Museums and national memorials."},{name:"Fairfax, Virginia",day:"Day 5",coords:[38.8462,-77.3064],note:"George Mason University and the overnight area."},{name:"Bristol",day:"Day 6",coords:[36.5951,-82.1887],note:"Soul food and country music history."},{name:"Knoxville",day:"Day 6",coords:[35.9694,-83.9197],note:"Coffee in the Old City."},{name:"Nashville",day:"Day 6–7",coords:[36.1627,-86.7816],note:"Ryman Auditorium and live music."},{name:"Lynchburg",day:"Day 7",coords:[35.2831,-86.3742],note:"Jack Daniel's distillery tour."},{name:"Memphis",day:"Day 7–8",coords:[35.1556,-90.0659],note:"Beale Street and the Mississippi River."},{name:"Little Rock",day:"Day 8",coords:[34.7487,-92.2671],note:"Junction Bridge and downtown Little Rock."},{name:"Old Mill, North Little Rock",day:"Day 8",coords:[34.7904,-92.2670],note:"A brief stop at the Old Mill."},{name:"Texarkana",day:"Day 8",coords:[33.4251,-94.0436],note:"A late stop at the Arkansas–Texas line."},{name:"Houston",day:"Finish",coords:[29.7604,-95.3698],note:"Arrived around 3:30 a.m. on October 3."}];
const q=s=>document.querySelectorAll(s),RV='.lede,.intro-block,.section-heading,.day,.ending>div';if('IntersectionObserver'in window){const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{threshold:.12,rootMargin:'0px 0px -6% 0px'});q(RV).forEach(e=>io.observe(e))}else q(RV).forEach(e=>e.classList.add('in'));const bar=document.getElementById('progress');let tick=false;const prog=()=>{const d=document.documentElement;bar.style.transform='scaleX('+Math.min(1,d.scrollTop/((d.scrollHeight-d.clientHeight)||1))+')';tick=false};addEventListener('scroll',()=>{if(!tick){tick=true;requestAnimationFrame(prog)}},{passive:true});prog();const el=document.getElementById('tripMap');if(el&&window.L){const map=L.map('tripMap',{scrollWheelZoom:false}).setView([37.8,-83.6],5);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);const points=stops.map(s=>s.coords),layer=L.layerGroup().addTo(map);const drawRoute=async seg=>{try{const coords=seg.map(p=>p[1]+','+p[0]).join(';'),r=await fetch('https://router.project-osrm.org/route/v1/driving/'+coords+'?overview=full&geometries=geojson');const d=await r.json();if(d.code==='Ok'&&d.routes.length)L.geoJSON(d.routes[0].geometry,{style:{color:'#a4502e',weight:4,opacity:.9}}).addTo(layer);else L.polyline(seg,{color:'#a4502e',weight:3,dashArray:'3 7'}).addTo(layer)}catch(e){L.polyline(seg,{color:'#a4502e',weight:3,dashArray:'3 7'}).addTo(layer)}};drawRoute(points.slice(0,2));L.polyline([stops[1].coords,stops[2].coords],{color:'#a4502e',weight:3,dashArray:'8 7'}).addTo(layer);drawRoute(points.slice(2));stops.forEach((s,i)=>{const pin=L.divIcon({className:'',html:'<div class="custom-pin'+(i===0||i===stops.length-1?' end':'')+'"></div>',iconSize:[16,16],iconAnchor:[8,8]});L.marker(s.coords,{icon:pin,title:s.name}).addTo(map).bindPopup('<strong>'+s.name+'</strong><em>'+s.day+'</em><p>'+s.note+'</p>')});map.fitBounds(L.latLngBounds(points).pad(.08));map.on('click',()=>map.scrollWheelZoom.enable());map.on('mouseout',()=>map.scrollWheelZoom.disable())}
=======
const stops = [
{name:"Roslyn Harbour",day:"Start",coords:[40.8168,-73.6368],note:"The road trip begins on Long Island."},
{name:"Port Jefferson Ferry",day:"Day 1",coords:[40.9465,-73.0693],note:"Evening ferry across Long Island Sound."},
{name:"Bridgeport",day:"Day 1",coords:[41.1792,-73.1894],note:"Landing in Connecticut."},
{name:"Smithfield / Providence",day:"Day 1",coords:[41.9212,-71.5495],note:"Overnight near Providence."},
{name:"Boston Common",day:"Day 2",coords:[42.3551,-71.0656],note:"Boston Common and Fenway Park."},
{name:"Harvard Square",day:"Day 2",coords:[42.3735,-71.1189],note:"Lunch at Santouka in Cambridge."},
{name:"Colchester, Vermont",day:"Day 2",coords:[44.5439,-73.1479],note:"Overnight in Vermont."},
{name:"Burlington Waterfront",day:"Day 3",coords:[44.4759,-73.2121],note:"Lake Champlain and Spot on the Dock."},
{name:"Smugglers' Notch",day:"Day 3",coords:[44.5567,-72.7904],note:"A winding mountain pass."},
{name:"Lake George",day:"Day 3–4",coords:[43.4262,-73.7123],note:"A lakeside stop and overnight."},
{name:"Carlisle, Pennsylvania",day:"Day 4",coords:[40.2010,-77.2003],note:"Overnight before Gettysburg."},
{name:"Gettysburg",day:"Day 5",coords:[39.7893,-77.2375],note:"Civil War battlefield and Little Round Top."},
{name:"Washington, DC",day:"Day 5",coords:[38.8895,-77.0353],note:"Museums and national memorials."},
{name:"Fairfax, Virginia",day:"Day 5",coords:[38.8462,-77.3064],note:"George Mason University and the overnight area."},
{name:"Bristol",day:"Day 6",coords:[36.5951,-82.1887],note:"Soul food and country music history."},
{name:"Knoxville",day:"Day 6",coords:[35.9694,-83.9197],note:"Coffee in the Old City."},
{name:"Nashville",day:"Day 6–7",coords:[36.1627,-86.7816],note:"Ryman Auditorium and live music."},
{name:"Lynchburg",day:"Day 7",coords:[35.2831,-86.3742],note:"Jack Daniel's distillery tour."},
{name:"Memphis",day:"Day 7–8",coords:[35.1556,-90.0659],note:"Beale Street and the Mississippi River."},
{name:"Little Rock",day:"Day 8",coords:[34.7487,-92.2671],note:"Junction Bridge and downtown Little Rock."},
{name:"Old Mill, North Little Rock",day:"Day 8",coords:[34.7904,-92.2670],note:"A brief stop at the Old Mill before continuing west."},
{name:"Texarkana",day:"Day 8",coords:[33.4251,-94.0436],note:"A late stop at the Arkansas–Texas line."},
{name:"Houston",day:"Finish",coords:[29.7604,-95.3698],note:"Arrived around 3:30 a.m. on October 3."}
];
const q=s=>document.querySelectorAll(s),RV=".lede,.intro-block,.section-heading,.day,.ending>div";
if("IntersectionObserver" in window){
 const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target)}}),{threshold:.12,rootMargin:"0px 0px -6% 0px"});
 q(RV).forEach(e=>io.observe(e));
 const links=[...q(".site-header nav a")];
 const so=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting)links.forEach(a=>a.classList.toggle("active",a.getAttribute("href")==="#"+e.target.id))}),{rootMargin:"-40% 0px -55% 0px"});
 ["new-york","route","journal"].forEach(id=>{const s=document.getElementById(id);s&&so.observe(s)});
}else q(RV).forEach(e=>e.classList.add("in"));
const bar=document.getElementById("progress");let tick=false;
const prog=()=>{const d=document.documentElement;bar.style.transform="scaleX("+Math.min(1,d.scrollTop/((d.scrollHeight-d.clientHeight)||1))+")";tick=false};
addEventListener("scroll",()=>{if(!tick){tick=true;requestAnimationFrame(prog)}},{passive:true});prog();

const el=document.getElementById("tripMap");
if(el&&window.L){
 const map=L.map("tripMap",{scrollWheelZoom:false}).setView([37.8,-83.6],5);
 L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',crossOrigin:true}).addTo(map);
 const points=stops.map(s=>s.coords);
 // Draw road-following driving routes with OSRM. The ferry crossing is kept as
 // its own dashed segment, rather than being mistaken for a road journey.
 const routeLayer=L.layerGroup().addTo(map);
 const drawRoute=async segment=>{
  const coords=segment.map(p=>p[1]+","+p[0]).join(";");
  const url="https://router.project-osrm.org/route/v1/driving/"+coords+"?overview=full&geometries=geojson&steps=false";
  try{
   const response=await fetch(url);
   if(!response.ok)throw new Error("Routing service unavailable");
   const data=await response.json();
   if(data.code!=="Ok"||!data.routes?.length)throw new Error("No route returned");
   L.geoJSON(data.routes[0].geometry,{style:{color:"#a4502e",weight:4,opacity:.9,lineCap:"round",lineJoin:"round"}}).addTo(routeLayer);
  }catch(error){
   // If online routing is unavailable, keep a subdued fallback line.
   L.polyline(segment,{color:"#a4502e",weight:3,opacity:.55,dashArray:"3 7",lineCap:"round"}).addTo(routeLayer);
  }
 };
 // Road route to the ferry terminal, ferry across Long Island Sound, then
 // the driving itinerary from Bridgeport through Houston.
 drawRoute(points.slice(0,2));
 L.polyline([stops[1].coords,stops[2].coords],{color:"#a4502e",weight:3,opacity:.9,dashArray:"8 7",lineCap:"round"}).addTo(routeLayer);
 drawRoute(points.slice(2));
 stops.forEach((s,i)=>{
  const end=i===0||i===stops.length-1;
  const pin=L.divIcon({className:"",html:'<div class="custom-pin'+(end?' end':'')+'"></div>',iconSize:[16,16],iconAnchor:[8,8],popupAnchor:[0,-10]});
  L.marker(s.coords,{icon:pin,title:s.name}).addTo(map).bindPopup("<strong>"+s.name+"</strong><em>"+s.day+"</em><p>"+s.note+"</p>");
 });
 map.fitBounds(L.latLngBounds(points).pad(.08));
 map.on("click",()=>map.scrollWheelZoom.enable());
 map.on("mouseout",()=>map.scrollWheelZoom.disable());
}
>>>>>>> 6983d44d23c38758372d3f1c2afec9529859d397
