# JARVIS Platform — Faz 1: Yerel Çekirdek

Windows PC'de çalışan kişisel sesli asistan projesinin platform katmanı.
Bu dizin, mevcut JARVIS v10 denemelerinden bağımsız, fazlı geliştirme
sürecinin kalıcı uygulama iskeletidir.

## Mimari (Faz 1)

```
platform/
├── pc-agent/            # Python 3.11+ — Windows'ta çalışan ana servis
│   ├── main.py          # Giriş noktası (uvicorn)
│   ├── jarvis_agent/
│   │   ├── config.py    # .env yükleme + sağlayıcı seçimi
│   │   ├── app.py       # FastAPI uygulama fabrikası + statik UI sunumu
│   │   ├── api/         # REST uçları + WebSocket (her alan kendi modülünde)
│   │   │   ├── routes_system.py        # /api/health, /api/system/stats, hava, audit
│   │   │   ├── routes_chat.py          # /api/chat (LLM + araç döngüsü)
│   │   │   ├── routes_settings.py      # /api/settings (renk, şehir)
│   │   │   ├── routes_conversation.py  # /api/conversation (+ export txt/md)
│   │   │   ├── routes_camera.py        # /api/camera/* (aç/kapa/çek)
│   │   │   └── ws.py                   # /ws/stats (2 sn'de bir canlı itme)
│   │   ├── core/        # stats (psutil monitör), weather (OWM), counters
│   │   ├── llm/         # Sağlayıcı soyutlaması: OpenAI-uyumlu / Anthropic / Mock
│   │   │   ├── provider.py    # ortak arayüz (ChatProvider, ChatResult, ToolCall)
│   │   │   ├── openai_compat.py  # OpenAI + Groq + Ollama (aynı protokol)
│   │   │   ├── anthropic_provider.py
│   │   │   ├── mock_provider.py   # anahtar yokken demo yanıtlar
│   │   │   └── tools.py   # get_system_stats / get_current_time / get_weather
│   │   ├── camera/       # OpenCV kamera servisi (thread-güvenli)
│   │   └── store/        # SQLite: mesajlar, ayarlar, audit log
│   └── tests/           # pytest — 19 test (ağ ve anahtardan bağımsız)
└── web/                 # React 18 + TypeScript + Vite + Tailwind
    └── src/
        ├── App.tsx              # 3 kolonlu düzen (masaüstü) + mobil çekmece
        ├── api/client.ts        # fetch sarmalayıcı + offline algılama
        ├── hooks/useJarvis.ts   # tüm durum yönetimi (WS + REST fallback)
        └── components/          # TopBar, kartlar, CenterStage, sohbet paneli
```

## Teknoloji Seçimleri ve Gerekçeleri

| Katman | Seçim | Gerekçe |
|---|---|---|
| Agent | Python 3.11 + FastAPI + Uvicorn | ASGI WebSocket desteği hazır; OpenAPI dokümantasyon bedava; Faz 3 ses/STT kütüphaneleri zaten Python ekosisteminde |
| İstatistik | psutil | CPU/RAM/disk/uptime için de facto standart |
| Veri | SQLite (stdlib) | Kişisel tek kullanıcı için yeterli; sıfır kurulum |
| LLM | Soyutlama katmanı | Groq/OpenAI/Anthropic/Ollama değiştirilebilir; OpenAI-uyumlu protokol Groq+Ollama'yı da kapsar |
| HTTP | httpx | Sync+async aynı API (hava sync, LLM async) |
| Web UI | React 18 + TS + Vite + Tailwind v3 | İstenen stack; dev'de Vite proxy, üretimde dist agent'ta |
| Hava | OpenWeatherMap | Ücretsiz katman, `lang=tr` Türkçe açıklama |

## Kurulum

### 1) PC Agent

