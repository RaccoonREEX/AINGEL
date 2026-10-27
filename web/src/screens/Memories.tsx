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
export default function Memories({
  profile,
  t,
  busy,
  run,
  refresh,
  date,
  version,
}: WithProfile & { version: number }) {
  const [items, setItems] = useState<Memory[]>([]);
  const base = `profiles/${profile.id}/memories/`;
  useEffect(() => {
    if (profile.permissions.memories)
      void run(async () => setItems(await api<Memory[]>(base)));
  }, [profile.id, version]);
  if (!profile.permissions.memories)
    return <p className="callout">{t("memoryDenied")}</p>;
  const localDate = new Date(
    Date.now() - new Date().getTimezoneOffset() * 60000,
  )
    .toISOString()
    .slice(0, 16);
  return (
    <>
      <p className="hint">{t("memoryNote")}</p>
      {profile.role === "owner" && (
        <section className="panel">
          <h2>{t("saveMemory")}</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const values = new FormData(form);
              const at = String(values.get("observed_at"));
              values.set("observed_at", new Date(at).toISOString());
              values.set("confirmed", "true");
              void run(async () => {
                await api(base, "POST", values);
                form.reset();
                await refresh();
              });
            }}
          >
            <div className="two-col">
              <Field label={t("entity")}>
                <input required name="entity" maxLength={100} />
              </Field>
              <Field label={t("location")}>
                <input required name="location" maxLength={200} />
              </Field>
              <Field label={t("observedAt")}>
                <input
                  required
                  name="observed_at"
                  type="datetime-local"
                  defaultValue={localDate}
                />
              </Field>
              <Field label={t("evidence")}>
                <input
                  name="evidence"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                />
              </Field>
            </div>
            <Field label={t("note")}>
              <textarea name="note" maxLength={1000} />
            </Field>
            <label className="check">
              <input required type="checkbox" />
              {t("confirmMemory")}
            </label>
            <button className="primary" disabled={busy}>
              {t("saveMemory")}
            </button>
          </form>
        </section>
      )}
      <section className="panel">
        <h2>{t("memoryTitle")}</h2>
        {items.length ? (
          items.map((item) => (
            <article className="message" key={item.id}>
              <span className="badge">{t("userReport")}</span>
              <h3>
                {item.entity} · {item.location}
              </h3>
              <p>{date(item.observed_at)}</p>
              <p className="prewrap">{item.note}</p>
              <p className="hint">
                {t("author")}: {item.author} · {t("expires")}:{" "}
                {date(item.expires_at)}
              </p>
              <div className="actions">
                {item.has_evidence && (
                  <a
                    className="button"
                    target="_blank"
                    rel="noreferrer"
                    href={"/api/v1/" + base + item.id + "/"}
                  >
                    {t("viewEvidence")}
                  </a>
                )}
                {profile.role === "owner" && (
                  <button
                    className="danger"
                    disabled={busy}
                    onClick={() =>
                      void run(async () => {
                        if (!window.confirm(t("confirmDelete"))) return;
                        await api(base + item.id + "/", "DELETE");
                        await refresh();
                      })
                    }
                  >
                    {t("delete")}
                  </button>
                )}
              </div>
            </article>
          ))
        ) : (
          <p className="empty">{t("noMemories")}</p>
        )}
      </section>
    </>
  );
}
