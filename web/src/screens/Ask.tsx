import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import Field from "../components/Field";
import type { Context, WithProfile } from "../ui";
import type { Key } from "../i18n";
import { activityLabel } from "../i18n";
import type {
  Circle,
  Member,
  Memory,
  Profile,
  Routine,
  CareMessage,
  Scene,
  Located,
} from "../types";
export default function Ask({ profile, t, busy, run, date }: WithProfile) {
  const [result, setResult] = useState<{
    tool: string;
    found?: boolean;
    evidence?: Memory;
    items?: (Routine & CareMessage)[];
  } | null>(null);
  const query = async (tool: string, entity?: string) => {
    setResult(
      await api(`profiles/${profile.id}/ask/`, "POST", { tool, entity }),
    );
  };
  return (
    <>
      <p>{t("askIntro")}</p>
      <section className="panel">
        <h2>{t("findMemory")}</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            void run(() => query("search_memory", String(data.get("entity"))));
          }}
        >
          <Field label={t("entity")}>
            <input name="entity" required maxLength={100} />
          </Field>
          <button
            className="primary"
            disabled={busy || !profile.permissions.memories}
          >
            {t("search")}
          </button>
        </form>
        <div className="actions spaced">
          <button
            disabled={busy}
            onClick={() => void run(() => query("get_routines"))}
          >
            {t("getRoutines")}
          </button>
          <button
            disabled={busy}
            onClick={() => void run(() => query("get_care_messages"))}
          >
            {t("getMessages")}
          </button>
        </div>
      </section>
      {result && (
        <section className="panel" aria-live="polite">
          <span className="badge">{t("evidenceMode")}</span>
          {result.tool === "search_memory" ? (
            result.evidence ? (
              <>
                <h2>
                  {t("lastReported")}: {result.evidence.location}
                </h2>
                <p>
                  {result.evidence.entity} · {date(result.evidence.observed_at)}
                </p>
                <p className="hint">
                  {t("author")}: {result.evidence.author} · {t("userReport")}
                </p>
              </>
            ) : (
              <p className="empty">{t("noEvidence")}</p>
            )
          ) : (
            <>
              <h2>
                {t(result.tool === "get_routines" ? "today" : "messages")}
              </h2>
              {!result.items?.length && (
                <p>
                  {t(
                    result.tool === "get_routines"
                      ? "noRoutines"
                      : "noMessages",
                  )}
                </p>
              )}
              {result.items?.map((x) => (
                <article className="message" key={x.id}>
                  <strong>
                    {x.title ? `${x.at.slice(0, 5)} · ${x.title}` : x.body}
                  </strong>
                  <p>{x.instructions}</p>
                  <p className="hint">
                    {t("author")}: {x.author}
                  </p>
                </article>
              ))}
            </>
          )}
        </section>
      )}
    </>
  );
}
