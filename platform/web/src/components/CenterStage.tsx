/** Orta alan: animasyonlu halkalar + logo çekirdeği + durum yazısı + alt butonlar.

Renk kuralı: data-logo-state yalnızca bu kapsamdadır; düşünme/yanıt
animasyonu başka hiçbir öğeye sıçramaz (CSS de bunu garanti eder).

Faz 3: mikrofon dinleme göstergesi her zaman görünür (gereklim 5.4);
sesli oturum aktifken "Sesli Mod" bandı ve çıkış butonu gösterilir.
*/
import type { LogoState, VoiceStatus } from "../types";

interface Props {
  phase: LogoState;
  onCamera: () => void;
  onMic: () => void;
  onKeyboard: () => void;
  onExitVoiceMode: () => void;
  cameraLive: boolean;
  voice: VoiceStatus | null;
  voiceError: string | null;
}

const STATUS_TEXT: Record<LogoState, string> = {
  idle: "Listening for wake word...",
  thinking: "Düşünüyor...",
  speaking: "Konuşuyor...",
  offline: "Çevrimdışı",
};

const MIC_LABEL: Record<string, string> = {
  off: "Mikrofon: Kapalı",
  wake: "Mikrofon: Uyanma bekleniyor",
  listening: "Mikrofon: Dinliyor",
  thinking: "Mikrofon: İşleniyor",
  speaking: "Mikrofon: Konuşuyor",
  error: "Mikrofon: Hata",
};

const MIC_COLOR: Record<string, string> = {
  off: "rgb(100 116 139)",
  wake: "rgb(59 130 246)",
  listening: "rgb(74 222 128)",
  thinking: "rgb(250 204 21)",
  speaking: "rgb(59 130 246)",
  error: "rgb(248 113 113)",
};

/** Mikrofon durumuna göre logo phase'i ve durum yazısı. */
function voicePhase(
  voice: VoiceStatus | null,
  base: LogoState
): { phase: LogoState; text: string | null } {
  if (!voice || voice.mic === "off") return { phase: base, text: null };
  switch (voice.mic) {
    case "wake":
      return { phase: "idle", text: "Listening for wake word..." };
    case "listening":
      return { phase: "idle", text: "Sizi dinliyorum efendim..." };
    case "thinking":
      return { phase: "thinking", text: "Düşünüyor..." };
    case "speaking":
      return { phase: "speaking", text: "Konuşuyor..." };
    case "error":
      return { phase: base, text: voice.error ?? "Ses hatası" };
    default:
      return { phase: base, text: null };
  }
}

