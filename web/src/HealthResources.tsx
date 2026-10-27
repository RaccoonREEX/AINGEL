import { useState } from "react";
import { api } from "./api";
import Field from "./components/Field";
import type { WithProfile } from "./ui";

type Resource = {
  title: string;
  url: string;
  lang: string;
  summary: string;
  source: string;
  downloaded_at: string;
};

export default function HealthResources({
  profile,
  t,
  busy,
  run,
  locale,
  date,
  onSelect,
}: Pick<WithProfile, "profile" | "t" | "busy" | "run" | "locale" | "date"> & {
  onSelect: (title: string, lang: string) => void;
}) {
  const [items, setItems] = useState<Resource[] | null>(null);
  return (
    <section className="panel">
      <h2>{t("knowledgeTitle")}</h2>
      <p>{t("knowledgeIntro")}</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          setItems(null);
          void run(async () =>
            setItems(
              await api<Resource[]>(
                `profiles/${profile.id}/resources/search/`,
                "POST",
                {
                  q: String(form.get("q") || "").trim(),
                  lang: locale === "en-US" ? "en" : "es",
                },
              ),
            ),
          );
        }}
      >
        <Field label={t("knowledgeSearch")}>
          <input name="q" maxLength={100} required />
        </Field>
        <button className="primary" disabled={busy}>
          {t("search")}
        </button>
      </form>
      <div aria-live="polite">
        {items && items.length === 0 && <p>{t("knowledgeNone")}</p>}
        {items?.map((item) => (
          <article className="message" key={item.url}>
            <h3>{item.title}</h3>
            <details>
              <summary>{t("knowledgeReadSummary")}</summary>
              <p>{item.summary}</p>
            </details>
            <p className="hint">
              {t("knowledgeSource")} · {t("knowledgeDate")}:{" "}
              {date(item.downloaded_at)}
            </p>
            <button
              type="button"
              onClick={() => onSelect(item.title, item.lang)}
            >
              {t("chatUseSource")}
            </button>{" "}
            <a href={item.url} target="_blank" rel="noopener noreferrer">
              {t("knowledgeOpen")}
            </a>
          </article>
        ))}
      </div>
    </section>
  );
}
