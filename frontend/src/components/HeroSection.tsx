import type { ReactNode } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight,
  BarChart3,
  Brain,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileSearch,
  FolderInput,
  Gauge,
  ListChecks,
  SearchCheck,
  ShieldAlert,
} from "lucide-react";
import { useLocale } from "../i18n";
import { LanguageSwitch } from "./LanguageSwitch";
import { ThemeSwitch } from "./ThemeSwitch";

type HeroSectionProps = {
  onPrimaryAction: () => void;
  onSecondaryAction: () => void;
};

export function HeroSection({ onPrimaryAction, onSecondaryAction }: HeroSectionProps) {
  const { copy } = useLocale();

  return (
    <section className="section-wrap pb-12 pt-8 lg:pb-14 lg:pt-12">
      <div className="grid items-stretch gap-7 xl:grid-cols-[1.08fr_0.92fr]">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55 }}
          className="surface-card relative min-h-[620px] overflow-hidden p-7 sm:p-10 lg:p-12"
        >
          <div className="absolute inset-x-0 top-0 h-56 bg-gradient-to-br from-accent/14 via-white/0 to-white/0" />
          <div className="absolute right-[-120px] top-[-110px] h-72 w-72 rounded-full bg-accent/10 blur-3xl" />
          <div className="relative">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <p className="eyebrow">{copy.hero.eyebrow}</p>
              <div className="flex flex-wrap gap-2 sm:justify-end">
                <ThemeSwitch />
                <LanguageSwitch />
              </div>
            </div>
            <h1 className="mt-10 max-w-4xl font-display text-5xl font-bold leading-[0.95] text-ink sm:text-6xl xl:text-[4.8rem]">
              {copy.hero.title}
            </h1>
            <p className="mt-7 max-w-2xl text-base leading-8 text-muted sm:text-lg">
              {copy.hero.description}
            </p>
            <div className="mt-6 inline-flex max-w-full items-center gap-3 rounded-full border border-accent/20 bg-accent-soft/80 px-4 py-2.5 text-sm font-bold leading-6 text-accent shadow-soft">
              <ShieldAlert className="h-5 w-5 shrink-0" />
              <span>{copy.hero.audienceLine}</span>
            </div>

            <div className="mt-9 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={onPrimaryAction}
                className="primary-button px-7 py-3.5"
              >
                {copy.hero.primaryCta}
                <ArrowRight className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={onSecondaryAction}
                className="secondary-button px-7 py-3.5"
              >
                {copy.hero.secondaryCta}
              </button>
            </div>

            <div className="mt-9 flex flex-wrap gap-2.5">
              <Badge icon={<Brain className="h-3.5 w-3.5" />} label={copy.hero.badges.nlp} />
              <Badge icon={<ShieldAlert className="h-3.5 w-3.5" />} label={copy.hero.badges.anomaly} />
              <Badge icon={<SearchCheck className="h-3.5 w-3.5" />} label={copy.hero.badges.patterns} />
              <Badge icon={<Database className="h-3.5 w-3.5" />} label={copy.hero.badges.scraping} />
            </div>

            <div className="mt-9 grid max-w-2xl gap-3 rounded-[26px] border border-slate-200/80 bg-white/76 p-3 shadow-soft sm:grid-cols-3">
              {copy.hero.flowSteps.map((step, index) => {
                const icons = [
                  <Database key="data" className="h-5 w-5" />,
                  <SearchCheck key="analysis" className="h-5 w-5" />,
                  <ClipboardCheck key="report" className="h-5 w-5" />,
                ];

                return (
                  <div key={step} className="flex items-center gap-3 rounded-[20px] bg-white/82 px-3 py-3 shadow-[0_10px_28px_rgba(15,23,42,0.04)]">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-accent-soft text-accent">
                      {icons[index]}
                    </span>
                    <span className="text-sm font-semibold text-ink">{step}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.08 }}
          className="surface-card relative grid h-full content-start gap-5 overflow-hidden p-5 sm:p-6 lg:p-7"
        >
          <div className="absolute inset-x-0 top-0 h-44 bg-gradient-to-br from-accent/10 via-white/0 to-white/0" />
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">{copy.hero.previewEyebrow}</p>
              <h2 className="mt-3 font-display text-3xl font-bold text-ink">{copy.hero.previewTitle}</h2>
            </div>
            <span className="badge-soft border-accent/20 bg-accent-soft text-accent">{copy.common.ready}</span>
          </div>

          <div className="product-card relative border-accent/20 bg-gradient-to-br from-accent-soft/85 via-white/78 to-white/60 p-5 shadow-float">
            <div className="flex items-start gap-4">
              <span className="icon-shell border-accent/15 bg-white/88 text-accent">
                <FileSearch className="h-6 w-6" />
              </span>
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent">{copy.hero.onboardingTitle}</p>
                <p className="mt-3 text-sm leading-7 text-muted">{copy.hero.onboardingDescription}</p>
              </div>
            </div>

            <div className="mt-5 grid gap-3">
              {copy.hero.onboardingSteps.map((step, index) => (
                <div key={step} className="product-card flex items-start gap-3 rounded-[20px] px-3 py-3 shadow-none">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink text-xs font-bold text-white">
                    {index + 1}
                  </span>
                  <p className="text-sm leading-6 text-muted">{step}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="surface-card-soft relative p-4">
            <div className="flex items-center gap-2">
              <FolderInput className="h-5 w-5 text-accent" />
              <p className="text-sm font-semibold text-ink">{copy.hero.outputTitle}</p>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {copy.hero.outputItems.map((item) => (
                <div key={item} className="flex items-start gap-2 rounded-2xl border border-slate-200/70 bg-white/76 px-3 py-2">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
                  <span className="text-xs leading-5 text-muted">{item}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="product-card p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="icon-shell icon-analysis h-11 w-11">
                  <BarChart3 className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-sm font-bold text-ink">{copy.hero.reportPreviewTitle}</p>
                  <p className="mt-1 text-xs leading-5 text-muted">{copy.hero.reportPreviewDescription}</p>
                </div>
              </div>
              <span className="badge-soft shrink-0 border-warning/20 bg-warning/10 text-warning">
                {copy.hero.reportPreviewBadge}
              </span>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-[0.42fr_0.58fr]">
              <div className="hero-report-chart rounded-[22px] p-3">
                <div
                  className="hero-risk-orbit mx-auto flex h-24 w-24 items-center justify-center rounded-full"
                  style={{
                    background:
                      "conic-gradient(rgb(var(--color-danger)) 0 34%, rgb(var(--color-warning)) 34% 62%, rgb(var(--color-accent)) 62% 100%)",
                  }}
                >
                  <div className="hero-risk-core flex h-16 w-16 flex-col items-center justify-center rounded-full text-center shadow-sm">
                    <Gauge className="h-5 w-5 text-ink" />
                    <span className="mt-1 text-[10px] font-bold uppercase tracking-[0.14em] text-muted">
                      {copy.hero.riskScore}
                    </span>
                  </div>
                </div>
              </div>

              <div className="grid gap-2">
                {copy.hero.reportPreviewRows.map((row, index) => (
                  <div key={row} className="rounded-2xl border border-slate-200/75 bg-white/76 px-3 py-2.5">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-xs font-bold text-ink">{row}</span>
                      <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-muted">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200/70">
                      <div
                        className={`h-full rounded-full ${
                          index === 0 ? "bg-danger" : index === 1 ? "bg-warning" : "bg-accent"
                        }`}
                        style={{ width: `${82 - index * 16}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {copy.hero.analysisScope.map((item, index) => (
                <div key={item} className="flex items-center gap-2 rounded-2xl border border-slate-200/70 bg-white/72 px-3 py-2">
                  <ListChecks
                    className={`h-4 w-4 shrink-0 ${
                      index === 0 ? "text-danger" : index === 1 ? "text-warning" : index === 2 ? "text-sky-700" : "text-success"
                    }`}
                  />
                  <span className="text-xs leading-5 text-muted">{item}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="product-card p-4">
            <div className="flex items-start gap-3">
              <span className="icon-shell icon-decision h-11 w-11">
                <ClipboardCheck className="h-5 w-5" />
              </span>
              <div>
                <p className="text-sm font-semibold text-ink">{copy.hero.recommendedAction}</p>
                <p className="mt-1 text-xs leading-6 text-muted">{copy.hero.recommendedActionText}</p>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

function Badge({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-200/70 bg-white/82 px-3.5 py-2 text-xs font-bold text-ink shadow-soft transition hover:-translate-y-0.5 hover:bg-white hover:shadow-float">
      {icon}
      {label}
    </span>
  );
}
