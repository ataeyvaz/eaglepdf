"""Tespit raporlarını JSON / CSV olarak dışa aktarır."""
from __future__ import annotations

import csv
import json
from datetime import datetime

from .detector import KIND_LABELS


def export_json(results, path: str) -> None:
    data = {
        "olusturma": datetime.now().isoformat(timespec="seconds"),
        "dosyalar": [
            {"dosya": r.path, "sayfa_sayisi": r.page_count, "metadata": r.metadata,
             "filigranlar": [f.to_dict() for f in r.findings]}
            for r in results
        ],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def export_csv(results, path: str) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["dosya", "bulgu", "tur", "baslik", "guven", "secili", "sayfa",
                    "x0", "y0", "x1", "y1", "pdf_adresi", "adresler_url"])
        for r in results:
            for f in r.findings:
                if not f.occurrences:          # belge bilgileri gibi sayfadan bağımsız bulgular
                    w.writerow([r.path, f.id, KIND_LABELS.get(f.kind, f.kind), f.title, f"{f.score:.2f}",
                                "evet" if f.selected else "hayır", "", "", "", "", "",
                                f.text.replace("\n", " | "), " ".join(f.urls)])
                for o in f.occurrences:
                    w.writerow([r.path, f.id, KIND_LABELS.get(f.kind, f.kind), f.title,
                                f"{f.score:.2f}", "evet" if f.selected else "hayır", o.page + 1,
                                *[f"{v:.1f}" for v in o.bbox], o.address, " ".join(f.urls)])
