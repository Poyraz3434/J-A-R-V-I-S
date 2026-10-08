# Changelog

## [10.0.0] — 2026-10-08

v10.0 "Apex": ATLAS alt sistemine arıza giderme akışı, 4 kademeli akıllı arama, 2026 arayüz estetiği ve 7 yeni yetenek.

### Eklenen

- **Özellik 1 — Otomatik Sunum:** Konu/slayt sayısı/ton bilgisiyle .pptx üretimi (`presentation_builder.py`); zincir: python-pptx → Canva API → PNG slayt seti. İçerik taşması otomatik slayt bölme.
- **Özellik 2 — Tam macOS Desteği:** `platform_service.py` soyutlaması (`WindowsPlatformService` / `MacPlatformService`), macOS Accessibility + Ekran Kaydı izin rehberi, LaunchAgent otomatik başlatma. Tek codebase, tek ürün; dağıtım derlemeleri platform başına ayrı ama bu "ayrı sürüm" değildir.
- **Özellik 3 — ATLAS Arıza Giderme:** `troubleshoot_flow.py` state machine (bekleme → araştırma → uygulama → test → kullanıcı onayı → kapanış/döngü). "+" menüsünden Windows/macOS alt seçimi; çözümler web'den araştırılır (Flash/Pro seçilebilir), bilinen adımlar otomatik uygulanır, "denenenler" listesiyle tekrar yok; tehlikeli işlemler için ek onay; alternatif tükenince manuel öneriler + kaynak linkleri.
- **Özellik 4 — Niyet Algılama + Ayarlar:** `intent_detection.py` (kural tabanlı Türkçe sınıflandırıcı: eylem talebi ↔ bilgi sorusu); "+" menüsünde en üstte ATLAS; ⚙ ayarlar menüsüne "ATLAS'ı Otomatik Aç" toggle'ı — `device_prefs.py` ile IP + makine kimliği bazlı kalıcı saklama.
- **Özellik 5 — Dosya Dönüştürücü:** `file_converter.py`: JPG/PNG→PDF, PDF→JPG/PNG (sayfa sırası korunur), PDF→TXT (image-only PDF'de OCR tespiti), JPG↔PNG. Doğal dille hedef format algılama; desteklenmeyen formatlarda açık yönlendirme.
- **Özellik 6 — Karşılıklı Dışlayıcı Pencereler:** `window_manager.py` — ATLAS açıkken JARVIS gizlenir, ATLAS kapanınca (✕ butonu, "Bitir", çözüldü akışı) JARVIS döner. Tepsi/uyandırma ile JARVIS'i açma girişimi ATLAS aktifken engellenir. Konuşma geçmişi geçişlerde korunur.
- **Özellik 7 — 2026 Arayüz Estetiği:** `status_border.py` (`StatusBorderWidget` + `StatusColorController`): üst durum çubuğu kaldırıldı, yerine tüm kenarı saran ince çerçeve — kırmızı (hata), mavi (çalışma), yeşil (yanıt sonrası tam 12 sn; yeni mesajla anında iptal), idle nefes animasyonu. Tüm geçişler yumuşak interpolasyon. Tüm köşeler ovalleştirildi (butonlar/kartlar/paneller/ATLAS overlay).
- **Özellik 8 — Müfredat + 3 sn Doğrulama:** `data/curriculum.json` (1-12. sınıf, güncellenebilir veri katmanı) + `curriculum.py`; eğitim sorularında 3 saniyelik kendini doğrulama adımı, sınıf seviyesine uygun cevap dili, `✅ Doğrulama` güven raporu.
- **Özellik 9 — Prompt Mimarı:** `prompt_architect.py` — 8 maddelik kalite checklist'i (rol, görev, kısıtlar, varsayımlar, kenar durumlar, çıktı formatı, örnek, doğrulama) ile üretilen prompt'ların self-check'i.
- **Özellik 10 — 4 Kademeli Arama:** `research_engine.py` — Flash Lite (≤5 sn / ~1 sayfa), Flash (~10 sn / ~1,5), Pro (≤40 sn / 2-3 sayfa + kaynak güvenilirlik analizi), Deep Research (10-15 dk / ≤20 sayfa, yuvarlak mm:ss geri sayım `research_ui.py`). Kullanıcı uzunluk isteyince mod varsayılanı geçersizleşir. Güvensiz kaynaklar rapora girmez; yalnızca güvenilir kaynak yoksa "Filtreler" bölümünde Evet/Hayır etiketleriyle sunulur (⚙ ayarından kapatılabilir).

### Altyapı & Dağıtım

- **Paketleme:** `jarvis.spec` (onedir + windowed, `data/curriculum.json` gömülü, playwright hariç ~40 MB tasarruf), `build_installer.py` tek komutlu derleme hattı (sürüm senkronu + PyInstaller + Inno Setup), `installer.iss` (Türkçe kurulum sihirbazı, sihirbaz görselleri), `JARVIS.ico/.icns` + `generate_icon.py`.
- **Sürüm tek kaynak:** `config.APP_VERSION` — pencere başlığı, sistem promptu, kurucu adı tek yerden.
- **Otomatik güncelleme denetimi:** açılıştan ~6 sn sonra arka plan QThread'inde sessiz kontrol (`services/update_check.py`); tercihler cihaz bazlı kalıcı; JARVIS asla kendini indirmez/kurmaz (opt-in).
- **Frozen mod .env:** paketlenmiş EXE `.env`'i EXE yanından okur; anahtarlar bundle'a gömülmez.
- **Lint kapısı:** `ruff.toml` (E9, F821, F811, F841, B023, B033) + F401 temizliği; `requirements.txt`'e `ruff` dev bağımlılığı.
- **Testler:** 242 birim testi (12 dosya), offscreen/gerçek ekran duman testleri, EXE canlı testi, sessiz kurulum/kaldırma uçtan uca testi, gerçek HTTPS güncelleme akışı testi. `JARVIS.exe --self-test` ile frozen doğrulama.

### Düzeltilen

- `automation_engine.py`: `logger` tanımsızdı — WebDriver kapatma ve YouTube oynatma doğrulama bloklarında hata anında except içinde `NameError` üretiliyordu (özellik sessizce çöküyordu). `logger_setup` import'u eklendi.
- `automation_engine.py`: döngü içi lambda'da B023 (geç bağlama) default-arg bağlamasıyla giderildi.
- `services/agent_core.py`, `overlay_ui.py`, `troubleshoot_flow.py`, `intent_detection.py`: ölü kod / kullanılmayan değişkenler temizlendi.
- Sürüm tutarsızlığı: UI'daki sabit "v9.0" etiketleri tek kaynağa (`APP_DISPLAY_VERSION`) bağlandı.

### Notlar

- 1 sayfa ≈ 500 kelime kabul edildi (spec'te netleştirilmemişti).
- OCR için sistem `tesseract` binary'si gerekir; yoksa kullanıcıya "OCR gerekli" bildirilir.
- macOS derlemesi ve izin rehberi manuel testi bir Mac gerektirir (tek makine-dışı kalan iş).
