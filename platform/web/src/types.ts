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

export interface AppSettings {
  background_color: "red" | "green" | "blue";
  city: string;
  allowed_background_colors: string[];
}
