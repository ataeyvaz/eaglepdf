# EaglePDF — süreç ve durum (2026-10-17)

Kalıcı kurallar için `CLAUDE.md`. Bu dosya: nerede kaldık, nasıl çalışıyoruz, sırada ne var. `/clear` sonrası önce bunu oku.

## 1. Neredeyiz
Planlanan **tüm fazlar ve artıklar tamam**: Faz 1–5, ayarlar, belge özellikleri, toplu yazdırma ve **belge sekmeleri** (plan: `docs/sekmeler-plani.md`, adım 1–7 bitti). Testler: `.venv\Scripts\python -m pytest` → **345 geçti** (tam paket ~4 dk; takılma riskine karşı parça parça + `timeout` ile çalıştır, bkz. §7 araç tuzakları). Kalan işler §2'de: elle denemeler, sonra çözülecek noktalar, karar bekleyenler.

| Faz | İçerik | Durum |
|---|---|---|
| Keşif | PDFgear özellik haritası (`docs/ozellikler.md`, 5 faz önerisi; kullanıcı onayladı) | ✅ |
| 1 Okuyucu | aç/parola, sürekli/tek/çift sayfa, yakınlaştırma, küçük resim + yer imi paneli, Türkçe arama, el/metin seçme (kopyala), gece modu, yazdırma (aralık/seçili), sayfa sil/çıkar/döndür/ekle/sırala, birleştir, böl, güvenli kayıt | ✅ |
| 2 Açıklama/form/imza | vurgu/altı/üstü/dalga, çizim, not, metin kutusu (Türkçe), çizgi/ok/dikdörtgen/elips, seç-taşı-renk-metin-sil, açıklama paneli, form doldurma, görsel imza (çiz/yaz/resim), bağlantı, düzenlenebilir yer imi, **geri al/yinele** | ✅ |
| 3 Düzenleme | metin bloğu düzenleme, resim/mühür (özel mühür dahil, taşı/boyutlandır), kalıcı silme (redaction + ara-ve-sil), düzleştir, kırp (+otomatik), sayfa boyutu, filigran (metin/resim, **kaldırılabilir**), arka plan, üstbilgi/altbilgi, sayfa numarası | ✅ |
| 4 Dönüştürme | PDF→Word/Excel/PowerPoint/resim/metin/HTML; resim/Word/Excel/metin/HTML→PDF; sıkıştır (3 düzey); karşılaştır (görsel + kelime farkı); tarayıcıdan PDF (WIA, **gerçek cihazla denenmedi**); toplu işlem + ilerleme + iptal | ✅ (son commit'e bak: `git log -1`) |
| 5 OCR / koruma / dijital imza | **Koruma ✅** (Koruma menüsü: parola ekle AES-256 + izinler, parolayı kaldır, belge izinleri; çıktı hep yeni dosya). **OCR ✅** (OCR menüsü: aranabilir PDF yap, bölgeden metin çıkar; taranmış belgede Word/Excel/HTML/metin dönüşümü otomatik OCR). **Dijital imza ✅** (Koruma menüsü: sertifika oluştur, dijital imzala (görünür/görünmez, art arda), boş imza alanı, imzaları doğrula; imzalı belge kaydı uyarır) | ✅ |
| Faz 1 artıkları | **Hepsi ✅:** ayarlar penceresi, belge özellikleri düzenleme, toplu yazdırma, belge sekmeleri | ✅ |
| Sekmeler | Aynı pencerede en çok 8 belge; her sekme kendi sayfa/ölçek/arama/panel/geri al durumunu saklar; ✕/orta tık/sağ tık menüsü; Ctrl+Tab gezinme; çoklu açma (sürükle-bırak, komut satırı); açık dosyayı ezmeme; genel geri al bellek bütçesi (400 MB); tek pencere (çift tık → çalışan pencerede sekme, `QLockFile`+`QLocalServer`); isteğe bağlı oturum geri yükleme | ✅ |

## 2. Sıradaki işler (güncel, 2026-10-17)
Planlı geliştirme bitti. Kalanlar üç grupta:

**A. Kullanıcının elle denemesi gerekenler** (otomatik test edilemiyor; sorun çıkarsa bildirilir):
- Sekmelerde gezinme: Ctrl+Tab / Ctrl+PgUp/PgDn, sol panel (QTabWidget) odaktayken kısayol çakışması olup olmadığı.
- Tek pencere: Ayarlar → Dosya İlişkisi → "Birlikte aç" listesine ekle → Gezgin'den çalışan EaglePDF varken PDF aç (yeni sekme mi?). Kayıt defteri kaydı gerçek makinede denenmedi.
- Tarayıcıdan PDF (WIA) gerçek cihazla; toplu yazdırma gerçek yazıcıyla (testler "PDF'e yazdır" kullanır).
- XMP güncelleme gerçek Acrobat/Word çıktılarıyla; görünür dijital imza kutusu başka okuyucularda (Acrobat) nasıl görünüyor.

**B. Sonra çözülecek noktalar** (öneri sırası):
1. Böl sonrası parçaları açma seçeneği. ~~Sekmede kaydırma konumu~~ ✅ (2026-10-17: `BelgeOturumu.kaydirma/duzen`, `Goruntuleyici.duzen_anahtari`; yalnızca ölçek/sayfa modu/sütun aynıysa geri yüklenir; yoksa sayfa).
2. OCR: `tessdata_best` seçeneği, dil verisini uygulama içinden indirme/kurulum sihirbazı; döndürülmüş sayfalar; Word çıktısında taranmış sayfa düzeni.
3. Dijital imza: kutuyu sürükleyerek yerleştirme, zaman damgası (RFC 3161)/LTV, Windows sertifika deposundan seçme, çizilmiş imza resmini kutuya koyma.
4. Geri al bütçesini (400 MB) ve sekme sınırını (8) Ayarlar'a taşımak.
5. Üstbilgi/altbilgi/sayfa numarası için "kaldır"; çizim/ok/vurgu taşıma; metin düzenlemede orijinal yazı tipi.
6. Word/Excel→PDF'te Office/LibreOffice kuruluysa yüksek sadakat; PDFgear'ı elle açıp `docs/ozellikler.md` ⚠ noktalarını gözlemle.

**C. Karar bekleyenler (kullanıcıya sorulur, önceden yapılmaz):**
- **Paketleme/dağıtım:** PyInstaller onedir (PySide6 LGPL gereği) + kurulum paketi, sürüm numarası, `EaglePDF.bat` yerine kısayol.
- **GitHub'a koymak** (`push` kullanıcı onayıyla), ad kalıcılaştırma (`APP_NAME` geçici sabit), Hakkında/iletişim bilgileri.

## 3. Çalışma sistemi (her adımda)
1. `surec.md`'yi oku, kaldığın yerden devam et.
2. Özelliği önce çekirdekte (Qt'siz, `eaglepdf/core/`) yaz + test et; sonra arayüze bağla.
3. `pytest` çalıştır (hepsi geçmeli); gerçek ekranda bir kez gözle (aşağıya bak).
4. `eaglepdf/yardim.md`, `README.md` (bağımlılık/lisans), `ui/hakkinda.py` `KATKILAR` ve bu dosyayı güncelle.
5. Başarılıysa **commit at** (kullanıcıdan izin istemeden; Co-Authored-By satırıyla). `push`/silme/taşıma kullanıcı onayıyla.
- Kullanıcıya dil: Türkçe, kısa; eksikleri "sınır" değil "sonra çözeceğimiz nokta" diye anlat, çözüm yolunu söyle (hafıza: `feedback-sinirlar-ifadesi`).

## 4. Dosya haritası
```
main.py, EaglePDF.bat, requirements.txt, README.md, LICENSE (AGPL-3.0)
eaglepdf/__init__.py     APP_NAME (geçici ad, tek yer), PAKET_ADI, sürüm
eaglepdf/metin_tr.py     Türkçe büyük/küçük harf (str.lower/upper YASAK; testlerde bile bunu kullan)
eaglepdf/yardim.md       Nasıl Kullanılır (konu ayracı: <!-- konu: kimlik | Başlık -->, {APP_NAME} yer tutucu)
eaglepdf/core/           Qt'siz
  belge.py               Belge sınıfı (açma, render, arama, sayfa işlemleri, kayıt); karışımlar: EkAciklamaIslemleri + DuzenlemeIslemleri
  ekaciklama.py          ek açıklama, bağlantı, yer imi, form, imza yerleştirme
  duzenleme.py           kırp, boyut, filigran(+kaldır), arka plan, üst/alt bilgi, sayfa no, redaction, düzleştir, mühür, metin düzenleme
  donustur.py            tüm dönüştürmeler, sıkıştır, karşılaştır (ilerleme callback + Iptal)
  tarayici.py            WIA (comtypes) tarama
  ocr.py                 OCR (PyMuPDF içindeki Tesseract; OcrIslemleri karışımı Belge'ye: aranabilir_yap, bolgeden_metin, metinsiz_sayfalar)
  dijital_imza.py        pyHanko ile imzala/doğrula/boş alan/sertifika üret (artımlı güncelleme; yeni dosyaya yazar)
  iliskilendirme.py      Windows 'Birlikte aç' kaydı (HKCU\Software\Classes\EaglePDF.PDF; yalnızca kullanıcı düzeyi)
  xmp.py                 XMP'de mevcut başlık/yazar/konu/anahtar alanlarını günceller (lxml; yeni alan eklemez)
  koruma.py              parola ekle/kaldır (AES-256), izinler (korumalı kopya yazar)
  gecmis.py              geri al/yinele (@geri_alinabilir dekoratörü, bayt anlık görüntüleri)
  yazitipi.py            Noto Sans (pymupdf-fonts) — PDF'e Türkçe metin gömme
  imzalar.py             kayıtlı imza/mühür PNG deposu (klasör)
  hatalar.py             BelgeHatasi, ParolaGerekli
eaglepdf/ui/             PySide6
  pencere.py             AnaPencere (menüler, araç çubuğu, paneller, kayıt, arama, sayfa işlemleri); karışımlar aşağıda
  aciklama_arayuzu.py    Faz 2 (açıklama araç çubuğu, araç eylemleri, imza, form, geri al)
  duzenleme_arayuzu.py   Faz 3 (Düzenle menüsü, Sayfa menüsü eklemeleri, mühür/resim yerleştirme)
  donusum_arayuzu.py     Faz 4 (Dönüştür menüsü, tarayıcı akışı)
  koruma_arayuzu.py      Faz 5 (Koruma menüsü, ParolaEkleDialog)
  toplu_yazdir.py        toplu yazdırma: toplu_yazdir() (Qt yazıcı, hata yalıtımı) + TopluYazdirPenceresi
  ozellikler_penceresi.py Belge Özellikleri (düzenlenebilir 4 alan + salt okunur bilgi + temizle); çekirdek: Belge.ozellikleri_ata/temizle/pdf_tarihi
  ayarlar_penceresi.py   Ayarlar (Genel / Klasörler ve OCR / Dosya İlişkisi); QSettings'e yazar, ana pencere `ayarlari_uygula`
  imza_arayuzu.py        Faz 5 (Koruma menüsüne dijital imza eylemleri, kayıt uyarısı `_imzali_kayit_onayi`)
  ocr_arayuzu.py         Faz 5 (OCR menüsü, aranabilir PDF penceresi + ilerleme/iptal, bölge aracı 'ocr_bolge')
  goruntuleyici.py       sayfa görüntüleyici + fare araçları (tembel çizim); sinyal: aracEylemi(araç, sayfa, veri)
  paneller.py            küçük resimler, yer imleri, açıklamalar paneli
  donusum_penceresi.py   ortak dönüştür/sıkıştır penceresi + IsParcacigi (QThread)
  karsilastirma_penceresi.py, sayfa_islem_dialoglari.py, dialoglar.py, sayfa_dialoglari.py (birleştir/böl), yardim.py, hakkinda.py, yazdir.py, simgeler.py (kodla çizilen SVG simgeler), theme.py (KIRMIZI vurgu)
tests/                   test_belge, test_ekaciklama, test_duzenleme, test_donustur (çekirdek); test_arayuz, test_aciklama_arayuzu, test_duzenleme_arayuzu, test_donusum_arayuzu (offscreen Qt)
docs/ozellikler.md       PDFgear özellik haritası (davranış tarifi)
```
Kullanıcı verisi (ayarlar, imzalar, mühürler): `%APPDATA%\EaglePDF\` (`EaglePDF.ini`, `imzalar\`, `muhurler\`).

## 5. Kararlar (tarihli)
- 2026-10-16: Ad ve klasör **EaglePDF** (`Desktop\EaglePDF`) — kullanıcı seçti; ad geçici sabitten okunur.
- 2026-10-16: PDFgear'ın **tüm özellikleri** hedef — kullanıcı isteği; aşamalara bölünür.
- 2026-10-16: Yaklaşım **clean-room**: davranış incelenir, kod sıfırdan yazılır; lisans/koruma aşılmaz.
- 2026-10-16: Yığın Python 3.11 + PySide6, arayüz Eagle Office düzeniyle (başlık şeridi, menü, araç çubuğu).
- 2026-10-16: **Arayüz vurgu rengi KIRMIZI** (`#c62828`, `ui/theme.py`) — kullanıcı isteği; Sözcük/Tabcel'in mavisinden bilerek ayrılır.
- 2026-10-16: **Arayüz tamamen Türkçe; OCR'da Türkçe (`tur`) zorunlu** — kullanıcı isteği.
- 2026-10-16: **Yardım → Nasıl Kullanılır menüsü** zorunlu; yeni özellik aynı iş parçasında yardıma yazılır.
- 2026-10-16: Her başarılı aşamadan sonra commit kullanıcıya sorulmadan atılır — kullanıcı izni.
- 2026-10-16: **Faz sırası onaylandı** (okuyucu → açıklama/form → düzenleme → dönüştürme/sıkıştırma → OCR/koruma/imza). **Yerel çeviri ve sohbet (yapay zekâ) alınmayacak** — kullanıcı.
- 2026-10-16: **PyMuPDF kullanılacak, proje AGPL-3.0 açık kaynak**; ticari bileşenler (Syncfusion/SautinSoft) kullanılmaz.
- 2026-10-16: Kayıt: her zaman geçici dosya → yerine koy; Kaydet açık dosyanın üzerine yazar ama onay sorar; Farklı Kaydet varsayılan önerilir. Kayıtta gömülü yazı tipleri belgenin **kopyasında** alt kümelenir.
- 2026-10-16: **Türkçe metin gömme:** PDF yerleşik yazı tipleri ş/ğ/ı/İ'yi desteklemez → Noto Sans (`pymupdf-fonts`, SIL OFL) gömülür; metin kutusu görünümü (AP) elle üretilir. Geri al/yinele: değişiklik öncesi belge baytları (30 adım / 300 MB).
- 2026-10-16: Görsel imza bir **resim**dir (sertifikasız); sertifikalı dijital imza Faz 5. Resim ve mühür **Stamp ek açıklaması** olarak eklenir (taşınır/boyutlandırılır, Düzleştir ile sayfaya işlenir).
- 2026-10-16: **Metin düzenleme:** orijinal yazı tipi şimdilik korunmuyor; paragraf silinip Noto Sans ile yeniden yazılır (döndürülmüş/taranmış sayfada yok) — yardımda açıkça yazıldı.
- 2026-10-16: Filigran isteğe bağlı içerik katmanına (OCG "EaglePDF Filigran") etiketlenir → **Sayfa → Filigranı Kaldır…** kayıttan sonra da çalışır.
- 2026-10-16: Belge sekmeleri ertelenmişti (tek belge mimarisi). **2026-10-17: yeniden ele alındı** — plan `docs/sekmeler-plani.md`; önerilen mimari tek görüntüleyici + `BelgeOturumu` + `belge` property.
- 2026-10-17: **Sekme kararları onaylandı** (kullanıcı): mimari A (tek görüntüleyici + oturum), en çok 8 sekme, tek örnek (çift tık → mevcut pencerede sekme) adım 6 olarak ayrı, açılışta oturum geri yükleme varsayılan kapalı (Ayarlar'dan açılır), aynı dosya ikinci kez açılırsa mevcut sekmeye geçilir. Uygulama adım adım (plan §6); testler parça parça çalıştırılır, adım sonunda tam paket.
- 2026-10-16: Dönüştürme bağımlılıkları (hepsi izin verici lisans): pdf2docx (MIT), python-docx (MIT), openpyxl (MIT), python-pptx (MIT), mammoth (BSD-2), numpy (BSD-3), Pillow (HPND), comtypes (MIT, tarayıcı). Word/Excel→PDF için Office gerekmez (mammoth/openpyxl → HTML → PyMuPDF Story).
- 2026-10-16: Kullanıcı "sınırlar" ifadesinden rahatsız oldu → "sonra çözeceğimiz noktalar" dili kullanılır.

## 6. Açık sorular / bekleyenler
- Dil verisi yeni kurulumda elle konmalı (`%APPDATA%\EaglePDF\tessdata`); ileride uygulama içinden indirme/kurulum sihirbazı düşünülebilir.
- Tarayıcıdan PDF gerçek cihazla denenmedi (kullanıcıda tarayıcı varsa denenip geri bildirim alınmalı).
- Bulut/yapay zekâ özellikleri (sohbet, çeviri, çevrimiçi dönüştürme) bilerek dışarıda.

## 7. Sonra çözülecek noktalar ve tuzaklar
- **Word/Excel→PDF** Office kullanmaz; sayfa düzeni (üst/alt bilgi, sütun, metin kutusu, grafik) birebir gelmez. İstenirse Word/LibreOffice kuruluysa onunla yüksek sadakatli dönüşüm eklenebilir.
- **Taranmış sayfalar:** Word/Excel/PPT/metin dönüşümü ve metin düzenleme/seçme OCR olmadan çalışmaz (uyarı verir) → Faz 5.
- Metin düzenleme: döndürülmüş sayfada yok; orijinal yazı tipi korunmuyor.
- Sayfa boyutu değişince o sayfaların açıklama/form/bağlantıları: açıklama+form sayfaya işlenir, bağlantılar düşer. Düzleştirme tüm belgeyi etkiler (sayfa bazlı değil).
- Çizim, çizgi/ok ve işaretler (vurgu vb.) taşınamaz (silip yeniden eklenir). Üstbilgi/altbilgi/sayfa numarası için 'kaldır' yok (Geri Al var).
- Form alanlarında Türkçe değer: PDF'in kendi alan görünümü (Helv) ş/ğ/ı için bozuk olabilir; `NeedAppearances` işaretlenir; uygulama içinde üstteki kutu doğru gösterir. Başka okuyucuda denenmedi.
- Metin seçme kelime tabanlı; sütunlu sayfalarda içerik sırasına göre seçer. Bölme kayıtlı dosya üzerinde çalışır.
- **PyMuPDF tuzakları:** ek açıklama nesnesi sayfaya zayıf bağlı (sayfa nesnesini canlı tut, yoksa `ReferenceError`/segfault); sayfa ekleme/silme eski sayfa nesnelerini geçersiz kılar; `add_stamp_annot` dikdörtgeni uydurur ve PNG saydamlığını yok sayar (`muhur_ekle` elle kurar); `add_freetext_annot` kenarlık rengi yalnızca zengin metinde (kenarlık `EaglePDFKenar` anahtarıyla kendi çiziminde); FreeText dolgusu `/C` içinde; resim filigranında `/OC` içerik akışında değil resim nesnesinde; döndürülmüş sayfada `rotate=sayfa_dönüşü` (ters değil) doğru, kırpmada mevcut kırpma kutusu başlangıcı eklenmeli (4 dönüşte testli).
- **Windows tuzakları:** açık PDF'in üzerine yazmak için belge kapatılıp yeniden açılır; `DocumentWriter` dosyaya yazınca kilit bırakır → Story çıktısı BytesIO'ya yazılır; sert boşluk (U+00A0) aramada/metin çıkarmada normalleştirilir.
- **Qt tuzakları:** `QSpinBox` + stil sayfası Fusion'da boş kalıyor (sayfa kutusu `QLineEdit` tabanlı); `QTest.qWaitFor` PySide6'da yok (testlerde `bekle_kosul`); offscreen testlerde yazı tipi yok (görsel kontrol gerçek platformda yapılır).
- **Araç tuzakları (bu ortam):** uzun `python - <<heredoc` / `cat <<` bazen kabukta ayrışmıyor ve satır sonu kaçışları (`\n`) bozuluyor → betikleri/dosyaları **Write/Edit** ile yaz, gerekirse betik dosyasından çalıştır. Gerçek ekran görüntüsü: geçici bir betikte `QApplication` + `AnaPencere(ayar_dosyasi)` kur, `p.grab().save(...)` ile kaydet, `Read` ile bak (scratchpad geçicidir).
- **Koruma tuzakları:** PyMuPDF'te açma parolası boşsa `needs_pass`/`is_encrypted` False kalır → şifre `metadata["encryption"]` ile, sahip parolası `authenticate()` (4/6) ile denetlenir; parolayla açılmış belgenin `tobytes()` çıktısı varsayılan şifreli olur → kopyalarken `encryption=PDF_ENCRYPT_NONE` ver. İzin kısıtları okuyucunun uyumuna bağlı (yardımda yazıyor). **Kayıtta parola korunur (2026-10-16 ✅):** `Belge.ac` parolayı/yetkiyi/izinleri hatırlar; `kaydet(parolayi_koru=True)` AES-256 ile aynı parola+izinle yazar. Yalnızca açma parolası biliniyorsa ve kısıt varsa sahip parolası rastgele (aynı parola sahip olsaydı kısıt aşılırdı) → kısıtlar kalır ama kaldırılamaz. Parolası bilinmeyen sahip-kısıtlı belgede (`koruma_dusecek`) kayıt kısıtları düşürür; UI önceden sorar.
- **OCR notları:** `tesseract.exe` GEREKMEZ (PyMuPDF kendi Tesseract'ını taşır); yalnızca dil verisi: `%APPDATA%\EaglePDF\tessdata\tur|eng.traineddata` (tessdata_fast, Apache-2.0; ayrıca TESSDATA_PREFIX ve Program Files\Tesseract-OCR\tessdata aranır). Makineye `winget` ile Tesseract 5.4 de kuruldu (kullanıcı onayıyla, 2026-10-16) ama kullanılmıyor. Görünmez katman `TextWriter.write_text(render_mode=3)` + Noto Sans; **pdf2docx render_mode 3 metni görmez** → OCR'lı Word çıktısı python-docx ile düz paragraf. Döndürülmüş sayfalar atlanır. Önce tüm sayfalar OCR'lanır, sonra tek geri-alınır adımda yazılır (iptalde belge değişmez). Test sırasında Helvetica Türkçe harf çizmez → test görüntüsünde Noto kullan. Kalite: 'ıİ' gibi belirsiz çiftler karışabilir (tessdata_best ile iyileşebilir).
- **Dijital imza notları:** pyHanko (MIT) artımlı güncelleme yapar → imzalamadan önce *kaydedilmiş dosya baytları* kullanılır (`_kaynak_bayt`); PyMuPDF `tobytes()` dosyayı yeniden yazar ve önceki imzaları bozar. İmzalı belgeyi PyMuPDF ile kaydetmek imzayı geçersiz kılar → kayıtta uyarı; değişmiş imzalı belgeye yeni imza eklenmez. Güven: sistem deposu kullanılmaz, kendinden imzalı sertifika 'kimlik doğrulanmadı' görünür. pyHanko `load_pkcs12` hatayı yutup None döner. Alan adları belgeye göre benzersiz (`Imza1…`). Görünür kutu: Noto Sans (uharfbuzz gerekir), 4 hazır konum. **Sonra çözülecek:** kutuyu sürükleyerek yerleştirme, zaman damgası (RFC 3161)/LTV, Windows sertifika deposundan seçme, imza kutusuna resim (çizilmiş imza), imzalı belgede sayfa işlemlerinin kısıtlanması, sistem güven deposu seçeneği.
- **Ayarlar notları:** Windows 10/11 varsayılan uygulamayı programdan atamaya izin vermez (UserChoice korumalı; atlatılmaz) → yalnızca 'Birlikte aç' kaydı + 'Varsayılan uygulamalar' ekranı açılır. İlişkilendirme testleri sahte anahtara (`Software\EaglePDFTest`) yazar, gerçek kayda dokunmaz. Arayüz dili seçeneği yok (yalnız Türkçe, karar). Üzerine yazma onayı ayarlanabilir DEĞİL (CLAUDE.md kural 6). Görünüm sabiti `MOD_SUREKLI` değeri `"sureklu"` (yazım hatası ama ayar dosyalarında kayıtlı; değiştirme).
- **Özellikler notu:** `set_metadata` yalnızca Info sözlüğünü yazar; XMP yalnızca 'temizle'de silinir (XMP'de ayrı başlık/yazar varsa okuyucular onu gösterebilir — bu durum denenmedi). Oluşturma/değiştirme tarihleri düzenlenemez.
- **Toplu yazdırma notu:** her dosya ayrı yazıcı işi (`setDocName`); bir `QPrinter` sayfa aralığı seçeneği toplu pencerede yok (aralığı kendi alanımız veriyor). Yazıcı 'PDF'e yazdır' (`QPrinter.PdfFormat`) ile test edilir; gerçek fiziksel yazıcıyla denenmedi. Kabuktan Python ile dosya yazarken `
` kaçışı gerçek satır sonuna dönüşüyor → çok satırlı kodu Write/Edit ile yaz (yukarıdaki araç tuzağı yine yaşandı).
- **XMP/PPTX/parola notları (2026-10-16):** XMP yalnızca mevcut alanları günceller; XMP'siz belgeye eklemez, bozuk XMP'ye dokunmaz. Aynı alan dc:title (Alt), dc:creator (Seq), dc:description, pdf:Keywords (öğe ya da nitelik) biçimlerinde ele alınır; gerçek Acrobat/Word çıktısı XMP'siyle denenmedi.
- **Sekme geçişi notları (2c):** `_oturumu_sessiz_kapat` komşuya geçmeden ÖNCE arama durumunu sıfırlar (sonra sıfırlamak komşunun geri yüklenen sonuçlarını siliyordu). Testte `QMessageBox` açan yollarda (uyarı/soru) sahte dönüş verilmezse test sonsuza dek bekler: sahte `toplu_yazdir` boş liste dönünce uyarı kutusu açılır → gerçek `DosyaSonucu` döndür; testleri `timeout` ile çalıştır.
- **Test tuzağı (2d):** `QMenu.exec` sınıf üzerinde `monkeypatch` ile yamalanamaz (PySide gerçek modal menüyü açar, test sonsuza dek bekler) → menüyü üreten yöntemi (`_sekme_menusu`) sahte nesneyle değiştir. Uzun çok satırlı heredoc bazen kabukta ayrışmıyor → dosyayı Write ile yaz. Sekme gezinme kısayollarının (Ctrl+Tab/PgUp/PgDn) `paneller` QTabWidget odaktayken çakışıp çakışmadığı gerçek ekranda denenmedi.
- **Geri al bütçesi notu (adım 4):** UI dışında açılan geçici `Belge`ler (dönüştürme/OCR kopyaları, toplu yazdırma) etkin olmadığı için 'diğer' sayılır ve bütçe aşımında önce budanır (zararsız). Testte düzenlenen `Belge`yi `gecmis.etkin_ata(b._gecmis)` ile etkin yapmazsan görüntüsü hemen budanır. `Gecmis.denetle` yalnızca `ekle`/`geri_al`/`yinele` sonrası çalışır; bütçe değişikliği hemen uygulanmaz. Değişmiş (degisti=True) belgede `tum_sekmeleri_kapat`/`kapat` testte QMessageBox açar → testte `degisti=False` yap.
- **Qt test tuzağı (adım 5):** `QDropEvent`/`QDragEnterEvent` yalnızca `QMimeData` işaretçisi tutar; veriyi geçici nesne olarak geçirirsen Python siler ve test sessizce çöker (çıktı yok) → `veri = mime(...)` değişkeninde canlı tut. Döngüde test başına `timeout` koşturmak takılan/çöken testi bulmanın en hızlı yolu.
- **Kaçış tuzağı (adım 7):** kabuk/heredoc ile Python'a `\\t`, `\\n` yazınca gerçek TAB/satır sonu oluşuyor; bu yüzden README/yardım/surec'teki `%APPDATA%\\EaglePDF\\tessdata` yolu bozulmuştu (kullanıcıya görünen yardımda da). Çok satırlı/ters eğik çizgili metni **Write/Edit** ile yaz; `tests/test_yardim_kapsami.py` yardımdaki TAB/kontrol karakterlerini ve tessdata yolunu denetler.
- **Tek örnek tuzakları (adım 6):** (1) Bu Qt/Windows sürümünde **aynı adlı adlandırılmış boruya ikinci `QLocalServer.listen` BAŞARILI olur** (istemciler iki sunucu arasında paylaştırılır) → tek örnek garantisi için `QLockFile` şart (`%TEMP%\EaglePDF-tek-ornek-<kullanıcı>.lock`; zorla öldürülen sürecin bayat kilidi bir sonraki açılışta temizlenir, doğrulandı). (2) Windows'ta yazma taşmalıdır: `waitForBytesWritten` tek başına `False` dönebilir; `gonder` 'yazılmamış bayt kalmadı'yı `processEvents` ile bekler (yalnızca ana iş parçacığında; başka iş parçacığından `processEvents` testte çökertti). (3) Aynı iş parçacığında hem sunucu hem istemci olursa yazma tamamlanmaz → testler istemciyi **ayrı süreçte** (`cocuk()` yardımcısı) çalıştırır. (4) Testlerde `tek_ornek.sunucu_adi`'nı benzersiz adla yamala; yoksa gerçek çalışan EaglePDF ile kilit çakışır. (5) Windows komut satırı sınırı (~32 KB) yüzünden büyük test verisi argümanla geçirilmez. Gerçek başlatıcı (`main.py`) offscreen 6 sn hatasız çalıştı; iki gerçek pencereyle (çift tık) elle deneme yapılmadı.
- Test notu: `tests/test_donustur.py` Arial'a (`C:\Windows\Fonts\arial.ttf`) bağlı; yoksa atlanır.
- RAM 7,9 GB ve dolu: büyük dönüşümlerde başka programları kapat. Git kimliği bu repoda yerel `Ata <ataeyvaz@gmail.com>`.
