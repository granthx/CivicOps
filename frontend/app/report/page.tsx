"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/Icon";
import { LocationPicker } from "@/components/LocationPicker";
import {
  ConfidenceMeter,
  StatusPill,
} from "@/components/Ui";
import { apiFetch, errorMessage } from "@/lib/api";
import {
  CATEGORY_LABELS,
  formatDate,
  percent,
} from "@/lib/format";
import type {
  Category,
  ReportSubmission,
  Ward,
} from "@/lib/types";

const DEFAULT_LATITUDE = 12.9716;
const DEFAULT_LONGITUDE = 77.5946;
const MAX_PHOTO_BYTES = 8 * 1024 * 1024;
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const ALLOWED_AUDIO_TYPES = [
  "audio/webm",
  "audio/ogg",
  "audio/mpeg",
  "audio/mp3",
  "audio/mp4",
  "audio/x-m4a",
  "audio/wav",
  "audio/x-wav",
];

type ReportLanguage = "en" | "hi" | "hinglish";

const LANGUAGE_HINTS: Record<
  ReportLanguage,
  { label: string; placeholder: string; voiceLabel: string }
> = {
  en: {
    label: "English",
    placeholder:
      "Example: The community bin near the 4th Cross footpath is overflowing and waste has been piling up for three days.",
    voiceLabel: "Record a voice note (optional if you write a description)",
  },
  hi: {
    label: "हिन्दी (Hindi)",
    placeholder:
      "उदाहरण: मुख्य बाजार के पास कूड़ादान भर गया है और तीन दिन से कचरा पड़ा है।",
    voiceLabel: "आवाज़ में शिकायत रिकॉर्ड करें (वैकल्पिक)",
  },
  hinglish: {
    label: "Hinglish",
    placeholder:
      "Example: Market ke paas kudedan bhar gaya hai aur 3 din se kachra nahi utha hai.",
    voiceLabel: "Voice note record karein (Hindi / Hinglish / English)",
  },
};

const categoryOptions = Object.entries(CATEGORY_LABELS) as [Category, string][];