```powershell
cd F:\Software\JARVİS\platform\pc-agent
# mevcut kök .venv ile:
F:\Software\JARVİS\.venv\Scripts\pip install -r requirements.txt
# yeni ortam için:
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Anahtarlar: depo kökündeki `.env` otomatik okunur (JARVIS_GROQ_API_KEY
vb.). Agent'a özel değerler için `platform/pc-agent/.env.example` → `.env`.

### 2) Web UI

```powershell
cd F:\Software\JARVİS\platform\web
npm install
npm run build        # dist/ üretir — agent bunu sunar
```

Geliştirme (hot-reload): `npm run dev` → http://localhost:5173
(Vite `/api`'yi 127.0.0.1:8000'e proxy'ler.)

### 3) Çalıştırma

```powershell
cd F:\Software\JARVİS\platform\pc-agent
F:\Software\JARVİS\.venv\Scripts\python main.py
# → http://127.0.0.1:8000
```

Yerel ağ erişimi: `.env`'de `JARVIS_BIND=0.0.0.0`. **Faz 1'de kimlik
doğrulama yoktur** — yalnızca güvenli ağda kullanın (Faz 2'de QR
eşleştirme + TLS gelir).

### 4) Testler

```powershell
cd F:\Software\JARVİS\platform\pc-agent
F:\Software\JARVİS\.venv\Scripts\python -m pytest tests -v
# 19 test — ağa/LLM anahtarına bağımsız (MockProvider)
```

## API Özeti

| Uç | Açıklama |
|---|---|
| `GET /api/health` | Bağlantı + LLM sağlayıcı durumu (offline algılamanın kalbi) |
| `GET /api/system/stats` · `WS /ws/stats` | Canlı CPU/RAM/disk/uptime/sayaçlar (WS 2 sn itme) |
| `POST /api/chat` | Yazılı sohbet; araçlar: saat, sistem, hava |
| `GET/PUT /api/settings` | Arka plan rengi (red/green/blue), şehir |
| `GET/DELETE /api/conversation` + `export?format=txt\|md` | Geçmiş, temizleme, dışa aktarma |
| `POST /api/camera/open\|close\|capture` · `status` | Kamera (kullanıcı eylemi şart) |
| `GET /api/audit` | Denetim kayıtları |
| `/docs` | OpenAPI (Swagger) otomatik dokümantasyon |

## Güvenlik (Faz 1)

- Anahtarlar `.env`'de, `.gitignore` kapsamında; koda yazılmaz.
- LLM'e shell/dosya aracı **yoktur** (kasıtlı) — yalnız okuma araçları.
- Kamera yalnız kullanıcı eylemiyle açılır; LIVE göstergesi; gerekirse
  `JARVIS_CAMERA_DISABLED=1` ile komple kapalı.
- Audit log: her komut/olay SQLite'a yazılır.
- Varsayılan `127.0.0.1`; dış erişim Faz 2'de TLS + cihaz anahtarıyla.

## Varsayımlar

1. LLM: **Groq** (`openai/gpt-oss-20b`) — kök `.env` anahtarı otomatik.
   `JARVIS_LLM_PROVIDER` ile değiştirilebilir (openai/anthropic/ollama/mock).
2. OWM anahtarı placeholder → Weather kartı bilgilendirme gösterir.
3. Faz 1 yalnız localhost: kimlik doğrulama bilinçli olarak kapsam dışı.
4. LLM'e son 24 mesaj gönderilir (bağlam sınırı).
5. PWA manifest hazır; service worker + kurulum akışı Faz 2'de.

## Sonraki Fazlar

- **Faz 2**: QR eşleştirme, relay sunucusu, TLS, PWA, Wake-on-LAN
- **Faz 3**: Wake word + çift alkış, STT/TTS, sesli mod arayüzü
- **Faz 4**: Sunucu tarafı hatırlatıcı zamanlayıcı + tekrarlı alarm
- **Faz 5-7**: Mail, AI haberleri, dosya transferi, akıllı ev, WhatsApp

