"""Filigran Temizle penceresi (offscreen Qt): tarama, seçim, önizleme, elle alan, kural, temizleme, ana pencere bağlantısı."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pymupdf as fitz
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from eaglepdf.core.filigran import rules
from eaglepdf.ui import filigran_penceresi, theme
from eaglepdf.ui.filigran_penceresi import FiligranPenceresi
from eaglepdf.ui.pencere import AnaPencere

SAYFA = 5


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.apply(a)
    return a


@pytest.fixture(autouse=True)
def kural_klasoru(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))   # kurallar gerçek %APPDATA%'ya yazılmasın


@pytest.fixture
def ornek(tmp_path):
    yol = str(tmp_path / "ornek.pdf")
    doc = fitz.open()
    for i in range(SAYFA):
        p = doc.new_page()
        p.insert_text((50, 100), f"Soru {i + 1}: Ucgenin ic acilari toplami kactir?", fontsize=12)
        p.insert_text((120, 600), "GIZLI www.ornekyayin.com", fontsize=40, morph=(fitz.Point(120, 600), fitz.Matrix(45)),
                      fill_opacity=0.25, color=(0.5, 0.5, 0.5))
    doc.save(yol)
    doc.close()
    return yol


def bekle(kosul, saniye=60.0):
    bitis = time.time() + saniye
    while time.time() < bitis:
        QApplication.processEvents()
        if kosul():
            return True
        time.sleep(0.01)
    return kosul()


def taranmis(app, yol):
    d = FiligranPenceresi(None, yol)
    d.tara()
    assert bekle(lambda: d.sonuc is not None)
    return d


def test_tarama_bulgulari_listeler_ve_otomatik_secer(app, ornek):
    d = taranmis(app, ornek)
    assert d.agac.topLevelItemCount() >= 1
    assert any("GIZLI" in f.text and f.selected for f in d.sonuc.findings)
    assert d.sayfa_etiket.text() == f"Sayfa {d._sayfa + 1} / {SAYFA}"
    assert d.onizleme.pixmap() is not None and not d.onizleme.pixmap().isNull()


def test_telif_onayi_olmadan_silinemez(app, ornek):
    d = taranmis(app, ornek)
    assert d.secili_bulgular()
    assert not d.temizle_dugme.isEnabled()
    d.telif.setChecked(True)
    assert d.temizle_dugme.isEnabled()
    for f in d.sonuc.findings:   # seçim kalmazsa yine kapalı
        d._ogeler[f.id].setCheckState(0, filigran_penceresi.Qt.Unchecked)
    assert not d.temizle_dugme.isEnabled()


def test_sonra_onizlemesi_ve_navigasyon(app, ornek):
    d = taranmis(app, ornek)
    d.sonra_kutu.setChecked(True)
    assert not d.onizleme.pixmap().isNull()
    d.sonraki.click()
    assert d._sayfa == 1 or d._sayfa == min(d._ilk_sayfa() + 1, SAYFA - 1)
    d._sayfaya_git(999)
    assert d._sayfa == SAYFA - 1 and not d.sonraki.isEnabled()


def test_elle_alan_isaretleme_bulgu_ekler(app, ornek):
    d = taranmis(app, ornek)
    onceki = len(d.sonuc.findings)
    d._sayfaya_git(0)
    d._alan_secildi(fitz.Rect(40, 85, 400, 110))   # gerçek metin satırı
    assert len(d.sonuc.findings) > onceki
    assert any(f.id.startswith("M") for f in d.sonuc.findings)
    assert d.agac.topLevelItemCount() == len(d.sonuc.findings)


def test_kural_kaydet_uygula_sil(app, ornek, monkeypatch):
    d = taranmis(app, ornek)
    monkeypatch.setattr(filigran_penceresi.QInputDialog, "getText", staticmethod(lambda *a, **k: ("Deneme", True)))
    d._kural_kaydet()
    assert [r["name"] for r in rules.load_rules()] == ["Deneme"] and d.kural_kutu.count() == 1
    for f in d.sonuc.findings:
        f.selected = False
    d._kurali_uygula()
    assert d.secili_bulgular()
    monkeypatch.setattr(filigran_penceresi.QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    d._kural_sil()
    assert rules.load_rules() == []


def test_temizle_yeni_dosya_yazar_orijinal_degismez(app, ornek, tmp_path, monkeypatch):
    onceki = open(ornek, "rb").read()
    cikti = str(tmp_path / "temiz.pdf")
    d = taranmis(app, ornek)
    d.telif.setChecked(True)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (cikti, "")))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.Ok))
    kaydedilen = []
    d.temizKaydedildi.connect(kaydedilen.append)
    d.temizle()
    assert bekle(lambda: kaydedilen)
    assert kaydedilen == [cikti] and os.path.exists(cikti)
    assert open(ornek, "rb").read() == onceki
    metin = "".join(p.get_text() for p in fitz.open(cikti))
    assert "GIZLI" not in metin and "Soru 1" in metin


def test_orijinalin_uzerine_yazmayi_reddeder(app, ornek, monkeypatch):
    d = taranmis(app, ornek)
    d.telif.setChecked(True)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (ornek, "")))
    uyarilar = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: uyarilar.append(a)))
    d.temizle()
    assert uyarilar and not d._mesgul()


def test_hatali_sayfa_araligi_uyarir(app, ornek, monkeypatch):
    d = taranmis(app, ornek)
    d.telif.setChecked(True)
    d.yalniz.setText("abc")
    uyarilar = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: uyarilar.append(a)))
    d.temizle()
    assert uyarilar


def test_rapor_json_ve_csv(app, ornek, tmp_path, monkeypatch):
    d = taranmis(app, ornek)
    for uzanti in ("json", "csv"):
        yol = str(tmp_path / f"rapor.{uzanti}")
        monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, y=yol, **k: (y, "")))
        d._rapor()
        assert os.path.getsize(yol) > 0


def test_ana_pencere_menusu_ve_kaydedilmemis_belge(app, ornek, tmp_path, monkeypatch):
    p = AnaPencere(str(tmp_path / "ayar.ini"))
    try:
        assert p.e_fil_temizle in p.m_duzenle.actions()
        assert not p.e_fil_temizle.isEnabled()          # belge yokken kapalı
        p.ac(ornek)
        assert p.e_fil_temizle.isEnabled()
        acilan = []
        monkeypatch.setattr(FiligranPenceresi, "exec", lambda self: acilan.append(self.yol) or 0)
        p.filigran_temizle_ac()
        assert acilan == [str(p.belge.yol)]
    finally:
        for o in p._oturumlar:
            o.belge.degisti = False
        p.close()
