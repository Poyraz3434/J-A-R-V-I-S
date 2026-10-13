/** Ayarlar modalı: arka plan rengi (kırmızı/yeşil/mavi) + şehir. */
import { useEffect, useState } from "react";
import type { AppSettings } from "../types";

interface Props {
  open: boolean;
  settings: AppSettings | null;
  online: boolean;
  health: { llm_provider: string; llm_ready: boolean } | null;
  onClose: () => void;
  onSave: (patch: { background_color?: string; city?: string }) => Promise<unknown>;
}

const COLORS: { value: AppSettings["background_color"]; label: string; css: string }[] = [
  { value: "red", label: "Kırmızı", css: "rgb(239 68 68)" },
  { value: "green", label: "Yeşil", css: "rgb(34 197 94)" },
  { value: "blue", label: "Mavi", css: "rgb(59 130 246)" },
];

export default function SettingsModal({ open, settings, online, health, onClose, onSave }: Props) {
  const [color, setColor] = useState<AppSettings["background_color"]>(
    settings?.background_color ?? "blue"
  );
  const [city, setCity] = useState(settings?.city ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && settings) {
      setColor(settings.background_color);
      setCity(settings.city);
      setError(null);
    }
  }, [open, settings]);

  if (!open) return null;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave({ background_color: color, city: city.trim() || undefined });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="panel w-full max-w-md p-5"
        style={{ background: "rgb(8 10 18 / 0.95)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-200">
            Ayarlar
          </h2>
          <button type="button" onClick={onClose} className="btn-accent rounded-md px-2 py-1 text-xs">
            ✕
          </button>
        </div>

        {/* Arka plan rengi */}
        <div className="mb-5">
          <label className="mb-2 block text-[11px] uppercase tracking-widest text-slate-400">
            Arka Plan Rengi
          </label>
          <div className="flex gap-3">
            {COLORS.map((c) => (
              <button
                key={c.value}
                type="button"
                onClick={() => setColor(c.value)}
                className="flex flex-1 flex-col items-center gap-1.5 rounded-lg border p-3 transition-transform hover:scale-[1.03]"
                style={{
                  borderColor: color === c.value ? c.css : "var(--border)",
                  background: color === c.value ? `${c.css.replace(")", " / 0.12)").replace("rgb", "rgb")}` : "transparent",
                  boxShadow: color === c.value ? `0 0 14px ${c.css}66` : "none",
                }}
              >
                <span className="h-5 w-5 rounded-full" style={{ background: c.css, boxShadow: `0 0 10px ${c.css}` }} />
                <span className="text-[10px] text-slate-300">{c.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Şehir */}
        <div className="mb-5">
          <label htmlFor="city" className="mb-1.5 block text-[11px] uppercase tracking-widest text-slate-400">
            Hava Durumu Şehri
          </label>
          <input
            id="city"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="Örn. Tuzla,TR"
            maxLength={64}
            className="w-full rounded-lg border bg-black/30 px-3 py-2 text-sm outline-none placeholder:text-slate-500"
            style={{ borderColor: "var(--border)" }}
          />
          <p className="mt-1 text-[10px] text-slate-500">
            OpenWeatherMap biçimi: "Şehir,ÜlkeKodu" (örn. İstanbul,TR)
          </p>
        </div>

        {/* Sistem bilgisi */}
        <div className="mb-5 rounded-lg border p-3 text-[11px] leading-relaxed text-slate-400"
          style={{ borderColor: "var(--border)" }}>
          <div className="flex justify-between">
            <span>Bağlantı</span>
            <span style={{ color: online ? "rgb(74 222 128)" : "rgb(248 113 113)" }}>
              {online ? "Çevrimiçi" : "Çevrimdışı"}
            </span>
          </div>
          <div className="mt-1 flex justify-between">
            <span>LLM Sağlayıcısı</span>
            <span className="text-slate-200">
              {health ? (health.llm_ready ? health.llm_provider : `${health.llm_provider} (demo)`) : "--"}
            </span>
          </div>
        </div>

        {error && <p className="mb-3 text-xs text-red-400">{error}</p>}

        <button
          type="button"
          onClick={save}
          disabled={saving || !online}
          className="btn-accent w-full rounded-lg py-2.5 text-sm font-semibold"
        >
          {saving ? "Kaydediliyor..." : "Kaydet"}
        </button>
      </div>
    </div>
  );
}
