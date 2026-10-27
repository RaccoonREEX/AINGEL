import { useState } from "react";
import { api } from "./api";
import Field from "./components/Field";
import type { WithProfile } from "./ui";

export type TopicChoice = { title: string; lang: "es" | "en" };
type Answer = {
  mode: "meta" | "mock";
  model: string | null;
  text: string;
  source: null | {
    title: string;
    url: string;
    source: string;
    downloaded_at: string;
  };
};

export default function CompanionChat({
  profile,
  t,
  busy,
  run,
  topic,
  clearTopic,
  speak,
}: Pick<WithProfile, "profile" | "t" | "busy" | "run"> & {
  topic: TopicChoice | null;
  clearTopic: () => void;
  speak: (text: string) => void;
}) {
  const [consent, setConsent] = useState(false);
  const [question, setQuestion] = useState("");
  const [saved, setSaved] = useState<{ key: string; value: Answer } | null>(
    null,
  );
  const key = JSON.stringify([
    profile.id,
    question.trim(),
    topic?.title,
    topic?.lang,
  ]);
  const answer = saved?.key === key ? saved.value : null;
  return (
    <section className="panel">
      <h2>{t("chatTitle")}</h2>
      <p>{t("chatIntro")}</p>
      <p className="callout">{t("chatPrivacy")}</p>
      {topic ? (
        <p>
          {t("chatSelectedSource")}: {topic.title}{" "}
          <button type="button" onClick={clearTopic}>
            {t("chatRemoveSource")}
          </button>
        </p>
      ) : (
        <p>{t("chatNoSource")}</p>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const text = question.trim();
          setSaved(null);
          setConsent(false);
          void run(async () => {
            const value = await api<Answer>(
              `profiles/${profile.id}/companion/chat/`,
              "POST",
              {
                text,
                synthetic: true,
                ...(topic
                  ? { topic_title: topic.title, topic_lang: topic.lang }
                  : {}),
              },
            );
            setSaved({ key, value });
          });
        }}
      >
        <Field label={t("chatQuestion")}>
          <textarea
            name="text"
            required
            maxLength={1000}
            value={question}
            onChange={(e) => {
              setQuestion(e.target.value);
              setConsent(false);
            }}
          />
        </Field>
        <label className="check">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
          />
          {t("chatConsent")}
        </label>
        <button className="primary" disabled={busy || !consent}>
          {t("chatSend")}
        </button>
      </form>
      {answer && (
        <article aria-live="polite" className="message">
          <span className="badge">
            {answer.mode === "meta" ? t("meta") : t("mock")}
          </span>
          <p>{answer.text}</p>
          <button onClick={() => speak(answer.text)}>{t("readAnswer")}</button>
          {answer.source && (
            <p>
              {answer.source.source} ·{" "}
              <a
                href={answer.source.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {answer.source.title}
              </a>
            </p>
          )}
        </article>
      )}
    </section>
  );
}
