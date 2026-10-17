# Belge sekmeleri — tasarım planı (2026-10-17)

Durum: **uygulandı (2026-10-17; adım 1–7 tamam)**. Karar kaydı: `surec.md` §5. Bu plan, 2026-10-16'daki "belge sekmeleri ertelendi" kararını değiştirdi.
Onaylanan kararlar: mimari A (tek görüntüleyici + oturum), en çok 8 sekme, tek örnek (adım 6), oturum geri yükleme varsayılan kapalı, aynı dosya ikinci kez açılırsa mevcut sekmeye geçilir.
Uygulamada plandan farklı olanlar: sayfa+ölçek saklama 2c yerine 2b'de yapıldı; tek örnekte yalnızca `QLocalServer` yetmedi (Windows aynı adlı ikinci sunucuya izin veriyor) → `QLockFile` eklendi; meşgulken gelen açma istekleri kuyruğa alınıyor.

## 1. Amaç ve kapsam
Aynı pencerede birden çok PDF'i sekmelerle açmak. Kapsam: sekme çubuğu, belge başına durum, kapatma/kaydetme akışı, bellek bütçesi, açma girişleri (aç, sürükle-bırak, komut satırı, son kullanılanlar). **Kapsam dışı (şimdilik):** sekmeleri pencereler arası sürükleme, yan yana bölünmüş görünüm.

## 2. Bugünkü durum (koddan çıkarılanlar)
- `AnaPencere.belge` tek `Belge`; **yalnızca iki yerde atanıyor** (`ac` → `self.belge = yeni`, `_belgeyi_kapat_sessiz` → `None`). Pencere ve karışımlarındaki diğer **146** kullanım (7 dosya) yalnızca okuyor; görüntüleyici/panellerdeki 30 `belge` kendi alanlarıdır, `belge_ata()` ile beslenir.
- Tek `Goruntuleyici`, `KucukResimler`, `YerImleri`, açıklama paneli; hepsinde zaten **`belge_ata(belge)`** var (belge değişince önbelleklerini temizler).
- Geri al/yinele geçmişi **zaten `Belge` başına** (`Belge._gecmis`, üst sınır 30 adım / 300 MB).
- `_sonuclar`/`_sonuc_no` (arama) pencerede tek; görüntüleyicide sayfa/ölçek/seçim tek.
- Testlerde `pencere.belge = ...` ataması 1 yerde (`test_ocr_arayuzu`); `pencere.ac(...)` ~24 çağrı, çoğu "aç → işlem → doğrula".

## 3. Önerilen mimari: tek görüntüleyici + belge oturumları
Her sekme için ayrı `Goruntuleyici`/panel kurmak yerine **tek görüntüleyici** kullanılır; sekme değişince `belge_ata()` ile yeniden bağlanır.

| Seçenek | Artı | Eksi |
|---|---|---|
| **A. Tek görüntüleyici + `BelgeOturumu` (önerilen)** | Bellek az (RAM 7,9 GB), mevcut paneller/ayar/araç mantığı aynen kalır, değişiklik küçük | Sekme dönüşünde küçük resimler yeniden çizilir (tembel, hızlı); sayfa içi kaydırma konumu kaybolabilir (sayfa+ölçek saklanır) |
| B. Sekme başına görüntüleyici (QStackedWidget) | Dönüşte anında, kaydırma korunur | Her sekmede ayrı sayfa önbelleği/küçük resim/panel → bellek ×N, araç/ayar senkronu karmaşık, 146 referansın hepsi "etkin görüntüleyiciyi" bulmalı |

