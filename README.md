# J.A.R.V.I.S. v10.0

Python + PySide6 ile yazılmış, masaüstünde çalışan yapay zekâ asistanı.
**Tek codebase** ile hem Windows hem macOS'ta çalışır (ayrı sürüm yok; platform farkı runtime'da soyutlama katmanıyla yönetilir). Bilgisayarı klavye/fare seviyesinde kontrol edebilen **ATLAS** alt sistemine sahiptir.

---

## Öne Çıkan Özellikler

| # | Özellik | Kısa Açıklama |
|---|---|---|
| 1 | **Otomatik Sunum** | Konudan .pptx üretir; mümkün değilse Canva, o da değilse PNG slayt seti (fallback zinciri) |
| 2 | **Tam macOS Desteği** | `PlatformService` soyutlaması: Windows/macOS alt servisleri, izin rehberi, tek codebase |
| 3 | **ATLAS Arıza Giderme** | Sorunu web'de araştırır (Flash/Pro), çözümü otomatik uygular, doğrular; "hayır" deyince sıradakini dener |
| 4 | **Akıllı Niyet Algılama** | Eylem talebi ↔ bilgi sorusu ayrımı; ATLAS'ı otomatik açma ayarı (IP + makine kimliğiyle kalıcı) |
| 5 | **Dosya Dönüştürücü** | JPG/PNG ↔ PDF, PDF → görsel/metin (OCR tespiti ile), doğal dille komut |
| 6 | **Karşılıklı Dışlayıcı Pencereler** | `WindowManager`: ATLAS açıkken JARVIS gizlenir, kapanınca geri döner |
| 7 | **2026 Estetiği** | Oval köşeler + tüm kenarı saran ince durum çerçevesi: kırmızı/mavi/yeşil (12 sn)/idle, yumuşak geçiş |
| 8 | **Müfredat Asistanı** | 1-12. sınıf müfredat referansı (`data/curriculum.json`) + 3 sn doğrulama + seviyeye uygun dil |
| 9 | **Prompt Mimarı** | Başka AI'lara verilecek, 8 maddelik kalite kontrol listesinden geçen detaylı prompt üretimi |
| 10 | **4 Kademeli Arama** | Flash Lite / Flash / Pro / Deep Research; kaynak güvenilirlik analizi, yuvarlak geri sayım |

Ayrıca: sesli komut ("Hey Jarvis" uyandırma), günlük brifing, hava durumu, finans takibi, düşük internet modu, otomatik güncelleme denetimi, sistem tepsisi entegrasyonu.

---

## Kurulum

