# JARVIS Geliştirme — MEGA PROMPT (Tüm Özellikler Tek Belgede)

> **Durum notu (bu depo için):** Bu belgedeki **10/10 özellik bu kod tabanında
> tamamlanmıştır** (testler: 101/101 passing). Mega prompt; özelliklerin taşınması,
> yeni projede tekrar uygulanması veya referans/arşiv için tek parça halinde
> sunulmuştur.

## Nasıl Kullanılır
1. Bu belgeyi tek seferde bir kod yazan AI'ya (Claude, GPT, ...) ver.
2. İstersen başına kendi proje dosya yapını/kod örneklerini ekle (sonuç ciddi
   şekilde iyileşir).
3. Tek tek özellik bloğu istersen yine ayrı ayrı da kullanılabilir.

---

## 🔧 Ortak Proje Bağlamı (mega promptun gövdesi)

Sen kıdemli bir Python/PySide6 masaüstü uygulama geliştiricisisin.

PROJE: JARVIS — Python ve PySide6 ile yazılmış, masaüstünde çalışan bir yapay zeka asistanı.
- Tek bir uygulama olarak hem Windows hem macOS'ta çalışır. "Jarvis Windows" / "Jarvis macOS" diye ayrı sürümler YOK ve olmayacak; tek codebase, platform farkı runtime'da (platform.system() vb.) tespit edilip soyutlama katmanlarıyla (ör. ayrı windows_utils.py / macos_utils.py modülleri, ortak bir PlatformController arayüzü üzerinden çağrılır) yönetilir.
- JARVIS'in "ATLAS" adında, bilgisayarı klavye/fare seviyesinde kontrol edebilen bir alt sistemi vardır (ekran otomasyonu, sistem arızası giderme vb. için kullanılır).
- Uygulamada bir "+" butonu ve alt menüsü, sağ altta bir ayarlar butonu bulunur.
- Amaç: mevcut çalışan yazılımı BOZMADAN, üzerine yeni özellik eklemek / var olan davranışı iyileştirmek.

ÇALIŞMA KURALLARI:
1. Kod yazmadan önce, sana verdiğim mevcut dosya/kod yapısını incele; yeni kodu projenin var olan mimarisine, isimlendirme ve stil kurallarına uydur.
2. PEP8'e uy, tip belirteçleri (type hints) ve kısa docstring'ler kullan, anlamlı hata yönetimi (try/except + loglama) ekle.
3. Platforma özgü davranışları (dosya sistemi, otomasyon, izinler) ayrı modüllerde izole et; ana mantık platformdan bağımsız kalsın.
4. Var olan bir özelliği kırabilecek bir değişiklik yapman gerekiyorsa, önce bunu açıkça belirt ve geriye dönük uyumlu bir alternatif öner.
5. Eksik/belirsiz bir noktada varsayım yapmak zorundaysan, kodun başında veya cevabının başında bu varsayımı 1-2 cümle ile açıkça yaz.
6. Cevabının sonunda: (a) hangi dosyaları değiştirdiğin/oluşturduğunun kısa listesini, (b) test etmem gereken 3-5 senaryoyu madde madde ver.

Şimdi sana JARVIS için tek bir özellik isteği vereceğim, sadece bu isteğe odaklan.
(Aşağıdaki mega modda: istekleri SIRAYLA, her biri için madde madde uygula.)

---

# 📋 ÖZELLİK LİSTESİ (mega modda sırayla uygula)

