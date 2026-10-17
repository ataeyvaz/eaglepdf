"""Kural şablonları: seçilen filigranların imzalarını kaydedip başka dosyalarda uygular.

Kural biçimi (rules.json):
  [{"name": "EDİTÖR YAYINLARI", "matches": [{"kind": "ocg", "ocg_name": "Watermark"}, ...]}]
"""
from __future__ import annotations

import json
import os
import re

from ... import APP_NAME


def _base() -> str:
    return os.environ.get("APPDATA") or os.path.expanduser("~")


def rules_path() -> str:
    """Kurallar APPDATA altındaki uygulama klasöründe `filigran_kurallari.json` olarak tutulur (klasör yoksa oluşturulur)."""
    folder = os.path.join(_base(), APP_NAME)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "filigran_kurallari.json")


def legacy_rules_path() -> str:
    """Eski tek başına uygulamanın (PDF Filigran Temizleyici / pdfedit) kural dosyası; yalnızca okunur."""
    return os.path.join(_base(), "PDFFiligran", "rules.json")


def _norm(v):
    return re.sub(r"\s+", " ", v).strip().casefold() if isinstance(v, str) else v


def signature_matches(sig: dict, pattern: dict) -> bool:
    """Desendeki her anahtar imzada aynı değere sahipse eşleşir."""
    if not pattern:
        return False
    return all(_norm(sig.get(k)) == _norm(v) for k, v in pattern.items())


def load_rules() -> list[dict]:
    """Kuralları okur. EaglePDF'in kendi dosyası henüz yoksa eski uygulamanın kurallarını (varsa) bir kez devralır:
    eski dosya okunur, değiştirilmez; ilk `save_rules` kendi dosyamıza yazar."""
    yol = rules_path()
    if not os.path.exists(yol) and os.path.exists(legacy_rules_path()):
        yol = legacy_rules_path()
    try:
        with open(yol, encoding="utf-8") as fh:
            data = json.load(fh)
        return [r for r in data if isinstance(r, dict) and r.get("matches")]
    except (OSError, ValueError):
        return []


def save_rules(rules: list[dict]) -> None:
    with open(rules_path(), "w", encoding="utf-8") as fh:
        json.dump(rules, fh, ensure_ascii=False, indent=2)


def add_rule(name: str, findings) -> dict:
    rules = [r for r in load_rules() if r["name"] != name]
    rule = {"name": name, "matches": [f.signature for f in findings]}
    rules.append(rule)
    save_rules(rules)
    return rule


def delete_rule(name: str) -> None:
    save_rules([r for r in load_rules() if r["name"] != name])


def apply_rule(rule: dict, findings) -> int:
    """Kurala uyan bulguları seçer, diğerlerinin seçimini kaldırır. Seçilen sayısını döndürür."""
    count = 0
    for f in findings:
        f.selected = any(signature_matches(f.signature, m) for m in rule["matches"])
        count += f.selected
    return count
