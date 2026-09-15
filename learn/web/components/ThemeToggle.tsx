"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function effectiveTheme(): Theme {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

/** Light/dark toggle. Until the visitor chooses, the page follows prefers-color-scheme (dark if unsupported). */
export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    setTheme(effectiveTheme());
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => setTheme(effectiveTheme());
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const next: Theme = theme === "light" ? "dark" : "light";
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={theme ? `Switch to ${next} theme` : "Toggle theme"}
      onClick={() => {
        document.documentElement.dataset.theme = next;
        try {
          localStorage.setItem("theme", next);
        } catch {
          /* storage unavailable: the choice lasts for this page view */
        }
        setTheme(next);
      }}
    >
      <span aria-hidden="true">{theme === "light" ? "☾" : "☀"}</span>
      <span className="theme-toggle__label">{theme === "light" ? "Dark" : "Light"}</span>
    </button>
  );
}
