import { useEffect, useState } from "react";
import { api } from "./api";
import type { translator } from "./i18n";
import type { Profile } from "./types";

type FaceState = {
  enabled: boolean;
  can_enroll: boolean;
  enrollments: {
    id: string;
    username: string;
    display_name: string;
    relationship: string;
    expires_at: string;
    sample_count: number;
  }[];
};
type Match = {
  box: number[];
  candidate: { id: string; display_name: string; relationship: string } | null;
};

export default function FamilyFaces({
  profile,
  t,
  busy,
  run,
  refresh,
  date,
}: {
  profile: Profile;
  t: ReturnType<typeof translator>;
  busy: boolean;
  run: (task: () => Promise<void>) => Promise<void>;
  refresh: () => Promise<void>;
  date: (value: string) => string;
}) {
  const [state, setState] = useState<FaceState | null>(null),
    [matches, setMatches] = useState<Match[] | null>(null);
  const base = `profiles/${profile.id}/faces/`;
  const load = async () => setState(await api<FaceState>(base));
  useEffect(() => {
    void run(load);
  }, [profile.id]);
  const speak = () => {
    if (!matches) return;
    const text = matches.length
      ? matches
          .map((m) =>
            m.candidate
              ? `${t("facePossible")} ${m.candidate.display_name}, ${m.candidate.relationship}.`
              : t("faceUnknown"),
          )
          .join(" ")
      : t("faceNone");
    const speech = new SpeechSynthesisUtterance(text);
    speech.lang = profile.locale;
    window.speechSynthesis?.cancel();
    window.speechSynthesis?.speak(speech);
  };
  return (
    <>
      <p>{t("faceIntro")}</p>
      <p className="callout">{t("faceWarning")}</p>
      {profile.role === "owner" && (
        <section className="panel">
          <h2>{t("faceTitle")}</h2>
          {!state?.enabled ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const form = e.currentTarget;
                const data = new FormData(form);
                void run(async () => {
                  await api(base + "consent/", "POST", {
                    enabled: true,
                    consent: data.has("consent"),
                    password: data.get("password"),
                  });
                  form.reset();
                  await load();
                  await refresh();
                });
              }}
            >
              <label className="field">
                {t("currentPassword")}
                <input
                  type="password"
                  name="password"
                  required
                  autoComplete="current-password"
                />
              </label>
              <label className="check">
                <input type="checkbox" name="consent" required />
                {t("faceOwnerConsent")}
              </label>
              <button disabled={busy} className="primary">
                {t("faceEnable")}
              </button>
            </form>
          ) : (
            <button
              disabled={busy}
              className="danger"
              onClick={() =>
                void run(async () => {
                  await api(base + "consent/", "POST", { enabled: false });
                  setMatches(null);
                  await load();
                  await refresh();
                })
              }
            >
              {t("faceDisable")}
            </button>
          )}
        </section>
      )}
      {!state?.enabled ? (
        <p>{t("faceDisabled")}</p>
      ) : (
        <>
          {state.can_enroll && (
            <section className="panel">
              <h2>{t("faceEnroll")}</h2>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = e.currentTarget;
                  const data = new FormData(form);
                  void run(async () => {
                    await api(base, "POST", data);
                    form.reset();
                    await load();
                  });
                }}
              >
                <label className="field">
                  {t("faceName")}
                  <input required name="display_name" maxLength={100} />
                </label>
                <label className="field">
                  {t("facePhoto")} · {t("faceSamplesHint")}
                  <input
                    required
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    name="image"
                    multiple
                    onChange={(e) => {
                      if ((e.target.files?.length ?? 0) > 3) {
                        e.target.value = "";
                      }
                    }}
                  />
                </label>
                <label className="check">
                  <input required type="checkbox" name="consent" value="true" />
                  {t("faceOwnConsent")}
                </label>
                <label className="check">
                  <input
                    required
                    type="checkbox"
                    name="own_photo"
                    value="true"
                  />
                  {t("faceOwnPhoto")}
                </label>
                <button disabled={busy} className="primary">
                  {t("faceEnroll")}
                </button>
              </form>
              <button
                disabled={busy}
                className="danger spaced"
                onClick={() =>
                  void run(async () => {
                    await api(base, "DELETE");
                    await load();
                  })
                }
              >
                {t("faceRevoke")}
              </button>
            </section>
          )}
          <section className="panel">
            <h2>{t("faceEnrolled")}</h2>
            {state.enrollments.map((x) => (
              <div className="list-row" key={x.id}>
                <strong>
                  {x.display_name} · {x.relationship} ({x.sample_count})
                </strong>
                <p>
                  {t("expires")}: {date(x.expires_at)}
                </p>
              </div>
            ))}
          </section>
          {profile.role === "owner" && (
            <section className="panel">
              <h2>{t("faceCapture")}</h2>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const data = new FormData(e.currentTarget);
                  void run(async () => {
                    const result = await api<{ faces: Match[] }>(
                      base + "recognize/",
                      "POST",
                      data,
                    );
                    setMatches(result.faces);
                  });
                }}
              >
                <label className="field">
                  {t("faceCapture")}
                  <input
                    required
                    type="file"
                    name="image"
                    accept="image/jpeg,image/png,image/webp"
                  />
                </label>
                <label className="check">
                  <input required type="checkbox" name="consent" value="true" />
                  {t("faceCaptureConsent")}
                </label>
                <button
                  disabled={busy || !state.enrollments.length}
                  className="primary"
                >
                  {t("faceRecognize")}
                </button>
              </form>
              {matches && (
                <div aria-live="polite">
                  {matches.length ? (
                    matches.map((m, i) => (
                      <p className="scene-result" key={i}>
                        {m.candidate
                          ? `${t("facePossible")} ${m.candidate.display_name} · ${m.candidate.relationship}`
                          : t("faceUnknown")}
                      </p>
                    ))
                  ) : (
                    <p>{t("faceNone")}</p>
                  )}
                  <button onClick={speak}>{t("speak")}</button>
                  <button onClick={() => window.speechSynthesis?.cancel()}>
                    {t("stopSpeaking")}
                  </button>
                </div>
              )}
            </section>
          )}
        </>
      )}
    </>
  );
}
