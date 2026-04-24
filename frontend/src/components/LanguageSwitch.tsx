import { Languages } from "lucide-react";
import { useLocale } from "../i18n";

export function LanguageSwitch() {
  const { copy, locale, setLocale } = useLocale();

  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-slate-200/80 bg-white/88 px-2 py-2 shadow-float">
      <span className="inline-flex items-center gap-2 rounded-full px-2 text-xs font-semibold uppercase tracking-[0.16em] text-muted">
        <Languages className="h-3.5 w-3.5 text-accent" />
        {copy.languageSwitch.label}
      </span>
      <div
        role="group"
        aria-label={copy.languageSwitch.ariaLabel}
        className="inline-flex items-center rounded-full bg-slate-100 p-1"
      >
        <button
          type="button"
          onClick={() => setLocale("ru")}
          className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
            locale === "ru" ? "bg-ink text-white shadow-sm" : "text-muted hover:text-ink"
          }`}
        >
          {copy.languageSwitch.russian}
        </button>
        <button
          type="button"
          onClick={() => setLocale("en")}
          className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
            locale === "en" ? "bg-ink text-white shadow-sm" : "text-muted hover:text-ink"
          }`}
        >
          {copy.languageSwitch.english}
        </button>
      </div>
    </div>
  );
}
