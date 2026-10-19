# JARVIS Projesi - AI Code Generation Prompts

## 🎯 Genel Kullanım Rehberi
Her prompt kopyalanıp biraz customized hali ile AI'ya yapıştırılabilir. Kendi projene göre detayları güncellemekten çekinme!

---

## 1️⃣ AUTHENTICATION & USER MANAGEMENT

### Prompt 1.1: JWT Authentication Sistemi

````text
Görev: JARVIS projesi için JWT token tabanlı authentication sistemi kur.

Teknoloji Stack:
- Backend: FastAPI (Python)
- Veritabanı: MongoDB
- Auth: JWT (Access Token: 15 dk, Refresh Token: 7 gün)
- Password: bcrypt (salt rounds: 12)

Gereksinimler:
1. User registration endpoint:
   - Input: isim, soyisim, doğum tarihi, şifre, güvenlik sorusu (user-defined)
   - Output: JWT tokens + user_id

2. User login endpoint:
   - Input: isim, soyisim, şifre
   - Output: JWT tokens

3. Password reset endpoint:
   - Verification: isim, soyisim, doğum tarihi + güvenlik sorusu
   - Output: yeni şifre belirleme

4. Token refresh endpoint:
   - Input: refresh_token
   - Output: yeni access_token

5. Middleware: Her protected endpoint'e JWT doğrulama ekle

6. Rate Limiting: Login denemelerine 5 hatalı girişte 15 dakika engelle

Sonuç: Complete FastAPI authentication modülü (auth.py), User model (models.py) ve database schema
````

### Prompt 1.2: Misafir Modu (Guest Mode)

````text
Görev: JARVIS'te misafir girişi özelliği ekle.

Kısıtlamalar:
- Sohbet kaydedilmeyecek (no database logging)
- Telefon kontrol ve dosya transferi devre dışı
- Sayfa yenilendiğinde sohbet sıfırlanacak
- Sadece AI sohbet erişimi

Teknik Detaylar:
- Guest token: Imzasız JWT veya temporary session ID
- Frontend: Guest modunda belirli butonlar gri/devre dışı göster
- Backend: Guest request'lerde database write işlemleri kontrol et

Sonuç: Guest mode auth flow, frontend components ve API guards
````

---

## 2️⃣ QR CODE & DEVICE PAIRING

### Prompt 2.1: QR Kod Üretimi ve Cihaz Eşleştirmesi

````text
Görev: JARVIS için QR kod tabanlı cihaz eşleştirme sistemi yap.

Sistem Akışı:
1. Backend: pairingToken (6 karakterli, tek kullanımlık, 5 dakika ömürlü) + deviceId içeren QR üret
2. PC: WebSocket dinlemeye geç
3. Telefon: QR kodu tarat, pairingToken + telefon device ID'sini sunucuya POST et
4. Backend: MongoDB'de cihazları birbirine linekle
5. WebSocket: Eşleşme tamamlanınca PC'ye event gönder

Güvenlik:
- pairingToken JWT signed olmalı
- Expiration check
- deviceId validation
- CORS + HTTPS only

Fallback Plan:
- QR altında 6 haneli PIN girme seçeneği

Tech Stack:
- QR Kütüphanesi: python-qrcode veya qrcode.js
- WebSocket: python-websockets
- Token: PyJWT

Sonuç: FastAPI endpoints (/pairing/generate, /pairing/confirm), WebSocket handler ve QR generator
````

### Prompt 2.2: Manuel PIN Fallback

````text
Görev: QR kod hatasında PIN fallback sistemi ekle.

Özellik:
- QR'ın altında "PIN ile eşleştir" butonu
- 6 haneli rastgele PIN generasyonu (sunucu tarafından)
- PIN'i girenin deviceId'sini doğrula
- 3 hatalı denemede 5 dakika kilit

Endpoint:
POST /pairing/pin-generate
POST /pairing/pin-confirm

Sonuç: PIN authentication API, rate limiting ve security validations
````

---

## 3️⃣ CHAT & CONVERSATION MANAGEMENT

### Prompt 3.1: Hesaba Özel Sohbet Geçmişi

````text
Görev: MongoDB'de kullanıcı sohbet geçmişi sistemi kur.

