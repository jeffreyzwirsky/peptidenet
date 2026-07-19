"""E.164 phone normalization — mirrors the platform-wide normalize fix from the
SMASH telephony rework (inconsistent formats broke thread matching + automations).
Defaults to North America (+1). Kept dependency-free."""
import re


def normalize(raw, default_country="1"):
    if not raw:
        return ""
    raw = str(raw).strip()
    keep_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    if keep_plus:
        return "+" + digits
    if len(digits) == 10:  # bare NANP
        return "+" + default_country + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return "+" + digits


def display(e164):
    """+15875551234 -> (587) 555-1234 for NANP; else return as-is."""
    if not e164:
        return ""
    d = re.sub(r"\D", "", e164)
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    if len(d) == 10:
        return f"({d[0:3]}) {d[3:6]}-{d[6:]}"
    return e164


# NANP area-code → province/state region hint, used for region-aware send-number
# selection (same idea as SMASH's MB→431 / SK→639 / AB→825 routing).
AREA_REGION = {
    "204": "MB", "431": "MB", "306": "SK", "639": "SK",
    "403": "AB", "587": "AB", "780": "AB", "825": "AB",
    "604": "BC", "778": "BC", "236": "BC", "416": "ON", "647": "ON", "437": "ON",
}


def region_of(e164):
    d = re.sub(r"\D", "", e164 or "")
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return AREA_REGION.get(d[0:3], "") if len(d) == 10 else ""
