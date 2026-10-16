# EaglePDF — süreç ve durum (2026-10-16)

Kalıcı kurallar için `CLAUDE.md`. Bu dosya: nerede kaldık, nasıl çalışıyoruz, sırada ne var. `/clear` sonrası önce bunu oku.

## 1. Neredeyiz
Faz 1–4 **tamam**; **Faz 1–5 tamam** (artıklar hariç): koruma ✅, OCR ✅, sertifikalı dijital imza ✅. **Faz 1 artıkları: ayarlar ✅, belge özellikleri ✅, toplu yazdırma ✅**; kalan tek artık: belge sekmeleri (ertelendi, §2). Testler: `.venv\Scripts\python -m pytest` → **216 geçti** (~2 dk).

| Faz | İçerik | Durum |
|---|---|---|
| Keşif | PDFgear özellik haritası (`docs/ozellikler.md`, 5 faz önerisi; kullanıcı onayladı) | ✅ |
| 1 Okuyucu | aç/parola, sürekli/tek/çift sayfa, yakınlaştırma, küçük resim + yer imi paneli, Türkçe arama, el/metin seçme (kopyala), gece modu, yazdırma (aralık/seçili), sayfa sil/çıkar/döndür/ekle/sırala, birleştir, böl, güvenli kayıt | ✅ |
| 2 Açıklama/form/imza | vurgu/altı/üstü/dalga, çizim, not, metin kutusu (Türkçe), çizgi/ok/dikdörtgen/elips, seç-taşı-renk-metin-sil, açıklama paneli, form doldurma, görsel imza (çiz/yaz/resim), bağlantı, düzenlenebilir yer imi, **geri al/yinele** | ✅ |
| 3 Düzenleme | metin bloğu düzenleme, resim/mühür (özel mühür dahil, taşı/boyutlandır), kalıcı silme (redaction + ara-ve-sil), düzleştir, kırp (+otomatik), sayfa boyutu, filigran (metin/resim, **kaldırılabilir**), arka plan, üstbilgi/altbilgi, sayfa numarası | ✅ |
| 4 Dönüştürme | PDF→Word/Excel/PowerPoint/resim/metin/HTML; resim/Word/Excel/metin/HTML→PDF; sıkıştır (3 düzey); karşılaştır (görsel + kelime farkı); tarayıcıdan PDF (WIA, **gerçek cihazla denenmedi**); toplu işlem + ilerleme + iptal | ✅ (son commit'e bak: `git log -1`) |
| 5 OCR / koruma / dijital imza | **Koruma ✅** (Koruma menüsü: parola ekle AES-256 + izinler, parolayı kaldır, belge izinleri; çıktı hep yeni dosya). **OCR ✅** (OCR menüsü: aranabilir PDF yap, bölgeden metin çıkar; taranmış belgede Word/Excel/HTML/metin dönüşümü otomatik OCR). **Dijital imza ✅** (Koruma menüsü: sertifika oluştur, dijital imzala (görünür/görünmez, art arda), boş imza alanı, imzaları doğrula; imzalı belge kaydı uyarır) | ✅ |
| Faz 1 artıkları | **Ayarlar penceresi ✅** (Dosya → Ayarlar…, Ctrl+,: yazar, açılış yakınlaştırma, sayfa düzeni, gece, araç, son liste, çıktı klasörü, OCR dili, “Birlikte aç” kaydı). **Belge özellikleri ✅** (Dosya → Belge Özellikleri…: başlık/yazar/konu/anahtar düzenle, tümünü temizle; geri alınır). **Toplu yazdırma ✅** (Dosya → Toplu Yazdır…: dosya listesi + ortak aralık + tek yazıcı ayarı, ilerleme/iptal, hata özeti). Kalan: belge sekmeleri (ertelendi) | ⏸ |

## 2. Sıradaki işler (Faz 5 — öncelik sırasıyla)
**Önce kullanıcıya sor / bilgilendir:** sertifikalı imza için pyHanko lisansı/uyumu doğrulanmalı.
- **OCR için Tesseract gerekir** (Apache-2.0, ayrı program). PDFgear'ın içindeki Tesseract/tessdata dosyaları kopyalanmaz (clean-room). Öneri: `winget install UB-Mannheim.TesseractOCR` + `tur.traineddata` (tessdata_best/fast, Apache-2.0) — kurulumu kullanıcıyla onayla; kurulu değilse uygulama anlaşılır yönlendirme yazsın. PyMuPDF `page.get_textpage_ocr(language="tur", tessdata=…)` ve `Pixmap.pdfocr_tobytes()` ile aranabilir PDF üretebilir (Tesseract bulunmalı). **Türkçe zorunlu** (I/ı/İ/i, ş, ğ, ç, ö, ü testi).
1. ~~**OCR**~~ ✅ yapıldı (`core/ocr.py`, `ui/ocr_arayuzu.py`, `donustur._metni_hazirla`; testler `test_ocr*.py`). PPTX: taranmış sayfanın OCR metni slayt notuna gider (kutu eklenmez, resimle çakışırdı) ✅.

2. ~~**Koruma**~~ ✅ yapıldı (`core/koruma.py`, `ui/koruma_arayuzu.py`, testler `test_koruma*.py`). Not: açık belgenin üzerine yazılmaz, korumalı/parolasız **kopya** yazılır.
3. ~~**Sertifikalı dijital imza**~~ ✅ yapıldı (`core/dijital_imza.py`, `ui/imza_arayuzu.py`; testler `test_dijital_imza.py`, `test_imza_arayuzu.py`). Sonra çözülecekler §7'de.
4. Artıklar: belge sekmeleri (büyük mimari değişiklik: tek `Belge` → belge listesi). (~~Ayarlar, belge özellikleri, toplu yazdırma~~ ✅) (~~Ayarlar penceresi~~ ✅)
5. (İsteğe bağlı) üstbilgi/altbilgi/sayfa numarası için "kaldır"; PDFgear'ı elle açıp `docs/ozellikler.md`'deki ⚠ noktaları gözlemle.

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
- 2026-10-16: **Belge sekmeleri ertelendi** (tek belge mimarisi; her belge ayrı pencerede/EaglePDF.bat).
- 2026-10-16: Dönüştürme bağımlılıkları (hepsi izin verici lisans): pdf2docx (MIT), python-docx (MIT), openpyxl (MIT), python-pptx (MIT), mammoth (BSD-2), numpy (BSD-3), Pillow (HPND), comtypes (MIT, tarayıcı). Word/Excel→PDF için Office gerekmez (mammoth/openpyxl → HTML → PyMuPDF Story).
- 2026-10-16: Kullanıcı "sınırlar" ifadesinden rahatsız oldu → "sonra çözeceğimiz noktalar" dili kullanılır.

## 6. Açık sorular / bekleyenler
- Dil verisi yeni kurulumda elle konmalı (`%APPDATA%\EaglePDF	essdata`); ileride uygulama içinden indirme/kurulum sihirbazı düşünülebilir.
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
- **OCR notları:** `tesseract.exe` GEREKMEZ (PyMuPDF kendi Tesseract'ını taşır); yalnızca dil verisi: `%APPDATA%\EaglePDF	essdata	ur|eng.traineddata` (tessdata_fast, Apache-2.0; ayrıca TESSDATA_PREFIX ve Program Files\Tesseract-OCR	essdata aranır). Makineye `winget` ile Tesseract 5.4 de kuruldu (kullanıcı onayıyla, 2026-10-16) ama kullanılmıyor. Görünmez katman `TextWriter.write_text(render_mode=3)` + Noto Sans; **pdf2docx render_mode 3 metni görmez** → OCR'lı Word çıktısı python-docx ile düz paragraf. Döndürülmüş sayfalar atlanır. Önce tüm sayfalar OCR'lanır, sonra tek geri-alınır adımda yazılır (iptalde belge değişmez). Test sırasında Helvetica Türkçe harf çizmez → test görüntüsünde Noto kullan. Kalite: 'ıİ' gibi belirsiz çiftler karışabilir (tessdata_best ile iyileşebilir).
- **Dijital imza notları:** pyHanko (MIT) artımlı güncelleme yapar → imzalamadan önce *kaydedilmiş dosya baytları* kullanılır (`_kaynak_bayt`); PyMuPDF `tobytes()` dosyayı yeniden yazar ve önceki imzaları bozar. İmzalı belgeyi PyMuPDF ile kaydetmek imzayı geçersiz kılar → kayıtta uyarı; değişmiş imzalı belgeye yeni imza eklenmez. Güven: sistem deposu kullanılmaz, kendinden imzalı sertifika 'kimlik doğrulanmadı' görünür. pyHanko `load_pkcs12` hatayı yutup None döner. Alan adları belgeye göre benzersiz (`Imza1…`). Görünür kutu: Noto Sans (uharfbuzz gerekir), 4 hazır konum. **Sonra çözülecek:** kutuyu sürükleyerek yerleştirme, zaman damgası (RFC 3161)/LTV, Windows sertifika deposundan seçme, imza kutusuna resim (çizilmiş imza), imzalı belgede sayfa işlemlerinin kısıtlanması, sistem güven deposu seçeneği.
- **Ayarlar notları:** Windows 10/11 varsayılan uygulamayı programdan atamaya izin vermez (UserChoice korumalı; atlatılmaz) → yalnızca 'Birlikte aç' kaydı + 'Varsayılan uygulamalar' ekranı açılır. İlişkilendirme testleri sahte anahtara (`Software\EaglePDFTest`) yazar, gerçek kayda dokunmaz. Arayüz dili seçeneği yok (yalnız Türkçe, karar). Üzerine yazma onayı ayarlanabilir DEĞİL (CLAUDE.md kural 6). Görünüm sabiti `MOD_SUREKLI` değeri `"sureklu"` (yazım hatası ama ayar dosyalarında kayıtlı; değiştirme).
- **Özellikler notu:** `set_metadata` yalnızca Info sözlüğünü yazar; XMP yalnızca 'temizle'de silinir (XMP'de ayrı başlık/yazar varsa okuyucular onu gösterebilir — bu durum denenmedi). Oluşturma/değiştirme tarihleri düzenlenemez.
- **Toplu yazdırma notu:** her dosya ayrı yazıcı işi (`setDocName`); bir `QPrinter` sayfa aralığı seçeneği toplu pencerede yok (aralığı kendi alanımız veriyor). Yazıcı 'PDF'e yazdır' (`QPrinter.PdfFormat`) ile test edilir; gerçek fiziksel yazıcıyla denenmedi. Kabuktan Python ile dosya yazarken `
` kaçışı gerçek satır sonuna dönüşüyor → çok satırlı kodu Write/Edit ile yaz (yukarıdaki araç tuzağı yine yaşandı).
- **XMP/PPTX/parola notları (2026-10-16):** XMP yalnızca mevcut alanları günceller; XMP'siz belgeye eklemez, bozuk XMP'ye dokunmaz. Aynı alan dc:title (Alt), dc:creator (Seq), dc:description, pdf:Keywords (öğe ya da nitelik) biçimlerinde ele alınır; gerçek Acrobat/Word çıktısı XMP'siyle denenmedi.
- Test notu: `tests/test_donustur.py` Arial'a (`C:\Windows\Fonts\arial.ttf`) bağlı; yoksa atlanır.
- RAM 7,9 GB ve dolu: büyük dönüşümlerde başka programları kapat. Git kimliği bu repoda yerel `Ata <ataeyvaz@gmail.com>`.
