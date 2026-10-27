import { useEffect, useState } from "react";
import { api } from "./api";
import type { Communication } from "./Communication";
import type { translator } from "./i18n";
import type { Profile } from "./types";

type Clip = {
  id: string;
  language: string;
  source: string;
  attribution: string;
  license: string;
  source_url: string | null;
};
type Lookup = { available: false } | { available: true; clip: Clip };
type Caption = { id: number; text: string; final: boolean };

/** Only complete final utterances can select a reviewed whole-phrase clip. */
export default function SignClips({
  profile,
  communication,
  turns,
  t,
}: {
  profile: Profile;
  communication: Communication | null;
  turns: Caption[];
  t: ReturnType<typeof translator>;
}) {
  const last = turns.at(-1);
  const text = last?.final ? last.text.trim() : "";
  const language = communication?.sign_language;
  const [state, setState] = useState<
    "idle" | "searching" | "unavailable" | "error" | "available"
  >("idle");
  const selectionKey = JSON.stringify([profile.id, language, last?.id, text]);
  const [clip, setClip] = useState<{ value: Clip; key: string } | null>(null);
  useEffect(() => {
    let active = true;
    setClip(null);
    setState("idle");
    if (!text || !language || language === "none" || language === "other")
      return () => {
        active = false;
      };
    if (text.length > 300) {
      setState("unavailable");
      return () => {
        active = false;
      };
    }
    setState("searching");
    api<Lookup>(`profiles/${profile.id}/signs/lookup/`, "POST", {
      text,
      language,
    })
      .then((result) => {
        if (!active) return;
        if (result.available) {
          setClip({ value: result.clip, key: selectionKey });
          setState("available");
        } else setState("unavailable");
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => {
      active = false;
    };
  }, [profile.id, language, last?.id, text]);
  if (!language || language === "none") return null;
  if (language === "other") return <p>{t("signOtherUnavailable")}</p>;
  return (
    <div aria-live="polite" className="spaced">
      {state === "idle" && <p>{t("signAwait")}</p>}
      {state === "searching" && <p>{t("signSearching")}</p>}
      {state === "unavailable" && <p>{t("signClipUnavailable")}</p>}
      {state === "error" && <p role="alert">{t("signClipError")}</p>}
      {state === "available" && text && clip?.key === selectionKey && (
        <>
          <p>{t("signClipAvailable")}</p>
          <video
            key={`${last?.id}:${clip.value.id}`}
            controls
            autoPlay
            muted
            playsInline
            preload="metadata"
            style={{ width: "100%", maxHeight: 480 }}
            aria-label={t("signClipAvailable")}
            src={`/api/v1/profiles/${encodeURIComponent(profile.id)}/signs/clips/${encodeURIComponent(clip.value.id)}/`}
            onError={() => {
              setClip(null);
              setState("error");
            }}
          />
          <p>
            {clip.value.attribution} · {clip.value.license} ·{" "}
            {clip.value.source}
          </p>
          {clip.value.source_url && (
            <a
              href={clip.value.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t("knowledgeOpen")}
            </a>
          )}
        </>
      )}
    </div>
  );
}
