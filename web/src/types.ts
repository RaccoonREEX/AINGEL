/** adult_declared: the account's own 18+ self-declaration (backend care.consent); Meta stays closed without it. */
export type User = { id: number; username: string; adult_declared?: boolean };
export type Session = {
  user: User | null;
  csrf: string;
  terms_version?: string;
  mfa_required?: boolean;
};
export type Profile = {
  id: string;
  display_name: string;
  locale: string;
  timezone: string;
  allergies: string;
  support_notes: string;
  emergency_contact: string;
  preferences: Record<string, boolean>;
  /** subject: the signed-in account is the person this profile describes (linked with a code). */
  role: "owner" | "caregiver" | "subject";
  subject_status?: SubjectStatus;
  permissions: {
    configure: boolean;
    memories: boolean;
    manage_circle: boolean;
  };
  caregiver_count: number;
  ready: boolean;
  consents?: Consents;
};
/** Legacy coarse flags, read-only: they no longer authorize anything (decisions are per purpose). */
export type Consents = { camera?: boolean; microphone?: boolean; meta_data?: boolean; version?: string; granted_at?: string; granted_by?: string };
export type SubjectStatus = "pending_confirmation" | "self" | "pending_consent" | "subject_linked" | "requires_legal_review";
export type Purpose = { id: string; to: "local" | "meta" | "aingel"; title: string; detail: string };
export type PurposeStatus = "granted" | "declined" | "revoked" | "pending";
export type Purposes = { version: string; terms_version: string; credits_notice: string; purposes: Purpose[] };
/** GET profiles/<id>/consent/: only the person (is_subject) decides, purpose by purpose. */
export type ConsentState = {
  version: string;
  subject_status: SubjectStatus;
  is_subject: boolean;
  subject_adult: boolean;
  purposes: (Purpose & { status: PurposeStatus })[];
  credits_notice: string;
  can_confirm?: boolean;
};
export type Routine = {
  id: string;
  category: string;
  title: string;
  at: string;
  weekdays: number[];
  instructions: string;
  active: boolean;
  author: string;
  confirmed_today: boolean;
  confirmation_actor: string | null;
};
export type CareMessage = {
  id: string;
  body: string;
  locale: string;
  author: string;
  created_at: string;
};
export type Memory = {
  id: string;
  entity: string;
  location: string;
  observed_at: string;
  source: string;
  note: string;
  author: string;
  has_evidence: boolean;
  expires_at: string;
};
export type Member = {
  id: string;
  username: string;
  relationship: string;
  can_configure: boolean;
  can_view_memories: boolean;
};
export type Circle = {
  members: Member[];
  pending: {
    id: string;
    username: string;
    relationship: string;
    expires_at: string;
  }[];
  maximum: number;
};
export type Scene = {
  text: string;
  mode: "mock" | "meta";
  model: string | null;
  latency_ms: number | null;
};
export type Located = {
  mode: "mock" | "meta";
  model: string | null;
  latency_ms: number | null;
  analyzed: boolean;
  matches: {
    id: string;
    box: [number, number, number, number];
    confidence: number | null;
    horizontal: "left" | "right" | "center";
    mask_png: string;
  }[];
};