Database Schema:
```
Conversation {
  _id: ObjectId
  user_id: string (JWT claim)
  created_at: timestamp
  updated_at: timestamp
  messages: [
    {
      id: string
      role: "user" | "assistant"
      content: string
      timestamp: timestamp
    }
  ]
  archived: boolean
}
```

Özellikler:
1. Her yeni sayfa açılışında yeni Conversation oluştur
2. Old conversations sol panelde arşivleme olarak göster
3. Conversation restore edebilme
4. Conversation delete
5. Full-text search geçmiş sohbetlerde

API Endpoints:
- GET /conversations (list all)
- GET /conversations/:id (get single)
- POST /conversations (create)
- PUT /conversations/:id/messages (add message)
- POST /conversations/:id/archive
- DELETE /conversations/:id

Frontend: Conversation list panel, pagination, search

Sonuç: MongoDB models, CRUD operations ve API endpoints
````

### Prompt 3.2: Dinamik Konuşma Modları

````text
Görev: JARVIS AI'ın 3 konuşma modunu implement et.

Modlar:
1. Resmi Mod (Formal): Holding toplantısı stili, profesyonel
2. Arkadaş Modu (Casual): Samimi, şaka, espri anlayışlı
3. Duruma Göre (Adaptive): 
   - Araştırma/info sunma → resmi
   - Kullanıcı şaka/yorum → samimi
   - Soru sorulunca → resmi döner

Implementasyon:
- Database'de user_settings'te mode kaydet
- System prompt'ta dinamik instruction ekle
- Frontend: Settings'te mode selector radio button

System Prompt Örneği:
```
Formal: "You are JARVIS, a professional AI assistant..."
Casual: "Hey! I'm JARVIS, your friendly AI buddy..."
Adaptive: "I'm JARVIS. I adapt my tone based on context..."
```

Sonuç: Mode selector component, system prompt builder, user preferences update
````

---

## 4️⃣ LOCALIZATION (ÇOKLU DİL)

### Prompt 4.1: Türkçe/İngilizce Localization

````text
Görev: JARVIS'e i18n (internationalization) ekle.

Kütüphane: i18next (React) veya lingui

Dosya Yapısı:
```
src/locales/
  ├── en.json
  ├── tr.json
```

JSON Yapısı (tr.json):
```json
{
  "auth": {
    "login": "Giriş Yap",
    "register": "Kaydol",
    "forgot_password": "Şifremi Unuttum"
  },
  "device_pairing": {
    "title": "Cihazını Eşleştir",
    "scan_qr": "QR Kodu Tarat"
  }
}
```

Frontend Implementation:
```javascript
import { useTranslation } from 'react-i18next';

function LoginPage() {
  const { t, i18n } = useTranslation();
  
  return (
    <button onClick={() => i18n.changeLanguage('tr')}>
      {t('auth.login')}
    </button>
  );
}
```

Backend: Sistem mesajları da JSON'dan çek (hata mesajları, bildirimler)

Sonuç: i18n config, tüm UI strings i18n wrapper'da, language switcher component
````

---

## 5️⃣ USER PREFERENCES & THEMES

### Prompt 5.1: Tema Sistemi (Bordo Dahil)

````text
Görev: Dinamik tema sistemi kur - user-specific, database'de kayıtlı.

Temalar:
1. Light (Açık)
2. Dark (Koyu)
3. Maroon (Bordo) - DEFAULT
4. Custom (Kullanıcı kendi oluştursun)

Database:
```
UserPreferences {
  user_id: string
  theme: "light" | "dark" | "maroon" | "custom"
  custom_palette: {
    primary: "#8B0000",
    secondary: "#D3D3D3",
    background: "#F5F5DC"
  }
  language: "tr" | "en"
  chat_panel_position: "right" | "center"
}
```

CSS Implementation (CSS Variables):
```css
:root {
  --primary: #8B0000;     /* Maroon */
  --bg: #FAFAFA;
  --text: #333;
}

[data-theme="dark"] {
  --primary: #C41E3A;
  --bg: #1a1a1a;
  --text: #fff;
}
```

Frontend:
- Settings'te theme selector
- localStorage + database'de sync
- Smooth transition

Sonuç: CSS themes, theme switcher component, user preferences API
````

### Prompt 5.2: Sohbet Paneli Konumlandırması

````text
Görev: Sohbet panelinin konumunu değiştirilebilir yap.

Özellik:
- Default: Sağ taraf
- Alternatif: Orta kısım
- User preference'da kayıt

