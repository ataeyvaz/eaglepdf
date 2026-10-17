"""Uygulama simgesini (eaglepdf.ico) üretir: beyaz yuvarlatılmış kare + kırmızı çerçeve + kartal logosu.
Koyu görev çubuğunda da görünür. Çalıştırma: python yapi/ikon_uret.py"""
from pathlib import Path

from PIL import Image, ImageDraw

KOK = Path(__file__).resolve().parents[1]
BOYUTLAR = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
KIRMIZI = "#c62828"   # eaglepdf/ui/theme.py ACCENT ile aynı


def ciz(boyut: int = 512) -> Image.Image:
    tuval = Image.new("RGBA", (boyut, boyut), (0, 0, 0, 0))
    d = ImageDraw.Draw(tuval)
    pay, yaricap = int(boyut * 0.04), int(boyut * 0.20)
    d.rounded_rectangle([pay, pay, boyut - pay, boyut - pay], radius=yaricap, fill="white", outline=KIRMIZI, width=int(boyut * 0.045))
    logo = Image.open(KOK / "eaglepdf" / "eagle-office-logo.png").convert("RGBA")
    hedef = int(boyut * 0.74)
    oran = hedef / max(logo.size)
    logo = logo.resize((round(logo.width * oran), round(logo.height * oran)), Image.LANCZOS)
    tuval.alpha_composite(logo, ((boyut - logo.width) // 2, (boyut - logo.height) // 2 + int(boyut * 0.01)))
    return tuval


if __name__ == "__main__":
    buyuk = ciz()
    hedef = Path(__file__).with_name("eaglepdf.ico")
    buyuk.save(hedef, format="ICO", sizes=BOYUTLAR)
    print("yazıldı:", hedef, hedef.stat().st_size, "bayt")