### a) Kurulum dosyasıyla (Windows — önerilen)
1. `Output\JARVIS-Setup-10.0.0.exe` dosyasını çalıştırın.
2. Kurulum dizinine (EXE'nin yanına) bir `.env` dosyası koyun (aşağıya bakın).
3. Masaüstü kısayolundan başlatın.

### b) Kaynak koddan
```powershell
# Python 3.11+ gerekir
python -m venv .venv
.\.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### c) Paketleme / dağıtım derlemesi
Ayrıntılar için **[BUILD.md](BUILD.md)** dosyasına bakın. Kısa yol:

```powershell
python build_installer.py   # sürüm senkronu + PyInstaller + Inno Setup (tek komut)
```

---

## Yapılandırma (`.env`)

`.env` dosyası proje kökünde (paketlenmiş uygulamada EXE'nin yanında) bulunur. **Asla bundle'a gömülmez** — anahtarlar derleme çıktısına sızmaz.

| Anahtar | Zorunlu? | Açıklama |
|---|---|---|
| `JARVIS_GROQ_API_KEY` veya `GROQ_API_KEY` | ✅ | Ana LLM sağlayıcısı (Groq) |
| `JARVIS_GEMINI_API_KEY` veya `GEMINI_API_KEY` | — | Yedek LLM (Gemini) |
| `JARVIS_GROQ_MODEL` | — | Varsayılan: `openai/gpt-oss-20b` |
| `JARVIS_OWM_API_KEY` | — | Hava durumu (OpenWeatherMap) |
| `JARVIS_SMTP_USER` / `JARVIS_SMTP_PASS` | — | E-posta gönderimi |
| `JARVIS_EPSON_EMAIL` | — | Epson Connect yazdırma adresi |
| `JARVIS_CITY` | — | Varsayılan: `Tuzla,TR` |
| `JARVIS_UPDATE_URL` | — | Otomatik güncelleme denetimi için "latest release" API adresi |
| `JARVIS_VERSION` | — | Sürümü geçersiz kılar (test için) |

Kullanıcı verileri `~/.jarvis/` altında tutulur (loglar, ayarlar, hafıza, kişiler) — izinleri `0600/0700` ile kısıtlanır.

---

## Kullanım (özet)

- **Sohbet:** Metin kutusuna yazın veya mikrofonla konuşun; "Hey Jarvis" uyandırma kelimesi desteklenir.
- **"+" menüsü:** ATLAS, Arıza (Windows/macOS) ve diğer görevler en üsttedir.
- **Ayarlar (⚙, sağ alt):** ATLAS otomatik açma, güncelleme denetimi, arama "Filtre sonucunu göster" vb. tercihler — IP + makine kimliğiyle cihaz bazında kalıcıdır.
- **Arama modları (alt çubuk):** Normal / ⚡ Flash Lite / ⚡ Flash / ⭐ Pro / 🔬 Deep Research. Rapor uzunluğu istenirse (`"3 sayfa istiyorum"`) mod varsayılanı geçersiz kılınır.
- **ATLAS:** Açıkken JARVIS penceresi gizlenir; sorunuzu ATLAS penceresinden de sorabilirsiniz. Arıza akışında tehlikeli işlemler (disk, sistem dosyaları…) için ek onay ister.

---

## Mimari Haritası

| Modül | Sorumluluk |
|---|---|
| `main.py` → `jarvis_v10.py` | Giriş noktası; ana pencere, sohbet akışı, arka plan işçileri (QThread) |
| `window_manager.py` | ATLAS ↔ JARVIS karşılıklı dışlayıcı pencere state machine |
| `status_border.py` | `StatusBorderWidget` + `StatusColorController` (idle/busy/error/success çerçevesi, 12 sn QTimer) |
| `overlay_ui.py` | ATLAS overlay arayüzü (arıza akışı, arama modeli seçici) |
| `intent_detection.py` | Türkçe niyet sınıflandırma (eylem talebi ↔ bilgi sorusu) |
| `device_prefs.py` | IP + makine kimliği bazlı kalıcı tercih deposu |
| `research_engine.py` + `research_ui.py` | 4 kademeli arama motoru, kaynak güvenilirlik analizi, yuvarlak geri sayım |
| `troubleshoot_flow.py` | Arıza giderme state machine (araştır → uygula → test → onay/tükenme) |
| `automation_engine.py` + `atlas_bridge.py` + `screen_watcher.py` | ATLAS'ın klavye/fare/ekran otomasyon altyapısı |
| `presentation_builder.py` | Sunum fallback zinciri (.pptx → Canva → PNG) |
| `file_converter.py` | PDF/JPG/PNG/TXT dönüşümleri (OCR tespiti dahil) |
| `platform_service.py` | Windows/macOS platform soyutlaması + macOS izin rehberi |
| `curriculum.py` + `data/curriculum.json` | 1-12 müfredat veri katmanı + 3 sn doğrulama |
| `prompt_architect.py` | Prompt Mimarı (8 maddelik kalite checklist'i) |
| `config.py` | Tek sürüm kaynağı (`APP_VERSION`), .env yükleme, özel dosya yardımcıları |
| `logger_setup.py` | Merkezi loglama |
| `services/` | `agent_core`, `model_router`, `network`, `update_check`, `troubleshoot_agent`, `permissions`, `packaging_validation`, … |

### Tasarım ilkeleri
- Platforma özgü kod yalnızca `platform_service.py` ve alt servislerinde izole edilir; ana mantık platformdan bağımsız kalır.
- Uzun işler (LLM, arama, sunum, dönüştürme) hep `QThread` işçilerinde çalışır — UI asla bloklanmaz.
- Yıkıcı işlemlerden önce ekstra onay (arıza akışındaki `is_dangerous` deseni).
- Sürüm tek kaynak: `config.APP_VERSION` → pencere başlığı, sistem promptu, kurucu adı otomatik senkron.

---

## Test

```powershell
# Tam birim test paketi (242 test)
.\.venv\Scripts\python.exe -m unittest discover -s tests

# Lint kapısı
.\.venv\Scripts\python.exe -m ruff check .

# Elle çalıştırılan duman / uçtan uca testler
.\.venv\Scripts\python.exe tests\_smoke.py        # offscreen UI duman testi
.\.venv\Scripts\python.exe tests\_smoke_real.py    # gerçek ekran duman testi
.\.venv\Scripts\python.exe tests\_update_e2e.py    # gerçek HTTPS güncelleme akışı
```

Paketlenmiş EXE kendi kendini doğrulayabilir: `JARVIS.exe --self-test` (bkz. `services/packaging_validation.py`).

---

## Dokümantasyon
- **[BUILD.md](BUILD.md)** — paketleme, dağıtım, `.env` yerleşimi, derleme sonrası kontrol listesi
- **[MEGA_PROMPT.md](MEGA_PROMPT.md)** — 10 özelliğin geliştirme prompt'ları (AI'lara verilmek üzere)
- **[CHANGELOG.md](CHANGELOG.md)** — sürüm geçmişi

## Geliştirme Kuralları
1. Her değişiklikten sonra `ruff check .` ve `unittest discover` yeşil olmalı.
2. PEP8, tip belirteçleri, kısa docstring'ler, `try/except` + loglama.
3. Platform farkı `platform_service.py` içinden yönetilir.
4. Yeni özellik, `tests/test_*.py` ile birlikte gelmeli.


