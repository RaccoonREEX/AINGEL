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
  // Optional so a server without these fields still loads; the UI then shows the server defaults.
  priority_support?: "visual" | "auditory" | "cognitive" | "communication" | "none";
  detail?: "brief" | "detailed";
  spontaneous?: "few" | "normal" | "many";
  repeat_important?: "yes" | "no";
};

/** Server defaults (backend care.serializers.COMMUNICATION_DEFAULTS). */
const CHOICE_DEFAULTS = {
  priority_support: "none",
  detail: "brief",
  spontaneous: "normal",
  repeat_important: "no",
} as const;
type ChoiceKey = keyof typeof CHOICE_DEFAULTS;

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
  // Segmented radio group: native radios in a fieldset + legend, so screen readers announce the group and position.
  const choice = <K extends ChoiceKey>(
    key: K,
    label: Key,
    help: Key,
    items: [NonNullable<Communication[K]>, Key][],
    note?: Key,
  ) => {
    const id = `comm-${key}`;
    const current = value?.[key] ?? CHOICE_DEFAULTS[key];
    return (
      <fieldset
        className="segmented-field"
        aria-describedby={note ? `${id}-help ${id}-note` : `${id}-help`}
      >
        <legend>{t(label)}</legend>
        <div className="segmented">
          {items.map(([option, optionLabel]) => (
            <label
              key={option}
              className={`segment${current === option ? " is-on" : ""}`}
            >
              <input
                type="radio"
                className="sr-only"
                name={id}
                value={option}
                checked={current === option}
                onChange={() => update(key, option)}
              />
              <span>{t(optionLabel)}</span>
            </label>
          ))}
        </div>
        <small id={`${id}-help`} className="segmented-help">
          {t(help)}
        </small>
        {note && (
          <small id={`${id}-note`} className="segmented-help segmented-note">
            {t(note)}
          </small>
        )}
      </fieldset>
    );
  };
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
            {choice("priority_support", "prioritySupport", "prioritySupportHelp", [
              ["visual", "prioVisual"],
              ["auditory", "prioAuditory"],
              ["cognitive", "prioCognitive"],
              ["communication", "prioCommunication"],
              ["none", "prioNone"],
            ], "prioritySupportMeta")}
            {choice("detail", "detailLevel", "detailHelp", [
              ["brief", "detailBrief"],
              ["detailed", "detailDetailed"],
            ])}
            {choice("spontaneous", "spontaneous", "spontaneousHelp", [
              ["few", "spontFew"],
              ["normal", "spontNormal"],
              ["many", "spontMany"],
            ])}
            {choice("repeat_important", "repeatImportant", "repeatHelp", [
              ["yes", "repeatYes"],
              ["no", "repeatNo"],
            ])}
            <Field label={t("communicationNotes")}>
              <textarea
                maxLength={1000}
                value={value.communication_notes}
                onChange={(e) => update("communication_notes", e.target.value)}
              />
            </Field>
            <section className="data-legend" aria-labelledby="comm-data-title">
              <h3 id="comm-data-title">{t("dataLegendTitle")}</h3>
              <ul>
                <li>
                  <b>{t("dataLegendStyleTag")}</b> {t("dataLegendStyle")}
                </li>
                <li>
                  <b>{t("dataLegendPriorityTag")}</b> {t("dataLegendPriority")}
                </li>
                <li>
                  <b>{t("dataLegendLocalTag")}</b> {t("dataLegendLocal")}
                </li>
              </ul>
            </section>
            <p className="hint">{t("communicationScope")}</p>
            <p className="hint">{t("signNotAvailable")}</p>
            <button className="primary">{t("save")}</button>
          </fieldset>
        </form>
      )}
    </section>
  );
}