**`BelgeOturumu`** (yeni, `ui/oturum.py`; Qt'siz alanlar): `belge`, `gecerli_sayfa`, `olcek`, `arama_sonuclari`, `arama_metni`, `panel_sekmesi`. `AnaPencere._oturumlar: list[BelgeOturumu]`, `_etkin: int`.

**Uyumluluk köprüsü:** `AnaPencere.belge` bir **property** olur (etkin oturumun belgesi / yoksa `None`); `setter` yalnızca testler/uyumluluk için. Böylece 7 dosyadaki 146 okuma **değişmeden** çalışır.

Belge başına olanlar: `Belge` (geri al geçmişi, değişti, yol, parola/yetki), `BelgeOturumu` alanları.
Ortak olanlar: menüler, araç çubukları, ayarlar, seçili araç/renk/kalınlık, görünüm modu (sürekli/tek, çift sayfa, gece), yazar adı, son kullanılanlar.

## 4. Davranış kararları (öneri)
1. **Aç:** her dosya yeni sekmede açılır. Aynı dosya zaten açıksa (yol `resolve()` + büyük/küçük harf duyarsız) o sekme etkinleşir (Windows dosya kilidi ve çift düzenleme riski). `ac(yol, yeniden=True)` ile (ör. kayıttan sonra) yeniden yükleme.
2. **Sekme başlığı:** dosya adı; kaydedilmemiş değişiklikte `●`/`*` işareti; ipucu = tam yol; parolalı belgede kilit simgesi (`kilit`).
3. **Kapat (Ctrl+W):** etkin sekmeyi kapatır; kaydedilmemişse mevcut "Farklı Kaydet / Kaydetmeden Kapat / Vazgeç" kutusu. Son sekme kapanınca bugünkü boş durum. **Pencereyi kapatma:** değişen sekmeleri sırayla sorar; "Vazgeç" hepsini durdurur.
4. **Gezinme:** Ctrl+Tab / Ctrl+Shift+Tab (ve Ctrl+PgUp/PgDn); **Ctrl+1…9 kullanılmaz** (Ctrl+1 zaten "Genişliğe Sığdır"). Orta tık = kapat; sağ tık menüsü: Kapat, Diğerlerini Kapat, Yolu Kopyala, Klasörde Göster.
5. **Sekme çubuğu:** menü altında, bul çubuğunun üstünde; belge yokken gizli; `setMovable(True)` (sürükleyerek sıralama), `setTabsClosable(True)`.
6. **Sekme değişince:** görüntüleyici/paneller yeni belgeye bağlanır, sayfa+ölçek geri yüklenir, **bekleyen yerleştirme (resim/mühür/imza) iptal edilir ve araç El'e döner**, arama çubuğu o sekmenin sonuçlarını gösterir, Geri Al/Yinele/menü durumu yenilenir.
7. **Sekme sınırı:** en çok **8** açık belge (ayarlanabilir); aşılınca "önce bir sekmeyi kapatın" uyarısı.
8. **Başlık şeridi/pencere başlığı:** etkin sekmeyi gösterir (bugünkü gibi).

## 5. Bellek bütçesi (RAM 7,9 GB)
- Bugün her `Belge` geri al için ayrı **300 MB** tutabilir → 8 sekme = 2,4 GB. **Karar:** geri al bütçesi **genel** olur (örn. toplam 400 MB; etkin sekmeye öncelik, eski sekmelerin en eski anlık görüntüleri önce atılır) — `gecmis.py`'de ortak bir sayaç.
- Etkin olmayan sekmelerin sayfa render önbelleği zaten görüntüleyicide tek; ek maliyet yok. Küçük resim önbelleği sekme başına tutulmaz (yeniden çizilir).
- Çok büyük belgeler için uyarı eşiği (örn. > 200 MB) yalnızca bilgi.

## 6. Adım adım uygulama (her adım sonunda tüm testler yeşil + commit)
| Adım | İş | Risk | Test |
|---|---|---|---|
| 0 | Taban: `pytest` yeşil, `surec.md` kararı; plan onayı | — | mevcut 216 |
| 1 | `BelgeOturumu`, `_oturumlar`, `belge` property + setter. Tek oturumla davranış **aynı** | düşük | mevcutlar aynen geçmeli |
| 2 | `QTabBar`, `ac()` yeni sekme / var olanı etkinleştir, `_oturum_degistir` (kaydet-geri yükle), sekme başlığı/işaretleri | **orta** (sinyal döngüleri: `sayfaDegisti` geri yükleme sırasında bloklanmalı) | yeni `test_sekmeler.py`: durum saklama, aynı dosya, başlık işareti |
| 3 | Kapatma akışı: sekme kapat, pencere kapat, "Tümünü kapat", kısayollar, sağ tık menüsü | orta (kaydet onayı sırası) | kapatma/iptal testleri |
| 4 | Bellek: genel geri al bütçesi, sekme sınırı | düşük | `gecmis` birim testleri |
| 5 | Girişler: sürükle-bırak çoklu, `main.py` çoklu argüman, imza/alan/birleştir "kopyayı aç" → sekme, son kullanılanlar | düşük | mevcut akış testleri güncellenir |
| 6 | **İsteğe bağlı:** tek örnek (`QLocalServer`): "Birlikte aç"/çift tık yeni pencere yerine çalışan pencerede sekme; açılışta son oturumu geri yükle (ayar) | orta (Windows IPC) | IPC birim testi |
| 7 | Yardım (Sekmeler konusu + kısayollar tablosu), `surec.md`, README yok (bağımlılık yok) | düşük | yardım testi |

Tahmini iş: adım 1–5 ≈ bir uzun oturum; adım 6 ayrı.

## 7. Riskler ve önlemler
1. **İşlem sürerken sekme değişimi** (OCR/dönüştürme/yazdırma ilerleme penceresi `processEvents` çağırıyor). Önlem: ilerleme pencereleri modal; yine de uzun işler `b = self.belge` ile belgeyi **başta yakalar** (mevcut kod çoğunlukla böyle); sekme değişimi işlem sırasında `_mesgul` bayrağıyla yok sayılır.
2. **Sinyal fırtınası:** geri yüklerken `sayfaDegisti`/`olcekDegisti` kaydı bozabilir → geri yükleme `blockSignals`/bayrakla yapılır.
3. **Testler `ac()`'ın belgeyi *değiştirdiğini* varsayıyor.** Çoğu "son açılan = etkin" olduğundan geçer; aynı dosyayı yeniden yazıp tekrar açan testler `yeniden=True` ister. `pencere.belge = None` ataması (1 test) setter ile desteklenir ya da test düzeltilir.
4. **Aynı dosya iki sekmede** → Windows kilidi/çift düzenleme: engellenir (madde 4.1). Kaydet-üzerine-yaz sırasında belge yeniden açılması mevcut `Belge.kaydet` içinde, sekmeden bağımsız.
5. **Belgeye bağlı bekleyen durum:** `_bekleyen_png`, seçili ek açıklama, görüntüleyici seçimi — sekme değişince temizlenir (madde 4.6).
6. **Bellek** (bölüm 5).
7. **Görsel regresyon:** sekme çubuğu tema (kırmızı vurgu, `theme.py` QSS) — gerçek ekranda gözle kontrol (offscreen testte yazı tipi yok).

## 8. Açık kararlar (onayınız gerek)
1. **Mimari:** A (önerilen) mi, B mi?
2. **Sekme sınırı:** 8 uygun mu?
3. **Tek örnek (adım 6):** "Birlikte aç"/çift tık mevcut pencerede sekme olarak açılsın mı, yoksa her dosya yeni pencere (bugünkü) kalsın mı?
4. **Oturum geri yükleme:** program açılışında son açık sekmeler yeniden açılsın mı (varsayılan kapalı, Ayarlar'dan açılır)?
5. **Aynı dosya** ikinci kez açılırsa mevcut sekmeye geçmek yeterli mi?