export default function ReportPage() {
  const [wards, setWards] = useState<Ward[]>([]);
  const [wardsError, setWardsError] = useState<string | null>(null);
  const [loadingWards, setLoadingWards] = useState(true);

  const [description, setDescription] = useState("");
  const [preferredLanguage, setPreferredLanguage] = useState<ReportLanguage>("en");
  const [category, setCategory] = useState<Category | "">("");
  const [address, setAddress] = useState("");
  const [wardId, setWardId] = useState("");
  const [latitude, setLatitude] = useState(DEFAULT_LATITUDE);
  const [longitude, setLongitude] = useState(DEFAULT_LONGITUDE);
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [audioPreview, setAudioPreview] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [audioError, setAudioError] = useState<string | null>(null);
  const [reporterName, setReporterName] = useState("");
  const [reporterContact, setReporterContact] = useState("");

  const [locating, setLocating] = useState(false);
  const [locationMessage, setLocationMessage] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submission, setSubmission] = useState<ReportSubmission | null>(null);
  const photoInputRef = useRef<HTMLInputElement>(null);
  const audioInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  async function loadWards() {
    setLoadingWards(true);
    setWardsError(null);
    try {
      const response = await apiFetch<Ward[]>("/wards");
      setWards(response);
      setWardId((current) => current || (response[0] ? String(response[0].id) : ""));
    } catch (caught) {
      setWardsError(errorMessage(caught));
    } finally {
      setLoadingWards(false);
    }
  }

  useEffect(() => {
    // Ward options are loaded once from the public API. Loading state is set
    // before the request so the select can show a deterministic placeholder.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadWards();
  }, []);

  useEffect(() => {
    if (!photoPreview) return;
    return () => URL.revokeObjectURL(photoPreview);
  }, [photoPreview]);

  useEffect(() => {
    if (!audioPreview) return;
    return () => URL.revokeObjectURL(audioPreview);
  }, [audioPreview]);

  useEffect(() => {
    if (!recording) return;
    const timer = window.setInterval(() => {
      setRecordingSeconds((sec) => sec + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [recording]);

  async function startRecording() {
    setAudioError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setAudioError("Voice recording is not supported in this browser. You can upload an audio file below.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : MediaRecorder.isTypeSupported("audio/ogg")
          ? "audio/ogg"
          : "";
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunks.push(ev.data);
      };
      recorder.onstop = () => {
        const finalType = recorder.mimeType || "audio/webm";
        const blob = new Blob(chunks, { type: finalType });
        const ext = finalType.includes("ogg") ? "ogg" : "webm";
        const file = new File([blob], `voice-complaint.${ext}`, { type: finalType });
        if (file.size > MAX_PHOTO_BYTES) {
          setAudioError("The voice recording must be 8 MB or smaller.");
        } else {
          setAudioFile(file);
          setAudioPreview(URL.createObjectURL(blob));
        }
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      };
      mediaRecorderRef.current = recorder;
      setRecordingSeconds(0);
      setRecording(true);
      recorder.start();
    } catch {
      setAudioError("Microphone permission denied or unavailable. You can upload an audio file instead.");
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setRecording(false);
  }

  function handleAudioFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setAudioError(null);
    if (!file) {
      setAudioFile(null);
      setAudioPreview(null);
      return;
    }
    const baseType = (file.type || "").split(";")[0].toLowerCase();
    if (!ALLOWED_AUDIO_TYPES.includes(baseType)) {
      setAudioError("Choose a WebM, OGG, MP3, M4A, or WAV audio file.");
      setAudioFile(null);
      setAudioPreview(null);
      if (audioInputRef.current) audioInputRef.current.value = "";
      return;
    }
    if (file.size > MAX_PHOTO_BYTES) {
      setAudioError("The audio file must be 8 MB or smaller.");
      setAudioFile(null);
      setAudioPreview(null);
      if (audioInputRef.current) audioInputRef.current.value = "";
      return;
    }
    setAudioFile(file);
    setAudioPreview(URL.createObjectURL(file));
  }

  function clearAudio() {
    setAudioFile(null);
    setAudioPreview(null);
    setAudioError(null);
    if (audioInputRef.current) audioInputRef.current.value = "";
  }

  function handlePhotoChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setFileError(null);
    if (!file) {
      setPhoto(null);
      setPhotoPreview(null);
      return;
    }
    if (!ALLOWED_TYPES.includes(file.type)) {
      setFileError("Choose a JPEG, PNG or WebP image.");
      setPhoto(null);
      setPhotoPreview(null);
      if (photoInputRef.current) photoInputRef.current.value = "";
      return;
    }
    if (file.size > MAX_PHOTO_BYTES) {
      setFileError("The photo must be 8 MB or smaller.");
      setPhoto(null);
      setPhotoPreview(null);
      if (photoInputRef.current) photoInputRef.current.value = "";
      return;
    }
    setPhoto(file);
    setPhotoPreview(URL.createObjectURL(file));
  }

  function clearPhoto() {
    setPhoto(null);
    setPhotoPreview(null);
    setFileError(null);
    if (photoInputRef.current) photoInputRef.current.value = "";
  }

  function useDeviceLocation() {
    setLocationMessage(null);
    if (!("geolocation" in navigator)) {
      setLocationMessage("This browser does not expose device location. Use the map or coordinates.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLatitude(Number(position.coords.latitude.toFixed(6)));
        setLongitude(Number(position.coords.longitude.toFixed(6)));
        setLocationMessage(
          "Using your device location. Confirm the pin against the map before submitting.",
        );
        setLocating(false);
      },
      () => {
        setLocationMessage(
          "Device location was unavailable. Place the pin manually on the map.",
        );
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 0 },
    );
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    if (!audioFile && description.trim().length < 10) {
      setFormError("Please describe the waste issue in at least 10 characters, or attach a voice note.");
      return;
    }
    if (!wardId) {
      setFormError("Select the ward where the issue is located.");
      return;
    }
    if (
      !Number.isFinite(latitude) ||
      !Number.isFinite(longitude) ||
      (latitude === 0 && longitude === 0)
    ) {
      setFormError("Place a valid location pin on the map.");
      return;
    }

    const formData = new FormData();
    formData.append("description", description.trim());
    formData.append("preferred_language", preferredLanguage);
    formData.append("latitude", String(latitude));
    formData.append("longitude", String(longitude));
    formData.append("ward_id", wardId);
    if (address.trim()) formData.append("address", address.trim());
    if (category) formData.append("submitted_category", category);
    if (photo) formData.append("photo", photo);
    if (audioFile) formData.append("audio", audioFile);
    if (reporterName.trim()) formData.append("reporter_name", reporterName.trim());
    if (reporterContact.trim()) formData.append("reporter_contact", reporterContact.trim());

    setSubmitting(true);
    try {
      const response = await apiFetch<ReportSubmission>("/reports", {
        method: "POST",
        body: formData,
      });
      setSubmission(response);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (caught) {
      setFormError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  function startAnotherReport() {
    setSubmission(null);
    setDescription("");
    setCategory("");
    setAddress("");
    setPhoto(null);
    setPhotoPreview(null);
    setAudioFile(null);
    setAudioPreview(null);
    setAudioError(null);
    setFileError(null);
    setFormError(null);
    setLocationMessage(null);
    setLatitude(DEFAULT_LATITUDE);
    setLongitude(DEFAULT_LONGITUDE);
    if (photoInputRef.current) photoInputRef.current.value = "";
    if (audioInputRef.current) audioInputRef.current.value = "";
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  if (submission) {
    const { report, incident, duplicate_candidates: duplicates, warnings } = submission;
    return (
      <div className="shell page-shell">
        <div className="track-panel">
          <article className="surface receipt">
            <header className="receipt-head">
              <span className="receipt-check">
                <Icon name="check" size={23} />
              </span>
              <div>
                <span className="eyebrow">Citizen report stored</span>
                <h1>Thank you. The report is on record.</h1>
                <p>
                  Your report was saved before AI enrichment ran. An operator
                  must review the suggestions before any operational decision
                  is made.
                </p>
              </div>
            </header>

            <div className="receipt-body">
              <div className="receipt-grid">
                <div className="receipt-id">
                  <span>Report ID</span>
                  <strong>{report.public_id}</strong>
                  <small>Use this ID to track the report.</small>
                </div>
                <div className="receipt-id">
                  <span>Incident reference</span>
                  <strong>{incident.public_id}</strong>
                  <small>
                    <StatusPill status={incident.status} />
                  </small>
                </div>
              </div>

              <div className="track-meta" style={{ marginBottom: 8 }}>
                <div>
                  <span>Submitted</span>
                  <strong>{formatDate(report.created_at)}</strong>
                </div>
                <div>
                  <span>Suggested category</span>
                  <strong>
                    {report.ai_category
                      ? CATEGORY_LABELS[report.ai_category]
                      : "Awaiting triage"}
                  </strong>
                </div>
                <div>
                  <span>AI confidence</span>
                  <strong>{percent(report.ai_confidence)}</strong>
                </div>
                <div>
                  <span>Ward</span>
                  <strong>{report.ward.name}</strong>
                </div>
              </div>

              {report.ai_status === "needs_review" && (
                <div className="notice notice-warning" style={{ marginTop: 14 }}>
                  <Icon name="alert" size={18} />
                  <div>
                    <strong>Manual review is expected</strong>
                    <p>
                      The suggestion confidence is low or the wording was
                      ambiguous. An operator will confirm the category.
                    </p>
                  </div>
                </div>
              )}

              {warnings.map((warning) => (
                <div
                  className="notice notice-warning"
                  key={warning}
                  style={{ marginTop: 10 }}
                >
                  <Icon name="spark" size={18} />
                  <div>
                    <strong>AI assistance note</strong>
                    <p>{warning}</p>
                  </div>
                </div>
              ))}

              {report.ai_summary && (
                <div className="receipt-section">
                  <h2>What we understood</h2>
                  <p>{report.ai_summary}</p>
                  <ConfidenceMeter value={report.ai_confidence} />
                </div>
              )}

              {duplicates.length > 0 ? (
                <div className="receipt-section">
                  <h2>Nearby reports that may be related</h2>
                  <p>
                    These are suggestions only. An operator decides whether to
                    link reports. Every report and its evidence stay preserved.
                  </p>
                  <div className="duplicate-mini">
                    {duplicates.map((duplicate) => (
                      <article key={duplicate.id}>
                        <header>
                          <strong className="mono">
                            {duplicate.candidate_report.public_id}
                          </strong>
                          <span>{Math.round(duplicate.score)}% match</span>
                        </header>
                        <p>{duplicate.candidate_report.description}</p>
                        <ul>
                          {duplicate.reasons.map((reason) => (
                            <li key={reason}>{reason}</li>
                          ))}
                        </ul>
                      </article>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="receipt-section">
                  <h2>Nearby reports</h2>
                  <p>
                    No related report candidates were found inside the current
                    proximity and time window. That is not a verification of
                    the location.
                  </p>
                </div>
              )}

              <div className="receipt-section">
                <div className="button-row">
                  <Link
                    className="button button-primary"
                    href={`/track?id=${encodeURIComponent(report.public_id)}`}
                  >
                    Track this report
                    <Icon name="arrow" size={17} />
                  </Link>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={startAnotherReport}
                  >
                    Submit another report
                  </button>
                </div>
                <p className="field-help" style={{ marginTop: 12 }}>
                  For immediate public-safety hazards, contact the appropriate
                  local emergency service. This demo intake is not monitored.
                </p>
              </div>

              <div className="provenance-note">
                <Icon name="shield" size={16} />
                <span>
                  This is a synthetic-capable hackathon environment. Do not
                  submit real personal or sensitive information.
                </span>
              </div>
            </div>
          </article>
        </div>
      </div>
    );
  }

  return (
    <div className="shell page-shell">
      <header className="page-head">
        <div className="page-head-copy">
          <span className="eyebrow">Citizen intake</span>
          <h1>Report a waste issue</h1>
          <p>
            Tell us what you can see and where it is. No account is needed. You
            will receive a report ID you can use to follow progress.
          </p>
        </div>
      </header>

      {wardsError && (
        <div className="error-panel" role="alert" style={{ marginBottom: 18 }}>
          <Icon name="alert" size={21} />
          <div>
            <strong>The report form cannot load yet</strong>
            <p>{wardsError}</p>
            <button
              className="button button-small button-secondary"
              type="button"
              onClick={() => void loadWards()}
            >
              <Icon name="refresh" size={15} />
              Retry
            </button>
          </div>
        </div>
      )}

      <div className="report-layout">
        <form className="surface form-card" onSubmit={handleSubmit} noValidate>
          {formError && (
            <div className="notice notice-error" role="alert" style={{ marginBottom: 18 }}>
              <Icon name="alert" size={18} />
              <div>
                <strong>Report not submitted</strong>
                <p>{formError}</p>
              </div>
            </div>
          )}

          <section className="form-section">
            <div className="form-section-head">
              <h2>What did you see?</h2>
              <p>Plain language is fine. Describe the waste and anything nearby.</p>
            </div>
            <div className="stack-form">
              <div className="field">
                <label htmlFor="report-language">Language / भाषा</label>
                <select
                  id="report-language"
                  value={preferredLanguage}
                  onChange={(event) =>
                    setPreferredLanguage(event.target.value as ReportLanguage)
                  }
                >
                  {(Object.entries(LANGUAGE_HINTS) as [ReportLanguage, { label: string }][]).map(
                    ([code, info]) => (
                      <option value={code} key={code}>
                        {info.label}
                      </option>
                    ),
                  )}
                </select>
                <p className="field-help">
                  You can write or speak in English, Hindi (हिन्दी), or Hinglish.
                </p>
              </div>

              <div className="field">
                <label htmlFor="report-description">
                  Description{" "}
                  <span className="optional">
                    ({audioFile ? "optional with voice note" : "required"})
                  </span>
                </label>
                <textarea
                  id="report-description"
                  required={!audioFile}
                  minLength={audioFile ? 0 : 10}
                  maxLength={2000}
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder={LANGUAGE_HINTS[preferredLanguage].placeholder}
                />
                <span className="form-counter">{description.length} / 2000</span>
                <p className="field-help">
                  Avoid including names, phone numbers or other personal details
                  in the description.
                </p>
              </div>

              <div className="field">
                <span className="field-label">
                  Voice note <span className="optional">(optional)</span>
                </span>
                <p className="field-help" style={{ marginTop: 0, marginBottom: 8 }}>
                  {LANGUAGE_HINTS[preferredLanguage].voiceLabel}
                </p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                  {!recording ? (
                    <button
                      type="button"
                      className="button button-secondary button-small"
                      onClick={() => void startRecording()}
                    >
                      Record voice note
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="button button-primary button-small"
                      onClick={stopRecording}
                    >
                      Stop recording ({recordingSeconds}s)
                    </button>
                  )}
                  <label
                    className="button button-secondary button-small"
                    htmlFor="report-audio-upload"
                    style={{ cursor: "pointer" }}
                  >
                    Upload audio file
                  </label>
                  <input
                    ref={audioInputRef}
                    id="report-audio-upload"
                    type="file"
                    accept="audio/webm,audio/ogg,audio/mpeg,audio/mp4,audio/wav"
                    onChange={handleAudioFileChange}
                    style={{ display: "none" }}
                  />
                  {audioFile && (
                    <button
                      type="button"
                      className="button button-small button-secondary"
                      onClick={clearAudio}
                    >
                      Remove audio
                    </button>
                  )}
                </div>
                {audioError && (
                  <p className="field-help" style={{ color: "var(--status-alert, #a83f2d)" }}>
                    {audioError}
                  </p>
                )}
                {audioPreview && (
                  <div style={{ marginTop: 10 }}>
                    <audio controls src={audioPreview} style={{ width: "100%", maxWidth: 420 }} />
                  </div>
                )}
              </div>

              <div className="field">
                <label htmlFor="report-category">
                  Category <span className="optional">(optional)</span>
                </label>
                <select
                  id="report-category"
                  value={category}
                  onChange={(event) =>
                    setCategory(event.target.value as Category | "")
                  }
                >
                  <option value="">Let the system suggest a category</option>
                  {categoryOptions.map(([value, label]) => (
                    <option value={value} key={value}>
                      {label}
                    </option>
                  ))}
                </select>
                <p className="field-help">
                  Your selection is a hint. AI triage and human review still
                  apply.
                </p>
              </div>

              <div className="field">
                <span className="field-label">
                  Photo <span className="optional">(optional)</span>
                </span>
                <label className="upload-field" htmlFor="report-photo">
                  <Icon name="camera" size={24} />
                  <strong>{photo ? "Replace photo" : "Add a photo"}</strong>
                  <span>JPEG, PNG or WebP · up to 8 MB</span>
                  <input
                    ref={photoInputRef}
                    id="report-photo"
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handlePhotoChange}
                  />
                </label>
                {fileError && <p className="field-error">{fileError}</p>}
                {photoPreview && (
                  <div className="upload-preview">
                    {/* Local object URL preview; file is uploaded only on submit. */}
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      className="photo-preview"
                      src={photoPreview}
                      alt="Selected report photo preview"
                    />
                    <button
                      className="button button-small button-secondary"
                      type="button"
                      onClick={clearPhoto}
                    >
                      Remove photo
                    </button>
                  </div>
                )}
                <p className="field-help">
                  Photos are re-encoded to remove metadata and are only visible
                  to authorised staff and you.
                </p>
              </div>
            </div>
          </section>

          <section className="form-section">
            <div className="form-section-head">
              <h2>Where is it?</h2>
              <p>Place the pin as close as you safely can to the issue.</p>
            </div>
            <div className="stack-form">
              <div className="field">
                <LocationPicker
                  latitude={latitude}
                  longitude={longitude}
                  onChange={(nextLatitude, nextLongitude) => {
                    setLatitude(nextLatitude);
                    setLongitude(nextLongitude);
                    setLocationMessage(null);
                  }}
                />
                <div className="location-tools">
                  <button
                    className="button button-small button-secondary"
                    type="button"
                    onClick={useDeviceLocation}
                    disabled={locating}
                  >
                    <Icon name="pin" size={15} />
                    {locating ? "Getting location…" : "Use my device location"}
                  </button>
                  {locationMessage && (
                    <span className="field-help" role="status">
                      {locationMessage}
                    </span>
                  )}
                </div>
              </div>

              <div className="field-row">
                <div className="field">
                  <label htmlFor="report-latitude">Latitude</label>
                  <input
                    id="report-latitude"
                    type="number"
                    step="0.000001"
                    min={-90}
                    max={90}
                    value={Number.isFinite(latitude) ? latitude : ""}
                    onChange={(event) =>
                      setLatitude(Number.parseFloat(event.target.value))
                    }
                    required
                  />
                </div>
                <div className="field">
                  <label htmlFor="report-longitude">Longitude</label>
                  <input
                    id="report-longitude"
                    type="number"
                    step="0.000001"
                    min={-180}
                    max={180}
                    value={Number.isFinite(longitude) ? longitude : ""}
                    onChange={(event) =>
                      setLongitude(Number.parseFloat(event.target.value))
                    }
                    required
                  />
                </div>
              </div>

              <div className="field-row">
                <div className="field">
                  <label htmlFor="report-ward">
                    Ward <span className="optional">(required)</span>
                  </label>
                  <select
                    id="report-ward"
                    required
                    value={wardId}
                    onChange={(event) => setWardId(event.target.value)}
                    disabled={loadingWards}
                  >
                    {loadingWards && <option value="">Loading wards…</option>}
                    {!loadingWards && wards.length === 0 && (
                      <option value="">No wards available</option>
                    )}
                    {wards.map((ward) => (
                      <option value={String(ward.id)} key={ward.id}>
                        {ward.name} ({ward.code})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="report-address">
                    Nearby landmark <span className="optional">(optional)</span>
                  </label>
                  <input
                    id="report-address"
                    value={address}
                    onChange={(event) => setAddress(event.target.value)}
                    maxLength={300}
                    placeholder="Street, cross, landmark or bin location"
                  />
                </div>
              </div>
            </div>
          </section>

          <section className="form-section">
            <div className="form-section-head">
              <h2>Your details</h2>
              <p>
                Optional. Contact information is used only for follow-up and is
                not shown to field workers by default.
              </p>
            </div>
            <div className="field-row">
              <div className="field">
                <label htmlFor="report-name">
                  Name <span className="optional">(optional)</span>
                </label>
                <input
                  id="report-name"
                  value={reporterName}
                  onChange={(event) => setReporterName(event.target.value)}
                  maxLength={120}
                  autoComplete="name"
                />
              </div>
              <div className="field">
                <label htmlFor="report-contact">
                  Email or phone <span className="optional">(optional)</span>
                </label>
                <input
                  id="report-contact"
                  value={reporterContact}
                  onChange={(event) => setReporterContact(event.target.value)}
                  maxLength={255}
                  autoComplete="email"
                  placeholder="Only if you want a follow-up"
                />
              </div>
            </div>
          </section>

          <div className="form-actions">
            <p className="form-actions-note">
              Submitting stores a citizen report. It does not dispatch a crew or
              confirm that the issue is verified.
            </p>
            <button
              className="button button-primary button-large"
              type="submit"
              disabled={submitting || loadingWards || wards.length === 0}
            >
              {submitting ? (
                <>
                  <span className="spinner spinner-small" />
                  Submitting report…
                </>
              ) : (
                <>
                  Submit report
                  <Icon name="arrow" size={18} />
                </>
              )}
            </button>
          </div>
        </form>

        <aside className="report-aside">
          <div className="aside-card">
            <h2>What happens next?</h2>
            <ol className="next-steps">
              <li>Your report is stored with a unique ID.</li>
              <li>
                AI suggests a category, severity and summary. If the model is
                unavailable, safe rules are used instead.
              </li>
              <li>
                Nearby reports are suggested to an operator. Nothing is merged
                automatically.
              </li>
              <li>
                An operator confirms triage before a work order can be assigned.
              </li>
              <li>
                Field evidence is reviewed by a human before the incident is
                marked verified.
              </li>
            </ol>
          </div>

          <div className="aside-card">
            <h2>AI, with limits</h2>
            <p>
              The model never rejects a report, dispatches a crew or closes a
              case. It can be uncertain, so confidence is shown and low-confidence
              results are queued for review.
            </p>
          </div>

          <div className="aside-card">
            <h2>Privacy</h2>
            <p>
              Photos are validated, re-encoded without metadata and served only
              to authorised users. Reporter contact details are withheld from
              field task views.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
