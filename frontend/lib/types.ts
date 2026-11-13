export type Role = "citizen" | "field_worker" | "operator" | "admin";

export type Category =
  | "garbage_accumulation"
  | "overflowing_bin"
  | "missed_collection"
  | "illegal_dumping"
  | "dead_animal"
  | "other_waste";

export type Severity = "low" | "moderate" | "high" | "critical";
export type Priority = "low" | "medium" | "high" | "critical";

export type IncidentStatus =
  | "open"
  | "triaged"
  | "assigned"
  | "in_progress"
  | "blocked"
  | "verification_pending"
  | "verified"
  | "reopened"
  | "merged";

export type WorkOrderStatus =
  | "assigned"
  | "accepted"
  | "in_progress"
  | "blocked"
  | "completed"
  | "verified"
  | "reopened";

export type TriageStatus = "pending" | "succeeded" | "failed" | "needs_review";
export type DuplicateStatus = "suggested" | "accepted" | "rejected";
export type MediaKind = "report_photo" | "report_audio" | "before_photo" | "after_photo";

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  team_id: number | null;
  team_name: string | null;
  is_demo: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: User;
}

export interface Ward {
  id: number;
  name: string;
  code: string;
  city: string;
}

export interface Team {
  id: number;
  name: string;
  ward_id: number;
  team_type: string;
  is_active: boolean;
}

export interface MediaAsset {
  id: number;
  public_id: string;
  kind: MediaKind;
  content_type: string;
  size_bytes: number;
  width: number;
  height: number;
  created_at: string;
}

export interface Report {
  id: number;
  public_id: string;
  description: string;
  preferred_language: string | null;
  voice_transcript: string | null;
  detected_language: string | null;
  address: string | null;
  latitude: number;
  longitude: number;
  ward: Ward;
  submitted_category: Category | null;
  ai_status: TriageStatus;
  ai_category: Category | null;
  ai_severity: Severity | null;
  ai_confidence: number | null;
  ai_summary: string | null;
  ai_indicators: string[];
  ai_rationale: string | null;
  ai_provider: string | null;
  ai_model: string | null;
  ai_fallback_used: boolean;
  ai_error: string | null;
  ai_processed_at: string | null;
  incident_id: number | null;
  incident_public_id: string | null;
  link_type: string | null;
  reporter_name: string | null;
  reporter_contact: string | null;
  citizen_rating?: number | null;
  citizen_feedback?: string | null;
  citizen_reopen_requested?: boolean;
  is_demo: boolean;
  media: MediaAsset[];
  created_at: string;
}

export interface PriorityFactor {
  label: string;
  points: number;
  max_points: number;
  explanation: string;
}

export interface PriorityFactors {
  score: number;
  priority: Priority;
  factors: PriorityFactor[];
  generated_at: string;
  model?: string;
  disclaimer?: string;
}

export interface WorkOrderBrief {
  id: number;
  public_id: string;
  status: WorkOrderStatus;
  team_id: number;
  team_name: string;
  due_at: string | null;
}

export type SlaState = "on_track" | "at_risk" | "breached" | "met";

export interface SlaStatus {
  sla_state: SlaState;
  due_at: string;
  remaining_hours: number;
  is_overdue: boolean;
}

