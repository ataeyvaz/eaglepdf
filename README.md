# EaglePDF

Sade, Türkçe, yerel çalışan PDF masaüstü uygulaması (Eagle Office ailesi). Belgeler bilgisayardan dışarı çıkmaz.
Kullanıcıya görünen ad geçicidir: `eaglepdf/__init__.py` içindeki `APP_NAME`.

## Çalıştırma
```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py        # ya da EaglePDF.bat
.venv\Scripts\python -m pytest      # testler
```

## Durum
Tüm fazlar tamam: okuyucu, ek açıklama/form/görsel imza, düzenleme, dönüştürme/sıkıştırma/karşılaştırma, OCR, parola koruma,
sertifikalı dijital imza (pyHanko), ayarlar, belge özellikleri, toplu yazdırma ve **belge sekmeleri** (en çok 8 belge, tek pencere,
isteğe bağlı oturum geri yükleme). Ayrıntı: `surec.md`, özellik haritası: `docs/ozellikler.md`, sekme tasarımı: `docs/sekmeler-plani.md`.
Uygulama içi kılavuz: **Yardım → Nasıl Kullanılır** (kısayollar dahil).

## OCR dil verisi (yeni kurulumda bir kez)
OCR motoru PyMuPDF'in içinde gelir; yalnızca dil verisi ayrı kurulur. **OCR → Dil Verisi…** penceresinden Türkçe/İngilizce (ve diğer dilleri) indirebilir (onaylarsanız; yalnızca dil dosyası istenir, belge verisi gönderilmez) ya da elinizdeki `*.traineddata` dosyalarını ekleyebilirsiniz. Elle kurulum: dosyaları (tessdata_fast, Apache-2.0: https://github.com/tesseract-ocr/tessdata_fast) `%APPDATA%\EaglePDF\tessdata` klasörüne koyun. `tesseract.exe` gerekmez.

## Paketleme (Windows, çift tıklanabilir uygulama)
```
.venv\Scripts\python -m pip install -r requirements-yapi.txt     # yalnızca derleme aracı (PyInstaller)
.venv\Scripts\python yapi\paketle.py                             # derle + paketi doğrula + zip'le
```
Çıktı `dist\` altında (depoya girmez): `EaglePDF\EaglePDF.exe` (onedir klasör), `EaglePDF-<sürüm>-tasinabilir.zip` ve AGPL gereği
`EaglePDF-<sürüm>-kaynak.zip`. Klasörü ya da zip'i başka bir bilgisayara kopyalayıp `EaglePDF.exe`'yi çalıştırmak yeter (Python gerekmez).

- **onedir:** PySide6 (LGPL) kütüphaneleri ayrı DLL olarak kalır; kullanıcı değiştirip yeniden bağlayabilir.
- **Kendini sınama:** `paketle.py` son adımda paketlenmiş exe'yi `EaglePDF.exe --oz-sinama=rapor.txt` ile çalıştırır; PDF, dönüştürmeler,
  parola, dijital imza, XMP, OCR (dil verisi varsa), yazdırma, tek pencere soketi ve ana pencere gerçekten denenir. Biri başarısızsa paket reddedilir.
  Aynı sınama geliştirmede `python main.py --oz-sinama` ile de çalışır.
- **Lisanslar:** `UCUNCU_TARAF_LISANSLAR.txt` (çalışma zamanı bağımlılıklarının lisans metinleri) ve `LICENSE` pakete eklenir.
- **İmzasız exe:** uygulama kod imzalama sertifikasıyla imzalı değildir; Windows SmartScreen "bilinmeyen yayıncı" uyarısı gösterebilir
  ("Ek bilgi → Yine de çalıştır"). Yaygın dağıtımda ücretli bir kod imzalama sertifikası gerekir.
- **Kullanıcı verisi** pakete girmez; ayarlar/imzalar/OCR dil verisi `%APPDATA%\EaglePDF\` altında kalır (kaldırınca silinmez).

## Lisans
Proje **GNU AGPL-3.0** (`LICENSE`), açık kaynak ve ticari amaçsız.

| Bağımlılık | Kullanım | Lisans |
|---|---|---|
| PyMuPDF (MuPDF) | PDF motoru | AGPL-3.0 |
| PySide6 (Qt) | Arayüz | LGPL-3.0 |
| pymupdf-fonts (Noto Sans) | PDF'e gömülen Türkçe karakterli yazı tipi | SIL OFL 1.1 |
| pdf2docx, python-docx, openpyxl, python-pptx | Word / Excel / PowerPoint dönüştürme | MIT |
| mammoth | Word → HTML (Word'den PDF) | BSD-2-Clause |
| pyHanko, pyhanko-certvalidator | sertifikalı dijital imza + doğrulama | MIT |
| cryptography, uharfbuzz, lxml, aiohttp | imza altyapısı | Apache-2.0 / BSD / MIT |
| Tesseract OCR (PyMuPDF içinde) + tessdata_fast `tur`/`eng` | metin tanıma (OCR); dil verisi `%APPDATA%\<Ad>\tessdata` içine konur | Apache-2.0 |
| NumPy, Pillow, OpenCV (headless, pdf2docx ile gelir) | Görüntü işleme, resim biçimleri | BSD / HPND / Apache-2.0 |
| comtypes | Tarayıcıdan sayfa alma (WIA) | MIT |
| pytest | Test | MIT |
