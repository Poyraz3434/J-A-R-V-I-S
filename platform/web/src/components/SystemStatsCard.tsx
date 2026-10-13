/** System Stats kartı: CPU %, RAM (GB + çubuk), CPU/Memory/Disk kutuları. */
import Card from "./Card";
import type { SystemStats } from "../types";

interface Props {
  stats: SystemStats | null;
  online: boolean;
}

/** Değer: offline ya da veri yoksa "--". */
function fmt<T>(online: boolean, value: T | undefined | null, render: (v: T) => string): string {
  if (!online || value === undefined || value === null) return "--";
  return render(value);
}

function Bar({ percent }: { percent: number }) {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ background: "rgb(255 255 255 / 0.08)" }}>
      <div
        className="h-full rounded-full transition-[width] duration-700 ease-out"
        style={{
          width: `${clamped}%`,
          background: "linear-gradient(90deg, rgb(var(--accent-rgb) / 0.55), rgb(var(--accent-soft-rgb)))",
          boxShadow: "0 0 8px rgb(var(--accent-rgb) / 0.5)",
        }}
      />
    </div>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-2 text-center" style={{ borderColor: "var(--border)", background: "rgb(255 255 255 / 0.02)" }}>
      <div className="text-[9px] uppercase tracking-[0.16em] text-slate-400">{label}</div>
      <div className="mt-0.5 text-sm font-semibold tabular-nums text-slate-100">{value}</div>
    </div>
  );
}

export default function SystemStatsCard({ stats, online }: Props) {
  const cpu = stats?.cpu;
  const mem = stats?.memory;
  const disk = stats?.disk;

  return (
    <Card title="System Stats">
      {/* CPU yüzdesi */}
      <div className="mb-3">
        <div className="mb-1 flex items-baseline justify-between">
          <span className="text-[10px] uppercase tracking-widest text-slate-400">CPU</span>
          <span className="text-xl font-bold tabular-nums text-slate-100">
            {fmt(online, cpu?.percent, (p) => `${p.toFixed(0)}%`)}
          </span>
        </div>
        <Bar percent={online ? (cpu?.percent ?? 0) : 0} />
      </div>

      {/* RAM: GB + çubuk */}
      <div className="mb-3">
        <div className="mb-1 flex items-baseline justify-between">
          <span className="text-[10px] uppercase tracking-widest text-slate-400">RAM Kullanımı</span>
          <span className="text-xs tabular-nums text-slate-200">
            {fmt(online, mem, (m) => `${m.used_gb.toFixed(1)} GB / ${m.total_gb.toFixed(1)} GB`)}
          </span>
        </div>
        <Bar percent={online ? (mem?.percent ?? 0) : 0} />
      </div>

      {/* CPU / Memory / Disk kutuları */}
      <div className="grid grid-cols-3 gap-2">
        <MetricBox label="CPU" value={fmt(online, cpu?.percent, (p) => `${p.toFixed(0)}%`)} />
        <MetricBox label="Memory" value={fmt(online, mem?.percent, (p) => `${p.toFixed(0)}%`)} />
        <MetricBox label="Disk" value={fmt(online, disk?.percent, (p) => `${p.toFixed(0)}%`)} />
      </div>
    </Card>
  );
}
