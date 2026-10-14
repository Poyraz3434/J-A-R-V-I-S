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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
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

export const api = {
  health: () => request<import("../types").HealthInfo>("/api/health"),
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
  exportUrl: (format: "txt" | "md") => `/api/conversation/export?format=${format}`,
};
