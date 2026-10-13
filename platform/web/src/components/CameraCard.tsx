/** Camera kartı: aç/kapa + fotoğraf çek; kapalıyken "Camera Off", açıkken LIVE göstergesi. */
import { useState } from "react";
import Card from "./Card";
import type { CameraStatus } from "../types";

interface Props {
  camera: CameraStatus;
  photo: string | null;
  busy: boolean;
  error: string | null;
  online: boolean;
  onToggle: () => void;
  onCapture: () => void;
  onClosePhoto: () => void;
}

export default function CameraCard({
  camera, photo, busy, error, online, onToggle, onCapture, onClosePhoto,
}: Props) {
  const [confirming, setConfirming] = useState(false);
  const live = online && camera.status === "live";

  const handleCapture = () => {
    // Kayıt yalnızca kullanıcının açık eylemiyle başlar (güvenlik 6).
    if (!confirming) {
      setConfirming(true);
      setTimeout(() => setConfirming(false), 2500);
      return;
    }
    setConfirming(false);
    onCapture();
  };

  return (
    <Card title="Camera">
      {!photo && (
        <div className="relative mb-2 flex h-24 items-center justify-center rounded-lg border"
          style={{
            borderColor: live ? "rgb(239 68 68 / 0.55)" : "var(--border)",
            background: live ? "rgb(239 68 68 / 0.05)" : "rgb(255 255 255 / 0.02)",
          }}>
          {live ? (
            <>
              {/* Belirgin aktif göstergesi (gereklim 4) */}
              <span className="absolute left-2 top-2 flex items-center gap-1.5 rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-bold tracking-widest text-red-400">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />
                LIVE {camera.width ? `${camera.width}×${camera.height}` : ""}
              </span>
              <span className="text-xs text-slate-300">Kamera etkin</span>
            </>
          ) : (
            <span className="text-xs text-slate-500">
              {online ? "Camera Off" : "--"}
            </span>
          )}
        </div>
      )}

      {photo && (
        <div className="relative mb-2">
          <img src={photo} alt="Son çekim" className="h-24 w-full rounded-lg object-cover" />
          <button
            type="button"
            onClick={onClosePhoto}
            className="absolute right-1.5 top-1.5 rounded-full bg-black/70 px-2 py-0.5 text-[10px] text-slate-200"
          >
            Kapat
          </button>
        </div>
      )}

      {error && <p className="mb-1.5 text-[11px] text-red-400">{error}</p>}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={onToggle}
          disabled={!online || busy}
          className="btn-accent flex-1 rounded-lg px-2 py-1.5 text-xs font-medium"
        >
          {busy ? "..." : live ? "Kapat" : "Aç"}
        </button>
        <button
          type="button"
          onClick={handleCapture}
          disabled={!live || busy}
          className="btn-accent flex-1 rounded-lg px-2 py-1.5 text-xs font-medium"
          title={live ? "Fotoğraf çek (iki dokunuş: onay)" : "Önce kamerayı açın"}
        >
          {confirming ? "Çek (onayla)" : "Fotoğraf Çek"}
        </button>
      </div>
    </Card>
  );
}