export interface Incident {
  id: number;
  public_id: string;
  title: string;
  description: string;
  category: Category;
  severity: Severity;
  status: IncidentStatus;
  priority: Priority;
  recommended_priority: Priority;
  priority_score: number;
  priority_factors: PriorityFactors | null;
  priority_overridden: boolean;
  priority_override_reason: string | null;
  ward: Ward;
  address: string | null;
  latitude: number;
  longitude: number;
  report_count: number;
  active_work_order: WorkOrderBrief | null;
  sla?: SlaStatus | null;
  triaged_at: string | null;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuditEvent {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number;
  old_status: string | null;
  new_status: string | null;
  note: string | null;
  actor_name: string;
  actor_role: string;
  event_metadata: Record<string, unknown>;
  created_at: string;
}

export interface CandidateReport {
  id: number;
  public_id: string;
  description: string;
  latitude: number;
  longitude: number;
  ward_name: string;
  ai_category: Category | null;
  created_at: string;
  media: MediaAsset[];
}

export interface DuplicateCandidate {
  id: number;
  score: number;
  distance_m: number;
  reasons: string[];
  status: DuplicateStatus;
  candidate_report: CandidateReport;
  candidate_incident_id: number | null;
  candidate_incident_public_id: string | null;
  candidate_incident_status: IncidentStatus | null;
  review_note: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface WorkOrderIncident {
  id: number;
  public_id: string;
  title: string;
  description: string;
  category: Category;
  priority: Priority;
  status: IncidentStatus;
  latitude: number;
  longitude: number;
  address: string | null;
  ward: Ward;
}

export interface WorkOrder {
  id: number;
  public_id: string;
  incident_id: number;
  incident: WorkOrderIncident;
  team: Team;
  instructions: string;
  due_at: string | null;
  status: WorkOrderStatus;
  completion_note: string | null;
  verification_note: string | null;
  completed_at: string | null;
  verified_at: string | null;
  evidence: MediaAsset[];
  sla?: SlaStatus | null;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkOrderDetail extends WorkOrder {
  reports: Report[];
  activity: AuditEvent[];
}

export interface IncidentDetail extends Incident {
  reports: Report[];
  work_orders: WorkOrder[];
  activity: AuditEvent[];
  duplicate_candidates: DuplicateCandidate[];
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ReportSubmission {
  report: Report;
  incident: Incident;
  duplicate_candidates: DuplicateCandidate[];
  warnings: string[];
}

export interface PublicReportStatus {
  public_id: string;
  submitted_at: string;
  category: Category | null;
  summary: string | null;
  incident_public_id: string | null;
  incident_status: IncidentStatus | null;
  verified_at?: string | null;
  sla_state?: SlaState | null;
  due_at?: string | null;
  citizen_rating?: number | null;
  citizen_feedback?: string | null;
  citizen_feedback_at?: string | null;
  citizen_reopen_requested?: boolean;
  is_demo: boolean;
}

export interface CountItem {
  key: string;
  label: string;
  count: number;
}

export interface Hotspot {
  incident_id: number;
  public_id: string;
  latitude: number;
  longitude: number;
  ward_name: string;
  category: Category;
  priority: Priority;
  status: IncidentStatus;
  report_count: number;
}

export interface AnalyticsSummary {
  generated_at: string;
  active_incidents: number;
  awaiting_triage: number;
  unassigned_incidents: number;
  in_progress: number;
  blocked: number;
  verification_pending: number;
  verified_last_7_days: number;
  total_reports: number;
  reports_last_7_days: number;
  accepted_duplicate_links: number;
  sla_breached_count: number;
  sla_at_risk_count: number;
  status_counts: CountItem[];
  category_counts: CountItem[];
  ward_counts: CountItem[];
  hotspots: Hotspot[];
}

export interface HotspotCluster {
  cluster_id: string;
  latitude: number;
  longitude: number;
  radius_m: number;
  ward_name: string;
  incident_count: number;
  active_incident_count: number;
  total_reports: number;
  top_category: Category;
  max_priority: Priority;
  chronic_score: number;
  is_chronic: boolean;
  recommendation: string;
  incident_ids: number[];
  public_ids: string[];
  latest_incident_at: string;
}

export interface HotspotListResponse {
  generated_at: string;
  window_days: number;
  radius_m: number;
  clusters: HotspotCluster[];
}

export interface SlaSweepResponse {
  swept_at: string;
  escalated_count: number;
  escalated_work_order_public_ids: string[];
}

export interface PublicIncidentMapItem {
  id: number;
  public_id: string;
  title: string;
  category: Category;
  priority: Priority;
  status: IncidentStatus;
  ward_name: string | null;
  latitude: number;
  longitude: number;
  report_count: number;
  primary_report_public_id?: string | null;
  created_at: string;
  verified_at: string | null;
  is_demo: boolean;
}

export interface ChatResponse {
  reply: string;
  guardrail_triggered: boolean;
  refusal_reason: string | null;
  provider: string;
  suggestions: string[];
}
