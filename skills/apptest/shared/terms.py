#!/usr/bin/env python3
"""apptest — kullanıcıya görünen metinde aranan sözcükler, dil başına tek yerde.
Tarayıcılar uygulamanın metnine bakar; o metin hangi dildeyse kural o dilde çalışmalı. Yeni dil buraya eklenir.
Kapsam: EN, TR, DE, IT, ES, FR, PT. Listede yoksa kural o dilde aday üretemez ya da yanlış alarm verir:
regressions.py her kavramı her dilde dener. Yalnız standart kütüphane."""
from __future__ import annotations

_T = {
    "restore": {
        "en": r"restore( purchases?)?", "tr": r"geri yükle|satın alımları geri", "de": r"wiederherstellen",
        "it": r"ripristina", "es": r"restaurar", "fr": r"restaurer", "pt": r"restaurar|repor compras"},
    "terms": {
        "en": r"terms of (use|service)|\beula\b", "tr": r"kullanım koşulları", "de": r"nutzungsbedingungen|\bagb\b",
        "it": r"termini (di|d')|condizioni d'uso", "es": r"términos de (uso|servicio)|condiciones de uso",
        "fr": r"conditions d'utilisation", "pt": r"termos de (uso|serviço)"},
    "privacy": {
        "en": r"privacy", "tr": r"gizlilik|kvkk", "de": r"datenschutz", "it": r"privacy|riservatezza",
        "es": r"privacidad", "fr": r"confidentialit", "pt": r"privacidade"},
    "auto_renew": {
        "en": r"auto[- ]?renew|automatically renew|renews automatically|cancel anytime",
        "tr": r"otomatik (olarak )?yenilen|istediğin(iz)? zaman iptal",
        "de": r"verlängert sich automatisch|automatisch verlängert|jederzeit kündbar",
        "it": r"si rinnova|rinnovo automatico|annulla quando vuoi", "es": r"se renueva|renovación automática|cancela cuando",
        "fr": r"renouvel", "pt": r"renova(ção)? automatica|renovação automática"},
    "report": {
        "en": r"\breport(ing)?\s+(post|user|account|content|comment|message|this|abuse)|\breport\b",
        "tr": r"şik[aâ]yet", "de": r"\bmelden\b", "it": r"segnala", "es": r"denunciar|reportar", "fr": r"signaler",
        "pt": r"denunciar"},
    "block": {
        "en": r"\bblock(ed|ing)?\s+(user|account|@|this)|\bblock\b", "tr": r"engelle", "de": r"blockieren|sperren",
        "it": r"blocca", "es": r"bloquear", "fr": r"bloquer", "pt": r"bloquear"},
    "mute": {
        "en": r"\bmute\b|\bfilter(s|ed)?\b|hide (post|repl)|content filter", "tr": r"sessize al|filtre",
        "de": r"stummschalten|ausblenden", "it": r"silenzia|nascondi", "es": r"silenciar|ocultar", "fr": r"masquer",
        "pt": r"silenciar|ocultar"},
    "contact": {
        "en": r"contact (us|support)|support@", "tr": r"bize ulaş|destek|iletişim", "de": r"kontakt",
        "it": r"contatta|assistenza", "es": r"contacto|contactar|soporte", "fr": r"contactez|contacter", "pt": r"contato|contacto|suporte"},
    "support": {
        "en": r"\bsupport\b|help center|contact us", "tr": r"destek", "de": r"\bsupport\b|\bhilfe\b|kontakt",
        "it": r"assistenza|\baiuto\b|contatta", "es": r"soporte|\bayuda\b|contacto", "fr": r"\bsupport\b|\baide\b|contactez",
        "pt": r"suporte|\bajuda\b"},
    "account_delete": {
        "en": r"delete (my |your )?account|account deletion|close (my )?account", "tr": r"hesab[ıi](m[ıi])? (sil|kapat)",
        "de": r"(konto|account) löschen", "it": r"(elimina|cancella) (il )?(tuo |mio )?account",
        "es": r"(eliminar|borrar) (mi |tu |la )?cuenta", "fr": r"supprimer (mon |le |votre )?compte",
        "pt": r"(excluir|eliminar|apagar) (a )?(minha |sua )?conta"},
    "beta": {
        "en": r"\b(beta version|demo version|trial version|test version|preview build)\b",
        "tr": r"\b(beta sürüm|deneme sürümü|test sürümü|demo sürüm)", "de": r"\b(beta-?version|demo-?version|test-?version)\b",
        "it": r"\bversione (beta|demo|di prova)\b", "es": r"\bversión (beta|demo|de prueba)\b", "fr": r"\bversion (bêta|beta|démo|d'essai)\b",
        "pt": r"\bversão (beta|demo|de teste)\b"},
    "coming_soon": {
        "en": r"\bcoming soon\b", "tr": r"^\s*yakında\.?:?\s*$|\bçok yakında\b", "de": r"\bdemnächst\b|\bin kürze\b|\bbald verfügbar\b",
        "it": r"\bprossimamente\b|\bin arrivo\b", "es": r"\bpróximamente\b", "fr": r"\bbientôt disponible\b|\bprochainement\b",
        "pt": r"\bem breve\b"},
    "ai_consent": {
        "en": r"consent|agree|allow", "tr": r"izin|onay|kabul", "de": r"einwilligung|zustimm|erlauben",
        "it": r"consenso|accetta|consenti", "es": r"consentimiento|acept|permitir", "fr": r"consentement|accept|autoriser",
        "pt": r"consentimento|aceit|permitir"},
    "ai": {
        "en": r"\bAI\b|artificial intelligence|language model", "tr": r"yapay zek", "de": r"\bKI\b|künstliche intelligenz",
        "it": r"\bIA\b|intelligenza artificiale", "es": r"\bIA\b|inteligencia artificial", "fr": r"\bIA\b|intelligence artificielle",
        "pt": r"\bIA\b|inteligência artificial"},
    "policy_analytics": {"en": r"analytic|tracking", "tr": r"analitik|izleme|takip", "de": r"analyse|tracking", "it": r"analisi|tracciamento", "es": r"analític|seguimiento", "fr": r"analyse|suivi", "pt": r"análise|rastreamento"},
    "policy_crash": {"en": r"crash|diagnostic", "tr": r"çökme|hata raporu", "de": r"absturz|diagnose", "it": r"arresto anomalo|crash|diagnostic", "es": r"fallo|bloqueo|diagnóstic", "fr": r"plantage|diagnostic", "pt": r"falha|diagnóstic"},
    "policy_ads": {"en": r"advertis", "tr": r"reklam", "de": r"werbung", "it": r"pubblicit", "es": r"publicidad", "fr": r"publicit", "pt": r"publicidade"},
    "policy_location": {"en": r"location", "tr": r"konum", "de": r"standort", "it": r"posizione", "es": r"ubicación", "fr": r"localisation", "pt": r"localização"},
    "policy_media": {"en": r"camera|photo", "tr": r"kamera|fotoğraf", "de": r"kamera|foto", "it": r"fotocamera|foto", "es": r"cámara|foto", "fr": r"caméra|appareil photo|photo", "pt": r"câmera|câmara|foto"},
    "policy_health": {"en": r"health", "tr": r"sağlık", "de": r"gesundheit", "it": r"salute", "es": r"salud", "fr": r"santé", "pt": r"saúde"},
    "policy_account": {"en": r"account|e-?mail", "tr": r"hesap|e-?posta", "de": r"konto|e-?mail", "it": r"account|e-?mail", "es": r"cuenta|correo", "fr": r"compte|e-?mail|courriel", "pt": r"conta|e-?mail"},
    "policy_delete": {"en": r"delet|erase", "tr": r"silme|sil\b", "de": r"lösch", "it": r"elimin|cancell", "es": r"elimin|borrar|supresión", "fr": r"suppr|effac", "pt": r"exclu|elimin|apag"},
    "destructive_label": {"en": r"delete|remove", "tr": r"sil|kaldır", "de": r"löschen|entfernen", "it": r"elimina|cancella|rimuovi", "es": r"eliminar|borrar|quitar", "fr": r"supprimer|retirer", "pt": r"excluir|eliminar|remover|apagar"},
}

