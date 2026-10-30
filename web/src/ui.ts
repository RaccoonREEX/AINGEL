import type { translator, Key, Locale } from "./i18n";
import type { Profile } from "./types";
export type Context = {
  currentUser?: string;
  t: ReturnType<typeof translator>;
  locale: Locale;
  busy: boolean;
  /** `notFound`: the message for a 404 in this task (generic error by default). */
  run: (task: () => Promise<void>, notFound?: Key) => Promise<void>;
  date: (value: string) => string;
  refresh: () => Promise<void>;
};
export type WithProfile = Context & { profile: Profile };
