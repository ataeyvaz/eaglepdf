"""Tek örnek: ikinci kez başlatılan uygulama dosyalarını çalışan pencereye gönderip kapanır (her dosya bir sekme).

Yerel soket (Windows'ta adlandırılmış boru) kullanılır; ağa çıkmaz, yalnızca bu kullanıcı erişir. Mesaj: tek satır JSON
`{"ac": [mutlak yollar]}`. Alıcı yalnızca mutlak `.pdf` yollarını kabul eder, boyut ve sayı sınırlıdır.
"""
from __future__ import annotations

import json
import os
import re
import time

from PySide6.QtCore import QCoreApplication, QDir, QLockFile, QObject, QThread, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from .. import APP_NAME

EN_COK_BAYT = 64 * 1024      # tek mesajın üst sınırı
EN_COK_YOL = 64              # bir mesajdaki en çok dosya
EN_COK_YOL_UZUNLUGU = 4096


def sunucu_adi() -> str:
    """Kullanıcıya özel soket adı (aynı bilgisayarda başka kullanıcının örneğiyle karışmaz)."""
    kullanici = re.sub(r"[^A-Za-z0-9_.-]", "_", os.environ.get("USERNAME") or os.environ.get("USER") or "kullanici")
    return f"{APP_NAME}-tek-ornek-{kullanici}"


def gonder(ad: str, yollar: list[str], zaman_asimi_ms: int = 700) -> bool:
    """Çalışan örneğe dosya listesini yollar (boş liste = yalnızca öne getir). True: bir örnek vardı ve mesajı aldı."""
    soket = QLocalSocket()
    soket.connectToServer(ad)
    if not soket.waitForConnected(zaman_asimi_ms):
        return False
    soket.write(json.dumps({"ac": [str(y) for y in yollar]}).encode("utf-8") + b"\n")
    # Windows'ta yazma taşmalı (overlapped) tamamlanır: tamamlanması bu iş parçacığının olay işlemesine bağlıdır.
    # waitForBytesWritten tek başına False dönebilir; bu yüzden "yazılmamış bayt kalmadı"yı olay işleyerek bekleriz.
    bitis = time.monotonic() + zaman_asimi_ms / 1000
    ana_is_parcacigi = QThread.currentThread() is QCoreApplication.instance().thread()
    while soket.bytesToWrite() > 0 and time.monotonic() < bitis:
        soket.waitForBytesWritten(50)
        if ana_is_parcacigi:   # başka iş parçacığından olay işlemek güvenli değil
            QCoreApplication.processEvents()
    yazildi = soket.bytesToWrite() == 0
    soket.disconnectFromServer()
    if soket.state() != QLocalSocket.UnconnectedState:
        soket.waitForDisconnected(zaman_asimi_ms)
    return yazildi


def mesaji_coz(ham: bytes) -> list[str] | None:
    """Gelen mesajdan güvenli yol listesi; geçersiz/yanlış biçimliyse None."""
    try:
        veri = json.loads(ham.decode("utf-8"))
        yollar = veri["ac"]
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return None
    if not isinstance(yollar, list):
        return None
    temiz = []
    for y in yollar[:EN_COK_YOL]:
        if (isinstance(y, str) and 0 < len(y) <= EN_COK_YOL_UZUNLUGU and os.path.isabs(y)
                and y.lower().endswith(".pdf") and y not in temiz):
            temiz.append(y)
    return temiz


class TekOrnekSunucu(QObject):
    istekGeldi = Signal(list)   # açılacak (süzülmüş) dosya yolları; boş olabilir (yalnızca öne getir)

    def __init__(self, ad: str | None = None, parent=None):
        super().__init__(parent)
        self.ad = ad or sunucu_adi()
        self._sunucu: QLocalServer | None = None
        self._kilit: QLockFile | None = None
        self._tamponlar: dict[QLocalSocket, bytearray] = {}

    @property
    def calisiyor(self) -> bool:
        return self._sunucu is not None and self._sunucu.isListening()

    def baslat(self) -> bool:
        """Dinlemeye başlar. False: başka bir süreç zaten çalışan örnek (kilit onda) ya da kurulamadı.
        Adlandırılmış boru aynı ada ikinci sunucuyu kabul edebildiği için *tek* örnek garantisi atomik bir dosya
        kilidiyle (`QLockFile`) sağlanır; ölü sürecin kilidi Qt tarafından bayat sayılıp temizlenir."""
        if self.calisiyor:
            return True
        kilit = QLockFile(os.path.join(QDir.tempPath(), f"{self.ad}.lock"))
        if not kilit.tryLock(0):
            return False
        sunucu = QLocalServer(self)
        sunucu.setSocketOptions(QLocalServer.UserAccessOption)
        QLocalServer.removeServer(self.ad)   # kilidi biz aldık: bu ada ait ölü kayıt varsa temizle (Windows'ta zararsız)
        if not sunucu.listen(self.ad):
            sunucu.deleteLater()
            kilit.unlock()
            return False
        self._kilit = kilit
        sunucu.newConnection.connect(self._yeni_baglanti)
        self._sunucu = sunucu
        return True

    def durdur(self):
        if self._sunucu is not None:
            self._sunucu.close()
            self._sunucu.deleteLater()
            self._sunucu = None
        if self._kilit is not None:
            self._kilit.unlock()
            self._kilit = None
        for s in list(self._tamponlar):
            s.abort()
        self._tamponlar.clear()

    def _yeni_baglanti(self):
        while self._sunucu is not None and self._sunucu.hasPendingConnections():
            soket = self._sunucu.nextPendingConnection()
            self._tamponlar[soket] = bytearray()
            soket.readyRead.connect(lambda s=soket: self._oku(s))
            soket.disconnected.connect(lambda s=soket: self._bitir(s))

    def _oku(self, soket: QLocalSocket):
        tampon = self._tamponlar.get(soket)
        if tampon is None:
            return
        tampon += bytes(soket.readAll())
        if len(tampon) > EN_COK_BAYT:   # aşırı büyük mesaj: reddet
            self._tamponlar.pop(soket, None)
            soket.abort()
            return
        if b"\n" in tampon:
            self._isle(soket)

    def _bitir(self, soket: QLocalSocket):
        if soket in self._tamponlar:
            self._oku(soket)
            if soket in self._tamponlar:   # satır sonu gelmeden bağlantı kapandı: eldekini dene
                self._isle(soket)
        soket.deleteLater()

    def _isle(self, soket: QLocalSocket):
        tampon = self._tamponlar.pop(soket, None)
        if tampon is None:
            return
        yollar = mesaji_coz(bytes(tampon).split(b"\n", 1)[0])
        if yollar is not None:
            self.istekGeldi.emit(yollar)


def baslat_veya_devret(yollar: list[str], ad: str | None = None) -> tuple[bool, TekOrnekSunucu | None]:
    """Açılışta çağrılır → (devredildi, sunucu).
    Çalışan örnek varsa dosyalar ona gönderilir (devredildi=True, çağıran kapanır). Yoksa bu süreç sunucu olur.
    İki süreç aynı anda başlarsa kaybeden, kazananı bulup devreder; kimse bulunamazsa sunucusuz devam eder."""
    ad = ad or sunucu_adi()
    if gonder(ad, yollar):
        return True, None
    sunucu = TekOrnekSunucu(ad)
    if sunucu.baslat():
        return False, sunucu
    if gonder(ad, yollar, 1500):   # yarışta kaybettik: diğeri artık dinliyor olmalı
        return True, None
    return False, None