# Otomatik gezinen testin BASMAYACAĞI düğmeler (veri siler, para alır, oturumu kapatır, dışarı gönderir).
# Şablonlar bu listeyi taşır; regressions.py ayrıldıklarını yakalar. Fazla atlamak güvenlidir, az atlamak değil.
SKIP_LABELS = ("delete|remove|erase|buy|purchase|subscribe|log ?out|sign ?out|account|share|"
               "sil|kaldır|satın|abone|çıkış|hesab|paylaş|"
               "löschen|entfernen|kaufen|abonnieren|abmelden|konto|teilen|"
               "elimina|cancella|rimuovi|acquista|abbonati|esci|disconnetti|condividi|"
               "borrar|quitar|comprar|suscrib|cerrar sesión|salir|cuenta|compartir|"
               "supprimer|retirer|acheter|abonner|déconnexion|compte|partager|"
               "excluir|remover|apagar|assinar|sair|conta")


def rx(*concepts: str) -> str:
    """Kavramların bütün dillerdeki hâli: büyük / küçük harf duyarsız, tek düzenli ifade."""
    return "(?i)" + "|".join(v for c in concepts for v in _T[c].values())


def rx_case(concept: str) -> str:
    """Büyük harfin anlam taşıdığı kısaltmalar için (AI, KI, IA): (?i) eklemez."""
    return "|".join(_T[concept].values())


def concepts() -> dict:
    return _T
