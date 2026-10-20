/**
 * i18n (madde 3) — Türkçe/İngilizce kullanıcıya görünür metinler.
 *
 * Kullanım: `import { t, setLang, getLang } from "../i18n"` → t("auth.login").
 * Dil tercihi localStorage'da önbelleklenir; oturum açıldığında DB'deki
 * user_settings.language ile senkronlanır (useJarvis bunu yapar).
 * Eksik anahtar durumunda: önce İngilizce fallback, sonra anahtarın kendisi
 * döner — böylece arayüz asla boş metin göstermez.
 */

export type Lang = "tr" | "en";

const STORAGE_KEY = "jarvis.lang";

type Dict = Record<string, string>;

const tr: Dict = {
  // Genel
  "app.title": "J.A.R.V.I.S",
  "common.save": "Kaydet",
  "common.saving": "Kaydediliyor...",
  "common.cancel": "İptal",
  "common.close": "Kapat",
  "common.refresh": "Yenile",
  "common.delete": "Sil",
  "common.online": "Çevrimiçi",
  "common.offline": "Çevrimdışı",
  "common.error": "Hata",
  "common.retry": "Tekrar dene",
  "common.loading": "Yükleniyor...",

  // TopBar
  "topbar.settings": "Ayarlar",
  "topbar.system_cards": "Sistem kartları",
  "topbar.online": "ONLINE",
  "topbar.offline": "OFFLINE",

  // Sohbet paneli
  "chat.title": "Conversation",
  "chat.clear": "Temizle",
  "chat.confirm_clear": "Emin misiniz?",
  "chat.export": "Dışa aktar",
  "chat.empty": "Konuşma boş. Bir şeyler yazın...",
  "chat.placeholder": "Jarvis'e yazın...",
  "chat.placeholder_offline": "Çevrimdışı — bağlantı bekleniyor",
  "chat.offline_note":
    "Bağlantı koptu — mesajlar kaydedilemiyor. Bağlantı gelince tekrar deneyin.",
  "chat.send": "Gönder",
  "chat.unknown_error": "Bilinmeyen hata",
  "alarm.mute": "Sustur",
  "alarm.more": "alarm daha",

  // Ayarlar
  "settings.title": "Ayarlar",
  "settings.language": "Dil",
  "settings.language_tr": "Türkçe",
  "settings.language_en": "English",
  "settings.theme": "Tema",
  "settings.chat_position": "Sohbet paneli konumu",
  "settings.chat_position_right": "Sağ",
  "settings.chat_position_center": "Orta",
  "settings.city": "Şehir",
  "settings.connection": "Bağlantı",
  "settings.llm_provider": "LLM Sağlayıcısı",
  "settings.microphone": "Mikrofon",
  "settings.save_failed": "Kaydedilemedi",
  "settings.wake_phrases": "Uyandırma İfadeleri (her satıra bir tane)",
  "settings.exit_phrases": "Sesli Mod Çıkış İfadeleri (virgülle)",
  "settings.clap": "Çift Alkış ile Uyandırma",
  "settings.clap_sensitivity": "Alkış Hassasiyeti",
  "settings.less_sensitive": "Daha az duyarlı",
  "settings.more_sensitive": "Daha duyarlı",
  "integrations.ready": "Hazır",
  "integrations.off": "Kapalı",
  "integrations.whatsapp": "WhatsApp",
  "integrations.mail": "E-posta",
  "integrations.home_assistant": "Home Assistant",
  "integrations.relay": "Relay",

  // Tema renkleri
  "theme.red": "Kırmızı",
  "theme.green": "Yeşil",
  "theme.blue": "Mavi",
  "theme.maroon": "Bordo",

  // Eşleştirme
  "pair.title": "Cihazlar",
  "pair.none": "Eşleşmiş cihaz yok. QR üreterek telefonu tanıt.",
  "pair.scan_hint": "Telefonun kamerasıyla okut",
  "pair.scan_hint_secs": "sn",
  "pair.browser_hint": "veya tarayıcıda aç:",
  "pair.start": "QR ile cihaz eşleştir",
  "pair.renew": "QR'ı yenile",
  "pair.remove_device": "Cihazı kaldır",
  "pair.start_failed": "Eşleştirme başlatılamadı",
  "pair.remove_failed": "Cihaz kaldırılamadı",
  "pair.last_seen": "son görülme",
  "pair.device": "cihaz",
};

