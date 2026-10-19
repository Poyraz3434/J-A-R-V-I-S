import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { SmartHomeDevice, SmartHomeStatus } from "../types";
import Card from "./Card";

export default function SmartHomeCard() {
  const [status, setStatus] = useState<SmartHomeStatus | null>(null);
  const [rooms, setRooms] = useState<Record<string, SmartHomeDevice[]>>({});
  const [room, setRoom] = useState("all");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const nextStatus = await api.smartHomeStatus();
      setStatus(nextStatus);
      if (!nextStatus.configured || !nextStatus.connected) {
        setRooms({});
        setError(null);
        return;
      }
      const result = await api.smartHomeDevices();
      setRooms(result.devices);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Google Home verisi alınamadı");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 10000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const connect = async () => {
    try {
      const result = await api.smartHomeOAuthStart();
      window.open(result.authorization_url, "jarvis-google-home", "width=520,height=700");
      window.setTimeout(() => void refresh(), 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Google Home bağlantısı başlatılamadı");
    }
  };

  const command = async (
    device: SmartHomeDevice,
    action: "on" | "off" | "brightness" | "temperature",
    value?: number
  ) => {
    setBusy(device.id);
    try {
      await api.smartHomeCommand(device.id, action, value);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Komut gönderilemedi");
    } finally {
      setBusy(null);
    }
  };

  const visibleRooms = room === "all" ? Object.entries(rooms) : Object.entries(rooms).filter(([name]) => name === room);

  return (
    <Card title="Google Home" onRefresh={() => void refresh()}>
      {!status?.configured ? (
        <div className="space-y-2 text-xs text-slate-400">
          <p>Google Home SDM bağlantısı yapılandırılmamış.</p>
          <p className="text-[10px] text-slate-500">Developer Console OAuth bilgilerini sunucu ortamına ekleyin.</p>
        </div>
      ) : !status.connected ? (
        <div className="space-y-2">
          <p className="text-xs text-slate-400">Akıllı cihazlarınızı JARVIS'e bağlayın.</p>
          <button type="button" onClick={() => void connect()} className="btn-accent w-full rounded-lg px-3 py-2 text-xs font-semibold">
            Google ile bağlan
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex gap-1 overflow-x-auto pb-1">
            <button type="button" onClick={() => setRoom("all")} className={`rounded px-2 py-1 text-[10px] ${room === "all" ? "bg-white/15" : "bg-white/5"}`}>Tümü</button>
            {Object.keys(rooms).map((name) => (
              <button type="button" key={name} onClick={() => setRoom(name)} className={`rounded px-2 py-1 text-[10px] ${room === name ? "bg-white/15" : "bg-white/5"}`}>{name}</button>
            ))}
          </div>
          {visibleRooms.map(([name, devices]) => (
            <div key={name} className="space-y-1">
              <div className="text-[10px] uppercase tracking-widest text-slate-500">{name}</div>
              {devices.map((device) => (
                <div key={`${device.id}-controls`}>
                  <div key={device.id} className="flex items-center gap-2 rounded-lg border border-white/10 px-2 py-2">
                    <span className={`h-2 w-2 rounded-full ${device.online ? "bg-emerald-400" : "bg-slate-600"}`} />
                    <span className="min-w-0 flex-1 truncate text-xs">{device.name}</span>
                    <button type="button" disabled={!device.online || busy === device.id} onClick={() => void command(device, "on")} className="rounded bg-emerald-500/15 px-2 py-1 text-[10px] text-emerald-200 disabled:opacity-40">Aç</button>
                    <button type="button" disabled={!device.online || busy === device.id} onClick={() => void command(device, "off")} className="rounded bg-red-500/15 px-2 py-1 text-[10px] text-red-200 disabled:opacity-40">Kapat</button>
                  </div>
                {device.traits.some((trait) => trait.endsWith(".Brightness")) && (
                  <label className="flex items-center gap-2 px-2 pb-1 text-[10px] text-slate-400">
                    Parlaklık
                    <input
                      type="range"
                      min="0"
                      max="100"
                      defaultValue={Number(device.state.brightness ?? 100)}
                      disabled={!device.online || busy === device.id}
                      onChange={(event) => void command(device, "brightness", Number(event.target.value))}
                      className="min-w-0 flex-1 accent-current"
                      style={{ accentColor: "rgb(var(--accent-soft-rgb))" }}
                    />
                  </label>
                )}
                {device.traits.some((trait) => trait.endsWith(".TemperatureSetting")) && (
                  <label className="flex items-center justify-between px-2 pb-1 text-[10px] text-slate-400">
                    Sıcaklık
                    <input
                      type="number"
                      min="7"
                      max="35"
                      step="0.5"
                      defaultValue={Number(device.state.heatCelsius ?? 21)}
                      disabled={!device.online || busy === device.id}
                      onBlur={(event) => void command(device, "temperature", Number(event.target.value))}
                      className="w-16 rounded border border-white/10 bg-white/5 px-1 py-0.5 text-right text-xs text-slate-200"
                    />
                  </label>
                )}
                </div>
              ))}
            </div>
          ))}
          <button type="button" onClick={() => void api.smartHomeDisconnect().then(refresh)} className="text-[10px] text-slate-500 hover:text-slate-300">Bağlantıyı kes</button>
        </div>
      )}
      {error && <p className="mt-2 text-[11px] text-red-300">{error}</p>}
    </Card>
  );
}