## Özellik 1 — Otomatik Sunum Oluşturma
GÖREV: JARVIS'e, kullanıcının verdiği konu/içerikten otomatik sunum (slayt seti) oluşturma özelliği ekle.
ÖNCELİK SIRASI (fallback zinciri — sırayla dene, biri tutmazsa bir sonrakine geç):
1. PowerPoint (.pptx) dosyası üret (ör. python-pptx kütüphanesi ile). Başlık, madde madde içerik, varsa basit görsel/ikon yerleşimi olan düzgün bir tasarım şablonu kullan.
2. .pptx üretimi mümkün değilse (ör. gerekli veri/şablon eksikse), Canva API entegrasyonu üzerinden sunum oluşturmayı dene.
3. İkisi de mümkün değilse, her slayt için ayrı bir GÖRSEL (PNG/JPEG) üret — yani sunumu "slayt görselleri" seti olarak sun.
GEREKSİNİMLER:
- Kullanıcıdan konu, slayt sayısı (belirtmezse mantıklı bir varsayılan, ör. 8-10 slayt) ve varsa ton/hedef kitle bilgisini al.
- Sunumun bir başlık slaydı, içindekiler/özet slaydı ve kapanış slaydı olsun; içerik slaytları madde madde, aşırı kalabalık olmayan (slayt başına ~4-6 madde) şekilde düzenlensin.
- Hangi yöntemin (pptx/Canva/görsel) kullanıldığını kullanıcıya net şekilde belirt.
- Üretilen dosyayı kullanıcının erişebileceği bir konuma kaydet ve JARVIS arayüzünden indirilebilir/açılabilir hale getir.
KENAR DURUMLARI:
- Canva API anahtarı/bağlantısı yoksa, adım 2'yi atlayıp otomatik adım 3'e geç, kullanıcıyı bilgilendir.
- Çok uzun içerik istenirse, tek slayta sığmayan içeriği otomatik olarak birden fazla slayta böl.
ÇIKTI: Yeni/değişen dosyaların listesi + fallback zincirinin nasıl test edileceğine dair senaryolar.

## Özellik 2 — Tam macOS Desteği (Tek Codebase, Tek "JARVIS")
GÖREV: JARVIS'e gerçek, tam kapsamlı macOS desteği ekle. Şu an sadece Windows'ta çalışıyor.
KESİN KURAL: "Jarvis Windows" ve "Jarvis macOS" diye AYRI ürünler/sürümler OLMAYACAK. Tek bir JARVIS uygulaması olacak; kullanıcı deneyimi, özellik seti, arayüz ve marka aynı kalacak. Platform farkı sadece motor kaputun altında, runtime'da tespit edilip yönetilecek.
GEREKSİNİMLER:
1. Mevcut kodda Windows'a özgü (dosya yolları, sistem çağrıları, klavye/fare otomasyonu, bildirimler, otomatik başlatma vb.) tüm noktaları tespit et ve listele.
2. Bunları soyutlayan bir arayüz/temel sınıf tasarla (ör. PlatformService/PlatformController) ve WindowsPlatformService + MacPlatformService olarak ikiye ayır; ana uygulama kodu sadece bu ortak arayüzü çağırsın.
3. macOS tarafında uygun kütüphaneleri kullan (PyObjC / AppleScript köprüsü, pathlib, Accessibility/Erişilebilirlik izinlerinin istenmesi).
4. Paketleme notu: Kaynak kodu tek codebase olsa da, dağıtılabilir uygulama (.app / .exe) her platform için ayrı ayrı derlenir (PyInstaller vb.) — bu normaldir ve "ayrı sürüm" sayılmaz.
5. macOS'a özgü ilk çalıştırmada gerekebilecek izin taleplerini (Accessibility, ekran kaydı) kullanıcıya açıklayan bir yönlendirme ekranı ekle.
ÇIKTI: Platform-bağımlı kod noktalarının envanteri, önerilen soyutlama mimarisi, macOS'ta test senaryoları.

