import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import Field from "../components/Field";
import type { Context, WithProfile } from "../ui";
import type { Key } from "../i18n";
import { activityLabel } from "../i18n";
import CommunicationSettings from "../Communication";
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
const prefKeys = [
  "visual_assistance",
  "hearing_assistance",
  "memory_assistance",
  "large_text",
  "high_contrast",
  "voice_output",
  "reduced_motion",
  "simple_instructions",
] as const;
export default function Settings({
  profile,
  t,
  busy,
  run,
  refresh,
}: WithProfile) {
  const [draft, setDraft] = useState(profile);
  const editable = profile.permissions.configure;
  const field = (
    key:
      | "display_name"
      | "allergies"
      | "support_notes"
      | "emergency_contact"
      | "timezone",
    label: Key,
    multiline = false,
  ) => (
    <Field label={t(label)}>
      {multiline ? (
        <textarea
          value={draft[key]}
          maxLength={key === "support_notes" ? 3000 : 2000}
          onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
        />
      ) : (
        <input
          value={draft[key]}
          maxLength={
            key === "display_name"
              ? 100
              : key === "emergency_contact"
                ? 200
                : 80
          }
          required={key === "display_name" || key === "timezone"}
          onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
        />
      )}
    </Field>
  );
  return (
    <>
      <section className="panel">
        <p className="hint">{t("privacyLocal")}</p>
        {!editable && <p className="callout">{t("readOnly")}</p>}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              await api(`profiles/${profile.id}/`, "PATCH", {
                display_name: draft.display_name,
                locale: draft.locale,
                timezone: draft.timezone,
                allergies: draft.allergies,
                support_notes: draft.support_notes,
                emergency_contact: draft.emergency_contact,
                preferences: draft.preferences,
              });
              await refresh();
            });
          }}
        >
          <fieldset disabled={!editable || busy}>
            <div className="two-col">
              {field("display_name", "profileName")}
              <Field label={t("profileLanguage")}>
                <select
                  value={draft.locale}
                  onChange={(e) =>
                    setDraft({ ...draft, locale: e.target.value })
                  }
                >
                  <option value="es-EC">Español</option>
                  <option value="en-US">English</option>
                </select>
              </Field>
              {field("timezone", "timezone")}
              {field("emergency_contact", "emergencyContact")}
            </div>
            <p className="hint">{t("emergencyHint")}</p>
            {field("allergies", "allergies", true)}
            <p className="hint">{t("allergiesHint")}</p>
            {field("support_notes", "supportNotes", true)}
            <p className="hint">{t("supportHint")}</p>
            <h2>{t("preferences")}</h2>
            <div className="preference-grid">
              {prefKeys.map((key) => (
                <label className="check" key={key}>
                  <input
                    type="checkbox"
                    checked={!!draft.preferences[key]}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        preferences: {
                          ...draft.preferences,
                          [key]: e.target.checked,
                        },
                      })
                    }
                  />
                  {t(key)}
                </label>
              ))}
            </div>
            <button className="primary">{t("save")}</button>
          </fieldset>
        </form>
      </section>
      <CommunicationSettings profile={profile} t={t} busy={busy} run={run} />
    </>
  );
}
