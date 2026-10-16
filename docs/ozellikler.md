# PDFgear özellik haritası (davranış tarifi)

Kaynak: `pdfeditor.exe` ve `pdfconverter.exe` içindeki arayüz/kaynak adları (yalnızca ad düzeyi, REA statik tarama + okunabilir metin çıkarımı) ve kurulu klasörün yapısı. Kod, görsel veya metin alınmadı; aşağıdakiler **ne yaptığının** kendi sözlerimizle tarifidir. Tarih: 2026-10-16.

> Durum: ad düzeyi keşif. Ayrıntılar (varsayılan değerler, kenar durumlar) uygulamayı elle gözlemleyerek eklenecek (⚠ = gözlem gerekir).

## A. Görüntüleme ve gezinme
| Özellik | Davranış |
|---|---|
| Açma / sekmeler | Birden çok PDF; son kullanılanlar; parolalı dosya için parola penceresi |
| Sayfa görünümü | Tek / çift, sürekli / sürekli değil; yakınlaştırma, genişliğe/yüksekliğe/gerçek boyuta sığdır, tam ekran |
| Gezinme paneli | Küçük resimler, yer imleri (ekle, alt yer imi, yeniden adlandır, sil), ek açıklama listesi, ekler paneli |
| Arama | Belge içinde metin arama, sonuç listesi |
| Okuma | Sunum (tam ekran) modu, otomatik kaydırma (hız ayarlı), el aracı / metin seçme aracı, gece-gündüz teması |
| Yazdırma | Yazdırma penceresi; **toplu yazdırma** (dosya listesi, ayarlar tümüne/seçilene); "yazdırılamaz" uyarısı |
| Belge özellikleri | Başlık, yazar, konu, anahtar sözcük, oluşturan, tarihler, boyut, sayfa sayısı |
| Ayarlar | Dil, varsayılan görünüm/seçim modu, dosya ilişkilendirme, açılışta araç/durum çubuğu, boş sayfa boyutu, yazar adı, otomatik kayıt/yedek |

## B. Sayfa işlemleri
Sayfa sil · çıkar · döndür (sol/sağ) · boş sayfa ekle · yeni PDF oluştur · birleştir · böl · kırp (kenar boşlukları, birim: cm/inç/mm/pt/pica, sayfa aralığı) · boyut değiştir · sayfa numarası · üstbilgi/altbilgi · arka plan · filigran · küçük resimlerde sürükle-bırak sıralama.

## C. Düzenleme
| Özellik | Davranış |
|---|---|
| Metin düzenleme | Sayfadaki metin nesnesini seçip yazı tipi/boyut/renk/kalın/italik ile değiştirme |
| Metin kutusu, resim | Yeni metin/resim ekleme; resim taşı/boyutlandır/döndür/çevir; ekran görüntüsü alıp ekleme |
| Bağlantı | Sayfa/URL bağlantısı oluştur-düzenle |
| Mühür (stamp) | Hazır ("Approved", "Confidential"…) + özel mühür oluştur/yönet/düzenle; çok sayfaya uygula |
| Kaldırma (redaction) | Seçilen içeriği kalıcı silme |
| Düzleştirme | Ek açıklama/form alanlarını sayfaya gömme (tek/toplu) |

## D. Ek açıklama (annotation)
Vurgula · alanı vurgula · altını çiz · üstünü çiz · düz çizgi/ok · kare/daire · serbest çizim (ink) + silgi · not · metin kutusu · dosya eki. Özellik panelinde renk, kalınlık, yazı tipi, "varsayılana uygula". Ek açıklama yönetimi: listele, kullanıcıya/türe göre süz, toplu sil.

## E. Form ve imza
| Özellik | Davranış |
|---|---|
| Form doldurma | AcroForm alanlarını doldur, alan vurgulama ayarı |
| İmza (görsel) | Çiz/yaz/resimden imza oluştur; birkaç imza sakla; sayfalara uygula |
| Dijital imza | Sertifika (.pfx) ile imzalama; sertifika yöneticisi; kimlik içe aktarma; imza doğrulama durumu ve özellikleri; ertelenmiş imza alanı |

## F. Güvenlik
Parola ekle (açma/sahip parolası, izinler) · parolayı kaldır · sahip parolası denetimi · yazdırılamaz belge uyarısı.

## G. OCR ve metin
| Özellik | Davranış |
|---|---|
| Aranabilir PDF | Taranmış PDF'e görünmez metin katmanı ekler; dil seçimi |
| Ekran görüntüsünden OCR / metin çıkarma | Seçilen alandaki metni okuyup kopyalatır |
| Çıkarılan metni gösterme | Sonuç penceresi |
| Dil verisi | Tesseract (kurulu klasörde Çince, Almanca, Fransızca, İtalyanca, Japonca, Korece, Felemenkçe, Portekizce, Rusça, İspanyolca, İngilizce; **Türkçe yok**) |

## H. Dönüştürme ve araçlar (ayrı uygulama: pdfconverter)
| Yön | Çıktı / girdi |
|---|---|
| PDF → | Word, Excel, resim (DPI, renk modu, kenarlık, tek resim/sayfa başına), PowerPoint, metin, HTML (⚠ doğrulanacak) |
| → PDF | Resim (çoklu: tek PDF ya da her resim ayrı; sayfa boyutu/yön/kenar boşluğu/sığdırma), Word, Excel, HTML (⚠) |
| Sıkıştır | Düşük / orta / yüksek; toplu; önce-sonra boyut |
| Birleştir / Böl | Dosya listesi, sıra, aralığa göre bölme |
| Karşılaştır | İki belgeyi karşılaştırma penceresi |
| Tarayıcıdan ekle | WIA tarayıcıdan sayfa alıp PDF yapma |
| Paylaş | E-posta ile gönderme, telefona aktarma (QR) |

## I. Bulut / yapay zekâ (CLAUDE.md kural 5: yapılmaz)
Sohbet / Copilot (PDF'le sohbet), çeviri, çevrimiçi dönüştürme, hesap/giriş, abonelik/satın alma, güncelleme ve anket pencereleri. Kullanıcı isterse yerel çeviri/özet ayrı bir karar olarak ele alınır; varsayılan: **dışarıda**.

## Önerilen fazlar (onay bekliyor)
1. **Faz 1 – Okuyucu ve sayfa işlemleri:** A, B (sil/çıkar/döndür/ekle/birleştir/böl/sırala), kayıt düzeni, Yardım.
2. **Faz 2 – Ek açıklama ve form:** D, E (form doldurma, görsel imza), bağlantı, yer imi.
3. **Faz 3 – Düzenleme:** C (metin/resim/mühür/redaction/düzleştirme), kırp, filigran, üstbilgi, numara, arka plan.
4. **Faz 4 – Dönüştürme ve sıkıştırma:** H (resim, Word, Excel, metin, → PDF), sıkıştır, karşılaştır.
5. **Faz 5 – OCR, koruma, dijital imza:** G, F, E (sertifikalı imza), tarayıcı, toplu yazdırma.
