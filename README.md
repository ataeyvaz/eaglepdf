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
OCR motoru PyMuPDF'in içinde gelir; yalnızca dil verisi ayrı konur. `tur.traineddata` ve `eng.traineddata` dosyalarını
(tessdata_fast, Apache-2.0: https://github.com/tesseract-ocr/tessdata_fast) `%APPDATA%\EaglePDF\tessdata` klasörüne kopyalayın.
Yoksa uygulama OCR kullanılmak istendiğinde bu klasörü söyler. `tesseract.exe` gerekmez.

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
