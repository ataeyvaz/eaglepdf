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
Faz 1 (okuyucu ve sayfa işlemleri) sürüyor. Ayrıntı: `surec.md`, özellik haritası: `docs/ozellikler.md`.

## Lisans
Proje **GNU AGPL-3.0** (`LICENSE`), açık kaynak ve ticari amaçsız.

| Bağımlılık | Kullanım | Lisans |
|---|---|---|
| PyMuPDF (MuPDF) | PDF motoru | AGPL-3.0 |
| PySide6 (Qt) | Arayüz | LGPL-3.0 |
| pytest | Test | MIT |
