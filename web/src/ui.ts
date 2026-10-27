import type { translator, Locale } from "./i18n";
import type { Profile } from "./types";
export type Context = {
  currentUser?: string;
  t: ReturnType<typeof translator>;
  locale: Locale;
  busy: boolean;
  run: (task: () => Promise<void>) => Promise<void>;
  date: (value: string) => string;
  refresh: () => Promise<void>;
};
export type WithProfile = Context & { profile: Profile };