## Özellik 3 — ATLAS ile Yazılımsal Arıza Çözümü
GÖREV: ATLAS alt sistemine, Windows/macOS yazılımsal arızalarını uçtan uca kendi başına çözmeye çalışan bir "Arıza Giderme" akışı ekle.
TETİKLEME AKIŞI:
1. Kullanıcı "+" butonuna basar, açılan menüde "Arıza" seçeneği vardır.
2. Fareyi "Arıza" üzerine getirdiğinde alt seçenekler açılır: "Windows" ve "macOS".
3. Kullanıcı işletim sistemini seçer → ATLAS penceresi açılır (bkz. Özellik 6: bu sırada JARVIS penceresi kapanır).
4. Kullanıcı problemi serbest metin olarak yazar.
ÇÖZÜM MANTIĞI (sırayla):
1. ATLAS önce "Bu hatayı nasıl çözerim?" sorusunu oluşturur ve arama modellerinden (Özellik 10) varsayılan olarak "Flash" ile araştırır; kullanıcı isterse ATLAS arayüzünden "Pro"ya değiştirebilir.
2. Bulunan çözüm adımlarını web'den toplar, adımları kullanıcıya kısaca özetler (opsiyonel).
3. ATLAS klavye/fare kontrolünü devralarak çözüm adımlarını otomatik uygular.
4. Uyguladıktan sonra sorunun düzeldiğini kendi başına test etmeye çalışır (mümkünse programatik doğrulama).
5. Otomatik test yeterli değilse (ör. ses sorunları) kullanıcıya "Bu çözüldü mü?" diye sorar. "Hayır" → sıradaki alternatif çözüm, "denenenler" listesi tutulur. "Evet" → ATLAS kapanır, JARVIS penceresi açılır.
GEREKSİNİMLER:
- Her adım loglanmalı ki bir şey ters giderse kullanıcı ne yapıldığını görebilsin.
- Disk formatlama, sistem dosyası silme vb. zararlı işlemlerden önce ekstra onay iste.
- Alternatif kalmadığında açıkça bildir; manuel öneriler/kaynak linkleri sun.
ÇIKTI: State machine tasarımı (bekleme → araştırma → uygulama → test → kullanıcı onayı → kapanış/döngü), değiştirilen dosyalar, test senaryoları ("hayır" döngüsü + "alternatif tükendi" uç durumu).

## Özellik 4 — "+" Menüsünde ATLAS, Akıllı Niyet Algılama ve Ayarlar
GÖREV: "+" butonu menüsünün davranışını ve ATLAS'ın otomatik açılma mantığını iyileştir; ayarlara ATLAS aç/kapa anahtarı ekle.
GEREKSİNİMLER:
1. "+" butonuna basıldığında açılan seçenekler listesinde "ATLAS" seçeneği EN ÜSTTE yer alsın.
2. Niyet algılama: Kullanıcı JARVIS'e (metinle) "şunu yap", "şu hatayı çöz" gibi somut bir GÖREV/EYLEM talebi verdiğinde ATLAS otomatik olarak açılmalı.
3. Ancak kullanıcı sadece merak ederek soru soruyorsa ("ATLAS ne işe yarar?", "ATLAS nasıl çalışıyor?") bu bir GÖREV DEĞİLDİR — ATLAS otomatik açılmamalı, soru normal şekilde cevaplanmalı.
4. Bu ayrımı yapan niyet sınıflandırma mantığını (kural tabanlı anahtar kelime + fiil kalıbı ya da LLM sınıflandırması) net tasarla; yanlış pozitif/negatifleri azaltacak örnek setlerle test et (doğru pozitif: "atlasla ekran kartı sürücüsünü güncelle"; doğru negatif: "atlas'ı kim yaptı", "atlas ne demek").
5. Sağ alt Ayarlar butonuna "ATLAS'ı Otomatik Aç/Kapat" toggle seçeneği ekle.
6. Bu ayar tercihi cihaz/oturum bazında kalıcı olarak saklanmalı; kullanıcının belirttiği yönteme göre IP adresine göre kaydedilsin.
NOT (geliştiriciye): IP değişebildiği için tek başına güvenilir anahtar olmayabilir; mümkünse IP'ye ek olarak sabit cihaz/kullanıcı kimliği (ör. makine ID) ile birlikte sakla, ama istenen davranış (IP bazlı kayıt) birincil gereksinim olarak kalsın.
ÇIKTI: Niyet modülünün tasarımı + en az 10 pozitif/10 negatif örnek cümle test tablosu, ayarlar UI bileşeni, ayarın saklandığı yer.

