# EaglePDF — Claude Code proje kılavuzu

Bu dosya klasörün kökünde durur; Claude Code otomatik okur. Güncel durum: `surec.md`.

## Proje nedir
PDFgear benzeri, sade, Türkçe, yerel çalışan bir PDF masaüstü uygulaması (görüntüle, düzenle, dönüştür, OCR, birleştir/böl, imzala, doldur, sıkıştır, korumala vb.). Kullanıcının kişisel kullanımı içindir; **Eagle Office** ailesinin (Sözcük, Tabcel) üçüncü ürünüdür ve aynı görünüm dilini kullanır. Python 3.11 + PySide6. Çalıştırma: `.venv\Scripts\python main.py` (kurulunca `EaglePDF.bat`).

## Nasıl geliştiriyoruz (clean-room)
- PDFgear (`C:\Program Files\PDFgear`, .NET/WPF) yalnızca **davranışı ve özellik listesini anlamak** için incelenir (REA ile statik analiz, menü/arayüz gözlemi). Çıkan bilgi `docs/ozellikler.md`'ye "ne yapıyor / nasıl kullanılıyor" olarak yazılır.
- Kod **sıfırdan** yazılır. PDFgear'dan kod, görsel, ses, metin, simge, OCR verisi kopyalanmaz.

## Kesin kurallar (değiştirme, önce kullanıcıya sor)
1. **Lisans/koruma aşılmaz:** PDFgear'ın veya başka bir yazılımın lisans/ürün anahtarı/ücret kontrolünü crack etme, patch'leme, atlatma yok. Dekompile edilmiş kod projeye girmez.
2. **Ad geçicidir.** Kullanıcıya görünen ad yalnızca `eaglepdf/__init__.py` içindeki `APP_NAME` sabitinden okunur (pencere başlığı, menüler, yardım, `%APPDATA%` dahil). Arayüz metnine "EaglePDF" elle yazılmaz. Ürün ailesi adı `PAKET_ADI` sabitinden gelir.
3. **Lisans: EaglePDF açık kaynaktır, AGPL-3.0** (`LICENSE`). Ticari amaç yok, satılmaz; GitHub'a konabilir. Ana PDF motoru **PyMuPDF (AGPL)**; yeni bağımlılık AGPL-3.0 ile uyumlu olmalı (MIT/BSD/Apache/LGPL serbest). Her bağımlılığın lisansı `README` / Hakkında listesine yazılır. PySide6 LGPL → yalnızca PyInstaller onedir. Kodu kapalı tutup dağıtmak/satmak istenirse önce kullanıcıya sor (Artifex ticari lisansı gerekir).
4. **Ticari kütüphane yok:** Syncfusion, SautinSoft gibi ücretli bileşenler kullanılmaz; açık kaynak alternatifler seçilir.
5. **Veri buluta gönderilmez.** Telemetri, hesap, bulut yapay zekâ yok. Her şey yerelde.
6. **Orijinal dosya korunur:** Kayıt her zaman geçici dosyaya yaz → yerine koy düzeniyle; "Farklı kaydet" varsayılan, üzerine yazma açık onayla.
7. **Arayüz Türkçe;** kod tanımlayıcıları İngilizce, yorumlar Türkçe ya da İngilizce (dosya içinde tutarlı). Türkçe büyük/küçük harfte `str.upper/lower` yerine ortak yardımcı (`metin_tr`) kullanılır.
8. **Yardım menüsü zorunlu:** "Yardım → Nasıl Kullanılır" (`eaglepdf/yardim.md`), klavye kısayolları ve Hakkında. Yeni/değişen özellik, kısayol aynı iş parçasında yardıma yazılır.
9. **Regresyon kuralı:** bir değişiklik mevcut özelliği/testi bozarsa kullanıcıya bildir; testi silerek/gevşeterek geçirme.
10. **Commit:** her başarılı aşamadan (testler geçti + `surec.md` güncel) sonra **kullanıcıya sormadan** commit atılır. Mesaj sonuna sistemin verdiği Co-Authored-By satırı eklenir. `push`, `force`, silme/taşıma yine kullanıcı onayıyla.
11. **Arayüz dili:** Sözcük/Tabcel ile aynı (şerit/menü düzeni, renkler, simgeler). Kararlar `surec.md` → Kararlar.

## Dosya yapısı (planlanan)
```
main.py                 giriş noktası
eaglepdf/__init__.py    APP_NAME, PAKET_ADI sabitleri
eaglepdf/core/          PDF işlemleri (Qt'siz, saf Python; test edilir)
eaglepdf/ui/            PySide6 arayüzü
eaglepdf/yardim.md      Nasıl kullanılır
docs/ozellikler.md      PDFgear özellik haritası (davranış tarifi)
tests/                  pytest
surec.md  CLAUDE.md  README.md  requirements.txt
```

## Teknoloji ve kısıtlar
- Python 3.11 (`.venv`), PySide6 (LGPL).
- Ana motor: **PyMuPDF** (render, metin, düzenleme, ek açıklama, form, şifreleme, birleştir/böl). Yardımcılar (lisansı doğrulanacak): Tesseract (OCR), Pillow, python-docx/openpyxl (dönüştürme çıktıları). PyMuPDF yetmezse pikepdf/pypdfium2 eklenir.
- RAM 7,9 GB: büyük PDF'lerde sayfaları tembel (lazy) yükle.

## Test ve çalıştırma
- Test: `.venv\Scripts\python -m pytest`
- Çalıştır: `.venv\Scripts\python main.py`

## Sonra çözülecek noktalar
Ayrıntı ve güncel liste: `surec.md` §7. Kısaca: belge sekmeleri, taranmış sayfalarda metin (OCR gelince), çizim/ok/vurgu taşıma.
