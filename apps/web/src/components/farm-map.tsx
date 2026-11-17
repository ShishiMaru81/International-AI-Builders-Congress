'use client';
import {useEffect,useRef,useState} from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
type Props={lat:number;lon:number;demo:boolean;onSelect?:(lat:number,lon:number)=>void};
export default function FarmMap({lat,lon,demo,onSelect}:Props){
 const ref=useRef<HTMLDivElement>(null);
 const mapRef=useRef<maplibregl.Map|null>(null);
 const markerRef=useRef<maplibregl.Marker|null>(null);
 const initial=useRef({lat,lon});
 const callback=useRef(onSelect);
 const editable=Boolean(onSelect);
 const [mapError,setMapError]=useState('');
 useEffect(()=>{callback.current=onSelect},[onSelect]);
 useEffect(()=>{
  if(!ref.current)return;
  // Set explicit worker URL for MapLibre 6 to avoid CSP/bundler issues
  try{
   maplibregl.setWorkerUrl(new URL('maplibre-gl/dist/maplibre-gl-worker.mjs',import.meta.url).toString());
  }catch{/* ignore if URL resolution fails in SSR contexts */}
  let map:maplibregl.Map;
  try{
   map=new maplibregl.Map({container:ref.current,style:{version:8,sources:{osm:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,attribution:'© OpenStreetMap contributors'}},layers:[{id:'osm',type:'raster',source:'osm'}]},center:[initial.current.lon,initial.current.lat],zoom:10});
   mapRef.current=map;
   map.on('error',(e)=>{console.error('[FarmMap]',e.error?.message||e);setMapError('Map tiles unavailable. Use area search or coordinates below.');});
   const marker=new maplibregl.Marker({color:'#0f6a47',draggable:editable}).setLngLat([initial.current.lon,initial.current.lat]).addTo(map);
   markerRef.current=marker;
   if(editable){
    const choose=(point:maplibregl.LngLat)=>{const wrapped=point.wrap();marker.setLngLat(wrapped);callback.current?.(Number(wrapped.lat.toFixed(6)),Number(wrapped.lng.toFixed(6)))};
    map.on('click',event=>choose(event.lngLat));
    marker.on('dragend',()=>choose(marker.getLngLat()));
    map.getCanvas().style.cursor='crosshair';
   }
   map.addControl(new maplibregl.NavigationControl());
  }catch{
   // Map construction failure is an external/browser capability signal; surface fallback UI.
   queueMicrotask(()=>setMapError('Map unavailable on this device. Use area search or coordinates below.'));
   return;
  }
  return()=>{markerRef.current=null;mapRef.current=null;map.remove()};
 },[editable]);
 useEffect(()=>{
  markerRef.current?.setLngLat([lon,lat]);
  const map=mapRef.current;
  if(map){const center=map.getCenter();if(Math.abs(center.lat-lat)>0.00001||Math.abs(center.lng-lon)>0.00001)map.flyTo({center:[lon,lat],duration:window.matchMedia('(prefers-reduced-motion: reduce)').matches?0:250})}
 },[lat,lon]);
 if(mapError)return <div className="map-wrap" data-testid="area-map"><p className="helper" style={{padding:'20px',textAlign:'center'}}>{mapError}</p></div>;
 return <div className="map-wrap" data-testid="area-map"><div ref={ref} className="map" role="region" aria-label={editable?'Choose a point on the area map':'Farm location map'}/><span className="map-label">{editable?'Click anywhere or drag the pin':demo?'Illustrative location · choose your own area':'Farmer-selected location'} · No flood overlay</span></div>;
}
