/** Backend ile paylaşılan tip tanımları (Faz 1). */

export type LogoState = "idle" | "thinking" | "speaking" | "offline";

export interface CpuInfo {
  percent: number;
  physical_cores: number;
  logical_cores: number;
  freq_mhz: number | null;
}

export interface MemoryInfo {
  total_gb: number;
  used_gb: number;
  percent: number;
}

export interface DiskInfo {
  total_gb: number;
  used_gb: number;
  percent: number;
}

export interface SystemStats {
  timestamp: string;
  cpu: CpuInfo;
  memory: MemoryInfo;
  disk: DiskInfo;
  uptime_seconds: number;
  boot_time: string;
  load_level: "low" | "medium" | "high";
  command_count?: number;
  session_count?: number;
  /** Faz 3: mikrofon durumu akışta her zaman taşınır. */
  voice?: VoiceStatus;
}

export interface HealthInfo {
  status: string;
  version: string;
  agent_uptime_seconds: number;
  llm_provider: string;
  llm_ready: boolean;
  session_count: number;
}

export interface WeatherInfo {
  available: boolean;
  reason?: string;
  city?: string;
  temperature?: number;
  feels_like?: number;
  humidity?: number;
  wind_speed?: number;
  description?: string;
  icon?: string;
  fetched_at: string;
}

export interface ChatMessage {
  id: number | string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
}

export interface CameraStatus {
  status: "live" | "off";
  width: number | null;
  height: number | null;
}

/** Faz 3: sesli mod durumu — /api/voice/status ve /ws/stats içindeki "voice". */
export interface VoiceStatus {
  mic: "off" | "wake" | "listening" | "thinking" | "speaking" | "error";
  session: boolean;
  mic_available: boolean;
  local_stt: boolean;
  clap_enabled: boolean;
  clap_sensitivity: number;
  wake_phrases: string[];
  exit_phrases: string[];
  last_heard?: string | null;
  last_reply?: string | null;
  error?: string | null;
}

export interface AppSettings {
  background_color: "red" | "green" | "blue";
  city: string;
  allowed_background_colors: string[];
}

/** Faz 4: hatırlatıcı — reminders/service.py şemasıyla uyumlu. */
export interface Reminder {
  id: number;
  title: string;
  due_at: string;
  status: "pending" | "firing" | "acknowledged" | "expired";
  repeat_count: number;
  last_fired_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Faz 2: eşleşmiş cihaz. */
export interface DeviceSummary {
  id: string;
  name: string;
  platform?: string;
  created_at?: string;
  last_seen_at?: string | null;
}
