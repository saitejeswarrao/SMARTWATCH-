import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Circle, Marker, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';

// Fix for default marker icons in Leaflet with Vite
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
    iconUrl: markerIcon,
    shadowUrl: markerShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

interface MapZoneProps {
  center: [number, number];
  userLocation: [number, number];
  radius: number;
  onZoneChange: (lat: number, lng: number) => void;
}

function ChangeView({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center);
  }, [center, map]);
  return null;
}

function MapEvents({ onZoneChange }: { onZoneChange: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      onZoneChange(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

export const MapZone: React.FC<MapZoneProps> = ({ center, userLocation, radius, onZoneChange }) => {
  return (
    <div className="h-full w-full rounded-xl overflow-hidden border border-white/10">
      <MapContainer 
        center={center} 
        zoom={14} 
        scrollWheelZoom={false}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Circle 
          center={center}
          pathOptions={{ color: '#3b82f6', fillColor: '#3b82f6', fillOpacity: 0.2 }}
          radius={radius}
        />
        <Marker position={userLocation}>
          {/* Note: In a real app we might use a custom icon for the user */}
        </Marker>
        <ChangeView center={userLocation} />
        <MapEvents onZoneChange={onZoneChange} />
      </MapContainer>
    </div>
  );
};