const en: Dict = {
  "app.title": "J.A.R.V.I.S",
  "common.save": "Save",
  "common.saving": "Saving...",
  "common.cancel": "Cancel",
  "common.close": "Close",
  "common.refresh": "Refresh",
  "common.delete": "Delete",
  "common.online": "Online",
  "common.offline": "Offline",
  "common.error": "Error",
  "common.retry": "Retry",
  "common.loading": "Loading...",

  "topbar.settings": "Settings",
  "topbar.system_cards": "System cards",
  "topbar.online": "ONLINE",
  "topbar.offline": "OFFLINE",

  "chat.title": "Conversation",
  "chat.clear": "Clear",
  "chat.confirm_clear": "Are you sure?",
  "chat.export": "Export",
  "chat.empty": "No messages yet. Say something...",
  "chat.placeholder": "Type to Jarvis...",
  "chat.placeholder_offline": "Offline — waiting for connection",
  "chat.offline_note":
    "Connection lost — messages cannot be saved right now. Try again once you're back online.",
  "chat.send": "Send",
  "chat.unknown_error": "Unknown error",
  "alarm.mute": "Mute",
  "alarm.more": "more alarm(s)",

  "settings.title": "Settings",
  "settings.language": "Language",
  "settings.language_tr": "Türkçe",
  "settings.language_en": "English",
  "settings.theme": "Theme",
  "settings.chat_position": "Chat panel position",
  "settings.chat_position_right": "Right",
  "settings.chat_position_center": "Center",
  "settings.city": "City",
  "settings.connection": "Connection",
  "settings.llm_provider": "LLM Provider",
  "settings.microphone": "Microphone",
  "settings.save_failed": "Could not save",
  "settings.wake_phrases": "Wake phrases (one per line)",
  "settings.exit_phrases": "Voice mode exit phrases (comma-separated)",
  "settings.clap": "Wake on double clap",
  "settings.clap_sensitivity": "Clap sensitivity",
  "settings.less_sensitive": "Less sensitive",
  "settings.more_sensitive": "More sensitive",
  "integrations.ready": "Ready",
  "integrations.off": "Off",
  "integrations.whatsapp": "WhatsApp",
  "integrations.mail": "E-mail",
  "integrations.home_assistant": "Home Assistant",
  "integrations.relay": "Relay",

  "theme.red": "Red",
  "theme.green": "Green",
  "theme.blue": "Blue",
  "theme.maroon": "Maroon",

  "pair.title": "Devices",
  "pair.none": "No paired devices. Generate a QR code to pair your phone.",
  "pair.scan_hint": "Scan with your phone camera",
  "pair.scan_hint_secs": "s",
  "pair.browser_hint": "or open in browser:",
  "pair.start": "Pair device via QR",
  "pair.renew": "Refresh QR",
  "pair.remove_device": "Remove device",
  "pair.start_failed": "Could not start pairing",
  "pair.remove_failed": "Could not remove device",
  "pair.last_seen": "last seen",
  "pair.device": "device",
};

const DICTS: Record<Lang, Dict> = { tr, en };

let currentLang: Lang = detectInitialLang();
const missing = new Set<string>();

function detectInitialLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "tr" || stored === "en") return stored;
  } catch {
    /* localStorage yok (gizli mod) — varsayılan tr */
  }
  const nav = typeof navigator !== "undefined" ? navigator.language.toLowerCase() : "tr";
  return nav.startsWith("en") ? "en" : "tr";
}

/** Şu anki dili döndürür. */
export function getLang(): Lang {
  return currentLang;
}

/** Dili değiştirir, kalıcı hale getirir ve değişiklik olayını yayınlar. */
export function setLang(lang: Lang): void {
  currentLang = lang === "en" ? "en" : "tr";
  try {
    localStorage.setItem(STORAGE_KEY, currentLang);
  } catch {
    /* kalıcı saklama yok — yalnızca oturumluk */
  }
  document.documentElement.lang = currentLang;
  window.dispatchEvent(new CustomEvent("jarvis:lang-change"));
}

/** Anahtarı aktif dilde döndürür; eksikse EN fallback, o da yoksa anahtar. */
export function t(key: string): string {
  const value = DICTS[currentLang][key] ?? DICTS.en[key];
  if (value !== undefined) return value;
  // Eksik anahtarı bir kez bildir (Faz 2 i18n testi bunu yakalar).
  if (!missing.has(key)) {
    missing.add(key);
    console.warn(`[i18n] Eksik çeviri anahtarı: "${key}"`);
  }
  return key;
}

/** i18n test yardımcısı — oturum boyunca eksik kalan anahtarlar. */
export function missingKeys(): string[] {
  return [...missing];
}

