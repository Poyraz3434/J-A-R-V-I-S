/** Backend API istemcisi — tüm fetch çağrıları tek yerde.

Offline davranış: her çağrı hata fırlatır, çağıran katman yakalar ve
arayüz "--" gösterir. fetch'in kendisi asla uygulamayı çökertmez.
*/

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
  }
}

/** Faz 2: eşleşmiş cihaz belirteci — telefonda claim sonrası saklanır. */
const TOKEN_KEY = "jarvis.device_token";
const CLIENT_ID_KEY = "jarvis.client_id";
function createClientId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

export const clientId = {
  get: () => {
    const existing = localStorage.getItem(CLIENT_ID_KEY);
    if (existing) return existing;
    const created = createClientId();
    localStorage.setItem(CLIENT_ID_KEY, created);
    return created;
  },
};

export const deviceToken = {
  get: () => localStorage.getItem(TOKEN_KEY) ?? "",
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = deviceToken.get();
  const resp = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Client-ID": clientId.get(),
      ...(token ? { "X-Device-Token": token } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* gövde yok — önemsiz */
    }
    throw new ApiError(resp.status, detail);
  }
  return (await resp.json()) as T;
}

async function requestBlob(path: string): Promise<Blob> {
  const token = deviceToken.get();
  const resp = await fetch(path, {
    headers: {
      ...(token ? { "X-Device-Token": token } : {}),
      "X-Client-ID": clientId.get(),
    },
  });
  if (!resp.ok) throw new ApiError(resp.status, `HTTP ${resp.status}`);
  return resp.blob();
}

export const api = {
  health: () => request<import("../types").HealthInfo>("/api/health"),
  integrations: () =>
    request<{ integrations: Record<string, { configured: boolean; connected?: boolean; reachable?: boolean; detail?: string }> }>(
      "/api/integrations"
    ),
  stats: () => request<import("../types").SystemStats>("/api/system/stats"),
  weather: (refresh = false) =>
    request<import("../types").WeatherInfo>(
      `/api/weather${refresh ? "?refresh=true" : ""}`
    ),
  settings: () => request<import("../types").AppSettings>("/api/settings"),
  updateSettings: (patch: Partial<{ background_color: string; city: string }>) =>
    request<import("../types").AppSettings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),
  conversation: () =>
    request<{ messages: import("../types").ChatMessage[]; count: number }>(
      "/api/conversation"
    ),
  sendChat: (message: string) =>
    request<{ reply: string; error: boolean; provider: string; model: string }>(
      "/api/chat",
      { method: "POST", body: JSON.stringify({ message }) }
    ),
  clearConversation: () => request<{ cleared: number }>("/api/conversation", { method: "DELETE" }),
  cameraOpen: () => request<import("../types").CameraStatus>("/api/camera/open", { method: "POST" }),
  cameraClose: () => request<import("../types").CameraStatus>("/api/camera/close", { method: "POST" }),
  cameraStatus: () => request<import("../types").CameraStatus>("/api/camera/status"),
  cameraCapture: () =>
    request<{ image: string; captured_at: string }>("/api/camera/capture", { method: "POST" }),

  /** Faz 3: sesli mod uçları. */
  voiceStatus: () => request<import("../types").VoiceStatus>("/api/voice/status"),
  voiceStart: () =>
    request<import("../types").VoiceStatus>("/api/voice/start", { method: "POST" }),
  voiceStop: () =>
    request<import("../types").VoiceStatus>("/api/voice/stop", { method: "POST" }),
  voiceModeOn: (reason?: string) =>
    request<import("../types").VoiceStatus>("/api/voice/mode/on", {
      method: "POST",
      body: JSON.stringify(reason ? { reason } : {}),
    }),
  voiceModeOff: () =>
    request<import("../types").VoiceStatus>("/api/voice/mode/off", { method: "POST" }),
  voiceSay: (text: string) =>
    request<{ spoken: boolean }>("/api/voice/say", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  voiceUpdateSettings: (patch: {
    wake_phrases?: string[];
    wake_response?: string;
    exit_phrases?: string[];
    clap_enabled?: boolean;
    clap_sensitivity?: number;
  }) =>
    request<import("../types").VoiceStatus>("/api/voice/settings", {
      method: "PUT",
      body: JSON.stringify(patch),
    }),

  /** Dışa aktarma indirme bağlantısı (tarayıcı dosyayı indirir). */
  exportConversation: (format: "txt" | "md") =>
    requestBlob(`/api/conversation/export?format=${format}`),

  /** Faz 4: hatırlatıcılar. */
  reminders: (history = false) =>
    request<{ reminders: import("../types").Reminder[] }>(
      `/api/reminders${history ? "?history=true" : ""}`
    ),
  createReminder: (title: string, due_at: string) =>
    request<{ reminder: import("../types").Reminder }>("/api/reminders", {
      method: "POST",
      body: JSON.stringify({ title, due_at }),
    }),
  deleteReminder: (id: number) =>
    request<{ deleted: number }>(`/api/reminders/${id}`, { method: "DELETE" }),
  ackReminder: (id: number) =>
    request<{ reminder: import("../types").Reminder }>(`/api/reminders/${id}/ack`, {
      method: "POST",
    }),
  ackAllAlarms: () =>
    request<{ acked: number }>("/api/reminders/ack-all", { method: "POST" }),
  snoozeReminder: (id: number, minutes = 10) =>
    request<{ reminder: import("../types").Reminder }>(`/api/reminders/${id}/snooze`, {
      method: "POST",
      body: JSON.stringify({ minutes }),
    }),
  reportActivity: () =>
    request<{ silenced: boolean }>("/api/reminders/activity", { method: "POST" }),

  /** Faz 2: eşleştirme — QR akışı ve cihaz yönetimi (routes_pair.py şekilleri). */
  pairStart: () =>
    request<{ code: string; expires_in: number; url: string }>("/api/pair/start", {
      method: "POST",
    }),
  pairStatus: () =>
    request<{
      pending: boolean;
      expires_in: number | null;
      devices: import("../types").DeviceSummary[];
      lan_ip: string | null;
    }>("/api/pair/status"),
  pairClaim: (code: string, device_name: string) =>
    request<{ device_id: string; name: string; device_token: string }>(
      "/api/pair/claim",
      { method: "POST", body: JSON.stringify({ code, device_name }) }
    ),
  revokeDevice: (id: string) =>
    request<{ revoked: string }>(`/api/pair/devices/${id}`, { method: "DELETE" }),

  /** Faz 2: WoL — kurulum durumu ve test (routes_system.py). */
  wolStatus: () => request<Record<string, unknown>>("/api/system/wol"),
  wolTest: () =>
    request<Record<string, unknown>>("/api/system/wol/wake", { method: "POST" }),

  smartHomeStatus: () => request<import("../types").SmartHomeStatus>("/api/smart-home/status"),
  smartHomeDevices: () =>
    request<{ devices: Record<string, import("../types").SmartHomeDevice[]>; total: number }>(
      "/api/smart-home/devices"
    ),
  smartHomeCommand: (device_id: string, action: "on" | "off" | "brightness" | "temperature", value?: number) =>
    request<{ ok: boolean; device_id: string; action: string }>("/api/smart-home/command", {
      method: "POST",
      body: JSON.stringify({ device_id, action, value }),
    }),
  smartHomeOAuthStart: () =>
    request<{ authorization_url: string }>("/api/smart-home/oauth/start"),
  smartHomeDisconnect: () =>
    request<{ disconnected: boolean }>("/api/smart-home/disconnect", { method: "POST" }),
};
