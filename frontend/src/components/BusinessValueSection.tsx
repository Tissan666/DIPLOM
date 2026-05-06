import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { AlertTriangle, BarChart3, Building2, ClipboardCheck, FileSearch, Handshake, Star, Store, Users } from "lucide-react";
import { useLocale } from "../i18n";

const audienceIcons: LucideIcon[] = [Building2, Store, Handshake];
const riskIcons: LucideIcon[] = [AlertTriangle, Users, BarChart3, Star];
const audienceTones = ["icon-decision", "icon-suspicious", "icon-analysis"] as const;
const riskTones = ["icon-risk", "icon-analysis", "icon-suspicious", "icon-decision"] as const;

export function BusinessValueSection() {
  const { copy } = useLocale();

  return (
    <section className="section-wrap pb-8">
      <motion.section
        initial={{ opacity: 0, y: 18 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.25 }}
        transition={{ duration: 0.45 }}
        className="surface-card overflow-hidden"
      >
        <div className="grid xl:grid-cols-[0.88fr_1.12fr]">
          <div className="relative border-b border-slate-200/80 bg-gradient-to-br from-accent-soft/90 via-white/76 to-white/42 p-7 sm:p-9 xl:border-b-0 xl:border-r">
            <div className="absolute right-7 top-7 hidden h-16 w-16 rounded-[24px] border border-accent/15 bg-white/70 shadow-float sm:flex sm:items-center sm:justify-center">
              <FileSearch className="h-7 w-7 text-accent" />
            </div>
            <p className="eyebrow pr-0 sm:pr-20">{copy.businessValue.eyebrow}</p>
            <h2 className="mt-4 max-w-3xl font-display text-4xl font-bold leading-[1] text-ink sm:pr-20">
              {copy.businessValue.title}
            </h2>
            <p className="mt-5 max-w-2xl text-sm leading-8 text-muted sm:text-[15px]">
              {copy.businessValue.description}
            </p>

            <div className="mt-7 rounded-[26px] border border-accent/20 bg-white/78 p-5 shadow-float">
              <div className="flex items-start gap-3">
                <span className="icon-shell icon-decision">
                  <ClipboardCheck className="h-6 w-6" />
                </span>
                <div>
                  <h3 className="text-base font-bold text-ink">{copy.businessValue.scenarioTitle}</h3>
                  <p className="mt-2 text-sm leading-7 text-muted">{copy.businessValue.scenarioText}</p>
                </div>
              </div>

              <div className="mt-5 grid gap-3">
                {copy.businessValue.scenarioSteps.map((step, index) => (
                  <div key={step} className="flex items-start gap-3 rounded-2xl border border-slate-200/70 bg-white/82 px-3 py-3 shadow-[0_10px_24px_rgba(15,23,42,0.035)]">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink text-xs font-bold text-white">
                      {index + 1}
                    </span>
                    <p className="text-sm leading-6 text-muted">{step}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-6 p-5 sm:p-7">
            <section>
              <SectionTitle title={copy.businessValue.audienceTitle} />
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                {copy.businessValue.audience.map((item, index) => {
                  const Icon = audienceIcons[index % audienceIcons.length];
                  return (
                    <ValueCard
                      key={item.title}
                      icon={Icon}
                      tone={audienceTones[index % audienceTones.length]}
                      title={item.title}
                      description={item.description}
                    />
                  );
                })}
              </div>
            </section>

            <section>
              <SectionTitle title={copy.businessValue.risksTitle} />
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {copy.businessValue.risks.map((item, index) => {
                  const Icon = riskIcons[index % riskIcons.length];
                  return (
                    <ValueCard
                      key={item.title}
                      icon={Icon}
                      tone={riskTones[index % riskTones.length]}
                      title={item.title}
                      description={item.description}
                      compact
                    />
                  );
                })}
              </div>
            </section>
          </div>
        </div>
      </motion.section>
    </section>
  );
}

function SectionTitle({ title }: { title: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="h-px flex-1 bg-slate-200/90" />
      <h3 className="shrink-0 text-sm font-bold uppercase tracking-[0.16em] text-ink">{title}</h3>
      <span className="h-px flex-1 bg-slate-200/90" />
    </div>
  );
}

function ValueCard({
  icon: Icon,
  tone,
  title,
  description,
  compact = false,
}: {
  icon: LucideIcon;
  tone: string;
  title: string;
  description: string;
  compact?: boolean;
}) {
  return (
    <article
      className={`product-card product-card-hover group p-4 ${
        compact ? "min-h-[132px]" : "min-h-[164px]"
      }`}
    >
      <div className="flex items-start gap-3">
        <span className={`icon-shell h-11 w-11 ${tone}`}>
          <Icon className="h-6 w-6" />
        </span>
        <div className="min-w-0">
          <h4 className="text-sm font-bold leading-6 text-ink">{title}</h4>
          <p className="mt-2 text-xs leading-6 text-muted/90">{description}</p>
        </div>
      </div>
    </article>
  );
}
