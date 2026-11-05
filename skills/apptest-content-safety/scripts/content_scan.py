#!/usr/bin/env python3
"""apptest-content-safety: static scan (report / block / filter / contact for
user content, generative AI output, features covered by the age rating
questionnaire, gambling / contests, medical claims, kids).

Standard library only; does NOT write to the project. Output is CANDIDATES
(verify against the CS-xx ids in SKILL.md). Never produces harmful content (CS-P1).

    python3 -I content_scan.py <project_root> [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys

_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "apptest", "shared", "scanlib.py")
_s = importlib.util.spec_from_file_location("apptest_scanlib", _p)
scan = importlib.util.module_from_spec(_s)
_s.loader.exec_module(scan)

MOD = {
    "report": (scan.terms.rx("report"),
               r"report\w*(Content|Post|User|Account|Message|Comment)|createReport|reportAbuse|flagContent"),
    "block": (scan.terms.rx("block"),
              r"block\w*(User|Account)|blockUser|BlockedUsers|blocklist|blockList"),
    "filter / mute": (scan.terms.rx("mute"),
                      r"mute\w*\(|filter\w*Content|ContentFilter|muteWords|mutedWords|KeywordFilter|moderation"),
    "published contact": (scan.terms.rx("contact") + r"|@[a-z0-9-]+\.(com|app|org)",
                          r"mailto:|supportEmail|contactEmail"),
}
# Plain "sendMessage(" is left out on purpose: platform channels and watch communication use that name too.
CHAT = r"\b(Conversation|Chat|DirectMessage|Inbox)\w*(View|Screen|Controller|Page|List)\b|sendChatMessage|" \
       r"ConversationsList|ChatComposer|MessageComposer"
# "following" is left out: it is an everyday word ("the following items"), which flagged browsers and readers.
SOCIAL = r"\b(followers|followersCount|unfollow|followUser|followAccount)\b"
# IN-APP browser only (a link opened in Safari does not count) with a variable address.
WEBVIEW = r"WKWebView|webview_flutter|flutter_inappwebview|react-native-webview|InAppBrowser|WebView\("
ARBITRARY_URL = r"(load\(\s*URLRequest\(\s*url\s*:\s*(?!URL\(string:\s*\")|loadRequest\(\s*(URLRequest\(\s*)?Uri\.parse\(\s*(?![\"'])|" \
                r"source\s*=\s*\{\s*\{\s*uri\s*:\s*(?![\"'`])|initialUrl\s*:\s*(?![\"'])|initialUrlRequest\s*:)"
GEN_AI = r"(?i)generate|completion|chat/completions|/v1/messages|imagine|dall-?e|stable.?diffusion|LanguageModelSession|" \
         r"GenerativeModel|generateContent|createImage"
AI_FEEDBACK = r"(?i)report (this )?(response|answer|output|image)|thumbs ?(up|down)|feedback|geri bildirim|bildir"
GAMBLING = r"(?i)\b(casino|bet(ting)?|wager|slot ?machine|poker|roulette|lottery|lotto|sweepstakes?|bahis|kumar|" \
           r"çekiliş|piyango|iddaa)\b"
CONTEST = r"(?i)\b(contest|giveaway|raffle|yarışma|çekiliş|kampanya ödülü)\b"
# "diagnostic(s)" is a technical diagnostics report, not medical.
MEDICAL = r"(?i)\b(diagnos(e|es|is|ed|ing)|cure[sd]?|medical treatment|treat(s|ing)? (your|the) (symptoms|condition|disease)|blood pressure|blood sugar|glucose|heart rate monitor|" \
          r"teşhis|tedavi|tansiyon|kan şekeri|ilaç dozu|dosage)\b"
# Wording that names the audience (not post "children" / reply chains).
KIDS = r"(?i)\b(for (kids|children|toddlers)|kids'? (app|games?|mode|zone)|child-friendly|toddlers?|preschool(ers)?|" \
       r"çocuklar için|çocuk modu|çocuk dostu|okul öncesi|für kinder)\b"
# New age rating descriptors (Apple, 2026-11-02; declared from 2026-11-16, all apps by 2027-01-12).
SHARED_LOCATION = (r"(?i)share (your |my |live |real.?time )?location|location.?sharing|live.?location|shareLocation|"
                   r"sharedLocation|konum(unu|umu)? paylaş|canlı konum")
DATING = (r"(?i)(?<![-\w])dating\b|\bmatchmaking\b|find (a |your )?(partner|soulmate)|romantic companion|"
          r"virtual (girlfriend|boyfriend)|\bflört\b|sevgili bul")
AGE_API = r"DeclaredAgeRange|AgeRangeService|ageRangeService|requestAgeRange"
PARENTAL = r"(?i)parental (gate|control)|ebeveyn (kapısı|denetimi)|age (gate|verification|assurance)|DeclaredAgeRange|" \
           r"yaş doğrulama"
TRACKERS = r"(?i)firebase_analytics|FirebaseAnalytics|Mixpanel|amplitude|appsflyer|adjust|facebook|google_mobile_ads|" \
           r"GoogleMobileAds|applovin|ironsource|unity.?ads"


def _is_health(perm):
    """Health permission labels look like "health (read)"."""
    return "health" in perm.lower()


SOURCE_LANG = re.compile(r"(?i)(^|[/_.-])(en|en[-_]us|en[-_]gb|base|tr|tr[-_]tr)([/_.-]|\.lproj|$)")


def texts_of(p, source_only: bool = False) -> str:
    """Translation strings. source_only: source language only (en / Base / tr), for meaning searches;
    same-spelled words in other languages (e.g. Dutch "bet") cause false alarms."""
    out, src = [], []
    for f in p.files:
        low = "/" + p.rel(f).lower()
        if low.endswith((".arb", ".strings", ".xcstrings", ".json", ".po", ".yml", ".yaml")) and \
                re.search(r"(l10n|locale|i18n|lproj|translations|strings|lang)", low) and "node_modules" not in low \
                and not re.search(r"(^|/)(qqq|qps-ploc)(\.lproj)?/", low):
            t = scan.p_read(f, 3_000_000)
            out.append(t)
            if SOURCE_LANG.search(p.rel(f)):
                src.append(t)
    return "\n".join(src or out) if source_only else "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    p = scan.load_profile(a.root)
    if scan.guard_unknown(p):
        return 0
    rep = scan.Report("CS", p, "content-safety scan")
    flags = p.mod.summary_flags(p)
    files = scan.code_files(p)
    texts = texts_of(p)
    src_texts = texts_of(p, source_only=True)
    code_text = "\n".join(scan.p_read(f, 200_000) for f in files[:6000])
    deps = "\n".join(scan.p_read(f) for f in p.files if os.path.basename(f) in
                     ("pubspec.yaml", "package.json", "Podfile", "Package.swift"))
    hay = texts + "\n" + code_text

    ugc = flags["user_content"]
    chat = re.search(CHAT, code_text) is not None
    social = len(re.findall(SOCIAL, code_text)) >= 10

    # CS-10: user content → report / block / filter / contact (1.2)
    if ugc or chat:
        for label, (txt_rx, code_rx) in MOD.items():
            if not (re.search(txt_rx, texts) or re.search(code_rx, code_text)):
                # Only a "Chat…View" name: may also be an AI chat or support (e.g. Apidash DashBot).
                rep.add("CS-10", "REJECTION RISK" if ugc else "SUGGESTION",
                        f"User content present, {label} not found" if ugc else f"Signs of a chat screen, {label} not found",
                        "text + code", ("" if ugc else "Does not apply unless it is person-to-person. ") + "1.2: an app with user content or messaging needs filtering of objectionable content, reporting with a timely "
                        "response, blocking of abusive users and published contact information. It may live on the server or "
                        "web: not verified.")
    else:
        rep.skip("CS-10", "no user content or messaging")

    # CS-11: generative AI output
    if flags["ai"] and re.search(GEN_AI, code_text):
        if not re.search(AI_FEEDBACK, hay):
            rep.add("CS-11", "SUGGESTION", "Generative AI output present, no way to report it or give feedback found",
                    "code", "Model output is also content shown to the user (1.1, 1.2): a filter and a 'report this response' "
                    "path; the related questions in the age rating questionnaire. Applies to on-device models too.")

    # CS-12: features covered by the age rating questionnaire (inventory)
    inv = []
    if ugc:
        inv.append("User-Generated Content")
    if chat:
        inv.append("Messaging and Chat")
    if social:
        inv.append("Social Media")
    if flags["ads"]:
        inv.append("Advertising")
    if re.search(WEBVIEW, code_text) and re.search(ARBITRARY_URL, code_text):
        inv.append("Unrestricted Web Access (verify: can the user open any address?)")
    if re.search(r"(?i)loot ?box|gacha|mystery box", hay):
        inv.append("Loot Boxes")
    if re.search(GAMBLING, src_texts):
        inv.append("Gambling / Simulated Gambling")
    if re.search(CONTEST, src_texts):
        inv.append("Contests")
    if any(_is_health(x) for x in flags["permissions"]) or re.search(MEDICAL, src_texts):
        inv.append("Medical or Wellness")
    if re.search(PARENTAL, hay):
        inv.append("In-App Controls (Parental Controls / Age Assurance)")
    if re.search(SHARED_LOCATION, hay):
        inv.append("Shared Location (verify: with another person or group?)")
    if re.search(DATING, src_texts):  # user-facing text only: code and block lists mention the word in passing
        inv.append("Dating and Relationships (minimum 18+)")
    if inv:
        rep.add("CS-12", "INFO", "Age rating questionnaire items that may be 'yes'", "; ".join(inv),
                "2.3.6: the questionnaire must be answered honestly; take the current questions from App Store Connect (principle 7). "
                "This list is a hint from the code; the answer is the user's.")

    # CS-16: social media feed without an age check
    if social and not re.search(AGE_API, code_text):
        rep.add("CS-16", "SUGGESTION", "Social media signs, Declared Age Range API not found", "code",
                "Answering 'yes' on the Social Media question gives a minimum rating of 13+. The 'disabled for users "
                "under 13' answer requires at least the Declared Age Range API. Not a finding if you accept 13+.")

    # CS-13: gambling / real money
    g = re.search(GAMBLING, src_texts)
    if g:
        rep.add("CS-13", "REJECTION RISK" if flags["purchases"] or re.search(r"(?i)stripe|paypal|braintree", deps) else "SUGGESTION",
                f"Gambling / game of chance wording: {g.group(0)!r}", "strings",
                "5.3: real-money gambling or lotteries need a license and geo-restriction, the app must be free and "
                "credits cannot be bought with in-app purchase; the developer runs any contest and states its rules in the app.")

    # CS-14: medical claims
    med = re.search(MEDICAL, src_texts)
    if med and (any(_is_health(x) for x in flags["permissions"]) or re.search(r"(?i)health|sağlık|medical|tıbbi", src_texts)):
        rep.add("CS-14", "SUGGESTION", f"Medical / health wording: {med.group(0)!r}", "strings",
                "1.4.1: a claim of measurement or diagnostic accuracy needs evidence and (if required) regulatory approval; otherwise "
                "state 'not medical advice' and refer people to a doctor.")

    # CS-15: kids
    kid_hits = len(re.findall(KIDS, src_texts))
    if kid_hits >= 2:
        tr = re.search(TRACKERS, deps)
        rep.add("CS-15", "REJECTION RISK" if tr else "INFO",
                "Strings aimed at kids" + (f"; third-party analytics / ads present ({tr.group(0)})" if tr else ""),
                f"{kid_hits} matches",
                "In the Kids category (1.3, 5.1.4): no third-party ads or analytics, external links and purchases behind "
                "a parental gate. Not a finding if the app is NOT aimed at kids: ask the user.")

    rep.emit(a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
