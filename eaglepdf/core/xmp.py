"""XMP üst verisinde mevcut başlık/yazar/konu/anahtar sözcük alanlarını günceller (Qt'siz; lxml, BSD).

Yalnızca belgede *zaten bulunan* alanlar değiştirilir (yeni alan eklenmez, başka XMP verisine dokunulmaz);
değer boşsa alan silinir. Amaç: Info sözlüğü değişince XMP'deki eski değerin okuyucularda görünmesini önlemek.
"""
from __future__ import annotations

from lxml import etree

NS = {"rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "dc": "http://purl.org/dc/elements/1.1/",
      "pdf": "http://ns.adobe.com/pdf/1.3/"}
# özellik kimliği → (ad alanı, yerel ad)
ALANLAR = {"baslik": ("dc", "title"), "yazar": ("dc", "creator"), "konu": ("dc", "description"), "anahtar": ("pdf", "Keywords")}


def _q(onek: str, ad: str) -> str:
    return f"{{{NS[onek]}}}{ad}"


def guncelle(xmp: str, degerler: dict[str, str]) -> tuple[str, int]:
    """`degerler`: {'baslik': ..., 'yazar': ..., ...} → (yeni xmp, değiştirilen alan sayısı).
    Ayrıştırılamayan XMP olduğu gibi döner (0 değişiklik)."""
    try:
        ag = etree.ElementTree(etree.fromstring(xmp.encode("utf-8"), etree.XMLParser(remove_blank_text=False)))
    except etree.XMLSyntaxError:
        return xmp, 0
    kok = ag.getroot()
    degisen = 0
    for kimlik, deger in degerler.items():
        if kimlik not in ALANLAR:
            continue
        onek, ad = ALANLAR[kimlik]
        deger = deger.strip()
        nitelik = _q(onek, ad)
        for oge in kok.iter(nitelik):  # <dc:title>…</dc:title> biçimi
            _oge_guncelle(oge, deger)
            degisen += 1
        for tanim in kok.iter(_q("rdf", "Description")):  # nitelik biçimi: <rdf:Description pdf:Keywords="…">
            if nitelik in tanim.attrib:
                if deger:
                    tanim.set(nitelik, deger)
                else:
                    del tanim.attrib[nitelik]
                degisen += 1
    if not degisen:
        return xmp, 0
    return etree.tostring(ag, encoding="unicode"), degisen


def _oge_guncelle(oge, deger: str):
    if not deger:
        oge.getparent().remove(oge)
        return
    kapsayici = next((c for c in oge if c.tag in (_q("rdf", "Alt"), _q("rdf", "Seq"), _q("rdf", "Bag"))), None)
    if kapsayici is None:  # düz metin öğesi
        oge.text = deger
        return
    kayitlar = [c for c in kapsayici if c.tag == _q("rdf", "li")]
    for fazla in kayitlar[1:]:
        kapsayici.remove(fazla)
    if kayitlar:
        kayitlar[0].text = deger
    else:
        etree.SubElement(kapsayici, _q("rdf", "li")).text = deger
