/** Orta alan: animasyonlu halkalar + logo çekirdeği + durum yazısı + alt butonlar.

Renk kuralı: data-logo-state yalnızca bu kapsamdadır; düşünme/yanıt
animasyonu başka hiçbir öğeye sıçramaz (CSS de bunu garanti eder).
*/
import type { LogoState } from "../types";

interface Props {
  phase: LogoState;
  onCamera: () => void;
  onMic: () => void;
  onKeyboard: () => void;
  cameraLive: boolean;
}

const STATUS_TEXT: Record<LogoState, string> = {
  idle: "Listening for wake word...",
  thinking: "Düşünüyor...",
  speaking: "Konuşuyor...",
  offline: "Çevrimdışı",
};

export default function CenterStage({ phase, onCamera, onMic, onKeyboard, cameraLive }: Props) {
  return (
    <div className="relative flex min-h-0 flex-1 flex-col items-center justify-center">
      {/* Logo sahnesi */}
      <div
        id="logo-stage"
        data-logo-state={phase}
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
          {STATUS_TEXT[phase]}
        </p>
        {phase === "offline" && (
          <p className="mt-1 text-[11px] text-slate-500">Yeniden bağlanıyor...</p>
        )}
      </div>

      {/* Alt butonlar: kamera / mikrofon / klavye */}
      <div className="mt-8 flex items-center gap-4">
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
          title="Mikrofon (Faz 3)"
          disabled
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
