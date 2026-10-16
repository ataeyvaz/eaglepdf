# EaglePDF — süreç ve durum (2026-10-16)

Kalıcı kurallar için `CLAUDE.md`. Bu dosya: nerede kaldık, nasıl çalışıyoruz, sırada ne var.

## 1. Neredeyiz
| İş / modül | Hedef | Yapılan | Durum |
|---|---|---|---|
| Keşif: PDFgear | Özellik haritası | `pdfeditor.exe` REA ile tarandı; REA üye çıkarımı boş döndü (metadata kabul edilmedi), bunun yerine exe içi okunabilir kaynak adları süzüldü | ✅ |
| Proje iskeleti | klasör, git, CLAUDE.md, surec.md | oluşturuldu | ✅ |
| Özellik haritası (`docs/ozellikler.md`) | Tüm özellikler listelensin | Ad düzeyi harita + 5 faz önerisi yazıldı; ⚠ işaretliler elle gözlem bekler | ✅ (faz onayı bekliyor) |
| Çekirdek (`core/belge.py`) | aç, parola, render, Türkçe arama, sayfa sil/döndür/ekle/sırala/çıkar, birleştir, böl, güvenli kayıt | 11 test geçti | ✅ |
| Uygulama iskeleti (PySide6) | pencere, menü, yardım, hakkında, kırmızı tema | Görüntüleyici (sürekli kaydırma, tembel çizim, yakınlaştırma), küçük resim + yer imi paneli, arama çubuğu, sayfa işlemleri menüsü, birleştir/böl pencereleri, yardım, hakkında; 4 arayüz testi | ✅ |
| Faz 1: görünüm ve araçlar | tek/çift/sürekli sayfa, el + metin seçme (kopyala), gece modu, yazdırma (+aralık/seçili), çizgi simgeler | tamamlandı; 20 test geçti | ✅ |
| Faz 2 çekirdek (`core/ekaciklama.py`, `gecmis.py`, `yazitipi.py`) | vurgu/altı/üstü/dalga, çizim, not, şekil, metin kutusu (Türkçe, Noto Sans), bul/sil/taşı/renk/metin, bağlantı, yer imi, form alanları, görsel imza yerleştirme, geri al/yinele | 11 yeni test geçti (toplam 31) | ✅ |
| Faz 2 arayüz | ikinci araç çubuğu (14 araç), seç/taşı/renk/metin düzenle/sil, açıklama paneli (süz, toplu sil), form doldurma (sayfa üstü kutular), görsel imza (çiz/yaz/resim, kayıtlı imzalar), bağlantı ekle/sil/tıkla, düzenlenebilir yer imleri, geri al/yinele | 47 test geçti; gerçek ekranda görüldü | ✅ |
| Faz 1: belge sekmeleri | çoklu belge | yapılmadı (bkz. Kararlar) | ⏸ |

Testler: `.venv\Scripts\python -m pytest` (47 geçti)

## 2. Sıradaki işler (öncelik sırasıyla)
1. **Faz 3'e başla:** düzenleme (metin düzenleme, resim ekle/taşı, mühür, redaction, düzleştirme, kırp, filigran, üstbilgi/altbilgi, sayfa numarası, arka plan, sayfa boyutu).
2. Toplu yazdırma, belge sekmeleri, belge özellikleri düzenleme, ayarlar penceresi (varsayılan görünüm, dosya ilişkilendirme) Faz 1 artıkları olarak uygun yerde eklenecek.
3. Türkçe OCR verisi (`tur.traineddata`, Apache-2.0) Faz 5'te temin edilecek.
4. (İsteğe bağlı) ⚠ işaretli noktaları PDFgear'ı elle açıp gözlemle.
3. Bağımlılık lisanslarını doğrula (pypdfium2, pypdf/pikepdf, Tesseract).
4. Uygulama iskeleti: pencere, Sözcük/Tabcel görünümü, Yardım menüsü, Hakkında.
5. Faz 1 uygulaması + testler.