Database:
UserPreferences.chat_panel_position = "right" | "center"

Frontend Layout:
- Sağ: Layout = [left sidebar] [main content] [chat panel-right]
- Orta: Layout = [left sidebar] [main content] [chat panel-center floating]

CSS: Responsive, responsive breakpoints'te panel collapse

Sonuç: Layout component, position toggle, responsive CSS
````

---

## 6️⃣ VOICE CONTROL & SCREEN ANALYSIS

### Prompt 6.1: Sesli Komut (Voice Control)

````text
Görev: Whisper API + Web Speech API ile sesli komut al ve execute et.

Teknoloji:
- STT (Speech-to-Text): OpenAI Whisper API veya Web Speech API
- Wakeword Detection: "Jarvis" tetikleme
- TTS (Text-to-Speech): Web Audio API veya Elevenlabs

Frontend Flow:
1. Mikrofon başlat
2. "Jarvis" kelimeleri algılandıktan sonra dinlemeye devam et
3. Sesli input Whisper API'ye gönder
4. Komut metne çevrildi
5. Backend'e gönder ve execute et
6. Sonuç TTS ile seslendir

Örnekler:
- "Jarvis Chrome aç" → subprocess.Popen('chrome')
- "Jarvis dosyalar göster" → file_explorer_window_open()
- "Jarvis ekranımı analiz et" → screenshot + vision_api

API Endpoint:
POST /voice/process
{
  "audio_file": base64,
  "command": "string"
}

Sonuç: Voice handler component, Whisper integration, command executor backend
````

### Prompt 6.2: Ekran Analizi & Computer Vision

````text
Görev: Screenshot alıp Vision API ile analiz et ve otonom işlem yap.

Teknoloji:
- Screenshot: python-mss veya PIL
- Vision: OpenAI Vision API veya Claude Vision
- OCR: EasyOCR veya pytesseract
- Automation: pyautogui

Senaryo:
"Jarvis ekrandaki kodları analiz et, aşağı kaydır ve hataları düzelt"

Backend Flow:
1. Screenshot al
2. Vision API'ye gönder: "Bu koddaki hatalar neler?"
3. AI response'u parse et
4. pyautogui ile otomatik düzeltme (scroll, mouse, keyboard)
5. Sonuç göster

Endpoint:
POST /vision/analyze-screen
{
  "command": "string",
  "action_type": "code_fix" | "video_edit" | "ui_interact"
}

Response:
{
  "analysis": "string",
  "actions_performed": ["scroll", "fix_line_3"],
  "screenshot_after": base64
}

Sonuç: Screenshot module, Vision API wrapper, automation executor
````

---

## 7️⃣ GEOLOCATION & WEATHER

### Prompt 7.1: Otomatik Konum & Hava Durumu

````text
Görev: Tarayıcı Geolocation + OpenWeatherMap ile konumu ve hava durumunu otomatik çek.

Frontend:
```javascript
navigator.geolocation.getCurrentPosition(
  (position) => {
    const { latitude, longitude } = position.coords;
    // Backend'e gönder
    fetch('/api/weather/get-by-coords', {
      method: 'POST',
      body: JSON.stringify({ lat: latitude, lng: longitude })
    });
  },
  (error) => {
    // Fallback: IP-based geolocation (ipapi.co)
    fetch('https://ipapi.co/json/')
      .then(res => res.json())
      .then(data => {
        // IP'den konum al
      });
  }
);
```

Backend (FastAPI):
```python
from openweathermap_api import OpenWeatherMap

@app.post("/weather/get-by-coords")
async def get_weather(lat: float, lng: float):
    # Reverse Geocoding: koordinatlardan şehir adı çıkar
    city = reverse_geocode(lat, lng)
    
    # OpenWeatherMap API
    weather = openweather.get_current(city)
    
    return {
        "city": city,
        "temp": weather['main']['temp'],
        "condition": weather['weather'][0]['main'],
        "humidity": weather['main']['humidity']
    }
```

User Permission:
- İlk kez "İzin ver" veya "Reddet" seç
- localStorage'da kayıt et

Fallback:
- İzin reddedilirse son kayıtlı şehir göster
- Varsayılan: İstanbul

Sonuç: Geolocation handler, Weather API wrapper, UI component
````

---

## 8️⃣ DEVICE DETECTION & SYSTEM STATUS

