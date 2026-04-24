import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Brain, Database, SearchCheck, ShieldAlert } from "lucide-react";
import { Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useLocale } from "../i18n";
import type { DashboardResult } from "../types/analysis";
import { LanguageSwitch } from "./LanguageSwitch";
import { ThemeSwitch } from "./ThemeSwitch";

type HeroSectionProps = {
  preview: DashboardResult;
  onPrimaryAction: () => void;
  onSecondaryAction: () => void;
};

export function HeroSection({ preview, onPrimaryAction, onSecondaryAction }: HeroSectionProps) {
  const { copy } = useLocale();

  return (
    <section className="section-wrap pt-8 pb-10 lg:pt-12">
      <div className="grid items-stretch gap-6 lg:grid-cols-[1.08fr_0.92fr]">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55 }}
          className="surface-card relative overflow-hidden p-8 sm:p-10"
        >
          <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-br from-accent/10 via-white/0 to-white/0" />
          <div className="relative">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <p className="eyebrow">{copy.hero.eyebrow}</p>
              <div className="flex flex-wrap gap-2 sm:justify-end">
                <ThemeSwitch />
                <LanguageSwitch />
              </div>
            </div>
            <h1 className="mt-5 max-w-3xl font-display text-5xl leading-[0.94] text-ink sm:text-6xl xl:text-7xl">
              {copy.hero.title}
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-8 text-muted sm:text-lg">
              {copy.hero.description}
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={onPrimaryAction}
                className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-3 text-sm font-semibold text-white shadow-float transition hover:-translate-y-0.5 hover:bg-slate-800"
              >
                {copy.hero.primaryCta}
                <ArrowRight className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={onSecondaryAction}
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-6 py-3 text-sm font-semibold text-ink transition hover:-translate-y-0.5 hover:border-accent/30 hover:bg-white"
              >
                {copy.hero.secondaryCta}
              </button>
            </div>

            <div className="mt-8 flex flex-wrap gap-2.5">
              <Badge icon={<Brain className="h-3.5 w-3.5" />} label={copy.hero.badges.nlp} />
              <Badge icon={<ShieldAlert className="h-3.5 w-3.5" />} label={copy.hero.badges.anomaly} />
              <Badge icon={<SearchCheck className="h-3.5 w-3.5" />} label={copy.hero.badges.patterns} />
              <Badge icon={<Database className="h-3.5 w-3.5" />} label={copy.hero.badges.scraping} />
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.08 }}
          className="surface-card grid content-start gap-5 p-6 sm:p-7 lg:self-start"
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">{copy.hero.previewEyebrow}</p>
              <h2 className="mt-3 font-display text-3xl text-ink">{copy.hero.previewTitle}</h2>
            </div>
            <span className="badge-soft border-accent/20 bg-accent-soft text-accent">{preview.overview.statusLabel}</span>
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(190px,0.72fr)_minmax(0,1fr)]">
            <div className="surface-card-soft flex min-h-[250px] items-center justify-center p-5">
              <div className="relative h-48 w-full max-w-[220px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={preview.trustBreakdown}
                      innerRadius={54}
                      outerRadius={78}
                      paddingAngle={3}
                      dataKey="value"
                      stroke="none"
                    >
                      {preview.trustBreakdown.map((entry) => (
                        <Cell key={entry.name} fill={entry.fill} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
                  <p className="max-w-[104px] text-[10px] font-semibold uppercase leading-4 tracking-[0.16em] text-muted">
                    {copy.hero.riskScore}
                  </p>
                  <p className="mt-1 text-4xl font-semibold leading-none text-ink">{preview.overview.riskScore}</p>
                </div>
              </div>
            </div>

            <div className="grid gap-4">
              <div className="surface-card-soft p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-muted">{copy.hero.reviewActivity}</p>
                    <p className="mt-1 text-lg font-semibold text-ink">{copy.hero.recentCadence}</p>
                  </div>
                  <span className="badge-soft">{preview.overview.reviewCount} {copy.common.reviews}</span>
                </div>
                <div className="mt-4 h-32">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={preview.activitySeries}>
                      <Tooltip />
                      <Line
                        type="monotone"
                        dataKey="reviews"
                        name={copy.resultsSuccess.reviewSeries}
                        stroke="#0f766e"
                        strokeWidth={3}
                        dot={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="suspicious"
                        name={copy.resultsSuccess.suspiciousSeries}
                        stroke="#c35e43"
                        strokeWidth={2.5}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <MiniMetric label={copy.hero.manipulationProbability} value={`${preview.overview.manipulationProbability}%`} />
                <MiniMetric label={copy.hero.confidence} value={`${preview.overview.confidence}%`} />
                <MiniMetric label={copy.hero.flaggedReviews} value={String(preview.overview.suspiciousCount)} />
                <MiniMetric label={copy.hero.manualReview} value={String(preview.overview.manualReviewCount)} />
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
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-200/70 bg-white/78 px-3.5 py-2 text-xs font-semibold text-ink shadow-float">
      {icon}
      {label}
    </span>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="surface-card-soft flex min-h-[112px] flex-col justify-between p-4">
      <p className="break-words text-[10px] font-semibold uppercase leading-4 tracking-[0.12em] text-muted sm:text-[11px]">
        {label}
      </p>
      <p className="mt-3 text-2xl font-semibold leading-none text-ink">{value}</p>
    </div>
  );
}
