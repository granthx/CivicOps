"use client";

import { useEffect, useState } from "react";

import { apiBlob } from "@/lib/api";
import { MEDIA_KIND_LABELS } from "@/lib/format";
import type { MediaAsset } from "@/lib/types";

export function SecureImage({
  media,
  className = "",
  sizes,
}: {
  media: MediaAsset;
  className?: string;
  sizes?: string;
}) {
  const [result, setResult] = useState<{
    mediaId: number;
    url: string | null;
    failed: boolean;
  }>({ mediaId: media.id, url: null, failed: false });

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    apiBlob(`/media/${media.id}`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setResult({ mediaId: media.id, url: objectUrl, failed: false });
      })
      .catch(() => {
        if (!cancelled) {
          setResult({ mediaId: media.id, url: null, failed: true });
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [media.id]);

  const current = result.mediaId === media.id ? result : null;
  const url = current?.url ?? null;
  const failed = current?.failed ?? false;

  if (failed) {
    return (
      <div className={`secure-image-placeholder ${className}`} role="img" aria-label="Photo unavailable">
        Photo unavailable
      </div>
    );
  }

  if (!url) {
    return (
      <div
        className={`secure-image-placeholder is-loading ${className}`}
        role="status"
        aria-label="Loading photo"
      >
        <span className="spinner spinner-small" />
      </div>
    );
  }

  return (
    // Blob URLs are generated from authenticated API responses; Next image optimisation is unsuitable.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={`${MEDIA_KIND_LABELS[media.kind]} for civic report`}
      className={className}
      sizes={sizes}
    />
  );
}

export function SecureAudio({
  media,
  className = "",
}: {
  media: MediaAsset;
  className?: string;
}) {
  const [result, setResult] = useState<{
    mediaId: number;
    url: string | null;
    failed: boolean;
  }>({ mediaId: media.id, url: null, failed: false });

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    apiBlob(`/media/${media.id}`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setResult({ mediaId: media.id, url: objectUrl, failed: false });
      })
      .catch(() => {
        if (!cancelled) {
          setResult({ mediaId: media.id, url: null, failed: true });
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [media.id]);

  const current = result.mediaId === media.id ? result : null;
  const url = current?.url ?? null;
  const failed = current?.failed ?? false;

  if (failed) {
    return <span className="field-help">Voice note unavailable.</span>;
  }
  if (!url) {
    return <span className="field-help">Loading voice note…</span>;
  }

  return (
    <audio
      controls
      preload="metadata"
      src={url}
      className={className}
      style={{ width: "100%", maxWidth: 420 }}
      aria-label={`${MEDIA_KIND_LABELS[media.kind]} player`}
    />
  );
}
