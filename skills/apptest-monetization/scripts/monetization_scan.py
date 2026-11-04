#!/usr/bin/env python3
"""apptest-monetization — static scan (in-app purchases, subscriptions, restore,
product IDs, hardcoded prices, outside payment, unlock codes, rewarded reviews,
random rewards, ads).

Standard library only; does NOT write to the project. The output is CANDIDATES
(verified against the MO-xx IDs in SKILL.md). Stays out of price and business
model (MO-P2).

    python3 -I monetization_scan.py <project_root> [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys

_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "apptest", "shared", "scanlib.py")
_s = importlib.util.spec_from_file_location("apptest_scanlib", _p)
scan = importlib.util.module_from_spec(_s)
_s.loader.exec_module(scan)

RESTORE = r"restorePurchases|restoreCompletedTransactions|AppStore\.sync\(|restoreTransactions|" \
          r"Purchases\.(shared\.)?restorePurchases|InAppPurchase\.instance\.restorePurchases|getAvailablePurchases|" \
          r"restorePurchase|RestorePurchases|storeKitRestore|restoreTransactions"
# Generic "restore()" deliberately ABSENT: it collides with drawing contexts (canvas.restore), state restoration etc.
RESTORE_TEXT = scan.terms.rx("restore") + "|復元"
SUB_SIGNS = r"SubscriptionStoreView|autoRenewable|subscriptionGroupID|subscriptionPeriod|SubscriptionPeriod|" \
            r"introductoryOffer|subscriptionOfferDetails|PurchasesPackage|entitlements\.active|RENEWABLE|" \
            r"\.subscription\b|isAutoRenew|SubscriptionInfo"
APPLE_SUB_VIEW = r"SubscriptionStoreView|StoreView\("
EULA = r"(?i)apple\.com/legal/internet-services/itunes/dev/stdeula|" + scan.terms.rx("terms")[4:]
PRIVACY = scan.terms.rx("privacy")
AUTO_RENEW = scan.terms.rx("auto_renew")
# Package NAMES (not substrings): "@braintree/sanitize-url" is a URL sanitizer, not payment.
DIGITAL_PAY = r"flutter_stripe|stripe_payment|stripe_sdk|@stripe/stripe-react-native|stripe-react-native|stripe-ios|" \
              r"pod ['\"]Stripe|StripePaymentSheet|flutter_braintree|braintree_drop_in|react-native-braintree|" \
              r"BraintreeDropIn|pod ['\"]Braintree|@paypal/react-native|flutter_paypal|PayPalCheckout|paypal-ios|" \
              r"iyzico|adyen-ios|@adyen/react-native|adyen_checkout|razorpay_flutter|react-native-razorpay|" \
              r"razorpay-pod|paddle_|mollie|lemonsqueezy"
# Source code / docs sites excluded (e.g. "github.com/RevenueCat/purchases-ios" is an acknowledgement link).
WEB_CHECKOUT = r"https?://(?!(?:[a-z]+\.)*apple\.com|(?:www\.)?(?:github|gitlab|bitbucket|docs\.|pub\.dev|npmjs|cocoapods|" \
               r"swiftpackageindex|stackoverflow)[a-z.]*/)[^\s'\"`)]*(checkout|/buy\b|/purchase|/subscribe|/pricing|" \
               r"/upgrade|/billing|/premium|/pro(?=[/?#]|$|[\"'`)\s]))[^\s'\"`)]*"
UNLOCK_CODE = r"(?i)(license|licen[cs]e key|activation|unlock|serial|promo|redeem|kupon|coupon|voucher)[ _-]?(code|key|kodu)"
OFFER_CODE = r"presentCodeRedemptionSheet|offerCodeRedemption|presentCodeRedemptionSheetIOS"
INCENTIVE = r"(?i)\b(rate|review)\s+(us|this app|the app|our app)\b[^\n]{0,60}(to (get|unlock|earn)|for (a reward|free|coins?)|" \
            r"and (get|earn|unlock))|\b(bizi|uygulamay[ıi])\s+(değerlendir|puanla)[^\n]{0,60}(kazan|açmak için|ödül)|" \
            r"\b(5|five) stars?\b[^\n]{0,40}(to (get|unlock|earn)|for (a reward|coins?))|5 yıldız[^\n]{0,40}(kazan|ödül|açmak)|" \
            r"★★★★★[^\n]{0,30}(unlock|get|kazan)"
LOOT = r"(?i)loot ?box|gacha|mystery box|random reward|rastgele ödül|sürpriz kutu"
ODDS = r"(?i)odds|probabilit|olasılık|ihtimal|drop rate"
# Decimal amount or 2+ digits after the currency symbol: "$0.pro" in Swift (a closure parameter) is not a price.
_AMT = r"(?:\d{1,4}[.,]\d{2}|\d{2,4}(?![\w.]))"
PRICE_LIT = re.compile(r"(?:[$€£₺¥₹]\s?" + _AMT + r"|\d{1,4}[.,]\d{2}\s?(?:[$€£₺¥₹]|TL|USD|EUR|TRY))"
                       r"[^\n]{0,30}(?i:/\s?(mo|month|yr|year|ay|yıl|week|hafta)|per (month|year)|aylık|yıllık|lifetime|ömür boyu|pro|premium)|"
                       r"(?i:(monthly|yearly|annual|aylık|yıllık|lifetime|ömür boyu|premium|pro)[^\n]{0,20})"
                       r"(?:[$€£₺¥₹]\s?" + _AMT + r"|\d{1,4}[.,]\d{2}\s?(?:[$€£₺¥₹]|TL))")
LOCALIZED_PRICE = r"displayPrice|localizedPrice|priceFormatStyle|priceLocale|\.price\b|priceString|formattedPrice|" \
                  r"product\.price|ProductDetails\b|storeProduct\.price|localizedPriceString"
PRODUCT_LIT = re.compile(r"""['"]([a-z][a-z0-9_-]*(?:\.[a-z0-9_-]+){2,})['"]""", re.I)
PRODUCT_WORD = re.compile(r"(?i)(pro|premium|plus|sub|subscription|month|year|annual|weekly|lifetime|unlock|tip|coin|gem|"
                          r"credit|pack|remove_?ads|noads|vip|gold|upgrade|full)")
