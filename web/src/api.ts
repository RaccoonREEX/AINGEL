import type { Key } from "./i18n";

let csrf = "";

export class APIError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super("api_error");
  }
}

/** The message for a failed request. `notFound` names what a 404 means for this task (an invitation code…). */
export function errorKey(e: unknown, notFound: Key = "errorGeneric"): Key {
  if (!(e instanceof APIError)) return "errorGeneric";
  const detail = JSON.stringify(e.detail);
  // Age and consent policy (backend care.consent): checked first, they are not Meta failures.
  if (detail.includes("adult_declaration_required")) return "errorAdult";
  // Meta's Restricted Territories (backend care.territory), before the generic Meta failure below.
  if (detail.includes("territory_declaration_required")) return "errorTerritoryDeclare";
  if (detail.includes("territory_restricted")) return "errorTerritory";
  if (detail.includes("subject_minor_not_supported")) return "errorMinor";
  if (detail.includes("consent_subject_only")) return "errorSubjectOnly";
  if (detail.includes("legal_review_required")) return "errorLegalReview";
  if (detail.includes("consent_code_invalid")) return "errorConsentCode";
  if (detail.includes("consent_not_pending")) return "errorNotPending";
  if (detail.includes("consents_moved")) return "errorConsentsMoved";
  if (detail.includes("consent_changed")) return "errorConsentChanged";
  if (detail.includes("subject_confirmation_required")) return "errorSubjectConfirm";
  if (detail.includes("subject_already_confirmed")) return "errorSubjectConfirmed";
  // Not a Meta failure: the person has not allowed sending this data to Meta (decided in Personalizar).
  if (detail.includes("privacy_review_required")) return "errorPrivacy";
  if (detail.includes("mfa_")) return "mfaError";
  // The server switch is off (care.faces hotfix): nothing was processed; consulting and withdrawing still work.
  if (detail.includes("face_recognition_disabled")) return "faceServerOff";
  if (detail.includes("face_consent_changed")) return "faceConsentChanged";
  if (detail.includes("face_") || detail.includes("self_enrollment")) return "faceError";
  if (detail.includes("credentials_invalid")) return "errorAuth";
  if (detail.includes("registration_invalid")) return "errorRegister";
  if (detail.includes("care_circle_full")) return "errorFull";
  if (detail.includes("image_")) return "errorImage";
  if (detail.includes("meta_") || detail.includes("sam_") || detail.includes("privacy_review")) return "errorMeta";
  if (detail.includes("observation_")) return "errorFuture";
  if (e.status === 403) return "noAccess";
  if (e.status === 404) return notFound;
  return "errorGeneric";
}

/** [signal]: aborts the request (e.g. a revoked authorization); the caller gets an AbortError. */
export async function api<T = unknown>(
  path: string,
  method = "GET",
  data?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const multipart = data instanceof FormData;
  const response = await fetch("/api/v1/" + path, {
    method,
    signal,
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      ...(method !== "GET" ? { "X-CSRFToken": csrf } : {}),
      ...(!multipart && data !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
    },
    body:
      data === undefined ? undefined : multipart ? data : JSON.stringify(data),
  });
  if (response.status === 204) return undefined as T;
  let body;
  try {
    body = await response.json();
  } catch {
    throw new APIError(response.status, "server_unavailable");
  }
  if (!response.ok) throw new APIError(response.status, body);
  if (body && typeof body.csrf === "string") csrf = body.csrf;
  return body as T;
}
