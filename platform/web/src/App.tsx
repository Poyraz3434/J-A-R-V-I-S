/** JARVIS Web UI — Faz 1 yerçekirdeği düzeni.

Masaüstü: sol kartlar | orta logo sahnesi | sağ sohbet paneli.
Mobil: logo + sohbet; sistem kartları açılır çekmecede.
*/
import { useEffect, useRef, useState } from "react";
import { useJarvis } from "./hooks/useJarvis";
import { api } from "./api/client";
import TopBar from "./components/TopBar";
import SystemStatsCard from "./components/SystemStatsCard";
import WeatherCard from "./components/WeatherCard";
import CameraCard from "./components/CameraCard";
import UptimeCard from "./components/UptimeCard";
import CenterStage from "./components/CenterStage";
import ConversationPanel from "./components/ConversationPanel";
import SettingsModal from "./components/SettingsModal";
import type { LogoState } from "./types";

export default function App() {
  const jarvis = useJarvis();
  const chatInputRef = useRef<HTMLInputElement>(null);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [speakingUntil, setSpeakingUntil] = useState(0);

  // Yanıt gelince kısa "Konuşuyor..." vurgusu (yalnızca logoda görünür)
  const messageCount = jarvis.messages.length;
  const lastIsAssistant = jarvis.messages[messageCount - 1]?.role === "assistant";
  useEffect(() => {
    if (!jarvis.sending && lastIsAssistant && messageCount > 0) {
      setSpeakingUntil(Date.now() + 1600);
    }
  }, [messageCount, jarvis.sending, lastIsAssistant]);

  useEffect(() => {
    if (!speakingUntil) return;
    const id = setInterval(() => {
      if (Date.now() >= speakingUntil) setSpeakingUntil(0);
    }, 200);
    return () => clearInterval(id);
  }, [speakingUntil]);

  // Logo durumu: offline > thinking > speaking > idle
  const phase: LogoState = !jarvis.online
    ? "offline"
    : jarvis.sending
      ? "thinking"
      : speakingUntil > 0
        ? "speaking"
        : "idle";

  const handleExport = (format: "txt" | "md") => {
    window.open(api.exportUrl(format), "_blank");
  };

  const cards = (
    <>
      <SystemStatsCard stats={jarvis.stats} online={jarvis.online} />
      <WeatherCard
        weather={jarvis.weather}
        online={jarvis.online}
        citySetting={jarvis.settings?.city}
        onRefresh={() => jarvis.refreshWeather(true)}
      />
      <CameraCard
        camera={jarvis.camera}
        photo={jarvis.photo}
        busy={jarvis.cameraBusy}
        error={jarvis.cameraError}
        online={jarvis.online}
        onToggle={jarvis.toggleCamera}
        onCapture={jarvis.capturePhoto}
        onClosePhoto={() => jarvis.setPhoto(null)}
      />
      <UptimeCard stats={jarvis.stats} online={jarvis.online} />
    </>
  );

  return (
    <div className="relative flex h-screen flex-col overflow-hidden">
      <TopBar
        online={jarvis.online}
        weather={jarvis.weather}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenDrawer={() => setDrawerOpen(true)}
      />

      {/* Mobil çekmece (sistem kartları) */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={() => setDrawerOpen(false)}>
          <div
            className="absolute bottom-0 left-0 right-0 max-h-[70vh] space-y-2.5 overflow-y-auto rounded-t-2xl border-t p-3 pb-6"
            style={{ borderColor: "var(--border-strong)", background: "rgb(6 8 14 / 0.97)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mx-auto mb-2 h-1 w-10 rounded-full bg-white/20" />
            {cards}
          </div>
        </div>
      )}

      {/* Ana ızgara */}
      <main className="relative z-10 grid min-h-0 flex-1 gap-3 p-3 lg:grid-cols-[280px_minmax(0,1fr)_340px]">
        {/* Sol kolon — masaüstü */}
        <div className="hidden min-h-0 space-y-2.5 overflow-y-auto pr-0.5 lg:block">{cards}</div>

        {/* Orta alan */}
        <CenterStage
          phase={phase}
          cameraLive={jarvis.camera.status === "live"}
          onCamera={() => {
            if (window.innerWidth < 1024) setDrawerOpen(true);
            else jarvis.toggleCamera();
          }}
          onMic={() => {
            /* Faz 3: sesli mod */
          }}
          onKeyboard={() => chatInputRef.current?.focus()}
        />

        {/* Sağ panel — sohbet */}
        <div className="min-h-0 lg:block">
          <ConversationPanel
            ref={chatInputRef}
            messages={jarvis.messages}
            sending={jarvis.sending}
            online={jarvis.online}
            lastError={jarvis.lastError}
            onSend={jarvis.sendMessage}
            onClear={jarvis.clearConversation}
            onExport={handleExport}
          />
        </div>
      </main>

      <SettingsModal
        open={settingsOpen}
        settings={jarvis.settings}
        online={jarvis.online}
        health={jarvis.health}
        onClose={() => setSettingsOpen(false)}
        onSave={jarvis.saveSettings}
      />
    </div>
  );
}