## Özellik 5 — Dosya Format Dönüştürme (PDF / JPG / PNG / Metin)
GÖREV: JARVIS'e, kullanıcının yüklediği dosyaları birbirine dönüştürebilen genel bir "Dosya Dönüştürücü" özelliği ekle.
DESTEKLENMESİ GEREKEN DÖNÜŞÜMLER (en az):
- Görsel → PDF (JPG/PNG → PDF)
- PDF → Görsel (PDF sayfalarını JPG/PNG olarak dışa aktarma)
- PDF → Metin (PDF içeriğini düz metin/txt olarak çıkarma; taranmış/görsel PDF'lerde OCR gerekebileceğini hesaba kat)
- Görsel formatları arası dönüşüm (JPG ↔ PNG)
GEREKSİNİMLER:
- Kullanıcı bir dosya yükleyip doğal dille ("bunu pdf yap", "bunu text'e çevir") ne istediğini belirttiğinde, JARVIS hedef formatı otomatik anlayıp uygun dönüştürme işlemini çalıştırsın.
- Çok sayfalı PDF ↔ çoklu görsel dönüşümlerinde sayfa sırası korunmalı.
- Dönüşüm sonrası dosya, kullanıcının indirilebileceği/açılabilir şekilde sunulmalı.
- Desteklenmeyen bir format istenirse (ör. .docx → .pdf) açıkça hangi formatların desteklendiği söylenmeli.
KENAR DURUMLARI: Bozuk/şifreli PDF için anlamlı hata mesajı; taranmış PDF'lerde OCR gerekliliğini otomatik tespit et.
ÇIKTI: Dönüştürme modülünün fonksiyon imzaları, kullanılan kütüphaneler, her dönüşüm yönü için en az bir test senaryosu.

## Özellik 6 — ATLAS ↔ JARVIS Pencere Geçişi (Karşılıklı Dışlayıcı)
GÖREV: ATLAS ve JARVIS pencerelerinin aynı anda açık olmasını engelle; biri açıkken diğeri kapansın.
MEVCUT DURUM (SORUN): ATLAS açıldığında hem ATLAS hem JARVIS aynı anda açık kalıyor.
İSTENEN DAVRANIŞ:
1. ATLAS herhangi bir sebeple açıldığında (bkz. Özellik 3 ve 4), JARVIS penceresi otomatik olarak kapanır/gizlenir; ekranda sadece ATLAS görünür.
2. Kullanıcı ATLAS açıkken JARVIS'e sorması gereken türde bir soruyu doğrudan ATLAS penceresi üzerinden sorabilir.
3. ATLAS kapandığında (görev bitince, manuel kapatınca veya Özellik 3'teki "evet, çözüldü" ile), ATLAS kapanır ve JARVIS tekrar açılır; ikisi birden açık kalmamalı.
GEREKSİNİMLER:
- Pencere durumu merkezi bir "WindowManager"/durum kontrolcüsü ile yönetilmeli; pencereler kendi başına karar vermemeli.
- Geçişler sırasında kullanıcı context'i (konuşma geçmişi, görev) kaybolmamalı.
- Geçişler ani/rahatsız olmamalı (kısa geçiş animasyonu düşünülebilir, zorunlu değil).
ÇIKTI: WindowManager tasarımı, değişen kod, test senaryoları (ATLAS açıkken JARVIS'i manuel açma girişiminin engellenmesi).

## Özellik 7 — Arayüz Modernizasyonu: 2026 Estetiği, Oval Kenarlar, Akıcı Durum Çerçevesi
GÖREV: JARVIS ve ATLAS arayüzlerini görsel olarak modernize et.
1) KENARLAR: Uygulamadaki TÜM köşeler (pencere, kartlar, butonlar, giriş kutuları) 90 derece keskin değil, tamamen OVAL/yuvarlatılmış olacak.
2) DURUM GÖSTERGESİ: Üstteki ayrı renkli "durum çubuğu/göstergesi" KALDIR. Yerine, pencerenin tüm kenarını çevreleyen İNCE bir renkli ÇERÇEVE (border/glow) koy — kalın değil, gözün rahatça fark edeceği netlikte.
3) RENK DURUMLARI VE GEÇİŞLERİ:
- KIRMIZI: Hata durumu (API bağlantısı yok/kopuk).
- MAVİ: Aktif çalışma (cevap aranıyor/işleniyor).
- YEŞİL: Cevap kullanıcıya sunulduğu andan itibaren TAM 12 SANİYE yeşil kalır; 12 sn dolunca idle'a döner. Ancak kullanıcı bu süre dolmadan yeni mesaj gönderirse çerçeve ANINDA mavieye döner (yeşilin kalan süresi iptal).
- BOŞTA (IDLE): Nötr/loş bir renkte (ör. düşük opaklıkta gri/beyaz) hafif "nefes alma" animasyonuyla göster.
- GEÇİŞ TARZI: ASLA ani/sert atlama yok; bir renkten diğerine YUMUŞAK, akıcı geçiş (HSL/RGB interpolasyonu) — iOS Siri hissi; sadece "akıcı ve yumuşak geçiş" referans alınır.
GEREKSİNİMLER:
- Bu renk/çerçeve mantığını merkezi bir "durum" değişkeninden besleyen ayrı bir bileşen (ör. StatusBorderWidget) olarak tasarla; farklı ekranlarda tekrar kullanılabilsin.
- 12 sn geri sayım ve "yeni mesaj gelirse iptal" TIMER (QTimer) ile yönetilsin.
- Performans: animasyon 30-60 fps'de hafif olmalı.
ÇIKTI: StatusBorderWidget kodu, durum state machine'i (idle/error/busy/success + süreler), üst çubuğun kaldırıldığı yerler, test senaryoları (12 sn timer'ın yeni mesajla iptali).