## 3. Çalışma sistemi (her adımda)
1. `surec.md`'yi oku, kaldığın yerden devam et.
2. Özelliği önce `docs/ozellikler.md`'de tarif et, sonra kendi kodumuzla yaz.
3. Test/denetim çalıştır (`pytest`).
4. `yardim.md` ve bu dosyayı güncelle.
5. Başarılıysa **commit at** (kullanıcıdan izin istemeden; Co-Authored-By satırıyla).

## 4. Kararlar (tarihli)
- 2026-10-16: Ad ve klasör **EaglePDF** (`Desktop\EaglePDF`) — kullanıcı seçti; ad geçici sabitten okunur.
- 2026-10-16: PDFgear'ın **tüm özellikleri** hedef — kullanıcı isteği; aşamalara bölünür.
- 2026-10-16: Yaklaşım **clean-room**: davranış incelenir, kod sıfırdan yazılır; lisans/koruma aşılmaz — kullanıcıyla konuşuldu.
- 2026-10-16: Yığın Python 3.11 + PySide6, arayüz Sözcük/Tabcel diliyle (Eagle Office ailesi) — kardeş uygulamalarla tutarlılık, ortak bilgi birikimi.
- 2026-10-16: **Yardım → Nasıl Kullanılır menüsü** zorunlu — kullanıcı isteği.
- 2026-10-16: Her başarılı aşamadan sonra commit kullanıcıya sorulmadan atılır — kullanıcı izni (genel kuraldaki "yalnızca isterse"nin bu proje için istisnası).
- 2026-10-16: **Arayüz tamamen Türkçe; OCR'da Türkçe (`tur`) zorunlu** (PDFgear'da yok, ayrıca eklenecek; Ibı/İi/ş/ğ testi) — kullanıcı isteği.
- 2026-10-16: **Faz sırası onaylandı** (okuyucu/sayfa → ek açıklama/form → düzenleme → dönüştürme/sıkıştırma → OCR/koruma/imza) — kullanıcı. **Yerel çeviri ve sohbet (yapay zekâ) alınmayacak** (ücretsiz uygun model yok) — kullanıcı.
- 2026-10-16: **Belge sekmeleri ertelendi:** görüntüleyici/panel yapısı tek belgeye göre; sekme için çoklu `Belge` + sekme başına görünüm durumu gerekir. Şimdilik her belge ayrı pencerede (EaglePDF.bat ile yeni örnek). İstenirse Faz 1 artığı olarak yapılır.
- 2026-10-16: **Türkçe metin gömme:** PDF yerleşik yazı tipleri ş/ğ/ı/İ'yi desteklemez; metin kutusu/filigran vb. için Noto Sans (`pymupdf-fonts`, SIL OFL) gömülür ve metin kutusunun görünümü (AP) elle üretilir. Geri al/yinele: değişiklik öncesi belge baytları (30 adım / 300 MB sınırı).
- 2026-10-16: Kayıtta gömülü yazı tipleri belgenin **kopyasında** alt kümelenir (506 KB → ~49 KB); çalışan belge tam yazı tipiyle kalır.
- 2026-10-16: Görsel imza bir **resim**dir (sertifikasız); sertifikalı dijital imza Faz 5.
- 2026-10-16: **Arayüz vurgu rengi KIRMIZI** (`#c62828`, `ui/theme.py`); yerleşim Eagle Office düzeniyle aynı (başlık şeridi, menü, araç çubuğu) — kullanıcı isteği. Sözcük/Tabcel'in mavisinden bilerek ayrılır.
- 2026-10-16: Kayıt davranışı: Kaydet açık dosyanın üzerine yazar ama onay sorar; Farklı Kaydet varsayılan önerilir; her kayıt geçici dosya → yerine koy.
- 2026-10-16: **PyMuPDF kullanılacak, proje AGPL-3.0 açık kaynak** (GitHub'a konabilir) — kullanıcı ticaret/satış yapmayacak; izinli lisanslı alternatifler PyMuPDF kadar kapsamlı değil, "tüm özellikler" hedefi için PyMuPDF şart. (Önceki "PyMuPDF yok" kararı iptal.) Syncfusion/SautinSoft gibi ticari bileşenler yine kullanılmaz.

## 5. Açık sorular / bekleyenler
- Bulut/yapay zekâ özellikleri (sohbet, çeviri, çevrimiçi dönüştürme) haritada "dışarıda" bırakıldı; yerel karşılık istenirse karar verilecek.
- PDFgear'ın bazı özellikleri bulut/yapay zekâ tabanlıysa (örn. sohbet, çeviri) yerel karşılığı olup olmayacağı belirsiz; keşifte netleşecek.
- OCR dil verisi (tessdata) kaynağı ve lisansı doğrulanacak.

## 6. Araçlar ve komutlar
| Ne | Komut / yer |
|---|---|
| REA kontrol | `rea doctor` (Ghidra/Hopper/IDA/JADX yok; .NET analizi için gerekmez) |
| PDFgear incele | `rea inspect-managed-artifact "C:/Program Files/PDFgear/pdfeditor.exe" --json` |
| Üye listesi | `rea inspect-managed-members <exe> --json` |
| Tam çıktı (ilk tarama) | `C:\Users\Ata\.claude\projects\C--Users-Ata\7032db82-389f-4606-af41-6141ec5d57f6\tool-results\bgi463nqm.txt` |
| Kardeş projeler | `Desktop\sozcuk`, `Desktop\tabcel` (arayüz ve yapı referansı) |

## 7. Bilinen sorunlar ve tuzaklar
- PyMuPDF: `add_freetext_annot` kenarlık rengini yalnızca zengin metinde kabul eder → kenarlık `EaglePDFKenar` anahtarıyla saklanıp kendi görünüm akışımızda çizilir; dolgu rengi `/C` içindedir (`colors['stroke']`).
- PyMuPDF ek açıklama nesnesi sayfaya zayıf bağlıdır: sayfa nesnesi canlı tutulmazsa `ReferenceError` (bkz. `_annot`).
- Form alanlarında Türkçe değer yazılınca PDF'in kendi alan görünümü (Helv) ş/ğ/ı için bozuk olabilir; `NeedAppearances` işaretlenir, uygulama içinde üstteki kutu doğru gösterir. Başka okuyucuda denenmedi.
- Ek açıklama taşıma: çizim, çizgi/ok ve işaretler (vurgu vb.) taşınamaz, silip yeniden eklenir.
- `QSpinBox` + stil sayfası Fusion'da boş kalıyor (metin alanı 1 px); sayfa kutusu bu yüzden `QLineEdit` tabanlı (`SayfaKutusu`).
- Bu ortamda uzun `python - <<heredoc` bazen kabukta ayrışmıyor; betikleri dosyaya yazıp çalıştır.
- Metin seçme kelime tabanlı (PyMuPDF kelime kutuları); sütunlu sayfalarda içerik sırasına göre seçer, görsel sıraya göre değil.
- Windows'ta açık PDF'in üzerine yazmak için PyMuPDF belgesi kapatılıp yeniden açılır (`Belge.kaydet`); testlenmiş.
- Bazı yazı tipleri boşluğu sert boşluk (U+00A0) üretir; aramada normalleştirilir.
- Offscreen Qt testlerinde yazı tipi yok (ekran görüntüsünde kutucuk çıkar); görsel kontrol gerçek platformda yapılır.
- Bölme kayıtlı dosya üzerinde çalışır (değişmiş belgede önce kaydetmek gerekir).
- RAM 7,9 GB ve dolu: REA analizi ve geliştirme sırasında Chrome/VS Code'u kapat.
- REA çıktıları çok büyük (2 MB+); bütünüyle okuma, süz.
- PDFgear bileşenleri: pdfium (açık), Tesseract (açık), Syncfusion/SautinSoft (ticari, kullanma).
- Git kimliği genel ayarda yer tutucu ("Ad Soyad"); bu repoda yerel olarak `Ata <ataeyvaz@gmail.com>` ayarlandı.
