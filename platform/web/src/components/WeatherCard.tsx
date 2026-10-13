/** Weather kartı: sıcaklık, şehir, durum, nem, rüzgar, hissedilen. */
import Card from "./Card";
import type { WeatherInfo } from "../types";

interface Props {
  weather: WeatherInfo | null;
  online: boolean;
  citySetting: string | undefined;
  onRefresh: () => void;
  refreshing?: boolean;
}

const REASONS: Record<string, string> = {
  no_api_key: "Hava durumu anahtarı tanımlı değil.",
  invalid_city: "Şehir bulunamadı.",
  invalid_api_key: "API anahtarı geçersiz.",
  network_error: "Ağ hatası — yeniden deneniyor.",
  http_error: "Servis hatası.",
  parse_error: "Yanıt okunamadı.",
  backend_offline: "Backend çevrimdışı.",
};

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-0.5 text-xs">
      <span className="text-slate-400">{label}</span>
      <span className="tabular-nums text-slate-200">{value}</span>
    </div>
  );
}

export default function WeatherCard({ weather, online, citySetting, onRefresh }: Props) {
  const available = online && weather?.available === true;
  const reason = weather && !weather.available
    ? REASONS[weather.reason ?? ""] ?? "Bilinmeyen durum."
    : null;

  return (
    <Card title="Weather" onRefresh={onRefresh}>
      <div className="mb-2 flex items-center justify-between">
        <div>
          <div className="text-[15px] font-semibold text-slate-100">
            {available ? weather?.city : (online ? citySetting ?? "--" : "--")}
          </div>
          <div className="text-[10px] capitalize text-slate-400">
            {available ? weather?.description ?? "--" : reason ?? "--"}
          </div>
        </div>
        <div className="text-3xl font-bold tabular-nums" style={{ color: "rgb(var(--accent-soft-rgb))" }}>
          {available && weather?.temperature !== undefined ? `${Math.round(weather.temperature)}°` : "--"}
        </div>
      </div>
      <div className="border-t pt-1.5" style={{ borderColor: "var(--border)" }}>
        <Row label="Nem" value={available && weather?.humidity !== undefined ? `%${weather.humidity}` : "--"} />
        <Row label="Rüzgar" value={available && weather?.wind_speed !== undefined ? `${weather.wind_speed} m/s` : "--"} />
        <Row label="Hissedilen" value={available && weather?.feels_like !== undefined ? `${weather.feels_like}°` : "--"} />
      </div>
    </Card>
  );
}
