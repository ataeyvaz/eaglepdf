# EaglePDF — süreç ve durum (2026-10-16)

Kalıcı kurallar için `CLAUDE.md`. Bu dosya: nerede kaldık, nasıl çalışıyoruz, sırada ne var.

## 1. Neredeyiz
| İş / modül | Hedef | Yapılan | Durum |
|---|---|---|---|
| Keşif: PDFgear | Özellik haritası | `pdfeditor.exe` REA ile tarandı; REA üye çıkarımı boş döndü (metadata kabul edilmedi), bunun yerine exe içi okunabilir kaynak adları süzüldü | ✅ |
| Proje iskeleti | klasör, git, CLAUDE.md, surec.md | oluşturuldu | ✅ |
| Özellik haritası (`docs/ozellikler.md`) | Tüm özellikler listelensin | Ad düzeyi harita + 5 faz önerisi yazıldı; ⚠ işaretliler elle gözlem bekler | ✅ (faz onayı bekliyor) |
| Uygulama iskeleti (PySide6) | pencere, menü, yardım | — | ⏳ |

Son commit: `ca6efcf` · Testler: henüz yok

## 2. Sıradaki işler (öncelik sırasıyla)
1. **Kullanıcıya faz sırasını onaylat** (`docs/ozellikler.md` sonu: 5 faz önerisi). Ayrıca Türkçe OCR verisi (`tur.traineddata`) PDFgear'da yok, ayrıca temin edilecek.
2. (İsteğe bağlı) ⚠ işaretli noktaları PDFgear'ı elle açıp gözlemle.
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
- 2026-10-16: **PyMuPDF kullanılacak, proje AGPL-3.0 açık kaynak** (GitHub'a konabilir) — kullanıcı ticaret/satış yapmayacak; izinli lisanslı alternatifler PyMuPDF kadar kapsamlı değil, "tüm özellikler" hedefi için PyMuPDF şart. (Önceki "PyMuPDF yok" kararı iptal.) Syncfusion/SautinSoft gibi ticari bileşenler yine kullanılmaz.

## 5. Açık sorular / bekleyenler
- Bulut/yapay zekâ özellikleri (sohbet, çeviri, çevrimiçi dönüştürme) haritada "dışarıda" bırakıldı; yerel karşılık istenirse karar verilecek.
- Arayüz: Sözcük/Tabcel görünümü kesin mi, yoksa MS Office şeridi mi? (Kullanıcı ikisini de uygun gördü; varsayılan: Eagle Office görünümü.)
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
- RAM 7,9 GB ve dolu: REA analizi ve geliştirme sırasında Chrome/VS Code'u kapat.
- REA çıktıları çok büyük (2 MB+); bütünüyle okuma, süz.
- PDFgear bileşenleri: pdfium (açık), Tesseract (açık), Syncfusion/SautinSoft (ticari, kullanma).
- Git kimliği genel ayarda yer tutucu ("Ad Soyad"); bu repoda yerel olarak `Ata <ataeyvaz@gmail.com>` ayarlandı.