### Prompt 8.1: Cihaz Algılama Paneli

````text
Görev: User-Agent'tan cihaz türünü (Mobile/Tablet/Desktop) ve OS/tarayıcısını tespit et.

Backend (FastAPI):
```python
from user_agents import parse

@app.get("/system-status")
async def system_status(request: Request):
    user_agent_string = request.headers.get('user-agent')
    user_agent = parse(user_agent_string)
    
    return {
        "device_type": "mobile" if user_agent.is_mobile else 
                       "tablet" if user_agent.is_tablet else "desktop",
        "os": user_agent.os.family,
        "os_version": user_agent.os.version_string,
        "browser": user_agent.browser.family,
        "browser_version": user_agent.browser.version_string
    }
```

Frontend Panel:
```
System Status
├── Device: iPhone 14 Pro
├── OS: iOS 16.3
├── Browser: Safari
└── Connection: 5G / WiFi
```

Real-time Update:
- Her request'te system status update et
- WebSocket ile live gösterimi (optional)

Sonuç: Device detection middleware, System Status component
````

---

## 9️⃣ SECURITY & 2FA

### Prompt 9.1: 2-Factor Authentication (Biometric + SMS)

````text
Görev: Kritik komutlarda (dosya sil, PC kapat, tüm pencere kapat) 2FA ekle.

