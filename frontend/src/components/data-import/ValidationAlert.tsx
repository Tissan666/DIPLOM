import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, ShieldAlert } from "lucide-react";

type ValidationAlertProps = {
  status: "success" | "warning" | "error";
  title: string;
  description: string;
  missingFields?: string[];
};

export function ValidationAlert({ status, title, description, missingFields = [] }: ValidationAlertProps) {
  const icon =
    status === "success" ? (
      <CheckCircle2 className="h-5 w-5 text-success" />
    ) : status === "warning" ? (
      <ShieldAlert className="h-5 w-5 text-warning" />
    ) : (
      <AlertTriangle className="h-5 w-5 text-danger" />
    );

  const palette =
    status === "success"
      ? "border-success/20 bg-success/10"
      : status === "warning"
        ? "border-warning/20 bg-warning/10"
        : "border-danger/20 bg-danger/10";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
      className={`rounded-[22px] border px-4 py-4 ${palette}`}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 rounded-2xl bg-white/80 p-2">{icon}</span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">{title}</p>
          <p className="mt-1 text-sm leading-7 text-muted">{description}</p>
          {missingFields.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {missingFields.map((field) => (
                <span key={field} className="rounded-full border border-danger/15 bg-white/80 px-3 py-1 text-xs font-semibold text-danger">
                  {field}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
