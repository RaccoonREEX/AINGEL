/**
 * AINGEL 3.0 documents (backend assistance.documents, `documents/`): the PDF's own text is read locally by the
 * server, page by page; scanned pages are transcribed by Meta on request; explanations and questions go to Meta.
 */

export const DOCUMENT_FIXTURES: Record<string, [string, string]> = {
  book_pdf: ["Libro ficticio en PDF (4 páginas, 3 capítulos)", "Fictitious PDF book (4 pages, 3 chapters)"],
  scanned_pdf: ["PDF escaneado ficticio (2 páginas, sin texto)", "Fictitious scanned PDF (2 pages, no text)"],
};

export type DocumentInfo = {
  document: string;
  pages: number;
  title: string;
  outline: { title: string; page: number; level: number }[];
  synthetic_fixture: string | null;
  expires_in: number;
};
export type DocumentPage = {
  page: number;
  pages: number;
  chapter: string | null;
  text: string;
  paragraphs: string[];
  has_text: boolean;
  transcribed: boolean;
};
export type DocumentAnswer = { text: string; paragraphs: string[]; mode: "mock" | "meta"; model: string | null; latency_ms: number | null };
export type DocumentAction = "explain" | "summarize" | "figures" | "question";

/** Opening: a server fixture carries only its id; the person's own file goes with their authorization fields. */
export function openForm(locale: string, source: { fixture: string } | { file: Blob; name: string; profile: string; testFields: Record<string, unknown> }): FormData {
  const form = new FormData();
  form.set("locale", locale);
  if ("fixture" in source) form.set("fixture", source.fixture);
  else {
    form.set("file", source.file, source.name);
    form.set("profile", source.profile);
    for (const [key, value] of Object.entries(source.testFields)) form.set(key, String(value));
  }
  return form;
}

/** A request to Meta about the document. A typed question never goes with a fixture (the server refuses it). */
export function askBody(action: DocumentAction, page: number, scope: "page" | "document", question?: string) {
  const body: Record<string, unknown> = { action, page, scope };
  const text = question?.trim();
  if (action === "question" && text) body.question = text.slice(0, 600);
  return body;
}

/** The page to show after [current] for a move, within 1..[pages]. */
export const clampPage = (value: number, pages: number) => Math.min(Math.max(1, Math.round(value) || 1), pages);

/** Errors after which the document is gone: expired or closed, or the person's decisions changed. */
export const endsDocument = (code: string) => ["document_expired", "consent_changed", "camera_consent_revoked"].includes(code);
