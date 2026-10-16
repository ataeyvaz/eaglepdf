"""Çekirdek hata türleri (mesajlar kullanıcıya gösterilebilir, Türkçe)."""


class BelgeHatasi(Exception):
    """Kullanıcıya gösterilebilir (Türkçe mesajlı) hata."""


class ParolaGerekli(BelgeHatasi):
    pass
