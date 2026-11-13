"use client";

import type { LayerGroup, Map as LeafletMap } from "leaflet";
import { useEffect, useRef, useState } from "react";

import { CATEGORY_LABELS, PRIORITY_LABELS } from "@/lib/format";
import type { HotspotCluster, Priority } from "@/lib/types";

export interface MapPoint {
  id: number;
  latitude: number;
  longitude: number;
  publicId: string;
  title: string;
  priority: Priority;
  reportCount: number;
}

const PRIORITY_COLORS: Record<Priority, string> = {
  critical: "#a83f2d",
  high: "#bb6b22",
  medium: "#4d735c",
  low: "#7f897f",
};

export function IncidentMap({
  points,
  hotspots = [],
  showHotspots = true,
  selectedClusterId,
  onSelectCluster,
  selectedId,
  onSelect,
  height = 480,
  label = "Incident map",
}: {
  points: MapPoint[];
  hotspots?: HotspotCluster[];
  showHotspots?: boolean;
  selectedClusterId?: string | null;
  onSelectCluster?: (cluster: HotspotCluster) => void;
  selectedId?: number | null;
  onSelect?: (id: number) => void;
  height?: number;
  label?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const groupRef = useRef<LayerGroup | null>(null);
  const onSelectRef = useRef(onSelect);
  const onSelectClusterRef = useRef(onSelectCluster);
  const [ready, setReady] = useState(false);
  const [tileIssue, setTileIssue] = useState(false);

  useEffect(() => {
    onSelectRef.current = onSelect;
    onSelectClusterRef.current = onSelectCluster;
  }, [onSelect, onSelectCluster]);

  const pointsJson = JSON.stringify(points);
  const hotspotsJson = JSON.stringify(showHotspots ? hotspots : []);

  useEffect(() => {
    let cancelled = false;
    let map: LeafletMap | undefined;

    async function initialise() {
      const L = await import("leaflet");
      if (cancelled || !containerRef.current) return;
      map = L.map(containerRef.current, {
        zoomControl: true,
        scrollWheelZoom: true,
        attributionControl: true,
      }).setView([12.9716, 77.5946], 11);
      const tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 19,
      }).addTo(map);
      tiles.on("tileerror", () => setTileIssue(true));
      groupRef.current = L.layerGroup().addTo(map);
      mapRef.current = map;
      setReady(true);
    }

    void initialise();
    return () => {
      cancelled = true;
      groupRef.current = null;
      mapRef.current = null;
      map?.remove();
    };
  }, []);

  useEffect(() => {
    if (!ready || !mapRef.current || !groupRef.current) return;
    let cancelled = false;

    async function draw() {
      const L = await import("leaflet");
      if (cancelled || !groupRef.current) return;
      const currentPoints = JSON.parse(pointsJson) as MapPoint[];
      const currentHotspots = JSON.parse(hotspotsJson) as HotspotCluster[];
      groupRef.current.clearLayers();

      for (const cluster of currentHotspots) {
        const clusterSelected = selectedClusterId === cluster.cluster_id;
        const zone = L.circle([cluster.latitude, cluster.longitude], {
          radius: cluster.radius_m,
          color: clusterSelected ? "#15231b" : "#a83f2d",
          weight: clusterSelected ? 2.5 : 1.5,
          dashArray: "5 4",
          fillColor: "#a83f2d",
          fillOpacity: clusterSelected ? 0.24 : 0.14,
        });
        const tip = document.createElement("div");
        tip.className = "map-tooltip-content";
        const name = document.createElement("strong");
        name.textContent = `${cluster.cluster_id} · ${cluster.ward_name} hotspot`;
        const detail = document.createElement("span");
        detail.textContent = `${cluster.incident_count} incidents · ${cluster.total_reports} reports · ${CATEGORY_LABELS[cluster.top_category]} · Chronic score ${cluster.chronic_score}`;
        tip.append(name, detail);
        zone.bindTooltip(tip, {
          direction: "top",
          offset: [0, -6],
          opacity: 1,
          className: "civic-map-tooltip",
        });
        zone.on("click", () => onSelectClusterRef.current?.(cluster));
        groupRef.current.addLayer(zone);
      }

      for (const point of currentPoints) {
        const color = PRIORITY_COLORS[point.priority];
        const selected = selectedId === point.id;
        const marker = L.circleMarker([point.latitude, point.longitude], {
          radius: 9 + Math.min(7, point.reportCount * 2),
          weight: selected ? 4 : 2,
          color: selected ? "#15231b" : "#ffffff",
          fillColor: color,
          fillOpacity: 0.9,
          opacity: 1,
        });
        const tip = document.createElement("div");
        tip.className = "map-tooltip-content";
        const name = document.createElement("strong");
        name.textContent = point.publicId;
        const detail = document.createElement("span");
        detail.textContent = `${point.title} · ${PRIORITY_LABELS[point.priority]} · ${point.reportCount} report${point.reportCount === 1 ? "" : "s"}`;
        tip.append(name, detail);
        marker.bindTooltip(tip, {
          direction: "top",
          offset: [0, -8],
          opacity: 1,
          className: "civic-map-tooltip",
        });
        marker.on("click", () => onSelectRef.current?.(point.id));
        groupRef.current.addLayer(marker);
      }
    }

    void draw();
    return () => {
      cancelled = true;
    };
  }, [ready, pointsJson, hotspotsJson, selectedId, selectedClusterId]);

  useEffect(() => {
    if (!ready || !mapRef.current || pointsJson === "[]") return;
    const currentPoints = JSON.parse(pointsJson) as MapPoint[];
    const L = import("leaflet");
    void L.then((leaflet) => {
      if (!mapRef.current) return;
      const bounds = leaflet.latLngBounds(
        currentPoints.map(
          (point) => [point.latitude, point.longitude] as [number, number],
        ),
      );
      mapRef.current.fitBounds(bounds, { padding: [34, 34], maxZoom: 15 });
    });
  }, [ready, pointsJson]);

  return (
    <div className="map-wrap">
      <div
        ref={containerRef}
        className="civic-map"
        style={{ height }}
        role="region"
        aria-label={`${label}. The adjacent incident queue is the accessible record list.`}
      />
      <div className="map-legend" aria-hidden="true">
        {(["critical", "high", "medium", "low"] as Priority[]).map((priority) => (
          <span key={priority}>
            <i style={{ background: PRIORITY_COLORS[priority] }} />
            {PRIORITY_LABELS[priority]}
          </span>
        ))}
      </div>
      {points.length === 0 && (
        <div className="map-empty">
          <strong>No mapped incidents</strong>
          <span>Adjust the queue filters to see records.</span>
        </div>
      )}
      {tileIssue && (
        <div className="map-note">
          Base-map tiles are unavailable. Markers and the queue still use API data.
        </div>
      )}
    </div>
  );
}