export default function CenterStage({
  phase,
  onCamera,
  onMic,
  onKeyboard,
  onExitVoiceMode,
  cameraLive,
  voice,
  voiceError,
}: Props) {
  const vp = voicePhase(voice, phase);
  const effPhase = vp.phase;
  const statusText = vp.text ?? STATUS_TEXT[phase];
  const micOn = !!voice && voice.mic !== "off";
  const voiceSession = !!voice?.session;
  const micState = voice?.mic ?? "off";

  return (
    <div className="relative flex min-h-0 flex-1 flex-col items-center justify-center">
      {/* Sesli oturum bandı */}
      {voiceSession && (
        <div
          className="mb-4 flex items-center gap-3 rounded-full border px-4 py-1.5 text-xs"
          style={{
            borderColor: "rgb(var(--accent-rgb) / 0.5)",
            background: "rgb(var(--accent-rgb) / 0.08)",
            color: "rgb(var(--accent-soft-rgb))",
          }}
        >
          <span
            className="h-2 w-2 animate-pulse rounded-full"
            style={{ background: MIC_COLOR[micState] ?? MIC_COLOR.off }}
          />
          Sesli Mod
          <button
            type="button"
            onClick={onExitVoiceMode}
            className="btn-accent rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
            title="Sesli moddan çık"
          >
            Çıkış
          </button>
        </div>
      )}

      {/* Logo sahnesi */}
      <div
        id="logo-stage"
        data-logo-state={effPhase}
        className="relative mb-7 aspect-square w-44 select-none sm:w-56 md:w-64"
      >
        <div className="logo-ring r1" />
        <div className="logo-ring r2" />
        <div className="logo-ring r3" />
        <div className="logo-core" />
        {/* İç halka kesikleri — HUD görünümü */}
        <div
          className="absolute left-1/2 top-1/2 h-[58%] w-[58%] -translate-x-1/2 -translate-y-1/2 rounded-full border"
          style={{ borderColor: "rgb(var(--logo-rgb) / 0.25)", borderStyle: "dotted" }}
        />
      </div>

      {/* Marka + durum yazısı */}
      <div className="text-center">
        <div
          className="mb-1.5 text-sm font-semibold tracking-[0.5em]"
          style={{ color: "rgb(var(--accent-soft-rgb))", textShadow: "0 0 16px rgb(var(--accent-rgb) / 0.45)" }}
        >
          J.A.R.V.I.S
        </div>
        <p className="text-sm text-slate-300" data-testid="status-text">
          {statusText}
        </p>
        {phase === "offline" && (
          <p className="mt-1 text-[11px] text-slate-500">Yeniden bağlanıyor...</p>
        )}
        {voiceError && <p className="mt-1 text-[11px] text-red-400">{voiceError}</p>}
        {voice && !voice.mic_available && (
          <p className="mt-1 text-[11px] text-slate-500">Mikrofon bulunamadı.</p>
        )}
      </div>

      {/* Mikrofon dinleme göstergesi — HER ZAMAN görünür (gereklim 5.4) */}
      <div
        className="mt-4 flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium tracking-wide"
        style={{
          borderColor: `color-mix(in srgb, ${MIC_COLOR[micState] ?? MIC_COLOR.off} 45%, transparent)`,
          color: MIC_COLOR[micState] ?? MIC_COLOR.off,
          background: "rgb(0 0 0 / 0.25)",
        }}
        data-testid="mic-indicator"
      >
        <span
          className={micOn ? "h-1.5 w-1.5 animate-pulse rounded-full" : "h-1.5 w-1.5 rounded-full"}
          style={{ background: MIC_COLOR[micState] ?? MIC_COLOR.off }}
        />
        {MIC_LABEL[micState] ?? MIC_LABEL.off}
      </div>

      {/* Alt butonlar: kamera / mikrofon / klavye */}
      <div className="mt-6 flex items-center gap-4">
        <CircleButton
          onClick={onCamera}
          title="Kamera"
          active={cameraLive}
          label="cam"
          icon={
            <path
              d="M23 7l-7 5 7 5V7z M14 5H3a2 2 0 00-2 2v10a2 2 0 002 2h11a2 2 0 002-2V7a2 2 0 00-2-2z"
              stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" fill="none"
            />
          }
        />
        <CircleButton
          onClick={onMic}
          title={micOn ? "Mikrofonu durdur" : "Sesli moda geç"}
          active={micOn}
          label="mic"
          icon={
            <path
              d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z M19 10v2a7 7 0 01-14 0v-2 M12 19v4"
              stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" fill="none"
            />
          }
        />
        <CircleButton
          onClick={onKeyboard}
          title="Yazılı mod"
          label="keyboard"
          icon={
            <path
              d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M8 12h.01M12 12h.01M16 12h.01M7 16h10"
              stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" fill="none"
            />
          }
        />
      </div>
    </div>
  );
}

function CircleButton({
  onClick, title, icon, active = false, disabled = false, label,
}: {
  onClick: () => void;
  title: string;
  icon: React.ReactNode;
  active?: boolean;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={label}
      disabled={disabled}
      className="grid h-12 w-12 place-items-center rounded-full border transition-all hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:scale-100"
      style={{
        borderColor: active ? "rgb(239 68 68 / 0.7)" : "rgb(var(--accent-rgb) / 0.4)",
        background: active ? "rgb(239 68 68 / 0.12)" : "rgb(var(--accent-rgb) / 0.06)",
        color: active ? "rgb(248 113 113)" : "rgb(var(--accent-soft-rgb))",
      }}
    >
      <svg width="20" height="20" viewBox="0 0 24 24">{icon}</svg>
    </button>
  );
}
