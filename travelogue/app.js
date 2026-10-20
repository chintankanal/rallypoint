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
{name:"Bristol",day:"Day 6",coords:[36.5951,-82.1887],note:"Soul food and country music history."},
{name:"Knoxville",day:"Day 6",coords:[35.9694,-83.9197],note:"Coffee in the Old City."},
{name:"Nashville",day:"Day 6–7",coords:[36.1627,-86.7816],note:"Ryman Auditorium and live music."},
{name:"Lynchburg",day:"Day 7",coords:[35.2831,-86.3742],note:"Jack Daniel's distillery tour."},
{name:"Memphis",day:"Day 7–8",coords:[35.1556,-90.0659],note:"Beale Street and the Mississippi River."},
{name:"Little Rock",day:"Day 8",coords:[34.7487,-92.2671],note:"Junction Bridge and the Old Mill nearby."},
{name:"Texarkana",day:"Day 8",coords:[33.4251,-94.0436],note:"A late stop at the Arkansas–Texas line."},
{name:"Houston",day:"Finish",coords:[29.7604,-95.3698],note:"Arrived around 3:30 a.m. on October 3."}
];
const el=document.getElementById("tripMap");
if(el&&window.L){
 const map=L.map("tripMap",{scrollWheelZoom:false}).setView([37.8,-83.6],5);
 L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:18,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
 const points=stops.map(s=>s.coords);
 L.polyline(points,{color:"#9b6247",weight:3,opacity:.8,dashArray:"6 7"}).addTo(map);
 const pin=L.divIcon({className:"",html:'<div class="custom-pin"></div>',iconSize:[12,12],iconAnchor:[6,6]});
 stops.forEach(s=>L.marker(s.coords,{icon:pin}).addTo(map).bindPopup("<strong>"+s.name+"</strong><br><span>"+s.day+"</span><br>"+s.note));
 map.fitBounds(L.latLngBounds(points).pad(.08));
}