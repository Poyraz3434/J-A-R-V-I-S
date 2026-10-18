/** Faz 4 — hatırlatıcı kartı: listele, oluştur, sustur, ertele, sil. */
import { useCallback, useEffect, useState } from "react";
import Card from "./Card";
import { api, ApiError } from "../api/client";
import type { Reminder } from "../types";

function fmtDue(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("tr-TR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const STATUS_STYLE: Record<Reminder["status"], string> = {
  firing: "text-rose-400",
  pending: "text-cyan-300",
  acked: "text-slate-500",
  expired: "text-slate-600",
};

export default function ReminderCard({
  online,
}: {
  online: boolean;
}) {
  const [items, setItems] = useState<Reminder[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    if (!online) return;
    try {
      const all = (await api.reminders()).reminders;
      setItems(all.filter((r) => r.status !== "expired").slice(0, 8));
      setError(null);
    } catch (e) {
      if (e instanceof ApiError && e.status !== 401) setError(e.message);
    }
  }, [online]);

  useEffect(() => {
    void reload();
    const id = setInterval(() => void reload(), 15000);
    return () => clearInterval(id);
  }, [reload]);

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      await reload();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "İşlem başarısız");
    } finally {
      setBusy(false);
    }
  };

  const add = () =>
    run(async () => {
      if (!title.trim() || !due) throw new ApiError(0, "Başlık ve tarih gerekli");
      const iso = new Date(due).toISOString();
      await api.createReminder(title.trim(), iso);
      setTitle("");
      setDue("");
    });

  const firing = items.filter((r) => r.status === "firing");

  return (
    <Card title="Hatırlatıcılar">
      {firing.length > 0 && (
        <div className="mb-2 rounded-lg border border-rose-500/40 bg-rose-500/10 p-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-rose-300">
            Çalan alarm ({firing.length})
          </p>
          <button
            className="mt-1.5 w-full rounded-md bg-rose-500/80 py-1.5 text-sm font-medium text-white hover:bg-rose-500 disabled:opacity-50"
            disabled={busy}
            onClick={() => void run(() => api.ackAllAlarms())}
          >
            Sustur
          </button>
        </div>
      )}

      <ul className="space-y-1">
        {items.length === 0 && (
          <li className="text-sm text-slate-500">Bekleyen hatırlatıcı yok.</li>
        )}
        {items.map((r) => (
          <li
            key={r.id}
            className="group flex items-center gap-2 rounded-lg border border-white/5 px-2.5 py-1.5 text-sm"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-slate-200">{r.title}</p>
              <p className={`text-xs ${STATUS_STYLE[r.status] ?? "text-slate-500"}`}>
                {fmtDue(r.due_at)}
                {r.repeat_count > 0 && ` · ${r.repeat_count}x yinelendi`}
              </p>
            </div>
            {r.status === "pending" && (
              <button
                title="10 dk ertele"
                disabled={busy}
                className="text-xs text-slate-400 hover:text-cyan-300 disabled:opacity-40"
                onClick={() => void run(() => api.snoozeReminder(r.id, 10))}
              >
                +10dk
              </button>
            )}
            {r.status === "firing" && (
              <button
                title="Sustur"
                disabled={busy}
                className="text-xs text-rose-400 hover:text-rose-300 disabled:opacity-40"
                onClick={() => void run(() => api.ackReminder(r.id))}
              >
                sustur
              </button>
            )}
            <button
              title="Sil"
              disabled={busy}
              className="text-xs text-slate-600 hover:text-rose-400 disabled:opacity-40"
              onClick={() => void run(() => api.deleteReminder(r.id))}
            >
              ✕
            </button>
          </li>
        ))}
      </ul>

      <form
        className="mt-3 space-y-2 border-t border-white/5 pt-3"
        onSubmit={(e) => {
          e.preventDefault();
          void add();
        }}
      >
        <input
          className="w-full rounded-md border border-white/10 bg-black/30 px-2.5 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan-400/50"
          placeholder="Ne hatırlatayım?"
          maxLength={200}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <div className="flex gap-2">
          <input
            type="datetime-local"
            className="min-w-0 flex-1 rounded-md border border-white/10 bg-black/30 px-2.5 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan-400/50"
            value={due}
            onChange={(e) => setDue(e.target.value)}
          />
          <button
            type="submit"
            disabled={busy || !online}
            className="rounded-md bg-cyan-500/90 px-3 py-1.5 text-sm font-medium text-slate-950 hover:bg-cyan-400 disabled:opacity-50"
          >
            Ekle
          </button>
        </div>
      </form>

      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
    </Card>
  );
}