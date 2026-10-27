import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import Field from "../components/Field";
import type { Context, WithProfile } from "../ui";
import type { Key } from "../i18n";
import { activityLabel } from "../i18n";
import { useCommunication } from "../Communication";
import HealthResources from "../HealthResources";
import CompanionChat, { type TopicChoice } from "../CompanionChat";
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
export default function Ask({
  profile,
  t,
  busy,
  run,
  date,
  locale,
}: WithProfile) {
  const { value: communication, failed: communicationFailed } =
    useCommunication(profile.id);
  const [itemIndex, setItemIndex] = useState(0);
  const [voiceError, setVoiceError] = useState(false);
  const [showSupport, setShowSupport] = useState(false);
  const [topic, setTopic] = useState<TopicChoice | null>(null);
  const [result, setResult] = useState<{
    tool: string;
    found?: boolean;
    evidence?: Memory;
    items?: (Routine & CareMessage)[];
  } | null>(null);
  const query = async (tool: string, entity?: string) => {
    setItemIndex(0);
    setResult(
      await api(`profiles/${profile.id}/ask/`, "POST", { tool, entity }),
    );
  };
  const greeting = `${t("greetingShort")}, ${communication?.preferred_name || profile.display_name}. ${t(
    communication?.addressing === "formal"
      ? "greetingFormal"
      : communication?.addressing === "informal"
        ? "greetingInformal"
        : "greetingNeutral",
  )}${communication?.sentence_length === "standard" ? ` ${t("greetingExtra")}` : ""}`;
  const speak = (text: string) => {
    if (
      !("speechSynthesis" in window) ||
      !("SpeechSynthesisUtterance" in window)
    ) {
      setVoiceError(true);
      return;
    }
    setVoiceError(false);
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = profile.locale;
    utterance.rate = communication?.pace === "slow" ? 0.8 : 1;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  };
  useEffect(() => () => window.speechSynthesis?.cancel(), []);
  return (
    <>
      <section className="panel">
        <span className="badge">{t("companionLocal")}</span>
        <h2>{greeting}</h2>
        <button onClick={() => speak(greeting)}>{t("readAnswer")}</button>
        <button onClick={() => window.speechSynthesis?.cancel()}>
          {t("stopSpeaking")}
        </button>
        {voiceError && <p role="alert">{t("noVoice")}</p>}
        {communicationFailed && <p role="alert">{t("errorGeneric")}</p>}
        <button onClick={() => setShowSupport(true)}>
          {t("supportButton")}
        </button>
        {showSupport && (
          <div aria-live="polite">
            <p>
              {t(
                communication?.distress === "contact_caregiver"
                  ? "supportCaregiverResponse"
                  : "supportQuietResponse",
              )}
            </p>
            <button
              onClick={() =>
                speak(
                  t(
                    communication?.distress === "contact_caregiver"
                      ? "supportCaregiverResponse"
                      : "supportQuietResponse",
                  ),
                )
              }
            >
              {t("readAnswer")}
            </button>
            <p className="hint">{t("supportNoCall")}</p>
          </div>
        )}
      </section>
      <p>{t("askIntro")}</p>
      <CompanionChat
        profile={profile}
        t={t}
        busy={busy}
        run={run}
        topic={topic}
        clearTopic={() => setTopic(null)}
        speak={speak}
      />
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
              {(communication?.interaction !== "standard"
                ? result.items?.slice(itemIndex, itemIndex + 1)
                : result.items
              )?.map((x) => (
                <article className="message" key={x.id}>
                  <strong>
                    {x.title ? `${x.at.slice(0, 5)} · ${x.title}` : x.body}
                  </strong>
                  <p>{x.instructions}</p>
                  <button
                    onClick={() =>
                      speak(
                        x.title
                          ? `${x.at.slice(0, 5)}. ${x.title}. ${x.instructions || ""}`
                          : x.body,
                      )
                    }
                  >
                    {t("readAnswer")}
                  </button>
                  <p className="hint">
                    {t("author")}: {x.author}
                  </p>
                </article>
              ))}
              {communication?.interaction !== "standard" &&
                (result.items?.length || 0) > 1 && (
                  <div className="actions">
                    <button
                      disabled={itemIndex === 0}
                      onClick={() => setItemIndex(itemIndex - 1)}
                    >
                      {t("pagePrevious")}
                    </button>
                    <span>
                      {t("itemOf")} {itemIndex + 1} / {result.items?.length}
                    </span>
                    <button
                      disabled={itemIndex >= (result.items?.length || 0) - 1}
                      onClick={() => setItemIndex(itemIndex + 1)}
                    >
                      {t("pageNext")}
                    </button>
                  </div>
                )}
            </>
          )}
        </section>
      )}
      <HealthResources
        profile={profile}
        t={t}
        busy={busy}
        run={run}
        locale={locale}
        date={date}
        onSelect={(title, lang) => {
          if (lang === "es" || lang === "en") setTopic({ title, lang });
        }}
      />
    </>
  );
}
