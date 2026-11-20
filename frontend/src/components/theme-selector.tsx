"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";
const key = "documind.theme";
function preference(value: string | null): Theme {
  return value === "light" || value === "dark" ? value : "system";
}

export function ThemeSelector() {
  const [theme, setTheme] = useState<Theme>("system");
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    function apply(selected: Theme) {
      document.documentElement.dataset.theme =
        selected === "dark" || (selected === "system" && media.matches)
          ? "dark"
          : "light";
      setTheme(selected);
    }
    function sync() {
      let selected: Theme = "system";
      try {
        selected = preference(localStorage.getItem(key));
      } catch {
        /* Storage can be unavailable. */
      }
      apply(selected);
    }
    function systemChanged() {
      if (document.documentElement.dataset.preference === "system")
        apply("system");
    }
    function storageChanged(event: StorageEvent) {
      if (event.key === key || event.key === null) sync();
    }
    sync();
    media.addEventListener("change", systemChanged);
    window.addEventListener("storage", storageChanged);
    return () => {
      media.removeEventListener("change", systemChanged);
      window.removeEventListener("storage", storageChanged);
    };
  }, []);
  // Keep the chosen preference separate from its resolved light/dark appearance.
  useEffect(() => {
    document.documentElement.dataset.preference = theme;
  }, [theme]);

  return (
    <label className="theme-selector">
      <span aria-hidden="true">◐</span>
      <span className="sr-only">Color theme</span>
      <select
        aria-label="Color theme"
        value={theme}
        onChange={(event) => {
          const selected = preference(event.target.value);
          setTheme(selected);
          document.documentElement.dataset.theme =
            selected === "dark" ||
            (selected === "system" &&
              window.matchMedia("(prefers-color-scheme: dark)").matches)
              ? "dark"
              : "light";
          try {
            localStorage.setItem(key, selected);
          } catch {
            /* The selection still works for this page. */
          }
        }}
      >
        <option value="system">System theme</option>
        <option value="light">Light mode</option>
        <option value="dark">Dark mode</option>
      </select>
    </label>
  );
}
