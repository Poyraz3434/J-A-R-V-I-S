/** System Uptime kartı: çalışma süresi, oturum sayısı, komut sayısı, sistem yükü. */
import Card from "./Card";
import type { SystemStats } from "../types";

interface Props {
  stats: SystemStats | null;
  online: boolean;
}

const LOAD_STYLES: Record<string, { label: string; color: string }> = {
  low: { label: "Düşük", color: "rgb(74 222 128)" },
  medium: { label: "Orta", color: "rgb(250 204 21)" },
  high: { label: "Yüksek", color: "rgb(248 113 113)" },
};

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const parts: string[] = [];
  if (d > 0) parts.push(`${d} gün`);
  if (d > 0 || h > 0) parts.push(`${h} sa`);
  parts.push(`${m} dk`);
  return parts.join(" ");
}

function Row({ label, value, valueStyle }: { label: string; value: string; valueStyle?: string }) {
  return (
    <div className="flex justify-between py-1 text-xs">
      <span className="text-slate-400">{label}</span>
      <span className="font-semibold tabular-nums" style={valueStyle ? { color: valueStyle } : { color: "var(--text-main)" }}>
        {value}
      </span>
    </div>
  );
}

export default function UptimeCard({ stats, online }: Props) {
  const load = online && stats ? LOAD_STYLES[stats.load_level] : null;

  return (
    <Card title="System Uptime">
      <Row label="Çalışma Süresi" value={online && stats ? formatUptime(stats.uptime_seconds) : "--"} />
      <div className="my-1 border-t" style={{ borderColor: "var(--border)" }} />
      <Row label="Oturum Sayısı" value={online && stats?.session_count !== undefined ? String(stats.session_count) : "--"} />
      <Row label="Komut Sayısı" value={online && stats?.command_count !== undefined ? String(stats.command_count) : "--"} />
      <div className="my-1 border-t" style={{ borderColor: "var(--border)" }} />
      <div className="flex items-center justify-between py-1 text-xs">
        <span className="text-slate-400">Sistem Yükü</span>
        {load ? (
          <span className="flex items-center gap-1.5 font-semibold" style={{ color: load.color }}>
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: load.color }} />
            {load.label}
          </span>
        ) : (
          <span className="text-slate-100">--</span>
        )}
      </div>
    </Card>
  );
}
