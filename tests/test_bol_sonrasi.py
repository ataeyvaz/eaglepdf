import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from eaglepdf.ui import pencere as pencere_modulu
from eaglepdf.ui import theme
from eaglepdf.ui.oturum import EN_COK_SEKME
from eaglepdf.ui.pencere import AnaPencere
from test_belge import pdf_yap


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.apply(a)
    return a


@pytest.fixture
def pencere(app, tmp_path):
    p = AnaPencere(str(tmp_path / "ayar.ini"))
    p.show()
    yield p
    for o in p._oturumlar:
        o.belge.degisti = False
    p.close()


def adlar(p):
    return [o.belge.yol.name for o in p._oturumlar]


def secim(monkeypatch, dugme: str):
    """`_parcalari_ac_sor` kutusunda `dugme` ('Hepsini Aç' | 'Klasörü Göster' | 'Kapat') seçilmiş gibi davran."""
    gorulen = []

    def exec_(self_):
        gorulen.append(self_.text())
        return 0
    monkeypatch.setattr(QMessageBox, "exec", exec_)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self_: next(b for b in self_.buttons() if b.text() == dugme))
    return gorulen


def bol_ayarla(monkeypatch, pencere, klasor, parcalar):
    monkeypatch.setattr(pencere_modulu.BolPenceresi, "exec", lambda self_: setattr(self_, "parcalar", parcalar) or True)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(klasor)))


def test_bol_hepsini_ac_parcalari_sekmede_acar(pencere, tmp_path, monkeypatch):
    pencere.ac(str(pdf_yap(tmp_path / "ana.pdf", 6)))
    klasor = tmp_path / "parcalar"
    bol_ayarla(monkeypatch, pencere, klasor, [[0, 1], [2, 3], [4, 5]])
    gorulen = secim(monkeypatch, "Hepsini Aç")
    pencere.bol()
    assert gorulen and "3 dosya yazıldı" in gorulen[0]
    assert adlar(pencere) == ["ana.pdf", "ana_1.pdf", "ana_2.pdf", "ana_3.pdf"] and pencere._etkin == 3
    assert [o.belge.sayfa_sayisi for o in pencere._oturumlar] == [6, 2, 2, 2]
    assert sorted(p.name for p in klasor.glob("*.pdf")) == ["ana_1.pdf", "ana_2.pdf", "ana_3.pdf"]


def test_bol_kapat_dosyalari_yazar_ama_acmaz(pencere, tmp_path, monkeypatch):
    pencere.ac(str(pdf_yap(tmp_path / "ana.pdf", 4)))
    bol_ayarla(monkeypatch, pencere, tmp_path / "p", [[0, 1], [2, 3]])
    secim(monkeypatch, "Kapat")
    pencere.bol()
    assert adlar(pencere) == ["ana.pdf"] and len(list((tmp_path / "p").glob("*.pdf"))) == 2
    assert "2 dosya yazıldı" in pencere.statusBar().currentMessage()


def test_bol_klasoru_goster(pencere, tmp_path, monkeypatch):
    pencere.ac(str(pdf_yap(tmp_path / "ana.pdf", 4)))
    klasor = tmp_path / "p"
    bol_ayarla(monkeypatch, pencere, klasor, [[0, 1], [2, 3]])
    secim(monkeypatch, "Klasörü Göster")
    acilan = []
    monkeypatch.setattr(pencere_modulu.QDesktopServices, "openUrl", staticmethod(lambda u: acilan.append(u.toLocalFile())))
    pencere.bol()
    assert [Path(a) for a in acilan] == [klasor] and adlar(pencere) == ["ana.pdf"]


def test_bol_sekme_siniri_tek_uyari(pencere, tmp_path, monkeypatch):
    for i in range(EN_COK_SEKME - 1):   # 1 boş yer kalsın (ana belge dahil)
        pencere.ac(str(pdf_yap(tmp_path / f"x{i}.pdf", 1)))
    pencere.ac(str(pdf_yap(tmp_path / "ana.pdf", 6)))
    assert len(pencere._oturumlar) == EN_COK_SEKME
    bol_ayarla(monkeypatch, pencere, tmp_path / "p", [[0, 1], [2, 3], [4, 5]])
    secim(monkeypatch, "Hepsini Aç")
    bilgi = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: bilgi.append(a[2])))
    pencere.bol()
    assert len(pencere._oturumlar) == EN_COK_SEKME and len(bilgi) == 1 and "3 dosya" in bilgi[0]


def test_bol_acik_sekmenin_dosyasini_ezmez(pencere, tmp_path, monkeypatch):
    klasor = tmp_path / "p"
    klasor.mkdir()
    pencere.ac(str(pdf_yap(klasor / "ana_2.pdf", 1)))     # <ad>_2.pdf adlı başka bir belge açık
    pencere.ac(str(pdf_yap(tmp_path / "ana.pdf", 4)))
    once = (klasor / "ana_2.pdf").read_bytes()
    bol_ayarla(monkeypatch, pencere, klasor, [[0, 1], [2, 3]])
    secim(monkeypatch, "Hepsini Aç")
    uyari = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: uyari.append(a[2])))
    pencere.bol()
    assert uyari and "ana_2.pdf" in uyari[0]
    assert (klasor / "ana_2.pdf").read_bytes() == once and not (klasor / "ana_1.pdf").exists()   # hiçbir şey yazılmadı


def test_bol_kaydedilmemis_belgede_hala_uyarir(pencere, tmp_path, monkeypatch):
    pencere.ac(str(pdf_yap(tmp_path / "ana.pdf", 4)))
    pencere.belge.ozellikleri_ata(baslik="x")
    bilgi = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: bilgi.append(a[2])))
    pencere.bol()
    assert bilgi and "kaydedin" in bilgi[0]
