import { Moon, Sun } from "lucide-react";
import { useLocale } from "../i18n";
import { useTheme, type Theme } from "../theme";

export function ThemeSwitch() {
  const { copy } = useLocale();
  const { theme, setTheme } = useTheme();
  const options: Array<{ value: Theme; label: string; icon: typeof Sun }> = [
    { value: "light", label: copy.themeSwitch.light, icon: Sun },
    { value: "dark", label: copy.themeSwitch.dark, icon: Moon },
  ];

  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-slate-200/80 bg-white/88 px-2 py-2 shadow-float">
      <span className="inline-flex items-center rounded-full px-2 text-xs font-semibold uppercase tracking-[0.16em] text-muted">
        {copy.themeSwitch.label}
      </span>
      <div
        role="group"
        aria-label={copy.themeSwitch.ariaLabel}
        className="inline-flex items-center rounded-full bg-slate-100 p-1"
      >
        {options.map((option) => {
          const Icon = option.icon;
          const active = theme === option.value;

          return (
            <button
              key={option.value}
              type="button"
              onClick={() => setTheme(option.value)}
              aria-pressed={active}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                active ? "bg-ink text-white shadow-sm" : "text-muted hover:text-ink"
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
