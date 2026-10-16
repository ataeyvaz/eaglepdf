"""PDF'e gömülecek Türkçe karakterli yazı tipi: Noto Sans (SIL OFL 1.1, `pymupdf-fonts` paketiyle gelir).

PDF'in yerleşik Helvetica'sı ş, ğ, ı, İ gibi harfleri içermez; metin kutusu, filigran, üstbilgi gibi her yazı
ekleme işlemi bu modüldeki yazı tipini kullanır.
"""

import pymupdf
import pymupdf_fonts

_AD = {(False, False): "notos", (True, False): "notosbo", (False, True): "notosit", (True, True): "notosbi"}
_KAYNAK = {(False, False): "NotoR", (True, False): "NotoB", (False, True): "NotoI", (True, True): "NotoBI"}
_onbellek: dict[tuple[bool, bool], bytes] = {}


def tampon(kalin: bool = False, italik: bool = False) -> bytes:
    anahtar = (bool(kalin), bool(italik))
    if anahtar not in _onbellek:
        _onbellek[anahtar] = pymupdf_fonts.myfont(_AD[anahtar])
    return _onbellek[anahtar]


def kaynak_adi(kalin: bool = False, italik: bool = False) -> str:
    """PDF sayfa kaynaklarında kullanılan yazı tipi adı (değişkenler arasında çakışmaz)."""
    return _KAYNAK[(bool(kalin), bool(italik))]


def font(kalin: bool = False, italik: bool = False) -> pymupdf.Font:
    return pymupdf.Font(fontbuffer=tampon(kalin, italik))
