"""Harici entegrasyonlar (Faz 5-7): mail, haberler, dosya, akıllı ev, WhatsApp.

Ortak ilkeler:
- Her entegrasyon `available()` ile yapılandırma kontrolü yapar; anahtar yoksa
  LLM aracı "yapılandırılmadı" yanıtı döndürür, uygulama asla düşmez.
- Ayarlar doğrudan `config.env("JARVIS_...")` üzerinden okunur.
- Salt-okunur olanlar (mail, haber) ağdan veri çeker; yıkıcı işlem yoktur.
"""
