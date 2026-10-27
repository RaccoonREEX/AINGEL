export type User = { id: number; username: string };
export type Session = {
  user: User | null;
  csrf: string;
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
  role: "owner" | "caregiver";
  permissions: {
    configure: boolean;
    memories: boolean;
    manage_circle: boolean;
  };
  caregiver_count: number;
  ready: boolean;
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
