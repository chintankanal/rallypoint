const stops = [
  {name:"Roslyn Harbour",day:"Before Day 1",coords:[40.8168,-73.6368],note:"The road trip begins on Long Island."},
  {name:"Port Jefferson Ferry",day:"Day 1",coords:[40.9465,-73.0693],note:"Evening ferry across Long Island Sound."},
  {name:"Bridgeport",day:"Day 1",coords:[41.1792,-73.1894],note:"The Connecticut landing, followed by a coastal drive."},
  {name:"Providence / Smithfield",day:"Day 1",coords:[41.9212,-71.5495],note:"Overnight near Providence."},
  {name:"Boston Common",day:"Day 2",coords:[42.3551,-71.0656],note:"The Soldiers and Sailors Monument, followed by Fenway Park."},
  {name:"Harvard Square",day:"Day 2",coords:[42.3735,-71.1189],note:"Ramen at Santouka before continuing north."},
  {name:"Colchester, Vermont",day:"Day 2",coords:[44.5439,-73.1479],note:"Overnight before exploring Burlington and the mountain roads."},
  {name:"Burlington Waterfront",day:"Day 3",coords:[44.4759,-73.2121],note:"Lake Champlain, the waterfront and lunch at Spot on the Dock."},
  {name:"Shelburne Farms",day:"Day 3",coords:[44.3775,-73.2377],note:"Rain meant the planned tour did not happen."},
  {name:"Smugglers' Notch",day:"Day 3",coords:[44.5567,-72.7904],note:"A winding mountain pass en route to Stowe."},
  {name:"Ben & Jerry's Factory",day:"Day 3",coords:[44.3376,-72.7562],note:"Ice cream just before closing."},
  {name:"Lake George",day:"Day 3–4",coords:[43.4262,-73.7123],note:"A lakeside walk and breakfast at Café Vero."},
  {name:"Carlisle, Pennsylvania",day:"Day 4",coords:[40.2010,-77.2003],note:"Overnight before the Gettysburg and Washington sightseeing day."},
  {name:"Gettysburg / Little Round Top",day:"Day 5",coords:[39.7893,-77.2375],note:"A drive through the historic Civil War battlefield."},
  {name:"Washington, DC",day:"Day 5",coords:[38.8895,-77.0353],note:"The Air and Space Museum and the national memorials."},
  {name:"Fairfax, Virginia",day:"Day 5",coords:[38.8462,-77.3064],note:"George Mason University en route."},
  {name:"Bristol",day:"Day 6",coords:[36.5951,-82.1887],note:"Soul food and the Birthplace of Country Music Museum."},
  {name:"Knoxville Old City",day:"Day 6",coords:[35.9694,-83.9197],note:"A coffee stop at Awaken Coffee."},
  {name:"Nashville",day:"Day 6–7",coords:[36.1627,-86.7816],note:"Lower Broadway, Ryman Auditorium and live music."},
  {name:"Lynchburg",day:"Day 7",coords:[35.2831,-86.3742],note:"The Jack Daniel's distillery tour."},
  {name:"Memphis / Mud Island",day:"Day 7–8",coords:[35.1556,-90.0659],note:"Beale Street, Memphis music heritage and the Mississippi River trail."},
  {name:"The Old Mill, North Little Rock",day:"Day 8",coords:[34.7804,-92.3571],note:"An unplanned, picturesque stop."},
  {name:"Junction Bridge, Little Rock",day:"Day 8",coords:[34.7487,-92.2671],note:"A short visit to the Arkansas capital."},
  {name:"Texarkana state line",day:"Day 8",coords:[33.4251,-94.0436],note:"A late-night stop at the Arkansas–Texas border."},
  {name:"Houston",day:"End of this leg",coords:[29.7604,-95.3698],note:"Arrived at approximately 3:30 a.m. on October 3."}
];

const mapEl = document.getElementById('tripMap');
if (mapEl && window.L) {
  const map = L.map('tripMap', {scrollWheelZoom:false, zoomControl:true}).setView([37.8,-83.6], 5);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  const points = stops.map(s => s.coords);
  L.polyline(points, {color:'#b96747', weight:3, opacity:.8, dashArray:'7 7'}).addTo(map);
  const pin = L.divIcon({className:'',html:'<div class="custom-pin"></div>',iconSize:[12,12],iconAnchor:[6,6]});
  stops.forEach((stop, i) => {
    const marker = L.marker(stop.coords, {icon:pin}).addTo(map);
    marker.bindPopup('<strong>'+stop.name+'</strong><span style="color:#b96747;font:10px monospace;letter-spacing:.06em">'+stop.day+'</span><br>'+stop.note+(i < 8 ? '<br><a href="#prologue">Read the prologue ↑</a>' : '<br><a href="#day'+Math.min(8,Math.max(1, i < 12 ? 3 : i < 13 ? 4 : i < 16 ? 5 : i < 18 ? 6 : i < 20 ? 7 : 8))+'">Read this chapter ↑</a>'));
  });
  map.fitBounds(L.latLngBounds(points).pad(0.08));
}

const progress = document.getElementById('readingProgress');
function updateProgress(){
  const max = document.documentElement.scrollHeight - window.innerHeight;
  progress.style.width = (max > 0 ? (window.scrollY / max) * 100 : 0) + '%';
}
window.addEventListener('scroll', updateProgress, {passive:true});
updateProgress();
