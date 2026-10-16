/** Dosya transferi kartı (Faz 5): telefon → PC yükleme + son aktarımlar.

Uç keşfi toleranslıdır: yükleme /api/files/upload, olmazsa /api/files;
listeleme /api/files/list, olmazsa /api/files üzerinde denenir.
*/
import { useCallback, useEffect, useRef, useState } from "react";
import Card from "./Card";

interface TransferItem {
  name?: string;
  filename?: string;
  size?: number;
  ts?: string;
  time?: string;
}

const UPLOAD_ENDPOINTS = ["/api/files/upload", "/api/files"];
const LIST_ENDPOINTS = ["/api/files/list", "/api/files"];

async function tryEndpoints<T>(urls: string[], init?: RequestInit): Promise<T> {
  let lastErr: unknown = null;
  for (const u of urls) {
    try {
      const res = await fetch(u, init);
      if (res.ok) return (await res.json()) as T;
      lastErr = new Error(`HTTP ${res.status}`);
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr instanceof Error ? lastErr : new Error("Uç bulunamadı");
}

export default function FileTransferCard() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [items, setItems] = useState<TransferItem[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const j = await tryEndpoints<{
        files?: TransferItem[];
        items?: TransferItem[];
        transfers?: TransferItem[];
      }>(LIST_ENDPOINTS);
      const list = j.files ?? j.items ?? j.transfers ?? [];
      setItems(Array.isArray(list) ? list.slice(0, 5) : []);
    } catch {
      /* çevrimdışı olabilir — sessizce yoksay */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const upload = async (fl: FileList | null) => {
    if (!fl || fl.length === 0) return;
    setBusy(true);
    setMsg(null);
    try {
      for (const f of Array.from(fl)) {
        const fd = new FormData();
        fd.append("file", f);
        fd.append("upload", f);
        await tryEndpoints(UPLOAD_ENDPOINTS, { method: "POST", body: fd });
      }
      setMsg(`${fl.length} dosya yüklendi ✓`);
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Yükleme başarısız");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <Card title="File Transfer">
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => void upload(e.target.files)}
      />
      <button
        type="button"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
        className="btn-accent w-full rounded-lg px-2 py-1.5 text-xs font-medium"
      >
        {busy ? "Yükleniyor..." : "PC'ye Dosya Yükle"}
      </button>
      {msg && <p className="mt-1.5 text-[11px] text-slate-300">{msg}</p>}
      {items.length > 0 && (
        <div className="mt-2 border-t pt-1.5" style={{ borderColor: "var(--border)" }}>
          {items.map((it, i) => (
            <div key={i} className="flex justify-between py-0.5 text-[11px]">
              <span className="truncate text-slate-300">{it.name ?? it.filename ?? "—"}</span>
              <span className="tabular-nums text-slate-500">
                {it.size !== undefined
                  ? `${(it.size / 1024).toFixed(0)} KB`
                  : (it.ts ?? it.time ?? "")}
              </span>
            </div>
          ))}
        </div>
      )}
      <p className="mt-1.5 text-[10px] text-slate-500">
        Dosyalar PC'de transfers klasörüne kaydedilir; "Jarvis, son dosyaları listele"
        diyerek de görebilirsin.
      </p>
    </Card>
  );
}
