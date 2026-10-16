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
Faz 1–4 tamam (okuyucu, ek açıklama/form/imza, düzenleme, dönüştürme/sıkıştırma/karşılaştırma); sırada Faz 5 (OCR, koruma, dijital imza). Ayrıntı: `surec.md`, özellik haritası: `docs/ozellikler.md`.

## Lisans
Proje **GNU AGPL-3.0** (`LICENSE`), açık kaynak ve ticari amaçsız.

| Bağımlılık | Kullanım | Lisans |
|---|---|---|
| PyMuPDF (MuPDF) | PDF motoru | AGPL-3.0 |
| PySide6 (Qt) | Arayüz | LGPL-3.0 |
| pymupdf-fonts (Noto Sans) | PDF'e gömülen Türkçe karakterli yazı tipi | SIL OFL 1.1 |
| pdf2docx, python-docx, openpyxl, python-pptx | Word / Excel / PowerPoint dönüştürme | MIT |
| mammoth | Word → HTML (Word'den PDF) | BSD-2-Clause |
| Tesseract OCR (PyMuPDF içinde) + tessdata_fast `tur`/`eng` | metin tanıma (OCR); dil verisi `%APPDATA%\<Ad>	essdata` içine konur | Apache-2.0 |
| NumPy, Pillow, OpenCV (headless, pdf2docx ile gelir) | Görüntü işleme, resim biçimleri | BSD / HPND / Apache-2.0 |
| comtypes | Tarayıcıdan sayfa alma (WIA) | MIT |
| pytest | Test | MIT |
