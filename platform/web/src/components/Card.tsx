/** Daraltılabilir kart kabuğu — her kartta başlık, yenile ikonu, açma/kapama. */
import { useState, type ReactNode } from "react";

interface CardProps {
  title: string;
  onRefresh?: () => void;
  refreshing?: boolean;
  defaultOpen?: boolean;
  children: ReactNode;
}

export default function Card({
  title,
  onRefresh,
  refreshing = false,
  defaultOpen = true,
  children,
}: CardProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="panel panel-hover transition-colors">
      <header className="flex items-center gap-2 px-3 py-2">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex flex-1 items-center gap-2 text-left"
          aria-expanded={open}
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 16 16"
            fill="none"
            className="transition-transform duration-200"
            style={{
              transform: open ? "rotate(90deg)" : "rotate(0deg)",
              color: "rgb(var(--accent-soft-rgb))",
            }}
          >
            <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-300">
            {title}
          </h2>
        </button>
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            title="Yenile"
            className="rounded p-1.5 hover:bg-white/5 disabled:opacity-50"
            style={{ color: "rgb(var(--accent-soft-rgb))" }}
          >
            <svg
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              className={refreshing ? "animate-spin" : ""}
            >
              <path
                d="M21 12a9 9 0 11-2.64-6.36M21 3v6h-6"
                stroke="currentColor"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        )}
      </header>
      {open && <div className="px-3 pb-3">{children}</div>}
    </section>
  );
}
