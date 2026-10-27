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
export default function Messages({
  profile,
  t,
  busy,
  run,
  refresh,
  date,
  version,
}: WithProfile & { version: number }) {
  const [items, setItems] = useState<CareMessage[]>([]);
  const base = `profiles/${profile.id}/messages/`;
  useEffect(() => {
    void run(async () => setItems(await api<CareMessage[]>(base)));
  }, [profile.id, version]);
  return (
    <>
      <section className="panel">
        <h2>{t("newMessage")}</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const data = new FormData(form);
            void run(async () => {
              await api(base, "POST", {
                body: data.get("body"),
                locale: profile.locale,
              });
              form.reset();
              await refresh();
            });
          }}
        >
          <Field label={t("messageBody")}>
            <textarea required name="body" maxLength={2000} />
          </Field>
          <button className="primary" disabled={busy}>
            {t("send")}
          </button>
        </form>
      </section>
      <section className="panel">
        {items.length ? (
          items.map((item) => (
            <article key={item.id} className="message">
              <p className="prewrap">{item.body}</p>
              <p className="hint">
                {item.author} · {date(item.created_at)} ·{" "}
                {t("originalLanguage")}: {item.locale}
              </p>
              {profile.role === "owner" && (
                <button
                  disabled={busy}
                  className="danger"
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
            </article>
          ))
        ) : (
          <p className="empty">{t("noMessages")}</p>
        )}
      </section>
    </>
  );
}
