import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import Field from "../components/Field";
import AingelOrb from "../components/aingel/AingelOrb";
import { longDate, summarizeToday } from "../today";
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
const categories = [
  "sleep",
  "wake",
  "medicine",
  "bathroom",
  "meal",
  "water",
  "appointment",
  "other",
] as const;
export default function Routines({
  profile,
  t,
  locale,
  busy,
  run,
  refresh,
  version,
  onAsk,
}: WithProfile & { version: number; onAsk?: (question: string) => void }) {
  const [items, setItems] = useState<Routine[]>([]),
    [editing, setEditing] = useState<Routine | null>(null),
    [due, setDue] = useState("");
  const announced = useRef(new Set<string>());
  const base = `profiles/${profile.id}/routines/`;
  const dayNames = Array.from({ length: 7 }, (_, i) =>
    new Intl.DateTimeFormat(locale, {
      weekday: "short",
      timeZone: "UTC",
    }).format(new Date(Date.UTC(2026, 0, 5 + i))),
  );
  const todayIndex = () =>
    ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].indexOf(
      new Intl.DateTimeFormat("en-US", {
        weekday: "short",
        timeZone: profile.timezone,
      }).format(new Date()),
    );
  useEffect(() => {
    void run(async () => setItems(await api<Routine[]>(base)));
  }, [profile.id, version]);
  useEffect(() => {
    const tick = () => {
      const now = new Intl.DateTimeFormat("en-GB", {
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
        timeZone: profile.timezone,
      }).format(new Date());
      const dateKey = new Intl.DateTimeFormat("en-CA", {
        timeZone: profile.timezone,
      }).format(new Date());
      for (const item of items) {
        const key = dateKey + item.id;
        if (
          item.active &&
          !item.confirmed_today &&
          item.weekdays.includes(todayIndex()) &&
          item.at.slice(0, 5) === now &&
          !announced.current.has(key)
        ) {
          announced.current.add(key);
          setDue(item.title);
        }
      }
    };
    tick();
    const timer = setInterval(tick, 15000);
    return () => clearInterval(timer);
  }, [items, profile.timezone]);
  const es = locale === "es-EC";
  const summary = summarizeToday(items, profile.timezone);
  const formRef = useRef<HTMLElement>(null);
  const confirm = (item: Routine) =>
    void run(async () => {
      await api(base + item.id + "/confirm/", item.confirmed_today ? "DELETE" : "POST");
      await refresh();
    });
  const progress = summary.list.length ? Math.round((summary.done / summary.list.length) * 100) : 0;
  const row = (item: Routine) => (
    <article className="routine-card" key={item.id}>
      <div className="routine-time">{item.at.slice(0, 5)}</div>
      <div className="routine-body">
        <span className="badge">{t(item.category as Key)}</span>
        <h3>{item.title}</h3>
        <p className="prewrap">{item.instructions}</p>
        <p className="hint">
          {item.weekdays.map((x) => dayNames[x]).join(" · ")} · {t("author")}:{" "}
          {item.author}
        </p>
        <p className="hint">
          {item.confirmed_today
            ? `${t("confirmedBy")} ${item.confirmation_actor}`
            : t("notConfirmed")}
          {!item.active && ` · ${t("paused")}`}
        </p>
      </div>
      {profile.permissions.configure && (
        <div className="actions">
          <button
            disabled={
              busy || !item.weekdays.includes(todayIndex()) || !item.active
            }
            onClick={() =>
              void run(async () => {
                await api(
                  base + item.id + "/confirm/",
                  item.confirmed_today ? "DELETE" : "POST",
                );
                await refresh();
              })
            }
          >
            {t(item.confirmed_today ? "undoDone" : "markDone")}
          </button>
          <button disabled={busy} onClick={() => setEditing(item)}>
            {t("edit")}
          </button>
          <button
            disabled={busy}
            onClick={() =>
              void run(async () => {
                await api(base + item.id + "/", "PATCH", {
                  active: !item.active,
                });
                await refresh();
              })
            }
          >
            {t(item.active ? "pause" : "resume")}
          </button>
          <button
            disabled={busy}
            className="danger"
            onClick={() =>
              void run(async () => {
                if (!window.confirm(t("confirmDelete"))) return;
                await api(base + item.id + "/", "DELETE");
                await refresh();
              })
            }
          >
            {t("delete")}
          </button>
        </div>
      )}
    </article>
  );
  return (
    <>
      <div className="today-page">
        <div className="today-main">
          <div className="today-page-head">
            <div>
              <h1>{t("dashboard")}</h1>
              <span>{longDate(locale, profile.timezone)}{summary.list.length ? ` · ${es ? `${summary.done} de ${summary.list.length} completadas` : `${summary.done} of ${summary.list.length} done`}` : ""}</span>
            </div>
            {profile.permissions.configure && (
              <button className="btn btn-primary btn-pill today-add" onClick={() => { setEditing(null); formRef.current?.scrollIntoView({ behavior: "smooth" }); formRef.current?.querySelector("input")?.focus({ preventScroll: true }); }}>
                {es ? "Añadir rutina" : "Add routine"}
              </button>
            )}
          </div>
          <div className="progress progress--gold" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} aria-label={t("dashboard")}><span style={{ width: `${progress}%` }} /></div>
          {due && (
            <p className="callout" role="alert">
              {t("reminderDue")}: <strong>{due}</strong>{" "}
              <button className="btn btn-outline btn-sm btn-pill" onClick={() => setDue("")}>{t("close")}</button>
            </p>
          )}
          <div className="routine-rows">
            {summary.list.length ? summary.list.map((r) => {
              const isNext = r.id === summary.next?.id;
              return (
                <div key={r.id} className={`routine-row${isNext ? " is-next" : ""}`}>
                  <span className="routine-row-time">{r.at.slice(0, 5)}</span>
                  <div className="routine-row-body">
                    <span className={`routine-row-title${r.confirmed_today ? " is-done" : ""}`}>{r.title}{isNext && <span className="next-tag">{es ? "SIGUIENTE" : "NEXT"}</span>}</span>
                    <span className="routine-row-meta">{r.instructions || t(r.category as Key)}</span>
                  </div>
                  {r.confirmed_today ? (
                    <span className="routine-row-done">
                      <span className="routine-row-status">{t("confirmedBy")} {r.confirmation_actor}</span>
                      <button className="ring ring--done ring--btn" disabled={busy || !profile.permissions.configure} onClick={() => confirm(r)} aria-label={`${t("undoDone")}: ${r.title}`} title={t("undoDone")}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
                      </button>
                    </span>
                  ) : profile.permissions.configure ? (
                    <button className="btn btn-outline btn-sm btn-pill routine-confirm" disabled={busy} onClick={() => confirm(r)}>{es ? "Confirmar" : "Confirm"}</button>
                  ) : <span className={`ring${isNext ? " ring--gold" : ""}`} />}
                </div>
              );
            }) : <p className="empty">{t("noRoutines")}</p>}
          </div>
        </div>
        <div className="today-side">
          <div className="ask-card">
            <AingelOrb size={140} reducedMotion={!!profile.preferences.reduced_motion} />
            <span>{es ? "Pregúntale a AINGEL" : "Ask AINGEL"}</span>
            <button className="pill" onClick={() => onAsk?.(es ? "¿Qué tengo que hacer hoy?" : "What do I need to do today?")}>{es ? "¿Qué tengo que hacer hoy?" : "What do I need to do today?"}</button>
          </div>
          <p className="today-note">{t("remindersNote")}</p>
        </div>
        {profile.permissions.configure && (
          <button className="today-fab btn btn-primary btn-shadow" onClick={() => { setEditing(null); formRef.current?.scrollIntoView({ behavior: "smooth" }); }}>{es ? "Añadir rutina" : "Add routine"}</button>
        )}
      </div>
      <details className="panel">
        <summary>
          {t("allRoutines")} ({items.length})
        </summary>
        {items.map(row)}
      </details>
      {profile.permissions.configure && (
        <section className="panel" ref={formRef}>
          <h2>{t(editing ? "edit" : "newRoutine")}</h2>
          <RoutineForm
            key={editing?.id || "new"}
            item={editing}
            {...{ profile, t, locale, busy, run, refresh }}
            onSaved={() => setEditing(null)}
          />
          {editing && (
            <button onClick={() => setEditing(null)}>{t("cancel")}</button>
          )}
        </section>
      )}
    </>
  );
}
function RoutineForm({
  profile,
  t,
  locale,
  busy,
  run,
  refresh,
  item,
  onSaved,
}: Omit<WithProfile, "date"> & { item: Routine | null; onSaved: () => void }) {
  const [days, setDays] = useState(item?.weekdays || [0, 1, 2, 3, 4, 5, 6]);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const form = e.currentTarget;
        const data = new FormData(form);
        void run(async () => {
          await api(
            `profiles/${profile.id}/routines/${item ? item.id + "/" : ""}`,
            item ? "PATCH" : "POST",
            { ...Object.fromEntries(data), weekdays: days },
          );
          onSaved();
          form.reset();
          await refresh();
        });
      }}
    >
      <div className="two-col">
        <Field label={t("routineTitle")}>
          <input
            required
            name="title"
            maxLength={150}
            defaultValue={item?.title}
          />
        </Field>
        <Field label={t("category")}>
          <select name="category" defaultValue={item?.category || "other"}>
            {categories.map((c) => (
              <option key={c} value={c}>
                {t(c)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("time")}>
          <input
            required
            name="at"
            type="time"
            defaultValue={item?.at.slice(0, 5) || "08:00"}
          />
        </Field>
      </div>
      <fieldset className="days">
        <legend>{t("weekdays")}</legend>
        {Array.from({ length: 7 }, (_, i) => (
          <label className="check" key={i}>
            <input
              type="checkbox"
              checked={days.includes(i)}
              onChange={(e) =>
                setDays((old) =>
                  e.target.checked ? [...old, i] : old.filter((x) => x !== i),
                )
              }
            />
            {new Intl.DateTimeFormat(locale, {
              weekday: "short",
              timeZone: "UTC",
            }).format(new Date(Date.UTC(2026, 0, 5 + i)))}
          </label>
        ))}
      </fieldset>
      <Field label={t("instructions")}>
        <textarea
          name="instructions"
          maxLength={2000}
          defaultValue={item?.instructions}
        />
      </Field>
      <p className="hint">{t("medicationHint")}</p>
      <button className="primary" disabled={busy || !days.length}>
        {t("save")}
      </button>
    </form>
  );
}
