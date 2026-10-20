/** Eşleştirme kartı (Faz 2) — QR üret, cihazları gör, cihaz kaldır.
    Madde 11: QR süresi dolunca BİR KEZ otomatik yenilenir (döngü korumalı). */
import { useCallback, useEffect, useRef, useState } from "react";
import Card from "./Card";
import { api, ApiError } from "../api/client";
import { t } from "../i18n";
import type { DeviceSummary } from "../types";

interface PairStatus {
  pending: boolean;
  expires_in?: number | null;
  devices: DeviceSummary[];
  lan_ip?: string | null;
}

export default function PairCard({ online }: { online: boolean }) {
  const [status, setStatus] = useState<PairStatus | null>(null);
  const [qrKey, setQrKey] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);
  /** Otomatik yenileme sayacı: sonsuz döngüyü (üret → süresi dol → üret) engeller. */
  const autoRenewRef = useRef(0);

  const load = useCallback(async () => {
    if (!online) return;
    try {
      setStatus(await api.pairStatus());
      setError(null);
    } catch (e) {
      if (e instanceof ApiError && e.status !== 401) setError(e.message);
    }
  }, [online]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 10000);
    return () => window.clearInterval(id);
  }, [load]);

  // QR aktifken geri sayım bitince listeyi tazele; otomatik yenileme en fazla
  // 2 kez üst üste yapılır (kullanıcı karttan ayrıldıysa döngü kurulmaz).
  useEffect(() => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    if (qrKey !== null && status?.pending && (status.expires_in ?? 0) > 0) {
      timerRef.current = window.setTimeout(
        () => void load(),
        ((status.expires_in ?? 5) + 1) * 1000
      );
    }
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [qrKey, status?.pending, status?.expires_in, load]);

  const startPairing = async (auto = false) => {
    setBusy(true);
    setError(null);
    try {
      await api.pairStart();
      setQrKey(Date.now());
      if (auto) autoRenewRef.current += 1;
      else autoRenewRef.current = 0;
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("pair.start_failed"));
    } finally {
      setBusy(false);
    }
  };

  // Madde 11: QR gösterilirken kodun süresi döndüyse bir kez yeni kod üret.
  useEffect(() => {
    if (
      qrKey !== null &&
      status &&
      !status.pending &&
      autoRenewRef.current < 2
    ) {
      void startPairing(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qrKey, status?.pending]);

  const revoke = async (id: string) => {
    setBusy(true);
    try {
      await api.revokeDevice(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cihaz kaldırılamadı");
    } finally {
      setBusy(false);
    }
  };

  const devices = status?.devices ?? [];

  return (
    <Card title="Cihazlar" onRefresh={() => void load()} refreshing={busy}>
      {devices.length === 0 && !status?.pending && (
        <p className="text-sm text-slate-500">
          Eşleşmiş cihaz yok. QR üreterek telefonu tanıt.
        </p>
      )}

      {status?.pending && qrKey !== null && (
        <div className="mb-2 rounded-lg border border-cyan-400/30 bg-cyan-400/5 p-2 text-center">
          <img
            src={`/api/pair/qr.svg?t=${qrKey}`}
            alt="Eşleştirme QR kodu"
            width={168}
            height={168}
            className="mx-auto rounded-md bg-[#0b1120] p-1"
          />
          <p className="mt-1.5 text-xs text-cyan-200">
            Telefonun kamerasıyla okut — {status.expires_in ?? 0} sn
          </p>
          {status.lan_ip && (
            <p className="mt-0.5 text-[10px] text-slate-500">
              veya tarayıcıda aç: http://{status.lan_ip}:8000
            </p>
          )}
        </div>
      )}

      {devices.length > 0 && (
        <ul className="space-y-1">
          {devices.map((d) => (
            <li
              key={d.id}
              className="flex items-center gap-2 rounded-lg border border-white/5 px-2.5 py-1.5 text-sm"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-slate-200">{d.name}</p>
                <p className="text-xs text-slate-500">
                  {d.platform ?? "cihaz"}
                  {d.last_seen_at ? ` · son görülme ${new Date(d.last_seen_at).toLocaleTimeString("tr-TR")}` : ""}
                </p>
              </div>
              <button
                title="Cihazı kaldır"
                disabled={busy}
                className="text-xs text-slate-600 hover:text-rose-400 disabled:opacity-40"
                onClick={() => void revoke(d.id)}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={() => void startPairing()}
        disabled={busy || !online}
        className="mt-3 w-full rounded-md border border-cyan-400/40 bg-cyan-400/10 py-1.5 text-sm font-medium text-cyan-200 hover:bg-cyan-400/20 disabled:opacity-40"
      >
        {status?.pending ? "QR'ı yenile" : "QR ile cihaz eşleştir"}
      </button>

      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
    </Card>
  );
}