PURCHASE_API = r"Product\.products|SKProductsRequest|queryProductDetails|getProducts|getSubscriptions|" \
               r"Purchases\.|getOfferings|productIdentifiers|ProductDetailsResponse|fetchProducts|InAppPurchase|" \
               r"StoreKit|in_app_purchase|react-native-iap|Purchasing"
# A real purchase CALL (the word "StoreKit" also appears in comments; e.g. a sample app's "onSubscribe stays unset until StoreKit lands").
BUY_CALL = r"buyNonConsumable|buyConsumable|\.purchase\(|\.purchase\s*\{|purchasePackage|purchaseProduct|requestPurchase|" \
           r"requestSubscription|SKPaymentQueue|SKMutablePayment|purchaseStoreProduct|\bpurchase\(\s*\w*([Pp]roduct|[Pp]ackage)"
DEV_SCREEN = re.compile(r"(?i)(debug|developer|betatools|designsystem|internal|playground|sample|example|preview|mock|fixture)")


def string_texts(p) -> str:
    out = []
    for f in p.files:
        low = "/" + p.rel(f).lower()
        if low.endswith((".arb", ".strings", ".xcstrings", ".json", ".po", ".yml", ".yaml")) and \
                re.search(r"(l10n|locale|i18n|lproj|translations|strings|lang)", low) and "node_modules" not in low:
            out.append(scan.p_read(f, 3_000_000))
    return "\n".join(out)


