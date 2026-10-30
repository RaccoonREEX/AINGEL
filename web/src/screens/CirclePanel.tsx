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
export default function CirclePanel(props: WithProfile & { version: number }) {
  const { profile, t, busy, run, refresh, version } = props;
  const [circle, setCircle] = useState<Circle | null>(null);
  const [code, setCode] = useState("");
  useEffect(() => {
    void run(async () =>
      setCircle(await api<Circle>(`profiles/${profile.id}/circle/`)),
    );
  }, [profile.id, version]);
  const base = `profiles/${profile.id}/`;
  return (
    <>
      <p className="callout">{t("circleRule")}</p>
      <section className="panel">
        <h2>
          {t("members")}{" "}
          <span className="count">{circle?.members.length || 0}/4</span>
        </h2>
        {circle?.members.map((member) => (
          <MemberRow
            key={member.id}
            member={member}
            {...props}
            onRevoke={() =>
              void run(async () => {
                if (!window.confirm(t("confirmDelete"))) return;
                await api(base + `circle/${member.id}/`, "DELETE");
                await refresh();
              })
            }
          />
        ))}
        {profile.permissions.manage_circle && circle?.pending.length !== 0 && (
          <>
            <h3>{t("pending")}</h3>
            {circle?.pending.map((inv) => (
              <div className="list-row" key={inv.id}>
                <div>
                  <strong>{inv.username}</strong>
                  <p>
                    {inv.relationship} · {t("expires")}:{" "}
                    {props.date(inv.expires_at)}
                  </p>
                </div>
                <button
                  disabled={busy}
                  className="danger"
                  onClick={() =>
                    void run(async () => {
                      await api(base + `invitations/${inv.id}/`, "DELETE");
                      await refresh();
                    })
                  }
                >
                  {t("cancel")}
                </button>
              </div>
            ))}
          </>
        )}
      </section>
      {profile.permissions.manage_circle && (
        <section className="panel">
          <h2>{t("invite")}</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              void run(async () => {
                const result = await api<{ code: string }>(
                  base + "circle/",
                  "POST",
                  {
                    username: data.get("username"),
                    relationship: data.get("relationship"),
                    can_configure: data.has("can_configure"),
                    can_view_memories: data.has("can_view_memories"),
                  },
                );
                setCode(result.code);
                await refresh();
              }, "errorTarget");
            }}
          >
            <div className="two-col">
              <Field label={t("username")}>
                <input
                  required
                  name="username"
                  maxLength={150}
                  autoComplete="off"
                />
              </Field>
              <Field label={t("relationship")}>
                <input
                  name="relationship"
                  required
                  maxLength={80}
                  placeholder={t("relationHint")}
                />
              </Field>
            </div>
            <label className="check">
              <input type="checkbox" name="can_configure" defaultChecked />
              {t("configurePermission")}
            </label>
            <label className="check">
              <input type="checkbox" name="can_view_memories" />
              {t("memoryPermission")}
            </label>
            <button
              className="primary"
              disabled={
                busy ||
                (!!circle && circle.members.length + circle.pending.length >= 4)
              }
            >
              {t("invite")}
            </button>
          </form>
          {code && (
            <div className="invite-code">
              <p>{t("codeCreated")}</p>
              <code>{code}</code>
              <button
                onClick={() =>
                  void run(async () => {
                    await navigator.clipboard.writeText(code);
                  })
                }
              >
                {t("copy")}
              </button>
              <button onClick={() => setCode("")}>{t("close")}</button>
            </div>
          )}
        </section>
      )}
    </>
  );
}
function MemberRow({
  member,
  profile,
  t,
  busy,
  run,
  refresh,
  currentUser,
  onRevoke,
}: WithProfile & { member: Member; onRevoke: () => void }) {
  const [configure, setConfigure] = useState(member.can_configure),
    [memory, setMemory] = useState(member.can_view_memories);
  return (
    <div className="member-row">
      <div>
        <strong>{member.username}</strong>
        <p>{member.relationship}</p>
      </div>
      <div>
        <label className="check">
          <input
            disabled={!profile.permissions.manage_circle || busy}
            type="checkbox"
            checked={configure}
            onChange={(e) => setConfigure(e.target.checked)}
          />
          {t("configurePermission")}
        </label>
        <label className="check">
          <input
            disabled={!profile.permissions.manage_circle || busy}
            type="checkbox"
            checked={memory}
            onChange={(e) => setMemory(e.target.checked)}
          />
          {t("memoryPermission")}
        </label>
      </div>
      {profile.permissions.manage_circle && (
        <div className="actions">
          <button
            disabled={busy}
            onClick={() =>
              void run(async () => {
                await api(
                  `profiles/${profile.id}/circle/${member.id}/`,
                  "PATCH",
                  { can_configure: configure, can_view_memories: memory },
                );
                await refresh();
              })
            }
          >
            {t("changePermissions")}
          </button>
          <button disabled={busy} className="danger" onClick={onRevoke}>
            {t("revoke")}
          </button>
        </div>
      )}
      {!profile.permissions.manage_circle &&
        member.username === currentUser && (
          <button disabled={busy} className="danger" onClick={onRevoke}>
            {t("leave")}
          </button>
        )}
    </div>
  );
}