Kritik Komutlar:
- DELETE /files/* (dosya silme)
- POST /shutdown (bilgisayarı kapat)
- POST /close-all-windows
- POST /system/execute-critical

2FA Seçenekleri (Mobil):
1. Face ID / Fingerprint
2. SMS OTP (6 haneli)

Flow:
1. Telefon: Kritik komutu gönder
2. Backend: 2FA challenge generate et
   - SMS OTP veya
   - Push notification (Biometric onay)
3. Telefon: User onaylasın
4. Backend: Token verify et
5. PC: Komutu execute et

Endpoint:
```
POST /critical/prepare-command
{
  "command": "delete_file",
  "target": "/path/to/file"
}
Response: { "challenge_id": "...", "2fa_method": "biometric" }

POST /critical/confirm-2fa
{
  "challenge_id": "...",
  "biometric_token": "..." // veya "otp": "123456"
}
```

Settings:
- User isterse 2FA'yı disable edebilsin
- Fallback method seçimi

Sonuç: 2FA verification logic, SMS OTP sender, biometric handler
````

---

## 🔟 FILE TRANSFER & MANAGEMENT

### Prompt 10.1: Dosya Transferi (Boyut ve Türü Kontrol)

````text
Görev: Telefon ↔ PC dosya transferi sistemi kur.

Sınırlamalar:
- Max dosya boyutu: 50MB
- Yasak uzantılar: .exe, .dll, .bat, .cmd, .msi, .vbs
- İzin verilen: .pdf, .doc, .jpg, .png, .zip, .txt, .mp3, .mp4

Frontend (Telefon):
- File picker açıp dosya seç
- Boyut ve tür validation
- Progress bar ile upload

Backend (FastAPI):
```python
ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.jpg', '.png', '.zip', '.txt', '.mp3', '.mp4']
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

@app.post("/files/upload-to-pc")
async def upload_file(file: UploadFile):
    # Türü kontrol et
    if Path(file.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed")
    
    # Boyutu kontrol et
    if file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    
    # PC'ye transfer et
    # WebSocket ile notify et
    
    return {"status": "success"}
```

PC Side:
- WebSocket notification alır
- Dosya Downloads'a kaydedilir
- User notification gösterilir

Sonuç: File upload API, validation middleware, progress tracking
````

---

## 1️⃣1️⃣ PERFORMANCE & SCROLLING

### Prompt 11.1: Scroll Performansı İyileştirmesi

````text
Görev: Chat panel'de scroll takılmalarını kaldır.

Problem:
- Çok mesaj geldiğinde scroll slow olur
- Mouse wheel event'i çok sık trigger

Çözüm:
```javascript
// BEFORE (problematic):
document.addEventListener('scroll', handleScroll);

// AFTER (optimized):
const observer = new MutationObserver(() => {
  // Mesaj DOM'a eklendiğinde trigger
  debounceScroll();
});

const scrollContainer = document.querySelector('.chat-panel');
observer.observe(scrollContainer, { 
  childList: true, 
  subtree: true 
});

// Webkit scroll event
scrollContainer.addEventListener('scroll', handleScroll, { passive: true });

// Debounce
const debounceScroll = debounce(() => {
  updateScrollPosition();
}, 100);  // 100ms debounce
```

Detaylar:
- Passive event listener kullan
- MutationObserver ile DOM change detection
- Debounce interval: 100ms
- Virtual scrolling (çok mesaj varsa)

Sonuç: Optimized scroll handling, MutationObserver, debounce utils
````

---

## 1️⃣2️⃣ ERROR HANDLING & OFFLINE

### Prompt 12.1: Offline Durum ve Retry Mekanizması

````text
Görev: Internet bağlantı kopma ve Render free tier uyku modu için handle et.

Frontend:
```javascript
let isOnline = navigator.onLine;

window.addEventListener('online', () => {
  isOnline = true;
  showNotification('Bağlantı yeniden sağlandı');
  retryFailedRequests();
});

window.addEventListener('offline', () => {
  isOnline = false;
  showNotification('Bağlantınız koptu, mesajlar kuyruğa alındı');
});

// Fetch wrapper with retry
async function fetchWithRetry(url, options, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch(url, options);
      if (response.ok) return response;
    } catch (error) {
      if (i < maxRetries - 1) {
        await sleep(2 ** i * 1000);  // Exponential backoff
      }
    }
  }
  throw new Error('Failed after retries');
}
```

States:
- Loading: "Bağlanılıyor..."
- Failed: "Bağlantı kurulamadı, tekrar deneyin"
- Retrying: "Yeniden deneniyor... (3/3)"
- Success: "Bağlantı sağlandı"

Sonuç: Online/offline handling, retry logic, exponential backoff
````

---

## 1️⃣3️⃣ MONITORING & ERROR TRACKING

### Prompt 13.1: Sentry Entegrasyonu

````text
Görev: Canlı ortamda (Render) hataları track et.

Backend Setup:
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="https://YOUR_DSN@sentry.io/PROJECT_ID",
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
    environment="production"
)
```

Frontend Setup:
```javascript
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: "https://YOUR_DSN@sentry.io/PROJECT_ID",
  environment: "production",
  tracesSampleRate: 0.1
});
```

Captured Errors:
- Backend exceptions
- API errors (500, 503)
- Frontend console errors
- Network failures
- Performance issues

Dashboard:
- Real-time error count
- Affected users
- Stack traces
- Breadcrumbs (events before error)

Sonuç: Sentry config, error middleware, custom event logging
````

---

## 1️⃣4️⃣ WEBSOCKET & REAL-TIME SYNC

### Prompt 14.1: WebSocket ile Gerçek Zamanlı Sinkronizasyon

````text
Görev: Settings değişikliklerini WebSocket ile cihazlar arasında senkronize et.

Teknoloji: FastAPI WebSockets + Socket.IO

Backend:
```python
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}
    
    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
    
    async def broadcast_user(self, user_id: str, message: dict):
        for connection in self.active_connections.get(user_id, []):
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Process ve diğer cihazlara broadcast
            await manager.broadcast_user(user_id, {
                "type": "setting_changed",
                "data": data
            })
    except Exception as e:
        manager.disconnect(user_id, websocket)
```

Frontend:
```javascript
const socket = new WebSocket(`wss://yourapp.com/ws/${userId}`);

socket.onmessage = (event) => {
  const { type, data } = JSON.parse(event.data);
  
  if (type === 'setting_changed') {
    // Ayarları güncelle
    updateUserPreferences(data);
  }
};
```

Sync Events:
- Theme değişikliği
- Language değişikliği
- Chat panel position
- Custom preferences

Sonuç: WebSocket handler, Connection manager, real-time sync logic
````

---

## 1️⃣5️⃣ API RATE LIMITING & CORS

### Prompt 15.1: Rate Limiting ve CORS

````text
Görev: Backend'e rate limiting ve CORS güvenliği ekle.

FastAPI Implementation:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.middleware.cors import CORSMiddleware

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# CORS Whitelist
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yourapp.com",
        "https://www.yourapp.com",
        "http://localhost:3000"  # development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Rate Limiting Rules
@app.post("/auth/login")
@limiter.limit("5/15 minutes")
async def login(request: Request, credentials: LoginRequest):
    # 15 dakikada 5 deneme
    pass

@app.get("/api/data")
@limiter.limit("100/minute")
async def get_data(request: Request):
    # Dakikada 100 request
    pass
```

Exception Handling:
```python
from slowapi.errors import RateLimitExceeded

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Çok fazla istek, lütfen bekleyin."}
    )
```

Sonuç: Rate limiting middleware, CORS configuration, custom error handlers
````

---

## 🎯 ÖRNEK PROMPT: Komple Feature

````text
Görev: JARVIS'e QR kod ile cihaz eşleştirme özelliğini entegre et.

Teknoloji Stack:
- Frontend: React + TypeScript
- Backend: FastAPI + Python
- Veritabanı: MongoDB
- Real-time: WebSocket
- QR: python-qrcode + qrcode.js

Özellikler:
1. PC'den "Cihaz Eşleştir" kliklenirse:
   - Backend: 6 karakterli alphanumeric pairingToken generate
   - Backend: deviceId + pairingToken + user_id encode edip QR oluştur
   - QR'ı API'den JSON response olarak dön (SVG string)
   - Frontend: QR göster ve WebSocket dinlemeye geç

2. Telefondaki QR taratıcı:
   - QR parse et (deviceId + pairingToken)
   - POST /pairing/confirm gönder:
     {
       "pairing_token": "abc123",
       "device_id": "phone-uuid",
       "device_name": "Mehmet's iPhone"
     }

3. Backend verifies:
   - pairingToken JWT'nin signature kontrol et
   - Expiration check (5 dakika)
   - deviceId validate
   - MongoDB'de cihazları link:
     User.devices = [
       { device_id: "pc-123", device_name: "Gaming PC", paired_at: ... },
       { device_id: "phone-456", device_name: "iPhone", paired_at: ... }
     ]

4. WebSocket:
   - PC'ye eşleşme başarılı event gönder
   - Frontend: Modal kapat, success message göster

Fallback:
- QR altında "PIN ile eşleştir" butonu
- 6 haneli PIN'i gir ve "Eşleştir" tıkla
- Backend: /pairing/pin-confirm endpoint

Error Cases:
- Token expired
- Invalid signature
- Device already paired
- Network timeout

Deliverables:
1. FastAPI endpoints (/pairing/generate, /pairing/confirm, /pairing/pin-confirm)
2. WebSocket handler
3. MongoDB schema update
4. React components (QRScanner, DevicePairingModal, ManualPINForm)
5. Error handling ve validation

Kod kalitesi:
- Type hints kullan (Python)
- Error messages kullanıcı-dostu olsun
- Logging ekle (debug/info/error)
- Security best practices (CORS, HTTPS, token expiry)
````

---

## 📋 PROMPT YAZARKEN İPUÇLARI

✅ **Yapılması Gerekenler:**
1. **Teknoloji Stack'i açıkça söyle** (Python, FastAPI, React, vb.)
2. **API endpoints'i define et** (URL, method, input/output)
3. **Database schema yaz** (structure, relationships)
4. **Flow'u step-by-step anlatır** (1. kullanıcı tıklar, 2. backend işler, vb.)
5. **Örnek kod veya JSON** verini ekle (input/output)
6. **Error cases'i belirt** (ne olur hata oluşursa?)
7. **Deliverables'ı list et** (hangi dosyalar yazılmalı?)

❌ **Yapılmaması Gerekenler:**
- Vague istekler: "Bana authentication yap" (too generic)
- Teknoloji belirtmeden: Stack'i söylemeden isteme
- Tüm feature'ı aynı promptta: Böl, modüler yap
- Güvenlik detaylarını unutma: Token expiry, validation, vb.

---

## 🚀 KULLANMA SIRALAMASI

1. **Auth & User Management** (1.1, 1.2)
2. **Database & Models** (3.1 - Conversation)
3. **QR & Device Pairing** (2.1, 2.2)
4. **Localization** (4.1)
5. **Themes & Preferences** (5.1, 5.2)
6. **Chat Features** (3.2 - Modes, Real-time)
7. **Voice & Vision** (6.1, 6.2)
8. **Geolocation & Weather** (7.1)
9. **Security** (9.1, 15.1)
10. **Performance & Monitoring** (11.1, 13.1)

Her prompt'u kopyala, kendi projene uyarla ve AI'ya gönder! 🎯