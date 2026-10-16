"""Türkçe büyük/küçük harf dönüşümü — TEK kaynak (T1). Qt yok, harici kütüphane yok.

Python'un `str.upper()/lower()` Türkçe kuralını bilmez: `"I".lower()` → `"i"` (olması gereken `"ı"`), `"i".upper()` →
`"I"` (olması gereken `"İ"`), `"İ".lower()` → `"i̇"` (i + birleşik nokta). Kullanıcının yazdığı metin (hücre, sözcük, sayfa
ya da ad) büyük/küçük harf duyarsız karşılaştırılacak ya da dönüştürülecekse YALNIZ bu modül kullanılır; `str.upper/lower/
casefold` yalnız ASCII teknik dizgilerde (onaltılık renk, İngilizce fonksiyon/hata adı…) serbesttir.

Excel/Windows davranışı: `İstanbul → istanbul`, `Izmir → ızmir`, `ılık → ILIK`, `Çorum → ÇORUM`, `Şile → ŞİLE`.
Bilerek DEĞİŞMEYEN (önceki dört kopyayla birebir aynı davranış): diğer harfler Python kuralıyla çevrilir
(`ß.upper()` → `SS`; Excel'in `ß` davranışı doğrulanmadı → surec.md §8b).
"""


def kucuk(metin: str) -> str:
    """Türkçe küçük harf: I → ı, İ → i."""
    return metin.replace("I", "ı").replace("İ", "i").lower()


def buyuk(metin: str) -> str:
    """Türkçe büyük harf: i → İ, ı → I."""
    return metin.replace("i", "İ").replace("ı", "I").upper()


def esit_mi(a: str, b: str) -> bool:
    """Büyük/küçük harf duyarsız (Türkçe) eşitlik."""
    return kucuk(a) == kucuk(b)


# Eski adlar (yerel.py, harmanla.py, doldur.py, sayi_bicimi.py bunlarla içe aktarıyordu)
tr_kucuk = kucuk
tr_buyuk = buyuk
