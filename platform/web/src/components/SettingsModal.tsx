/** Ayarlar modalı: arka plan rengi, şehir ve ses ayarları (Faz 3). */
import { useEffect, useState } from "react";
import type { AppSettings, VoiceStatus } from "../types";

interface Props {
  open: boolean;
  settings: AppSettings | null;
  online: boolean;
  health: { llm_provider: string; llm_ready: boolean } | null;
  voice: VoiceStatus | null;
  onClose: () => void;
  onSave: (patch: { background_color?: string; city?: string }) => Promise<unknown>;
  onSaveVoice: (patch: {
    wake_phrases?: string[];
    exit_phrases?: string[];
    clap_enabled?: boolean;
    clap_sensitivity?: number;
  }) => Promise<unknown>;
}

const COLORS: { value: AppSettings["background_color"]; label: string; css: string }[] = [
  { value: "red", label: "Kırmızı", css: "rgb(239 68 68)" },
  { value: "green", label: "Yeşil", css: "rgb(34 197 94)" },
  { value: "blue", label: "Mavi", css: "rgb(59 130 246)" },
];

const inputCls = "w-full rounded-lg border bg-black/30 px-3 py-2 text-sm outline-none placeholder:text-slate-500";
const inputStyle = { borderColor: "var(--border)" };

export default function SettingsModal({
  open, settings, online, health, voice, onClose, onSave, onSaveVoice,
}: Props) {
  const [color, setColor] = useState<AppSettings["background_color"]>("blue");
  const [city, setCity] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Ses ayarları (Faz 3 — gereklim 5.4: ifadeler düzenlenebilir)
  const [wakeText, setWakeText] = useState("");
  const [exitText, setExitText] = useState("");
  const [clapEnabled, setClapEnabled] = useState(true);
  const [clapSens, setClapSens] = useState(6.0);

  useEffect(() => {
    if (open && settings) {
      setColor(settings.background_color);
      setCity(settings.city);
      setError(null);
    }
  }, [open, settings]);

  useEffect(() => {
    if (open && voice) {
      setWakeText((voice.wake_phrases ?? []).join("\n"));
      setExitText((voice.exit_phrases ?? []).join(", "));
      setClapEnabled(!!voice.clap_enabled);
      setClapSens(voice.clap_sensitivity ?? 6.0);
    }
  }, [open, voice]);

  if (!open) return null;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave({ background_color: color, city: city.trim() || undefined });
      const wakes = wakeText.split("\n").map((l) => l.trim()).filter((l) => l.length >= 4).slice(0, 12);
      const exits = exitText.split(",").map((l) => l.trim()).filter((l) => l.length >= 3).slice(0, 12);
      await onSaveVoice({
        wake_phrases: wakes.length > 0 ? wakes : undefined,
        exit_phrases: exits.length > 0 ? exits : undefined,
        clap_enabled: clapEnabled,
        clap_sensitivity: clapSens,
      });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-black/60 p-4" onClick={onClose}>
      <div
        className="panel my-8 w-full max-w-md p-5"
        style={{ background: "rgb(8 10 18 / 0.95)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-200">Ayarlar</h2>
          <button type="button" onClick={onClose} className="btn-accent rounded-md px-2 py-1 text-xs">✕</button>
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
                  background: color === c.value ? "rgb(255 255 255 / 0.04)" : "transparent",
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
            className={inputCls}
            style={inputStyle}
          />
          <p className="mt-1 text-[10px] text-slate-500">OpenWeatherMap biçimi: "Şehir,ÜlkeKodu" (örn. İstanbul,TR)</p>
        </div>

        {/* Ses ayarları (Faz 3) */}
        <div className="mb-5 border-t pt-4" style={{ borderColor: "var(--border)" }}>
          <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.2em]"
            style={{ color: "rgb(var(--accent-soft-rgb))" }}>
            Ses Ayarları
          </h3>

          {!voice?.mic_available && (
            <p className="mb-3 text-[10px] text-amber-400">
              Mikrofon bu cihazda bulunamadı; ayarlar yine de kaydedilir.
            </p>
          )}

          {/* Uyandırma ifadeleri — satır satır */}
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-slate-400">
            Uyandırma İfadeleri (her satıra bir tane)
          </label>
          <textarea
            value={wakeText}
            onChange={(e) => setWakeText(e.target.value)}
            placeholder={"hey jarvis\nuyan bakalım baba eve geldi"}
            rows={3}
            maxLength={600}
            className={`${inputCls} resize-none font-mono text-xs`}
            style={inputStyle}
          />
          <p className="mt-1 mb-3 text-[10px] text-slate-500">
            Her ifade en az 4 karakter olmalı; en fazla 12 ifade.
          </p>

          {/* Çıkış ifadeleri */}
          <label className="mb-1.5 block text-[11px] uppercase tracking-widest text-slate-400">
            Sesli Mod Çıkış İfadeleri (virgülle)
          </label>
          <input
            value={exitText}
            onChange={(e) => setExitText(e.target.value)}
            placeholder="kapat, çıkış, sesli modu kapat"
            maxLength={300}
            className={inputCls}
            style={inputStyle}
          />
          <p className="mt-1 mb-3 text-[10px] text-slate-500">
            Bu ifadeler duyulduğunda Jarvis sesli moddan çıkar.
          </p>

          {/* Çift alkış */}
          <div className="mb-2 flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-200">Çift Alkış ile Açma</p>
              <p className="text-[10px] text-slate-500">
                İki kez alkışlayınca Jarvis aktif programın üstünde açılır.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setClapEnabled((v) => !v)}
              role="switch"
              aria-checked={clapEnabled}
              className="relative h-6 w-11 rounded-full transition-colors"
              style={{
                background: clapEnabled ? "rgb(var(--accent-rgb) / 0.6)" : "rgb(255 255 255 / 0.12)",
              }}
            >
              <span
                className="absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all"
                style={{ left: clapEnabled ? "22px" : "2px" }}
              />
            </button>
          </div>

          {/* Alkış hassasiyeti */}
          <div className="mb-1">
            <div className="flex justify-between text-[11px]">
              <span className="text-slate-400">Alkış Hassasiyeti</span>
              <span className="tabular-nums text-slate-200">{clapSens.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min={1}
              max={20}
              step={0.5}
              value={clapSens}
              onChange={(e) => setClapSens(parseFloat(e.target.value))}
              className="mt-1 w-full accent-current"
              style={{ accentColor: "rgb(var(--accent-soft-rgb))" }}
            />
            <div className="flex justify-between text-[9px] text-slate-500">
              <span>Daha az duyarlı</span>
              <span>Daha duyarlı</span>
            </div>
          </div>
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
          <div className="mt-1 flex justify-between">
            <span>Mikrofon</span>
            <span className="text-slate-200">
              {voice ? (voice.mic_available ? voice.mic : "yok") : "--"}
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