def storekit_products(p) -> tuple[set, list]:
    ids, files = set(), []
    for f in p.files:
        if not f.endswith(".storekit"):
            continue
        try:
            d = json.loads(scan.p_read(f, 3_000_000))
        except ValueError:
            continue
        files.append(f)
        for pr in d.get("products", []) or []:
            ids.add(pr.get("productID"))
        for g in d.get("subscriptionGroups", []) or []:
            for sub in g.get("subscriptions", []) or []:
                ids.add(sub.get("productID"))
        for pr in d.get("nonRenewingSubscriptions", []) or []:
            ids.add(pr.get("productID"))
    return {i for i in ids if i}, files


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    p = scan.load_profile(a.root)
    if scan.guard_unknown(p):
        return 0
    rep = scan.Report("MO", p, "monetization scan")
    flags = p.mod.summary_flags(p)
    files = scan.code_files(p)
    texts = string_texts(p)
    deps = "\n".join(scan.p_read(f) for f in p.files if os.path.basename(f) in
                     ("pubspec.yaml", "package.json", "Podfile", "Package.swift"))

    iap = flags["purchases"]
    sub = flags["subscriptions"] or scan.count(p, SUB_SIGNS, files=files)[0] > 0
    if not iap and not flags["ads"]:
        rep.skip("MO-10…19", "no in-app purchases / ads")

    if iap:
        # MO-10: product IDs ↔ StoreKit configuration file
        sk_ids, sk_files = storekit_products(p)
        bundle_ids = [v["value"] for k, v in p.items.items() if k == "setting:bundle id"]
        code_ids = {}
        # Only files and lines in a purchase context (not translation keys or SF Symbol names).
        buy_files = [f for f in files if re.search(PURCHASE_API, scan.p_read(f, 300_000))]
        for f, n, line, m in scan.grep(p, PRODUCT_LIT, files=buy_files):
            ctx = "\n".join(scan.p_read(f).splitlines()[max(0, n - 4):n])
            if not re.search(r"(?i)product|sku|iap|purchase|offering|entitlement|subscription", ctx) or \
                    re.search(r"\bText\(|Localized|localized|\.tr\(|NSLocalizedString|l10n|i18n", line):
                continue  # a translation key, not a product ID
            pid = m.group(1)
            if DEV_SCREEN.search(p.rel(f)) or pid.startswith(("com.apple.", "group.", "iCloud.", "http")):
                continue
            if PRODUCT_WORD.search(pid.split(".")[-1]) and not re.search(r"(?i)notification|queue|background|widget|"
                                                                         r"extension|keychain|bundle|domain", pid):
                code_ids.setdefault(pid, f"{p.rel(f)}:{n}")
        if code_ids:
            rep.add("MO-10", "INFO", "Possible product IDs in code", ", ".join(sorted(code_ids)[:12]),
                    "Must match the product IDs in App Store Connect EXACTLY (case included); "
                    "otherwise the app says 'product not found' (e.g. a budgeting app while the product was not yet in ASC).")
        if sk_files:
            missing = sorted(set(code_ids) - sk_ids)
            if missing and sk_ids:
                rep.add("MO-11", "USER BUG", "Product in code but not in the StoreKit configuration file",
                        ", ".join(missing[:8]), "Local testing cannot find the product; compare with the ID in ASC too.")
        else:
            rep.add("MO-12", "SUGGESTION", "No StoreKit configuration file (.storekit)",
                    "—", "For trying purchase / refund / renewal on the simulator without real money (MO-P1).")

        # MO-13: restore
        r_code, r_first = scan.count(p, RESTORE, files=files)
        r_text = re.search(RESTORE_TEXT, texts) is not None
        sk2 = scan.count(p, r"Transaction\.currentEntitlements|Transaction\.updates", files=files)[0]
        if not r_code and not scan.count(p, BUY_CALL, files=files)[0]:
            # Unfinished project: package / sales screen present but no purchase code. Nothing is being sold yet.
            rep.add("MO-13", "INFO", "Purchases not wired up yet (package or text present, no purchase call)",
                    "code scan", "When wiring up, add a visible 'Restore' too (3.1.1). Before release, either wire it up "
                    "or remove the sales screen: a non-working purchase screen is grounds for 2.1.")
        elif not r_code and sk2:
            # StoreKit 2: entitlements are read at launch, purchases come back anyway (e.g. Pocket Casts, live).
            rep.add("MO-13", "SUGGESTION", "StoreKit 2 entitlements are read; no visible 'Restore' (AppStore.sync) found",
                    "code scan" + (" ('restore' appears in the strings)" if r_text else ""),
                    "3.1.1: a visible restore path for the user is recommended; on another device or after reinstall "
                    "AppStore.sync() syncs with the Apple account. Account-based sync, if any, can also be a path.")
        elif not r_code:
            rep.add("MO-13", "REJECTION RISK", "Purchases exist but no 'Restore' call was found",
                    "code scan" + (" ('restore' appears in the strings)" if r_text else ""),
                    "3.1.1: with non-consumables and subscriptions the user must be able to restore purchases (visible button). "
                    "Not needed if only consumables (coins) are sold: not verified.")
        else:
            rep.add("MO-13", "INFO", "Restore call exists", f"{p.rel(r_first[0])}:{r_first[1]}",
                    "Verify the button is VISIBLE on the purchase screen and the result is reported afterwards.")

        # MO-14: subscription disclosures (3.1.2(c))
        if sub:
            own_view = scan.count(p, APPLE_SUB_VIEW, files=files)[0] > 0
            code_text = "\n".join(scan.p_read(f, 300_000) for f in files[:4000]
                                  if re.search(r"(?i)paywall|purchase|subscri|premium|pro|store|upgrade", p.rel(f)))
            hay = texts + "\n" + code_text
            for label, rx in (("terms of use (EULA) link", EULA), ("privacy policy link", PRIVACY),
                              ("auto-renewal / cancellation info", AUTO_RENEW)):
                if not re.search(rx, hay):
                    rep.add("MO-14", "REJECTION RISK" if not own_view else "SUGGESTION",
                            f"No {label} found on the subscription screen", "strings + purchase screen code",
                            "3.1.2(c): name, length, price, unit price, auto-renewal, terms and privacy link "
                            "must be visible before purchase" + (" (Apple's SubscriptionStoreView shows most of these)."
                                                               if own_view else "."))

        # MO-15: hardcoded price
        for f, n, line, m in scan.grep(p, PRICE_LIT, files=files):
            if DEV_SCREEN.search(p.rel(f)) or re.search(LOCALIZED_PRICE, line):
                continue
            rep.add("MO-15", "USER BUG", "Price may be hardcoded in code",
                    f"{p.rel(f)}:{n} `{m.group(0)[:50]}`",
                    "Price and currency vary by country; show the localized price from the store (2.3, 3.1.1).")
        for mm in PRICE_LIT.finditer(texts):
            rep.add("MO-15", "USER BUG", "Hardcoded price in translated text", f"`{mm.group(0)[:50]}`",
                    "Fill the price through a placeholder, with the value from the store.")
            break

    # MO-16: outside payment / web checkout link for digital content
    pay = re.search(DIGITAL_PAY, deps)
    web, web_first = scan.count(p, WEB_CHECKOUT, files=files)
    if pay or web:
        rep.add("MO-16", "SUGGESTION" if not iap else "REJECTION RISK",
                "Sign of outside payment: " + (pay.group(0) if pay else "web checkout link"),
                f"{p.rel(web_first[0])}:{web_first[1]}" if web_first else "dependency file",
                "Correct for physical goods / services (food, transport, person-to-person services) and donations (approved organization) (3.1.3, 3.2.1). "
                "DIGITAL content / feature unlocks must be sold through in-app purchase (3.1.1); regional exceptions "
                "(e.g. US / EU link rules) are read from Apple's current text.")

    # MO-17: unlock / promo code
    if iap:
        uc, ufirst = scan.count(p, UNLOCK_CODE, files=files)
        if uc and not scan.count(p, OFFER_CODE, files=files)[0]:
            rep.add("MO-17", "SUGGESTION", "Sign of unlocking with a code (license / promo / coupon)",
                    f"{p.rel(ufirst[0])}:{ufirst[1]}",
                    "3.1.1: unlocking digital content with a code outside in-app purchase is prohibited; Apple's "
                    "offer codes may be used.")

    # MO-18: rewarded review / download
    inc = re.search(INCENTIVE, texts) or None
    ic, ifirst = scan.count(p, INCENTIVE, files=files)
    if inc or ic:
        rep.add("MO-18", "REJECTION RISK", "Sign of a reward in exchange for a review / rating",
                f"{p.rel(ifirst[0])}:{ifirst[1]}" if ifirst else f"`{inc.group(0)[:60]}`",
                "3.2.2 / 5.6.1: reviews cannot be incentivized with rewards; ask only through Apple's API.")

    # MO-19: random reward
    if iap and (re.search(LOOT, texts) or scan.count(p, LOOT, files=files)[0]):
        if not re.search(ODDS, texts):
            rep.add("MO-19", "REJECTION RISK", "Random rewards (loot box) exist, odds may not be shown",
                    "text / code", "3.1.1: for purchased random rewards, the odds of each type must be shown before purchase.")

    # MO-20: ads
    if flags["ads"]:
        rep.add("MO-20", "INFO", "Ad SDK present", ", ".join(p.mod.display(k.split(":", 1)[1]) for k in p.items if k == "capability:ads"),
                "Tracking permission (ATT) → privacy-permissions PP-20; third-party ads prohibited in the kids category (1.3); "
                "ads cannot appear in widgets / notifications / keyboard extensions; the close button cannot be hidden.")

    rep.emit(a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
