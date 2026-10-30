import type { Routine } from "./types";

const WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export const todayIndex = (timeZone: string) =>
  WEEK.indexOf(new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone }).format(new Date()));

export const nowMinutes = (timeZone: string) => {
  const [h, m] = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone })
    .format(new Date()).split(":").map(Number);
  return h * 60 + m;
};

const minutesOf = (at: string) => Number(at.slice(0, 2)) * 60 + Number(at.slice(3, 5));

/** Today's active routines in time order, with the next pending one and how far away it is. */
export function summarizeToday(items: Routine[], timeZone: string) {
  const day = todayIndex(timeZone);
  const list = items.filter((x) => x.active && x.weekdays.includes(day)).sort((a, b) => a.at.localeCompare(b.at));
  const now = nowMinutes(timeZone);
  const pending = list.filter((x) => !x.confirmed_today);
  const next = pending.find((x) => minutesOf(x.at) >= now) || pending[0] || null;
  return {
    list,
    done: list.length - pending.length,
    next,
    minutesUntil: next ? minutesOf(next.at) - now : null,
  };
}

export const longDate = (locale: string, timeZone: string) => {
  const text = new Intl.DateTimeFormat(locale, { weekday: "long", day: "numeric", month: "long", timeZone }).format(new Date());
  return text.charAt(0).toUpperCase() + text.slice(1);
};

export const greetingKey = (timeZone: string) => {
  const m = nowMinutes(timeZone);
  return m < 12 * 60 ? "morning" : m < 19 * 60 ? "afternoon" : "evening";
};

export const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((x) => x[0]!.toUpperCase()).join("") || "A";