## Özellik 8 — Tam Müfredat Bilgisi + 3 Saniyelik Doğrulama Süresi
GÖREV: JARVIS'e 1-12. sınıfa kadar güncel müfredat bilgisini kazandır ve eğitim sorularında 3 saniyelik "doğrulama" adımı ekle.
GEREKSİNİMLER:
1. Bilgi tabanında/sistem promptunda her sınıf seviyesinde hangi derslerde hangi konuların işlendiğine dair kapsamlı müfredat referansı bulunmalı (ideal: resmi kaynağa dayalı, GÜNCELLENEBİLİR veri katmanı — JSON/veritabanı; statik/hard-code DEĞİL).
2. Kullanıcı eğitimle ilgili bir soru sorduğunda, cevabı sunmadan önce 3 SANİYELİK "doğrulama/teyit" süresi geçir; bu süre içinde cevabı kendi içinde kontrol et (ikinci iç kontrol/self-check ya da güvenilir kaynakla çapraz doğrulama) ve güven durumunu belirle.
3. Bu 3 saniyelik süre arayüzde "kontrol ediliyor" göstergesiyle (ör. mavi durum çerçevesi) yansıtılabilir.
4. Cevap, sorunun ait olduğu sınıf seviyesine uygun dil/karmaşıklıkta verilmeli (3. sınıf ≠ 11. sınıf); seviye belirtilmemişse içerikten tahmin et ya da genel/orta seviyede cevapla.
ÇIKTI: Müfredat veri katmanı şeması/örneği, doğrulama adımının teknik tasarımı (self-check), test senaryoları (doğru + yanlış/şüpheli cevap örneğinde doğrulamanın davranışı).

