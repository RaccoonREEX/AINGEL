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
export function AcceptInvite({
  t,
  busy,
  run,
  onAccepted,
}: Context & { onAccepted: (id: string) => Promise<void> }) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const data = new FormData(e.currentTarget);
        void run(async () => {
          const value = await api<{ profile_id: string }>(
            "invites/accept/",
            "POST",
            Object.fromEntries(data),
          );
          await onAccepted(value.profile_id);
        });
      }}
    >
      <p className="hint">{t("inviteHint")}</p>
      <Field label={t("inviteCode")}>
        <input
          name="code"
          required
          minLength={20}
          maxLength={100}
          autoComplete="off"
        />
      </Field>
      <button className="primary" disabled={busy}>
        {t("acceptInvite")}
      </button>
    </form>
  );
}
export default function Onboarding(
  props: Context & { onCreated: (id: string) => Promise<void> },
) {
  const { t, busy, run, onCreated } = props;
  return (
    <div className="two-col">
      <section>
        <h2>{t("createProfile")}</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            void run(async () => {
              const value = await api<Profile>("profiles/", "POST", {
                display_name: data.get("display_name"),
                locale: props.locale,
              });
              await onCreated(value.id);
            });
          }}
        >
          <Field label={t("profileName")}>
            <input name="display_name" required maxLength={100} />
          </Field>
          <button className="primary" disabled={busy}>
            {t("createProfile")}
          </button>
        </form>
      </section>
      <section>
        <h2>{t("acceptInvite")}</h2>
        <AcceptInvite {...props} onAccepted={onCreated} />
      </section>
    </div>
  );
}
