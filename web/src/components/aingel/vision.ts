/**
 * AINGEL 3.0 deep vision (backend assistance.vision, `vision/`). The server reads the detail level and the kind of
 * image from the question unless the request names them; each answer opens a short session so follow-ups are
 * answered about the same picture without sending it again.
 */

export type DetailLevel = "brief" | "standard" | "detailed" | "deep";
export const LEVELS: DetailLevel[] = ["brief", "standard", "detailed", "deep"];
export const LEVEL_NAMES: Record<DetailLevel, [string, string]> = {
  brief: ["Breve", "Brief"],
  standard: ["Estándar", "Standard"],
  detailed: ["Detallada", "Detailed"],
  deep: ["A fondo", "In depth"],
};
/** Server-drawn synthetic images (assistance.synthetic.IMAGES): choosing one sends only its id. */
export const FIXTURES: Record<string, [string, string]> = {
  shapes: ["Figuras: cuadrado azul y círculo rojo", "Shapes: blue square and red circle"],
  drawing_dog: ["Dibujo a mano de un perro", "Hand drawing of a dog"],
  drawing_ambiguous: ["Dibujo de trazos ambiguos", "Drawing of ambiguous strokes"],
  face_drawn: ["Retrato ilustrado de una persona ficticia", "Illustrated portrait of a fictitious person"],
  document_page: ["Página de un libro ficticio", "Page of a fictitious book"],
  chart_bars: ["Gráfico de barras", "Bar chart"],
};
export const REGIONS = ["top_left", "top", "top_right", "left", "center", "right", "bottom_left", "bottom", "bottom_right", "background"] as const;
export type Region = (typeof REGIONS)[number];
export const REGION_NAMES: Record<Region, [string, string]> = {
  top_left: ["Arriba a la izquierda", "Upper left"], top: ["Arriba", "Top"], top_right: ["Arriba a la derecha", "Upper right"],
  left: ["Izquierda", "Left"], center: ["Centro", "Centre"], right: ["Derecha", "Right"],
  bottom_left: ["Abajo a la izquierda", "Lower left"], bottom: ["Abajo", "Bottom"], bottom_right: ["Abajo a la derecha", "Lower right"],
  background: ["Fondo", "Background"],
};

export type VisionResult = {
  text: string;
  paragraphs?: string[];
  mode: "mock" | "meta";
  model: string | null;
  latency_ms: number | null;
  level: DetailLevel;
  task: string;
  region: Region | null;
  steps: number;
  session?: string;
  session_seconds?: number;
  safety_adjusted?: boolean;
};

type Picture =
  | { fixture: string }
  | { image: Blob; profile: string; testFields: Record<string, unknown>; question?: string };

/** A new picture. A typed question only goes with the person's own authorized image: next to a server fixture it
 * would be free content, which the server refuses. */
export function visionForm(locale: string, picture: Picture, level?: DetailLevel | "", source = "gallery"): FormData {
  const form = new FormData();
  form.set("locale", locale);
  form.set("source_kind", source);
  if (level) form.set("detail_level", level);
  if ("fixture" in picture) form.set("fixture", picture.fixture);
  else {
    form.set("image", picture.image, "image.jpg");
    form.set("profile", picture.profile);
    for (const [key, value] of Object.entries(picture.testFields)) form.set(key, String(value));
    const question = picture.question?.trim();
    if (question) form.set("question", question.slice(0, 600));
  }
  return form;
}

/** A follow-up about the session's picture: no profile or test declaration (the server rechecks the consent). */
export function followUpForm(locale: string, session: string, ask: { question?: string; level?: DetailLevel | ""; region?: Region | "" }): FormData {
  const form = new FormData();
  form.set("locale", locale);
  form.set("session", session);
  const question = ask.question?.trim();
  if (question) form.set("question", question.slice(0, 600));
  if (ask.level) form.set("detail_level", ask.level);
  if (ask.region) form.set("focus_region", ask.region);
  return form;
}

/** Errors that end a follow-up session: it expired, or the person's decisions changed. */
export const endsSession = (code: string) => ["visual_session_expired", "consent_changed", "camera_consent_revoked", "privacy_review_required"].includes(code);

/** [text] in parts a browser voice reads reliably (some stop long utterances): paragraphs, then sentences. */
export function speechParts(text: string, max = 1200): string[] {
  const parts: string[] = [];
  let current = "";
  const add = (piece: string) => {
    if (current && current.length + 1 + piece.length > max) { parts.push(current); current = ""; }
    current = current ? `${current} ${piece}` : piece;
  };
  for (const paragraph of text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean)) {
    if (current) { parts.push(current); current = ""; }
    for (const sentence of paragraph.length <= max ? [paragraph] : paragraph.split(/(?<=[.!?…])\s+/)) {
      for (let start = 0; start < sentence.length; start += max) add(sentence.slice(start, start + max));
    }
  }
  if (current) parts.push(current);
  return parts.length ? parts : [text];
}
