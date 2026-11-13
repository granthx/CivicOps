"use client";

import type { CircleMarker, Map as LeafletMap } from "leaflet";
import { useEffect, useRef, useState } from "react";

export function LocationPicker({
  latitude,
  longitude,
  onChange,
}: {
  latitude: number;
  longitude: number;
  onChange: (latitude: number, longitude: number) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markerRef = useRef<CircleMarker | null>(null);
  const onChangeRef = useRef(onChange);
  const [ready, setReady] = useState(false);
  const [tileIssue, setTileIssue] = useState(false);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    let cancelled = false;
    let map: LeafletMap | undefined;

    async function initialise() {
      const L = await import("leaflet");
      if (cancelled || !containerRef.current) return;
      map = L.map(containerRef.current, {
        zoomControl: true,
        scrollWheelZoom: false,
      }).setView([latitude, longitude], 15);
      const tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 19,
      }).addTo(map);
      tiles.on("tileerror", () => setTileIssue(true));
      markerRef.current = L.circleMarker([latitude, longitude], {
        radius: 11,
        color: "#ffffff",
        weight: 3,
        fillColor: "#245b43",
        fillOpacity: 1,
      }).addTo(map);
      map.on("click", (event) => {
        onChangeRef.current(
          Number(event.latlng.lat.toFixed(6)),
          Number(event.latlng.lng.toFixed(6)),
        );
      });
      mapRef.current = map;
      setReady(true);
    }

    void initialise();
    return () => {
      cancelled = true;
      markerRef.current = null;
      mapRef.current = null;
      map?.remove();
    };
    // Initialisation intentionally runs once. Position updates are handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!ready || !mapRef.current || !markerRef.current) return;
    markerRef.current.setLatLng([latitude, longitude]);
    mapRef.current.panTo([latitude, longitude], { animate: true });
  }, [ready, latitude, longitude]);

  return (
    <div className="location-picker">
      <div
        ref={containerRef}
        className="civic-map location-map"
        role="application"
        aria-label="Choose the report location by clicking the map. You can also use the latitude and longitude fields."
      />
      {tileIssue && (
        <div className="map-note">
          Base-map tiles are unavailable. You can still enter coordinates or use your
          device location.
        </div>
      )}
      <p className="map-hint">Click the map to place or move the report pin.</p>
    </div>
  );
}
