import sys

import pytest

from eaglepdf.core import iliskilendirme as il

pytestmark = pytest.mark.skipif(il.winreg is None, reason="Yalnızca Windows")

TEST_TABAN = r"Software\EaglePDFTest\Classes"


@pytest.fixture(autouse=True)
def temizle():
    yield
    il._anahtar_sil(r"Software\EaglePDFTest")


def test_komut_bicimi():
    k = il.baslatici_komutu()
    assert k.startswith('"') and k.endswith('"%1"') and "main.py" in k


def test_kaydet_kayitli_kaldir():
    assert not il.kayitli_mi(TEST_TABAN)
    il.kaydet('"x.exe" "%1"', TEST_TABAN)
    assert il.kayitli_mi(TEST_TABAN)
    il.kaydet('"y.exe" "%1"', TEST_TABAN)  # tekrar kaydetmek zararsız
    assert il.kayitli_mi(TEST_TABAN)
    il.kaldir(TEST_TABAN)
    assert not il.kayitli_mi(TEST_TABAN)
    il.kaldir(TEST_TABAN)  # olmayanı silmek hata vermez


def test_baska_kayitlara_dokunmaz():
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{TEST_TABAN}\.pdf\OpenWithProgids") as k:
        winreg.SetValueEx(k, "Baska.PDF", 0, winreg.REG_NONE, b"")
    il.kaydet('"x.exe" "%1"', TEST_TABAN)
    il.kaldir(TEST_TABAN)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{TEST_TABAN}\.pdf\OpenWithProgids") as k:
        assert winreg.QueryValueEx(k, "Baska.PDF")
