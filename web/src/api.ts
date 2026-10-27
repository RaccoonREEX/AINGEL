let csrf = "";

export class APIError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super("api_error");
  }
}

export async function api<T = unknown>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const multipart = data instanceof FormData;
  const response = await fetch("/api/v1/" + path, {
    method,
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