## Özellik 9 — JARVIS'in Kendi "Detaylı Prompt Yazma" Yeteneği
GÖREV: JARVIS'e, kullanıcı adına başka yapay zekalara verilecek son derece detaylı ve kaliteli prompt'lar üretebilen bir "Prompt Mimarı" modu/yetenek ekle.
AMAÇ: Kullanıcı "şunun için bana bir prompt yaz" dediğinde, JARVIS piyasadaki hiçbir asistanın üretemeyeceği kadar detaylı, yapılandırılmış ve kullanıma hazır bir prompt üretebilsin.
GEREKSİNİMLER — üretilen her prompt'ta şunlar bulunmalı:
1. Net rol/bağlam tanımı (AI'ya kim olduğu, hangi proje/durum için çalıştığı).
2. Görevin net, tek anlamlı, adım adım tanımı.
3. Kısıtlar ve gereksinimler (format, uzunluk, ton, teknik kısıtlar).
4. Belirsiz noktalar için makul varsayımlar + bunların açıkça belirtilmesi.
5. Kenar durumları ve nasıl ele alınacağı.
6. Beklenen çıktı formatının net tanımı (kod, liste, tablo, madde madde rapor).
7. Uygunsa örnek girdi/çıktı ya da mini şablon.
8. Gerekiyorsa test/doğrulama kriterleri (başarılı sayılma koşulları).
UYGULAMA ÖNERİSİ: Bunu JARVIS'in genel konuşma yeteneğinin bir "modu"/komutu olarak tasarla (ör. "prompt modu" ya da "bunun için prompt yaz"). İç sistem promptunda yukarıdaki 8 maddeyi checklist olarak ver; JARVIS her prompt'u vermeden önce bu listeye göre kendi kendini kontrol etsin.
ÇIKTI: Tetiklenme mantığı, sistem prompt şablonu/checklist metni, örnek bir kullanıcı isteğine karşı üretilecek örnek prompt çıktısı.

## Özellik 10 — 4 Kademeli Akıllı Arama Modu Sistemi
GÖREV: JARVIS'e 4 farklı arama/araştırma modu ekle; kullanıcı aralarında seçim yapabilsin.
GENEL KURAL: Kullanıcı isteğinin sonunda açıkça rapor uzunluğu isterse ("3 sayfa istiyorum"), hangi mod seçili olursa olsun çıktı bu uzunluğa göre ayarlanır; mod bazlı varsayılanlar sadece uzunluk BELİRTİLMEDİĞİNDE geçerlidir.
### MOD 1 — Flash Lite (en hızlı): 1-6 kaynak; ~1 sayfa; en geç 5 saniye. Web araştırması GEREKTİRMEYEN sorularda araştırmadan milisaniyeler içinde doğrudan cevap.
### MOD 2 — Flash: 4-10 kaynak; ~1,5 sayfa; 10 kaynakta en geç ~10 saniye (kaynakla orantılı).
### MOD 3 — Pro: 6-20 kaynak; 2-3 (bazen 3-6) sayfa; 20 kaynakta en geç 40 saniye. KAYNAK GÜVENİLİRLİK ANALIZI yapar (tür: haber/bilimsel/resmi; bilimsel mi; genel güvenilir mi; hakem/editör değerlendirmesi; bağımsız uzman incelemesi; son gelişmeleri yansıtıyor mu; güncel mi). GÜVENSİZ kaynaklar rapora ASLA dahil edilmez. İstisna: güvenilir başka kaynak yoksa düşük güvenilirlikli kaynaklar her kriteri Evet/Hayır ile "Filtreler" adlı ayrı bölümde sunulabilir. Kullanıcı Ayarlar'dan "Filtre sonucunu göster" tikini kaldırarak bu bölümü kapatabilir.
### MOD 4 — Deep Research: pratik olarak TÜM kaynaklara bakar (Pro ile AYNI güvenilirlik kriterleri); genelde 10-15 dakika; tahmin ≥5 dakika ise ekranda YUVARLAK geri sayım göster (ortasında dakika:saniye canlı); en fazla 20 sayfa.
GEREKSİNİMLER (ortak): Mod seçimi arayüzden net yapılabilsin (dropdown). Kaynak sayısı arttıkça süre orantılı artsın (zamanlayıcı/ilerleme tahmini; "kaç kaynağa bakılıyor" bilgisi önerilir). Güvenilirlik analiz modülü Pro ve Deep'te TEK yerde tanımlı olsun, kod tekrarı olmasın.
ÇIKTI: 4 modun mimarisi (ortak "ResearchEngine" + mod parametreleri), güvenilirlik puanlama mantığı, Deep Research geri sayım bileşeni, her mod için en az bir test senaryosu (Pro/Deep'te "sadece güvensiz kaynak var" uç durumu).

---

## 📝 Genel Notlar / Yapılan Varsayımlar
- Özellik 4 (IP bazlı ayar): IP dinamik olabilir; makine ID ile birlikte sakla, IP birincil anahtar olarak kalsın.
- Özellik 7 (idle rengi): nötr/loş gri-beyaz varsayıldı (istenen renk kolayca değiştirilebilir).
- Özellik 8 (sayfa ölçütü): "1 sayfa ≈ 500 kelime" (mega mod notu; müfredat metin içeriği JSON veri katmanında tutulur).
- Özellik 2 (paketleme): tek codebase korunur; .exe/.app ayrı derlenir = teknik zorunluluk, ayrı sürüm değildir.

## ✅ Bu Depodaki Uygulama Durumu
10/10 özellik uygulandı ve test edildi (101/101 unittest + offscreen duman testi).
Ana modüller: window_manager, status_border, intent_detection, device_prefs, research_engine/research_ui, troubleshoot_flow, presentation_builder, file_converter, platform_service, curriculum (+data/curriculum.json), prompt_architect.
