import { useEffect, useState } from "react";
import { api } from "./api";
import Field from "./components/Field";
import type { WithProfile } from "./ui";
import type { Key } from "./i18n";

export type Communication = {
  preferred_name: string;
  addressing: "preferred_name" | "formal" | "informal";
  sentence_length: "short" | "standard";
  pace: "slow" | "standard";
  interaction: "one_step" | "standard";
  distress: "quiet_reassurance" | "contact_caregiver";
  sign_language: "none" | "lsec" | "asl" | "other";
  communication_notes: string;
};

export function useCommunication(profileId: string) {
  const [value, setValue] = useState<Communication | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    setValue(null);
    setFailed(false);
    api<Communication>(`profiles/${profileId}/communication/`)
      .then((result) => {
        if (active) setValue(result);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [profileId]);
  return { value, setValue, failed };
}

export default function CommunicationSettings({
  profile,
  t,
  busy,
  run,
}: Pick<WithProfile, "profile" | "t" | "busy" | "run">) {
  const { value, setValue, failed } = useCommunication(profile.id);
  const update = <K extends keyof Communication>(
    key: K,
    next: Communication[K],
  ) => {
    if (value) setValue({ ...value, [key]: next });
  };
  const select = <K extends keyof Communication>(
    key: K,
    label: Key,
    items: [Communication[K], Key][],
  ) => (
    <Field label={t(label)}>
      <select
        value={String(value?.[key] ?? "")}
        onChange={(e) => update(key, e.target.value as Communication[K])}
      >
        {items.map(([option, optionLabel]) => (
          <option value={String(option)} key={String(option)}>
            {t(optionLabel)}
          </option>
        ))}
      </select>
    </Field>
  );
  return (
    <section className="panel">
      <h2>{t("communicationTitle")}</h2>
      <p>{t("communicationIntro")}</p>
      {failed ? (
        <p role="alert">{t("errorGeneric")}</p>
      ) : !value ? (
        <p>{t("loading")}</p>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              const saved = await api<Communication>(
                `profiles/${profile.id}/communication/`,
                "PATCH",
                value,
              );
              setValue(saved);
            });
          }}
        >
          <fieldset disabled={!profile.permissions.configure || busy}>
            <Field label={t("preferredName")}>
              <input
                maxLength={100}
                value={value.preferred_name}
                onChange={(e) => update("preferred_name", e.target.value)}
              />
            </Field>
            <div className="two-col">
              {select("addressing", "addressing", [
                ["preferred_name", "addressNeutral"],
                ["formal", "addressFormal"],
                ["informal", "addressInformal"],
              ])}
              {select("sentence_length", "sentenceLength", [
                ["short", "sentenceShort"],
                ["standard", "sentenceStandard"],
              ])}
              {select("pace", "speechPace", [
                ["slow", "paceSlow"],
                ["standard", "paceStandard"],
              ])}
              {select("interaction", "interactionStyle", [
                ["one_step", "oneStep"],
                ["standard", "allItems"],
              ])}
              {select("distress", "supportPreference", [
                ["quiet_reassurance", "supportQuiet"],
                ["contact_caregiver", "supportCaregiver"],
              ])}
              {select("sign_language", "signLanguage", [
                ["none", "signNone"],
                ["lsec", "signLsec"],
                ["asl", "signAsl"],
                ["other", "signOther"],
              ])}
            </div>
            <Field label={t("communicationNotes")}>
              <textarea
                maxLength={1000}
                value={value.communication_notes}
                onChange={(e) => update("communication_notes", e.target.value)}
              />
            </Field>
            <p className="hint">{t("communicationScope")}</p>
            <p className="hint">{t("signNotAvailable")}</p>
            <button className="primary">{t("save")}</button>
          </fieldset>
        </form>
      )}
    </section>
  );
}
