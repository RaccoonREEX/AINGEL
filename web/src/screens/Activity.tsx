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
export default function Activity({
  profile,
  t,
  locale,
  run,
  date,
  version,
}: WithProfile & { version: number }) {
  const [items, setItems] = useState<
    { id: number; actor: string; action: string; created_at: string }[]
  >([]);
  useEffect(() => {
    void run(async () => setItems(await api(`profiles/${profile.id}/audit/`)));
  }, [profile.id, version]);
  return (
    <section className="panel">
      <p className="hint">{t("activityNote")}</p>
      {items.length ? (
        items.map((item) => (
          <div className="list-row" key={item.id}>
            <strong>{activityLabel(item.action, locale)}</strong>
            <span>
              {item.actor} · {date(item.created_at)}
            </span>
          </div>
        ))
      ) : (
        <p>{t("noActivity")}</p>
      )}
    </section>
  );
}
