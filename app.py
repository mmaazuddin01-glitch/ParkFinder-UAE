"""ParkFinder UAE - STREAMLIT app, version 2 (mobile-app look).     PARKFINDER_STREAMLIT_V2

Install:  py -m pip install streamlit
Run:      py -m streamlit run "parkfinder_streamlit_v2.py"      (from Command Prompt)
      or: put run_parkfinder.py next to this file and press F5 on it in IDLE.

Pages: Home, Search, Map, Saved, Profile (bottom bar) + Nearby, About, Parking Timer, Cost Calculator.

HONEST NOTES (tell the judges):
 - LIVE LOCATIONS: parking places are loaded from OpenStreetMap (Overpass API) for Dubai, Sharjah and Ajman and
   refreshed every 30 minutes. They are REAL mapped locations, but nobody publishes live free/occupied spaces for
   them, so availability is a TYPICAL-PATTERN ESTIMATE for the weekday + time (labelled "Usually...", not live), or
   a driver report / average of driver reports when those exist. If the internet/OSM is unreachable
   the app shows the last saved copy, or the 26 DEMO entries below.
 - The 26 DEMO parking entries (only used offline). The places are real, but the spaces, prices and opening
   hours are MADE UP and coordinates are approximate. There are NO live sensors.
 - Community reports come from users, are labelled, and expire after 2 hours.
 - "Recommended" / "Best Match" use a simple visible score (distance, availability, price). Not AI.
 - Accounts are LOCAL to this computer (passwords are salted + hashed). Google sign-in only works if you
   add Streamlit's [auth] settings in .streamlit/secrets.toml; otherwise use email or guest.
 - Streamlit cannot read your phone/browser location, so "location" = type an area.
 - Optional: put a photo called hero.jpg next to this file to use it as the Home banner.
 - Built with help from AI tools.
"""
import base64
import datetime
import hashlib
import hmac
import html
import json
import math
import os
import re
import secrets
import time
import urllib.parse
import urllib.request

import streamlit as st

try:   # optional: real browser location (pip install streamlit-geolocation)
    from streamlit_geolocation import streamlit_geolocation
except Exception:
    streamlit_geolocation = None

st.set_page_config(page_title="ParkFinder UAE", page_icon="🅿️", layout="centered",
                   initial_sidebar_state="collapsed")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "user_data")
REPORT_LIFETIME = 2 * 3600          # community reports expire after 2 hours
HEADERS = {"User-Agent": "ParkFinderUAE-school-project/1.0"}
ss = st.session_state

# ============================================================== 1. DEMO DATA ====
KEYS = ["id", "name", "city", "area", "type", "price", "total", "occupied", "hours", "lat", "lon"]
RAW = [  # price: 0 = free, None = not listed.  total/occupied: None = unknown.  ALL numbers are DEMO values.
    ("D1", "Dubai Mall Parking", "Dubai", "Downtown Dubai", "Garage", 20, 5000, 5000, "24/7", 25.1972, 55.2797),
    ("D2", "Al Wasl Road Street Parking", "Dubai", "Jumeirah 1", "Street", 4, 40, 23, "8:00 AM – 10:00 PM", 25.2085, 55.2600),
    ("D3", "Business Bay Parking", "Dubai", "Business Bay", "Garage", 8, 400, 174, "24/7", 25.1860, 55.2620),
    ("D4", "Sheikh Zayed Road Street Bays", "Dubai", "Trade Centre", "Street", 6, 25, 12, "7:00 AM – 11:00 PM", 25.2230, 55.2830),
    ("D5", "DIFC Gate Parking", "Dubai", "DIFC", "Garage", 25, 900, 487, "24/7", 25.2132, 55.2796),
    ("D6", "City Walk Parking", "Dubai", "Al Wasl", "Garage", 0, 1300, 1300, "10:00 AM – 10:00 PM", 25.2074, 55.2630),
    ("D7", "Jumeirah Beach Road Bays", "Dubai", "Jumeirah", "Street", 0, 30, 25, "24/7", 25.2300, 55.2450),
    ("D8", "Marina Walk Parking", "Dubai", "Dubai Marina", "Garage", 15, 600, 599, "6:00 AM – 12:00 AM", 25.0805, 55.1403),
    ("D9", "JBR Beach Parking", "Dubai", "Jumeirah Beach Residence", "Garage", 0, 180, 180, "24/7", 25.0780, 55.1337),
    ("D10", "Mall of the Emirates", "Dubai", "Al Barsha", "Garage", 10, 7000, 7000, "24/7", 25.1181, 55.2007),
    ("D11", "Karama Public Parking", "Dubai", "Al Karama", "Garage", 0, 150, 150, "6:00 AM – 10:00 PM", 25.2430, 55.3040),
    ("D12", "Al Fahidi Street Parking", "Dubai", "Bur Dubai", "Street", 0, 35, 22, "24/7", 25.2637, 55.2974),
    ("D13", "Deira Corniche Street Bays", "Dubai", "Deira", "Street", 3, 60, 60, "7:00 AM – 11:00 PM", 25.2700, 55.3170),
    ("S1", "Al Majaz Waterfront Parking", "Sharjah", "Al Majaz", "Open lot", 3, 400, 150, "24/7", 25.3263, 55.3836),
    ("S2", "Sahara Centre Parking", "Sharjah", "Al Nahda", "Garage", 0, 1800, 1500, "10:00 AM – 12:00 AM", 25.2989, 55.3744),
    ("S3", "Sharjah Corniche Street Parking", "Sharjah", "Corniche", "Street", 2, 150, 120, "24/7", 25.3573, 55.3827),
    ("S4", "Heart of Sharjah Garage", "Sharjah", "Old Souq", "Garage", 4, 200, 200, "8:00 AM – 10:00 PM", 25.3569, 55.3860),
    ("S5", "University City Parking", "Sharjah", "University City", "Open lot", 2, 600, 210, "24/7", 25.2894, 55.4627),
    ("S6", "Al Qasba Parking", "Sharjah", "Al Qasba", "Open lot", 3, 300, 280, "4:00 PM – 12:00 AM", 25.3230, 55.3850),
    ("S7", "City Centre Sharjah Parking", "Sharjah", "Al Khan", "Garage", 0, 2000, 900, "24/7", 25.3319, 55.3856),
    ("A1", "Ajman University Parking", "Ajman", "Al Jurf", "Open lot", 0, 450, 72, "24/7", 25.3990, 55.4680),
    ("A2", "City Centre Ajman Parking", "Ajman", "Al Zahra", "Garage", 0, 1200, 1100, "24/7", 25.3978, 55.4553),
    ("A3", "Ajman Corniche Bays", "Ajman", "Corniche", "Street", 2, 160, 60, "24/7", 25.4146, 55.4350),
    ("A4", "Ajman Marina Garage", "Ajman", "Ajman Marina", "Garage", 4, 350, 120, "24/7", 25.4066, 55.4410),
    ("A5", "Ajman Old Souq Bays", "Ajman", "Old Souq", "Street", 2, 80, 80, "7:00 AM – 11:00 PM", 25.4052, 55.4440),
    ("A6", "Ajman Museum Parking", "Ajman", "Al Bustan", "Open lot", None, None, None, "Not listed", 25.4041, 55.4457),
]
PARKINGS = [dict(zip(KEYS, row)) for row in RAW]
for _p in PARKINGS:
    _p.update(src="demo", fee=("yes" if (_p["price"] or 0) > 0 else "no" if _p["price"] == 0 else None), capacity=_p["total"])
DEMO_PARKINGS = PARKINGS
BY_ID = {p["id"]: p for p in PARKINGS}
CITIES = ["Dubai", "Sharjah", "Ajman"]
CITY_VIEW = {"Whole UAE": (25.20, 55.35, 8.2), "Dubai": (25.17, 55.24, 10.0),
             "Sharjah": (25.32, 55.40, 11.0), "Ajman": (25.40, 55.45, 12.0)}
REFS = {"Downtown Dubai": (25.1972, 55.2744)}          # default point distances are measured from


# ======================================================= 2. CALCULATIONS (logic) ====
def haversine_km(lat1, lon1, lat2, lon2):
    """Straight-line distance between two coordinates in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def has_cap(p):
    """True only when real total + occupied numbers exist (we never invent them)."""
    t, o = p["total"], p["occupied"]
    return isinstance(t, int) and isinstance(o, int) and t > 0 and 0 <= o <= t


def free_spaces(p):
    """free = total - occupied (calculated by Python, never typed in)."""
    return p["total"] - p["occupied"] if has_cap(p) else None


def base_status(p):
    """No spaces -> Full. Fewer than 20 free OR 70%+ occupied -> Almost Full ("Limited"). Else Available."""
    if not has_cap(p):
        return "Unknown"
    free = free_spaces(p)
    if free == 0:
        return "Full"
    return "Almost Full" if (free < 20 or p["occupied"] / p["total"] >= 0.70) else "Available"


EST = "Typical estimate (not live)"
# Typical % of spaces taken at hour 0,3,6,...21. These are ASSUMED daily patterns, not measurements.
PATTERN = {  # (type, kind of day) -> occupancy at 0h,3h,6h,9h,12h,15h,18h,21h
    ("Garage", "work"): [15, 8, 25, 60, 78, 80, 85, 70], ("Garage", "off"): [20, 10, 18, 45, 80, 90, 95, 85],
    ("Street", "work"): [25, 15, 35, 85, 92, 90, 70, 45], ("Street", "off"): [30, 20, 25, 45, 60, 70, 75, 60],
    ("Open lot", "work"): [15, 10, 30, 80, 85, 75, 50, 25], ("Open lot", "off"): [20, 12, 20, 40, 55, 60, 55, 35],
}


def now_uae():
    return datetime.datetime.now(UAE_TZ)


def day_kind(dt):
    return "off" if dt.weekday() in (5, 6) else "work"          # UAE weekend: Saturday and Sunday


def typical_occupancy(p, dt):
    """Assumed typical % full for this kind of place at this weekday + time (simple pattern, NOT measured)."""
    row = PATTERN.get((p["type"], day_kind(dt))) or PATTERN[("Open lot", day_kind(dt))]
    h = dt.hour + dt.minute / 60
    i = int(h // 3)
    a, b = row[i], row[(i + 1) % 8]
    value = a + (b - a) * ((h - i * 3) / 3)
    if p["price"] == 0:
        value += 8                                             # free places fill up faster
    return max(5.0, min(100.0, value))


def report_average(p, dt):
    """Average of USER reports for this parking on the same weekday within +-1 hour. Needs 3+ reports."""
    vals = []
    for r in REPORTS:
        if r["parking_id"] != p["id"]:
            continue
        t = datetime.datetime.fromtimestamp(r["timestamp"], UAE_TZ)
        if t.weekday() == dt.weekday() and abs(t.hour - dt.hour) <= 1:
            vals.append({"available": 40, "almost_full": 85, "full": 100}[r["feedback_type"]])
    return (sum(vals) / len(vals), len(vals)) if len(vals) >= 3 else None


def occupancy_estimate(p, dt):
    """(percent full, source text). Real user average if there are enough reports, else the typical pattern."""
    avg = report_average(p, dt)
    if avg:
        return avg[0], "Average of %d user reports for this weekday and hour" % avg[1]
    return typical_occupancy(p, dt), EST


def status_from_percent(pct):
    return "Full" if pct >= 95 else "Almost Full" if pct >= 75 else "Available"


def effective_status(p):
    """(status, source). A community report from the last 2 hours beats the stored demo status."""
    for r in reversed(REPORTS):
        if r["parking_id"] == p["id"] and time.time() - r["timestamp"] <= REPORT_LIFETIME:
            return {"available": "Available", "almost_full": "Almost Full", "full": "Full"}[r["feedback_type"]], "Community report"
    status = base_status(p)
    if status != "Unknown":
        return status, "Demo data"
    pct, source = occupancy_estimate(p, now_uae())
    return status_from_percent(pct), source


def dist_km(p):
    lat, lon = ss.ref["pt"]
    return haversine_km(lat, lon, p["lat"], p["lon"])


def walk_text(km):
    m = max(1, round(km / 5 * 60))                       # walking at 5 km/h
    return "%d min" % m if m < 60 else "%dh %dm" % (m // 60, m % 60)


def price_text(p):
    if p["price"] is None:
        return "Paid (rate not listed)" if p.get("fee") == "yes" else "Not listed"
    return "Free" if p["price"] == 0 else "AED %s/hr" % num(p["price"])


def num(x):
    return ("%.2f" % x).rstrip("0").rstrip(".")


def score(p, status, source, km):
    """Visible rule-based score (NOT AI): availability, distance, price, data reliability."""
    pts = {"Available": 35, "Almost Full": 15, "Unknown": 8, "Full": -50}[status]
    pts += {"Community report": 6, "Demo data": 3, EST: 2}.get(source, 0)
    pts += 30 * max(0.0, 1 - km / 15)
    if p["price"] == 0:
        pts += 20
    elif p["price"] is not None:
        pts += 20 * (1 - min(p["price"], 25) / 25)
    else:
        pts += 6
    return pts


def reason(p, status, km):
    d = ("very close" if km < 1 else "close" if km < 3 else "within reach" if km < 10 else "%.1f km away" % km)
    free = free_spaces(p)
    if free is not None and status == "Available":
        s = "has %d available spaces" % free
    elif free is not None and status == "Almost Full":
        s = "has %d spaces left" % free
    else:
        s = "is usually %s at this time" % {"Available": "available", "Almost Full": "fairly busy", "Full": "full"}.get(status, "unknown")
    pr = ("is free" if p["price"] == 0 else "has a price that is not listed" if p["price"] is None
          else "costs AED %s/hr" % num(p["price"]))
    return "It is %s, %s, and %s." % (d, s, pr)


def recommend(items):
    """Best first. Full places are skipped."""
    ranked = []
    for p in items:
        status, source = effective_status(p)
        if status != "Full":
            km = dist_km(p)
            ranked.append((p, score(p, status, source, km), reason(p, status, km)))
    return sorted(ranked, key=lambda r: -r[1])


def estimate_cost(rate, minutes, free_min=0.0, daily_cap=None):
    """cost = rate x (duration - free period)/60, limited by an optional daily maximum."""
    billable = max(0.0, minutes - free_min)
    raw = rate * billable / 60
    if daily_cap is None:
        return billable, round(raw, 2), round(raw, 2)
    days, rest = divmod(billable, 1440)
    capped = days * min(rate * 24, daily_cap) + min(rate * rest / 60, daily_cap)
    return billable, round(raw, 2), round(capped, 2)


def fmt_duration(sec):
    m = int(sec // 60)
    h, m = divmod(m, 60)
    if h == 0 and m == 0:
        return "less than a minute"
    out = []
    if h:
        out.append("%d hour%s" % (h, "" if h == 1 else "s"))
    if m or not h:
        out.append("%d minute%s" % (m, "" if m == 1 else "s"))
    return " ".join(out)


def fmt_clock(sec):
    s = int(sec)
    return "%02d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60)


def directions_url(p):
    return "https://www.google.com/maps/dir/?api=1&destination=%s,%s" % (p["lat"], p["lon"])


# ============================================================ 3. STORAGE + ACCOUNTS ====
def load_json(name, default):
    try:
        with open(os.path.join(DATA_DIR, name), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(name, data):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, name), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def hash_pw(password, salt_hex):
    """Salted PBKDF2 hash. We never store the real password."""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 200_000).hex()


def make_account(name, email, password):
    users = load_json("users.json", {})
    email = email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return None, "Please enter a valid email address."
    if len(password) < 8:
        return None, "Your password needs at least 8 characters."
    if email in users:
        return None, "An account with this email already exists. Try logging in."
    salt = secrets.token_hex(16)
    users[email] = {"name": name.strip() or email.split("@")[0].title(), "salt": salt, "hash": hash_pw(password, salt)}
    save_json("users.json", users)
    return {"name": users[email]["name"], "email": email, "guest": False}, ""


def check_login(email, password):
    rec = load_json("users.json", {}).get(email.strip().lower())
    if rec and hmac.compare_digest(rec["hash"], hash_pw(password, rec["salt"])):
        return {"name": rec["name"], "email": email.strip().lower(), "guest": False}
    return None


def user_key():
    return (ss.user or {}).get("email") or "guest"


def get_saved():
    return [i for i in load_json("saved.json", {}).get(user_key(), []) if i in BY_ID]


def google_user():
    """Returns a user dict when Streamlit's Google/OIDC sign-in is configured and completed."""
    try:
        if st.user.is_logged_in:
            return {"name": st.user.get("name") or "Google user", "email": st.user.get("email") or "", "guest": False}
    except Exception:
        pass
    return None


# ============================================ 3b. PARKING LOCATIONS FROM OPENSTREETMAP ====
REFRESH_SECONDS = 30 * 60                               # locations are refreshed every 30 minutes
OVERPASS_URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
EMIRATES = {"Dubai": ("AE-DU", "Dubai"), "Sharjah": ("AE-SH", "Sharjah"), "Ajman": ("AE-AJ", "Ajman")}
UAE_TZ = datetime.timezone(datetime.timedelta(hours=4))
TYPE_OF = {"multi-storey": "Garage", "underground": "Garage", "rooftop": "Garage",
           "street_side": "Street", "lane": "Street", "on_kerb": "Street"}


def overpass(query):
    last = None
    for url in OVERPASS_URLS:
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": query}).encode(), headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception as error:
            last = error
    raise last


def osm_to_parking(el, city):
    tags = el.get("tags", {})
    if tags.get("access") in ("private", "no"):
        return None
    lat = el.get("lat", (el.get("center") or {}).get("lat"))
    lon = el.get("lon", (el.get("center") or {}).get("lon"))
    if lat is None or lon is None:
        return None
    kind = TYPE_OF.get(tags.get("parking"), "Open lot")
    area = tags.get("addr:suburb") or tags.get("addr:neighbourhood") or tags.get("addr:street") or tags.get("addr:city") or city
    name = tags.get("name:en") or tags.get("name") or ((tags.get("operator") + " parking") if tags.get("operator") else "Parking (%s)" % kind.lower())
    cap = re.match(r"\d+", str(tags.get("capacity", "")))
    return {"id": "O%s%s" % (el["type"][0], el["id"]), "name": name, "city": city, "area": area, "type": kind,
            "price": 0 if tags.get("fee") == "no" else None, "fee": tags.get("fee"),
            "total": None, "occupied": None, "capacity": int(cap.group()) if cap else None,
            "hours": tags.get("opening_hours", "Not listed"), "lat": float(lat), "lon": float(lon), "src": "osm"}


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner="Updating parking locations from OpenStreetMap (the first load can take a minute)...")
def osm_parkings():
    """Downloads every amenity=parking in Dubai, Sharjah and Ajman. Streamlit keeps the result for 30 minutes."""
    items, seen = [], set()
    for city, (code, name) in EMIRATES.items():
        found = 0
        for area_filter in ('["ISO3166-2"="%s"]' % code, '["name:en"="%s"]["boundary"="administrative"]' % name):
            query = '[out:json][timeout:90];area%s->.a;nwr["amenity"="parking"](area.a);out center tags;' % area_filter
            for el in overpass(query).get("elements", []):
                item = osm_to_parking(el, city)
                if item and item["id"] not in seen:
                    seen.add(item["id"])
                    items.append(item)
                    found += 1
            if found:
                break
    if len(items) < 50:
        raise ValueError("OpenStreetMap returned only %d parking places" % len(items))
    return {"items": items, "fetched": time.time()}


def load_parkings():
    """Sets the global PARKINGS / BY_ID. Order: fresh OSM data -> last saved copy -> 26 demo entries."""
    global PARKINGS, BY_ID, DATA_INFO
    info = {"source": "osm", "fetched": None, "error": ""}
    try:
        data = osm_parkings()
        save_json("osm_cache.json", data)
    except Exception as error:
        info["error"] = "%s: %s" % (type(error).__name__, error)
        data = load_json("osm_cache.json", None)
        info["source"] = "saved copy" if data else "demo"
    if data and data.get("items"):
        PARKINGS, info["fetched"] = data["items"], data.get("fetched")
    else:
        PARKINGS = DEMO_PARKINGS
    BY_ID = {p["id"]: p for p in PARKINGS}
    DATA_INFO = info


DATA_INFO = {"source": "demo", "fetched": None, "error": ""}


def fmt_updated(ts):
    return datetime.datetime.fromtimestamp(ts, UAE_TZ).strftime("%I:%M %p").lstrip("0") if ts else "-"


def cb_refresh_data():
    st.cache_data.clear()
    st.toast("Refreshing parking locations...")


def data_status(key):
    """Honest line about where the list comes from and when it was refreshed."""
    i = DATA_INFO
    if i["source"] == "osm":
        st.caption("📡 %d parking places from OpenStreetMap · updated %s (UAE time) · refreshes every 30 minutes · "
                   "availability is a typical-pattern estimate unless drivers report." % (len(PARKINGS), fmt_updated(i["fetched"])))
    elif i["source"] == "saved copy":
        st.warning("Couldn't reach OpenStreetMap, so this is the last saved copy from %s. (%s)" % (fmt_updated(i["fetched"]), i["error"]))
    else:
        st.warning("Couldn't reach OpenStreetMap, so only the 26 demo places are shown. (%s)" % i["error"])
    st.button("Refresh now", key="refresh_" + key, on_click=cb_refresh_data)


# ================================================================ 4. STATE ====
for _k, _v in {"search_limit": 25, "user": None, "page": "home", "detail": None, "theme": "light", "loaded": False, "q": "",
               "auth_view": "login", "auth_msg": "", "nearby_msg": "",
               "ref": {"label": "Downtown Dubai", "pt": REFS["Downtown Dubai"]},
               "timer": {"state": "idle", "parking": None, "rate": None, "acc": 0.0, "seg": None},
               "timer_rate": "", "calc_rate": 5.0, "calc_hours": 1, "calc_mins": 0, "calc_free": 0.0,
               "calc_use_cap": False, "calc_cap": 30.0}.items():
    ss.setdefault(_k, _v)
REPORTS = load_json("reports.json", [])

# ================================================================ 5. LOOK (CSS) ====
LIGHT = dict(bg1="#EFE4D2", bg2="#FBF7EF", card="#FFFBF4", border="#EADFCB", text="#1B2A4A", muted="#7C7466",
             tile="#F6EDDF", blue="#2F6FDB", terra="#C0652B", navy="#1B2A4A", navtext="#FFF3DC", shadow="rgba(80,60,30,.12)", edge="#7A6D58", edge2="#0F1A33")
DARK = dict(bg1="#0F1426", bg2="#171E36", card="#1C2440", border="#2A3458", text="#EAF0FF", muted="#9AA7C7",
            tile="#252F50", blue="#6EA2FF", terra="#F0A168", navy="#2F6FDB", navtext="#FFFFFF", shadow="rgba(0,0,0,.35)", edge="#7F8FBF", edge2="#B7CCFF")

CSS = """
<style>
:root{--bg1:@bg1@;--bg2:@bg2@;--card:@card@;--border:@border@;--text:@text@;--muted:@muted@;--tile:@tile@;
--blue:@blue@;--terra:@terra@;--navy:@navy@;--navtext:@navtext@;--shadow:@shadow@;--edge:@edge@;--edge2:@edge2@}
.stApp{background:linear-gradient(180deg,var(--bg1),var(--bg2)) fixed;color:var(--text)}
header[data-testid="stHeader"],footer,#MainMenu,[data-testid="stSidebar"],[data-testid="stToolbar"],[data-testid="collapsedControl"]{display:none !important}
.block-container{max-width:620px;padding:1rem 1rem 8rem}
.stApp,[data-testid="stMarkdownContainer"],[data-testid="stMarkdownContainer"] p,label,[data-testid="stWidgetLabel"] p{color:var(--text)}
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p{color:var(--muted)}
.pf-eyebrow{font-size:.72rem;letter-spacing:.14em;font-weight:800;color:var(--muted);text-transform:uppercase}
.pf-title{font-size:1.9rem;font-weight:800;line-height:1.1;margin:.15rem 0 .35rem;color:var(--text)}
.pf-lead{color:var(--muted);margin-bottom:.8rem;line-height:1.45}
.pf-hero{position:relative;border-radius:28px;padding:22px 20px 26px;color:#fff;overflow:hidden;min-height:250px;
background:linear-gradient(135deg,#27325A 0%,#4B5E91 50%,#C9906E 100%);background-size:cover;background-position:center;box-shadow:0 14px 34px var(--shadow)}
.pf-hero::before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(22,30,62,.72),rgba(22,30,62,.08))}
.pf-hero>*{position:relative}
.pf-hero .pf-brand{font-size:.78rem;letter-spacing:.18em;font-weight:800;color:#F4E6CF}
.pf-hero .pf-h1{font-size:2.35rem;line-height:1.04;font-weight:800;margin:.7rem 0 .5rem;color:#fff;max-width:11em}
.pf-hero .pf-hsub{color:#F1EEF8;font-size:1rem}
.pf-cardhead{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.pf-name{font-size:1.15rem;font-weight:800;color:var(--text)}
.pf-sub{color:var(--muted);font-size:.9rem;margin-top:2px}
.pf-tag{display:inline-block;background:var(--tile);color:var(--muted);border-radius:10px;padding:3px 10px;font-size:.78rem;font-weight:700;margin-top:10px}
.pf-tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0 8px}
.pf-tiles div{background:var(--tile);border-radius:14px;padding:10px 4px;text-align:center}
.pf-tiles small{display:block;color:var(--muted);font-size:.74rem}
.pf-tiles b{font-size:.98rem;color:var(--text)}
.pf-foot{display:flex;justify-content:space-between;color:var(--muted);font-size:.84rem;border-top:1px solid var(--border);padding-top:9px}
.pf-src{color:var(--muted);font-size:.74rem;margin-top:6px}
.pf-pill{display:inline-flex;align-items:center;gap:6px;border-radius:99px;padding:5px 12px;font-weight:700;font-size:.78rem;white-space:nowrap}
.pf-pill i{width:8px;height:8px;border-radius:50%;background:currentColor;display:inline-block}
.pf-ok{background:rgba(46,158,107,.15);color:#2E9E6B}.pf-warn{background:rgba(213,138,27,.17);color:#D58A1B}
.pf-bad{background:rgba(201,75,90,.15);color:#C94B5A}.pf-unk{background:rgba(120,125,140,.18);color:#7B8190}
.pf-banner{display:flex;gap:14px;align-items:center;border-radius:24px;padding:18px;color:#fff;background:linear-gradient(135deg,#1E3A8A,#2F5FD6);box-shadow:0 12px 28px rgba(30,58,138,.35)}
.pf-bicon{background:rgba(255,255,255,.18);border-radius:16px;width:46px;height:46px;display:grid;place-items:center;font-size:1.4rem;flex:none}
.pf-b1{font-size:.72rem;letter-spacing:.12em;font-weight:800;color:#BBD0FF}
.pf-b2{font-size:1.15rem;font-weight:800;color:#fff}
.pf-b3{font-size:.9rem;color:#E4ECFF;margin-top:2px}
.pf-icon{width:48px;height:48px;border-radius:16px;display:grid;place-items:center;font-size:1.4rem;background:var(--tile)}
.pf-row{display:flex;gap:14px;align-items:center}
.pf-rowt{font-weight:800;color:var(--text)}.pf-rowd{color:var(--muted);font-size:.88rem}
.pf-empty{text-align:center;padding:34px 10px;color:var(--muted)}
.pf-empty .pf-icon{margin:0 auto 10px;border-radius:50%;width:56px;height:56px}
.pf-empty b{display:block;color:var(--text);margin-bottom:4px}
.pf-info{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid var(--border)}
.pf-info span{color:var(--muted)}.pf-info b{text-align:right;color:var(--text)}
[class*="st-key-card_"]{background:var(--card);border:1px solid var(--border);border-radius:24px;box-shadow:0 10px 26px var(--shadow);padding:16px 16px 12px}
.stButton>button,.stLinkButton>a,.stFormSubmitButton>button,[data-testid^="stBaseButton"]{border-radius:14px;min-height:44px;font-weight:700;border:1px solid var(--border);background:var(--card);color:var(--text);transition:.15s}
.stButton>button:hover,.stLinkButton>a:hover,.stFormSubmitButton>button:hover{transform:translateY(-1px);border-color:var(--terra);color:var(--terra)}
button[kind="primary"],button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"]{background:var(--navy);color:var(--navtext);border-color:var(--navy)}
button[kind="primary"] p,button[data-testid="stBaseButton-primary"] p,button[data-testid="stBaseButton-primaryFormSubmit"] p{color:var(--navtext)}
.stButton>button p,.stLinkButton>a p,.stFormSubmitButton>button p{color:inherit}
button[data-testid="stBaseButton-pills"],button[data-testid="stBaseButton-pillsActive"]{border-radius:99px;padding:6px 18px}
button[data-testid="stBaseButton-pillsActive"]{background:var(--blue);color:#fff;border-color:var(--blue)}
button[data-testid="stBaseButton-pillsActive"] p{color:#fff}
[data-baseweb="input"],[data-baseweb="input"]>div,[data-baseweb="select"]>div,[data-baseweb="base-input"]{background:var(--card) !important;border-color:var(--border) !important;border-radius:14px !important}
[data-baseweb="input"] input,[data-baseweb="select"] div{color:var(--text) !important}
[data-testid="stForm"]{border:0;padding:0;background:transparent}
[data-testid="stExpander"]{border:1px solid var(--border);border-radius:16px;background:var(--card)}
.st-key-bottomnav{position:fixed;left:0;right:0;bottom:0;z-index:999;background:var(--card);border-top:1px solid var(--border);padding:6px 8px calc(6px + env(safe-area-inset-bottom,0px));box-shadow:0 -6px 20px var(--shadow)}
.st-key-bottomnav [data-testid="stHorizontalBlock"]{max-width:600px;margin:0 auto;gap:0;flex-wrap:nowrap !important}
.st-key-bottomnav [data-testid="stColumn"],.st-key-bottomnav [data-testid="column"]{min-width:0 !important;flex:1 1 0 !important}
.st-key-bottomnav button{background:transparent !important;border:0 !important;box-shadow:none !important;color:var(--muted) !important;min-height:54px;font-size:.72rem;padding:0}
.st-key-bottomnav button p{color:inherit !important;font-size:.72rem}
.st-key-bottomnav button>div{flex-direction:column;gap:2px}
[class*="st-key-card_"] [data-testid="stHorizontalBlock"]{flex-wrap:nowrap !important;gap:8px}
[class*="st-key-card_"] [data-testid="stColumn"],[class*="st-key-card_"] [data-testid="column"]{min-width:0 !important;flex:1 1 0 !important}
#pf-load{position:fixed;inset:0;z-index:99999;background:radial-gradient(circle at 50% 35%,#1F2C52,#0E1428);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;color:#fff}
#pf-load .pf-lp{font-size:2rem;animation:pfbob 1.1s ease-in-out infinite;filter:drop-shadow(0 0 14px rgba(110,162,255,.7))}
#pf-load .pf-lb{width:104px;height:104px;border-radius:30px;background:linear-gradient(145deg,#243461,#1A2547);border:1px solid #3B4B7C;display:grid;place-items:center;font-size:3.4rem;font-weight:800;color:#F4D9A6;box-shadow:0 18px 40px rgba(0,0,0,.4)}
#pf-load .pf-lt{font-size:1.7rem;font-weight:800;margin-top:12px}#pf-load .pf-lt em{color:#6EA2FF;font-style:normal}
#pf-load .pf-ls{color:#A9B6D8}
#pf-load .pf-bar{width:210px;height:5px;border-radius:9px;background:#26325A;overflow:hidden}
#pf-load .pf-bar i{display:block;height:100%;background:linear-gradient(90deg,#3B82F6,#7FB0FF);animation:pffill 2.2s ease forwards}
@keyframes pfbob{50%{transform:translateY(-10px)}}@keyframes pffill{from{width:0}to{width:100%}}
.block-container>div{animation:pffade .3s ease}@keyframes pffade{from{opacity:.0;transform:translateY(6px)}to{opacity:1;transform:none}}
</style>
"""


BUTTON_BORDERS = """
/* clear, professional borders on every button so they never blend into the background */
.stButton>button,.stLinkButton>a,.stFormSubmitButton>button,.stDownloadButton>button,[data-testid^="stBaseButton"]{
  border:1.5px solid var(--edge) !important;box-shadow:0 2px 0 var(--shadow),0 1px 3px var(--shadow) !important;border-radius:14px}
button[kind="primary"],button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"]{
  border:1.5px solid var(--edge2) !important}
button[data-testid="stBaseButton-pills"]{border:1.5px solid var(--edge) !important;box-shadow:none !important}
button[data-testid="stBaseButton-pillsActive"]{border:1.5px solid var(--edge2) !important;box-shadow:none !important}
.stButton>button:hover,.stLinkButton>a:hover,.stFormSubmitButton>button:hover{border-color:var(--terra) !important}
.stButton>button:focus-visible,.stLinkButton>a:focus-visible,.stFormSubmitButton>button:focus-visible{outline:3px solid var(--blue) !important;outline-offset:2px}
.stButton>button:disabled{opacity:.55;border-style:dashed !important}
.st-key-bottomnav button{border:1.5px solid var(--edge) !important;border-radius:14px !important;background:var(--card) !important;margin:0 2px}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="base-input"]{border:1.5px solid var(--edge) !important}
"""


def inject_css():
    css = CSS
    for k, v in (DARK if ss.theme == "dark" else LIGHT).items():
        css = css.replace("@%s@" % k, v)
    nav_on = ".st-key-nav_%s button{color:var(--blue) !important}" % {"detail": "search"}.get(ss.page, ss.page)
    st.markdown(css + "<style>" + BUTTON_BORDERS + nav_on + "</style>", unsafe_allow_html=True)


inject_css()

# ---------------------------------------------------------- loading screen ----
if not ss.loaded:
    holder = st.empty()
    holder.markdown('<div id="pf-load"><div class="pf-lp">📍</div><div class="pf-lb">P</div>'
                    '<div class="pf-lt">ParkFinder <em>UAE</em></div>'
                    '<div class="pf-ls">Finding the best parking near you...</div>'
                    '<div class="pf-bar"><i></i></div></div>', unsafe_allow_html=True)
    time.sleep(2.4)
    holder.empty()
    ss.loaded = True


# ============================================================== 6. CALLBACKS ====
def cb_go(page):
    ss.page, ss.detail = page, None


def cb_open(pid):
    ss.detail = pid


def cb_close():
    ss.detail = None


def cb_theme():
    ss.theme = "dark" if ss.theme == "light" else "light"


def cb_toggle_save(pid):
    data = load_json("saved.json", {})
    mine = [i for i in data.get(user_key(), []) if i in BY_ID]
    if pid in mine:
        mine.remove(pid)
        st.toast("Removed from saved parking")
    else:
        mine.append(pid)
        st.toast("Saved: " + BY_ID[pid]["name"])
    data[user_key()] = mine
    save_json("saved.json", data)


def cb_more_results():
    ss.search_limit += 25


def cb_search(src):
    ss.search_limit = 25
    ss.q = ss.get(src, "").strip()
    ss.page, ss.detail = "search", None


def cb_start_parking(pid):
    p, t = BY_ID[pid], ss.timer
    if t["state"] in ("running", "paused"):
        st.toast("A timer is already running. Stop or reset it first.")
    else:
        ss.timer = {"state": "idle", "parking": pid, "rate": None, "acc": 0.0, "seg": None}
        ss.timer_rate = num(p["price"]) if p["price"] is not None else ""
    ss.page, ss.detail = "timer", None


def cb_calc_cost(pid):
    price = BY_ID[pid]["price"]
    ss.calc_rate = float(price) if price is not None else 0.0
    ss.page, ss.detail = "calc", None


def t_elapsed(t):
    """Elapsed seconds from real timestamps (not from counting screen refreshes)."""
    return t["acc"] + (time.time() - t["seg"]) if t["state"] == "running" else t["acc"]


def cb_timer_start():
    text = str(ss.get("timer_rate", "")).strip().replace(",", ".")
    rate = None
    if text:
        try:
            rate = float(text)
            if rate < 0:
                raise ValueError
        except ValueError:
            st.toast("The rate was not a valid number, so no rate will be used.")
            rate = None
    ss.timer.update(state="running", rate=rate, acc=0.0, seg=time.time())


def cb_timer_pause():
    t = ss.timer
    if t["state"] == "running":
        t["acc"] += time.time() - t["seg"]
        t.update(state="paused", seg=None)
    elif t["state"] == "paused":
        t.update(state="running", seg=time.time())


def cb_timer_stop():
    t = ss.timer
    if t["state"] in ("running", "paused"):
        t.update(acc=t_elapsed(t), state="stopped", seg=None)


def cb_timer_reset():
    ss.timer = {"state": "idle", "parking": None, "rate": None, "acc": 0.0, "seg": None}


def cb_set_area():
    """Set the point distances are measured from: a demo place name, or any UAE place (needs internet)."""
    text = ss.get("nearby_q", "").strip().lower()
    if not text:
        ss.nearby_msg = "Please type an area, landmark or city."
        return
    hit = next((p for p in PARKINGS if text in " ".join([p["name"], p["area"], p["city"]]).lower()), None)
    if hit:
        ss.ref = {"label": hit["area"] if text in hit["area"].lower() else hit["name"], "pt": (hit["lat"], hit["lon"])}
        ss.nearby_msg = "Distances are now measured from %s." % ss.ref["label"]
        return
    try:
        query = urllib.parse.urlencode({"q": text, "format": "json", "limit": 1, "countrycodes": "ae"})
        req = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + query, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.load(r)
        if data:
            ss.ref = {"label": data[0].get("display_name", text).split(",")[0], "pt": (float(data[0]["lat"]), float(data[0]["lon"]))}
            ss.nearby_msg = "Distances are now measured from %s." % ss.ref["label"]
        else:
            ss.nearby_msg = "We couldn't find that place in the UAE. Try another area or landmark."
    except Exception:
        ss.nearby_msg = "Couldn't look that place up online. Try an area from the list, like Dubai Marina or Deira."


def cb_reset_area():
    ss.ref = {"label": "Downtown Dubai", "pt": REFS["Downtown Dubai"]}
    ss.nearby_msg = ""


def cb_logout():
    try:
        if st.user.is_logged_in:
            st.logout()
    except Exception:
        pass
    ss.user, ss.page, ss.detail, ss.auth_view = None, "home", None, "login"


def cb_guest():
    ss.user = {"name": "Guest", "email": "", "guest": True}


def cb_auth_view(view):
    ss.auth_view, ss.auth_msg = view, ""


def google_configured():
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def cb_google():
    if not google_configured():
        ss.auth_msg = ("Google sign-in isn't switched on for this copy of the app yet (the owner must add Google "
                       "keys in Streamlit's secrets). Use email or continue as a guest.")
        return
    try:
        st.login()
    except Exception:
        ss.auth_msg = "Google sign-in could not start. Please use email or continue as a guest."


def cb_delete_account():
    users = load_json("users.json", {})
    users.pop((ss.user or {}).get("email", ""), None)
    save_json("users.json", users)
    data = load_json("saved.json", {})
    data.pop(user_key(), None)
    save_json("saved.json", data)
    ss.user, ss.page, ss.detail, ss.auth_view = None, "home", None, "login"
    ss.auth_msg = "Your account was deleted."


# =========================================================== 7. UI HELPERS ====
def esc(x):
    return html.escape(str(x))


def md(x):
    st.markdown(x, unsafe_allow_html=True)


PILL = {"Available": ("pf-ok", "Available"), "Almost Full": ("pf-warn", "Limited"),
        "Full": ("pf-bad", "Full"), "Unknown": ("pf-unk", "Unknown")}


def pill(status, src=""):
    cls, label = PILL[status]
    if src.startswith(("Typical", "Average")):
        label = "Usually " + label.lower()
    return '<span class="pf-pill %s"><i></i>%s</span>' % (cls, label)


def title(eyebrow, text, lead=""):
    md((('<div class="pf-eyebrow">%s</div>' % esc(eyebrow)) if eyebrow else "")
       + '<div class="pf-title">%s</div>' % esc(text)
       + (('<div class="pf-lead">%s</div>' % esc(lead)) if lead else ""))


def empty_state(icon, head, text):
    md('<div class="pf-empty"><div class="pf-icon">%s</div><b>%s</b>%s</div>' % (icon, esc(head), esc(text)))


def card_html(p, status, src, tag=None):
    km = dist_km(p)
    free = free_spaces(p)
    if free is not None:
        spaces = "%d / %d spaces" % (free, p["total"])
    else:
        spaces = "~%d%% full now (typical)" % round(occupancy_estimate(p, now_uae())[0])
    return ('<div class="pf-cardhead"><div>'
            + ('<div class="pf-eyebrow" style="color:var(--blue)">★ %s</div>' % esc(tag) if tag else "")
            + '<div class="pf-name">%s</div><div class="pf-sub">%s · %s</div></div>%s</div>'
            % (esc(p["name"]), esc(p["area"]), esc(p["city"]), pill(status, src))
            + '<span class="pf-tag">%s</span>' % esc(p["type"])
            + '<div class="pf-tiles"><div><small>Distance</small><b>%s</b></div><div><small>Walk</small><b>%s</b></div>'
              '<div><small>Price</small><b>%s</b></div></div>' % ("%.1f km" % km, walk_text(km), esc(price_text(p)))
            + '<div class="pf-foot"><span>%s</span><span>%s</span></div>' % (spaces, esc(p["hours"]))
            + '<div class="pf-src">Source: %s</div>' % esc(src))


def parking_card(p, ctx, tag=None, show_start=False):
    status, src = effective_status(p)
    saved = p["id"] in SAVED
    with st.container(key="card_%s_%s" % (ctx, p["id"])):
        md(card_html(p, status, src, tag))
        c1, c2, c3 = st.columns(3)
        c1.button("Details", key="%s_d_%s" % (ctx, p["id"]), on_click=cb_open, args=(p["id"],), use_container_width=True)
        c2.link_button("Directions", directions_url(p), use_container_width=True)
        c3.button("♥ Saved" if saved else "♡ Save", key="%s_s_%s" % (ctx, p["id"]), on_click=cb_toggle_save,
                  args=(p["id"],), use_container_width=True)
        if show_start:
            st.button("Start Parking", key="%s_t_%s" % (ctx, p["id"]), on_click=cb_start_parking, args=(p["id"],),
                      type="primary", use_container_width=True)


def banner(p, text, label="Recommended for you", key="rec"):
    md('<div class="pf-banner"><div class="pf-bicon">✨</div><div><div class="pf-b1">%s</div>'
       '<div class="pf-b2">%s</div><div class="pf-b3">%s</div></div></div>' % (esc(label.upper()), esc(p["name"]), esc(text)))
    st.button("View details", key="%s_v_%s" % (key, p["id"]), on_click=cb_open, args=(p["id"],))


def info_card(icon, head, text, key, button=None, target=None):
    with st.container(key="card_%s" % key):
        left, right = st.columns([4, 1.4])
        left.markdown('<div class="pf-row"><div class="pf-icon">%s</div><div><div class="pf-rowt">%s</div>'
                      '<div class="pf-rowd">%s</div></div></div>' % (icon, esc(head), esc(text)), unsafe_allow_html=True)
        if button:
            right.button(button, key="btn_" + key, on_click=cb_go, args=(target,), use_container_width=True)


def chips(options, key, default):
    try:
        value = st.pills("Filter", options, default=default, key=key, label_visibility="collapsed")
    except Exception:           # older Streamlit versions have no pills
        value = st.radio("Filter", options, index=options.index(default), key=key, horizontal=True,
                         label_visibility="collapsed")
    return value or default


def ref_caption():
    st.caption("Distances are measured from %s (straight-line estimates). Change it on the Nearby page." % ss.ref["label"])


def footer():
    st.caption("Prototype · locations © OpenStreetMap contributors · no live availability sensors · built with help from AI tools"
               if DATA_INFO["source"] != "demo" else "Prototype · demo data, not live availability · built with help from AI tools")


def hero_style():
    for name in ("hero.jpg", "hero.jpeg", "hero.png", "dubai.jpg", "dubai.png"):
        path = os.path.join(HERE, name)
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                return "background-image:url(data:image/%s;base64,%s)" % ("png" if name.endswith("png") else "jpeg", b64)
            except OSError:
                pass
    return ""


# ================================================================= 8. PAGES ====
def page_home():
    _, right = st.columns([6, 1])
    right.button("🌙" if ss.theme == "light" else "☀️", key="home_theme", on_click=cb_theme, help="Light / dark mode")
    md('<div class="pf-hero" style="%s"><div class="pf-brand">📍 PARKFINDER UAE</div>'
       '<div class="pf-h1">Find parking near your destination</div>'
       '<div class="pf-hsub">Street bays and garages across Dubai, Sharjah and Ajman.</div></div>' % hero_style())
    with st.form("home_form"):
        c1, c2 = st.columns([3, 1.4])
        c1.text_input("Search", key="home_q", placeholder="Where do you want to park?", label_visibility="collapsed")
        c2.form_submit_button("Find Parking", type="primary", on_click=cb_search, args=("home_q",), use_container_width=True)
    info_card("🎯", "Enable location", "Show every parking spot near you, including street parking", "h_loc", "Open →", "nearby")
    info_card("✨", "Smart Recommendation", "Let us pick the best parking for you.", "h_rec", "Try →", "nearby")
    info_card("🧭", "Nearby Parking", "Parking around you, with a free-parking filter and our best pick.", "h_near", "Open →", "nearby")
    info_card("⏱️", "Parking Timer", "Keep track of how long you've been parked.", "h_timer", "Open →", "timer")
    info_card("🧮", "Cost Calculator", "Estimate your parking cost before you park.", "h_calc", "Open →", "calc")
    c1, c2 = st.columns([4, 1])
    c1.markdown('<div class="pf-eyebrow" style="margin-top:14px">Nearby</div><div class="pf-title">Nearby parking</div>', unsafe_allow_html=True)
    c2.button("See all", key="home_all", on_click=cb_go, args=("search",))
    ref_caption()
    data_status("home")
    for p in sorted(PARKINGS, key=dist_km)[:3]:
        parking_card(p, "home")
    md('<div class="pf-eyebrow" style="margin-top:14px">Explore</div><div class="pf-title">Map view</div>')
    info_card("🗺️", "All {:,} parking locations".format(len(PARKINGS)), "Pick a city, then tap a pin for details.", "h_map", "Open →", "map")
    info_card("📍", "ParkFinder UAE", "Street and garage parking across Dubai, Sharjah and Ajman.", "h_about", "About", "about")
    footer()


FILTER_CHIPS = ["All", "Free", "Paid", "Street", "Garage"]
STATUS_FILTER = {"Any": None, "Available": "Available", "Limited": "Almost Full", "Full": "Full", "Unknown": "Unknown"}


def passes_chip(p, chip):
    return (chip == "All" or (chip == "Free" and p["price"] == 0) or (chip == "Paid" and ((p["price"] or 0) > 0 or p.get("fee") == "yes"))
            or (chip in ("Street", "Garage") and p["type"] == chip))


def page_search():
    title(None, "Search results")
    with st.form("search_form"):
        c1, c2 = st.columns([4, 1])
        c1.text_input("Search", value=ss.q, key="search_q", placeholder="Where do you want to park?",
                      label_visibility="collapsed")
        c2.form_submit_button("Go", type="primary", on_click=cb_search, args=("search_q",), use_container_width=True)
    chip = chips(FILTER_CHIPS, "chip", "All")
    with st.expander("More filters"):
        f1, f2, f3 = st.columns(3)
        city = f1.selectbox("City", ["All"] + CITIES)
        avail = f2.selectbox("Availability", list(STATUS_FILTER))
        within = f3.selectbox("Within", ["Any", "1 km", "3 km", "5 km", "10 km", "25 km"])
    words = ss.q.lower().split()
    items = []
    for p in PARKINGS:
        hay = " ".join([p["name"], p["area"], p["city"], p["type"]]).lower()
        if not all(w in hay for w in words) or not passes_chip(p, chip):
            continue
        if city != "All" and p["city"] != city:
            continue
        if STATUS_FILTER[avail] and effective_status(p)[0] != STATUS_FILTER[avail]:
            continue
        if within != "Any" and dist_km(p) > float(within.split()[0]):
            continue
        items.append(p)
    items.sort(key=dist_km)
    ref_caption()
    ranked = recommend(items)
    if ranked:
        banner(ranked[0][0], ranked[0][2])
        st.caption("Rule-based pick from distance, availability and price. It is not AI.")
    st.markdown("**%d parking location%s found**" % (len(items), "" if len(items) == 1 else "s"))
    if not items:
        empty_state("🔍", "No parking locations found.", "Try searching another area or city, or loosen the filters.")
    shown = items[:ss.search_limit]
    for p in shown:
        parking_card(p, "search")
    if len(items) > len(shown):
        st.caption("Showing the closest %d of %d." % (len(shown), len(items)))
        st.button("Show 25 more", key="search_more", on_click=cb_more_results, use_container_width=True)
    footer()


def draw_map(city):
    """Pins coloured by status. Returns the id of a tapped pin (or None). Falls back to a plain map / message."""
    color = {"Available": [46, 158, 107], "Almost Full": [233, 162, 59], "Full": [229, 88, 107], "Unknown": [138, 146, 144]}
    rows = []
    for p in PARKINGS:
        if city != "Whole UAE" and p["city"] != city:
            continue
        status = effective_status(p)[0]
        rows.append({"pid": p["id"], "name": p["name"], "label": PILL[status][1], "lat": p["lat"], "lon": p["lon"],
                     "color": color[status]})
    lat, lon, zoom = CITY_VIEW[city]
    try:
        import pydeck as pdk
        layer = pdk.Layer("ScatterplotLayer", data=rows, id="spots", get_position="[lon, lat]", get_fill_color="color",
                          get_line_color=[255, 255, 255], stroked=True, line_width_min_pixels=2, get_radius=180,
                          radius_min_pixels=9 if len(rows) < 300 else 4, radius_max_pixels=18, pickable=True)
        deck = pdk.Deck(layers=[layer], initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom),
                        map_style="dark" if ss.theme == "dark" else "light", tooltip={"text": "{name}\n{label}"})
        try:
            event = st.pydeck_chart(deck, height=380, on_select="rerun", selection_mode="single-object", key="map_" + city)
            objects = event.selection.get("objects", {}).get("spots", [])
            return objects[0]["pid"] if objects else None
        except TypeError:                       # older Streamlit: no tap-to-select
            st.pydeck_chart(deck)
            return None
    except Exception:
        try:
            import pandas as pd
            st.map(pd.DataFrame(rows), latitude="lat", longitude="lon")
        except Exception:
            st.warning("The map isn't available right now, so please use the list below.")
        return None


def page_map():
    title(None, "Parking map", "All %d parking locations across the UAE. Pick a city to zoom in, then tap a pin for details." % len(PARKINGS))
    city = chips(list(CITY_VIEW), "map_city", "Whole UAE")
    pid = draw_map(city)
    md('<div style="display:flex;gap:18px;justify-content:center;color:var(--muted);font-size:.85rem;margin:6px 0 12px">'
       '<span><span style="color:#2E9E6B">●</span> Available</span><span><span style="color:#E9A23B">●</span> Limited</span>'
       '<span><span style="color:#E5586B">●</span> Full</span></div>')
    near = sorted(PARKINGS if city == "Whole UAE" else [p for p in PARKINGS if p["city"] == city], key=dist_km)[:40]
    labels = {p["id"]: "%s · %s · %.1f km" % (p["name"], p["area"], dist_km(p)) for p in near}
    pick = st.selectbox("Or choose one of the 40 closest spots", ["—"] + list(labels), format_func=lambda i: labels.get(i, "—"))
    chosen = pid or (pick if pick != "—" else None)
    if chosen:
        parking_card(BY_ID[chosen], "map", tag="Selected")
    else:
        st.caption("Tap a pin on the map, or choose a spot above.")
    st.markdown("**Where we cover**")
    cols = st.columns(3)
    for col, c in zip(cols, CITIES):
        col.metric(c, "{:,}".format(sum(1 for p in PARKINGS if p["city"] == c)))
    st.caption("Total: {:,} parking places · {:,} with a mapped capacity · {:,} marked free".format(
        len(PARKINGS), sum(1 for p in PARKINGS if p.get("capacity")), sum(1 for p in PARKINGS if p["price"] == 0)))
    data_status("map")
    footer()


def use_my_location():
    """'Enable location' - the browser itself asks the person for permission. Nothing is stored."""
    with st.container(key="card_geo"):
        md('<div style="font-weight:700">🎯 Enable location</div>'
           '<div style="color:var(--muted);font-size:.9rem;margin-bottom:6px">Tap the button. Your browser will ask for '
           'permission, then we measure distances from where you are. Your position stays in this session only.</div>')
        if streamlit_geolocation is None:
            st.caption("Location button not installed (pip install streamlit-geolocation). Type an area below instead.")
            return
        loc = streamlit_geolocation()
        lat, lon = (loc or {}).get("latitude"), (loc or {}).get("longitude")
        if lat is None or lon is None:
            st.caption("Waiting for permission... If nothing happens, allow location for this site in your browser, "
                       "or type an area below.")
            return
        key = (round(lat, 5), round(lon, 5))
        if ss.get("geo_applied") != key:
            ss.geo_applied = key
            nearest = min(haversine_km(lat, lon, p["lat"], p["lon"]) for p in PARKINGS)
            if nearest > 150:
                ss.nearby_msg = ("Your location is %.0f km from the nearest demo parking, so these distances are not "
                                 "useful. Type a UAE area below instead." % nearest)
            else:
                ss.ref = {"label": "your location", "pt": (lat, lon)}
                ss.nearby_msg = "Using your device location (accuracy about %s m)." % int(loc.get("accuracy") or 0)


def page_nearby():
    title("Nearby", "Nearby Parking", "Use your location, filter for free parking, and see our best pick for you.")
    use_my_location()
    with st.form("nearby_form"):
        c1, c2 = st.columns([3, 1.4])
        c1.text_input("Area", key="nearby_q", placeholder="e.g. Dubai Marina, Deira, Mall of the Emirates",
                      label_visibility="collapsed")
        c2.form_submit_button("Set location", type="primary", on_click=cb_set_area, use_container_width=True)
    if ss.nearby_msg:
        st.caption(ss.nearby_msg)
    ref_caption()
    st.button("Reset to Downtown Dubai", key="n_reset", on_click=cb_reset_area)
    free_only = st.toggle("Free parking only")
    items = [p for p in sorted(PARKINGS, key=dist_km) if not free_only or p["price"] == 0]
    ranked = recommend(items)
    if ranked:
        banner(ranked[0][0], "Recommended: %s" % ranked[0][2], label="Best parking", key="best")
    if not items:
        empty_state("🔍", "No parking locations found.", "Turn off the free filter or set another area.")
    for p in items[:12]:
        parking_card(p, "near")
    if len(items) > 12:
        st.caption("Showing the 12 closest. Use Search to see all %d." % len(items))
    footer()


def page_saved():
    title(None, "Saved Parking", "Your saved parking locations.")
    items = [BY_ID[i] for i in SAVED]
    if not items:
        empty_state("♡", "Nothing saved yet", "Save parking locations so you can quickly find them again.")
    for p in items:
        parking_card(p, "saved", show_start=True)
    footer()


def page_profile():
    title("Your account", "Profile", "Review the details linked to your ParkFinder account.")
    u = ss.user
    info_card("✉️", u["name"], u["email"] or "Guest mode: nothing is linked to an email.", "p_user")
    with st.container(key="card_p_theme"):
        st.toggle("Dark mode", value=ss.theme == "dark", on_change=cb_theme, key="dark_toggle")
        st.caption("Your theme is remembered while the app is open.")
    if u.get("guest"):
        info_card("👤", "Guest mode", "Saved spots stay on this computer. Log out to create an account.", "p_guest")
    elif u["email"] and u["email"] in load_json("users.json", {}):
        with st.container(key="card_p_delete"):
            md('<div class="pf-row"><div class="pf-icon">🗑️</div><div><div class="pf-rowt">Delete account</div>'
               '<div class="pf-rowd">Permanently removes your ParkFinder account and your saved spots. This cannot be undone.</div></div></div>')
            sure = st.checkbox("I understand this cannot be undone", key="del_sure")
            st.button("Delete my account", key="del_btn", on_click=cb_delete_account, disabled=not sure)
    st.button("Log out", key="logout", on_click=cb_logout, use_container_width=True)
    footer()


def page_about():
    title("About", "Parking in the UAE, without the circling",
          "ParkFinder UAE brings street bays and paid garages across Dubai, Sharjah and Ajman into one simple view, so you "
          "can see what is available, what it costs and how far you will walk before you set off.")
    info_card("🔍", "Search or tap a pin", "Look up an area, a landmark or a city and see what is free right now.", "a1")
    info_card("✨", "Compare at a glance", "Distance, walking time and hourly price sit side by side on every card.", "a2")
    info_card("🧭", "Drive straight there", "Open directions in one tap, or save the spot to your favourites for later.", "a3")
    md('<div class="pf-eyebrow" style="margin-top:14px">Coverage</div><div class="pf-title">Where we cover</div>')
    for c in CITIES:
        info_card("📍", c, "{:,} parking locations listed".format(sum(1 for p in PARKINGS if p["city"] == c)), "cov_" + c)
    with st.container(key="card_a_how"):
        md('<div class="pf-eyebrow">How we choose</div><div class="pf-title" style="font-size:1.5rem">Free street bays and paid garages, side by side</div>'
           '<div class="pf-lead">Every listing shows whether it is free or paid, a street bay or a garage, its opening hours and how '
           'many spaces are free. Locations come from OpenStreetMap and refresh every 30 minutes. Live free-space counts are not published for them, '
           'so availability shows a typical estimate for the day and time (marked "Usually..."), replaced by driver reports when '
           'they exist, and the top suggestion is a simple visible score of distance, availability and price.</div>')
        st.button("Browse parking", key="a_browse", on_click=cb_go, args=("search",), type="primary")
    footer()


def page_timer():
    t = ss.timer
    st.button("← Home", key="timer_back", on_click=cb_go, args=("home",))
    title(None, "Parking Timer", "Start the timer yourself when you park. It uses real timestamps, so it stays accurate.")
    p = BY_ID.get(t["parking"])
    st.markdown("**Parking:** " + (p["name"] if p else "none selected (manual timer)"))
    if t["state"] == "idle":
        st.text_input("Rate in AED per hour (optional)", key="timer_rate", placeholder="e.g. 5 or 2.50")
    timer_clock()
    b1, b2, b3, b4 = st.columns(4)
    b1.button("START", on_click=cb_timer_start, disabled=t["state"] != "idle", type="primary", use_container_width=True)
    b2.button("RESUME" if t["state"] == "paused" else "PAUSE", on_click=cb_timer_pause,
              disabled=t["state"] not in ("running", "paused"), use_container_width=True)
    b3.button("STOP", on_click=cb_timer_stop, disabled=t["state"] not in ("running", "paused"), type="primary", use_container_width=True)
    b4.button("RESET", on_click=cb_timer_reset, disabled=t["state"] == "idle", use_container_width=True)
    if t["state"] == "stopped":
        with st.container(key="card_t_done"):
            st.subheader("Parking Session Complete")
            st.write("**Parking:** " + (p["name"] if p else "Manual timer"))
            st.write("**Duration:** " + fmt_duration(t["acc"]))
            if t["rate"] is not None:
                st.success("Estimated cost: AED %.2f" % estimate_cost(t["rate"], t["acc"] / 60)[2])
                st.caption("An estimate based on AED %s/hour. The official fee may be different." % num(t["rate"]))
            else:
                st.caption("Add a rate next time to see an estimated cost.")
    footer()


def _live(fn):
    """Re-draw the clock every second when this Streamlit version supports fragments."""
    fragment = getattr(st, "fragment", None)
    if fragment:
        try:
            return fragment(run_every=1)(fn)
        except TypeError:
            pass
    return fn


@_live
def timer_clock():
    t = ss.timer
    e = t_elapsed(t)
    md("<div style='text-align:center;font-size:4rem;font-weight:800;color:var(--blue)'>%s</div>"
       "<div style='text-align:center;color:var(--muted)'>%s</div>"
       % (fmt_clock(e), "Parked for " + fmt_duration(e) if t["state"] != "idle" else "Press START when you park."))
    if t["rate"] is not None and t["state"] != "idle":
        md("<div style='text-align:center;font-weight:800'>Estimated cost: AED %.2f <span style='font-weight:400'>(estimate)</span></div>"
           % estimate_cost(t["rate"], e / 60)[2])


def page_calc():
    st.button("← Home", key="calc_back", on_click=cb_go, args=("home",))
    title(None, "Cost Calculator", "An estimate only. It does not know the official parking fee.")
    rate = st.number_input("Parking rate (AED per hour)", min_value=0.0, step=0.5, key="calc_rate")
    c1, c2 = st.columns(2)
    hours = c1.number_input("Duration: hours", min_value=0, step=1, key="calc_hours")
    mins = c2.number_input("Duration: minutes", min_value=0, step=5, key="calc_mins")
    free = st.number_input("Free period in minutes (optional)", min_value=0.0, step=5.0, key="calc_free")
    use_cap = st.checkbox("Use a maximum daily charge", key="calc_use_cap")
    cap = st.number_input("Maximum daily charge (AED)", min_value=0.0, step=1.0, key="calc_cap", disabled=not use_cap)
    total = hours * 60 + mins
    if total <= 0:
        st.info("Enter a parking duration to see the estimate.")
        return
    billable, raw, cost = estimate_cost(rate, total, free, cap if use_cap else None)
    with st.container(key="card_c_result"):
        st.markdown("**Parking rate:** AED %s/hour  \n**Duration:** %s" % (num(rate), fmt_duration(total * 60)))
        if free:
            st.markdown("**Free period:** %s minutes" % num(free))
        st.markdown("**Calculation:** %s × %s hours = AED %.2f" % (num(rate), num(billable / 60), raw))
        if use_cap and cost < raw:
            st.markdown("Daily maximum of AED %s applied." % num(cap))
        st.success("Estimated cost: AED %.2f" % cost)
        st.caption("This is an estimate. The official parking fee may be different.")
    footer()


def weekly_pattern(p):
    """Typical busyness for every weekday at four times, plus today's quietest hour. Clearly labelled as an estimate."""
    now = now_uae()
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    times = [(9, "9 AM"), (13, "1 PM"), (18, "6 PM"), (21, "9 PM")]
    base = now - datetime.timedelta(days=now.weekday())
    head = "".join("<th style='padding:4px 6px;%s'>%s</th>" % ("color:var(--blue)" if i == now.weekday() else "", d) for i, d in enumerate(days))
    body = ""
    for hour, label in times:
        cells = ""
        for i in range(7):
            dt = (base + datetime.timedelta(days=i)).replace(hour=hour, minute=0)
            pct = occupancy_estimate(p, dt)[0]
            colour = "#2E9E6B" if pct < 75 else "#E9A23B" if pct < 95 else "#E5586B"
            cells += "<td style='padding:4px 6px;text-align:center;color:%s;font-weight:700'>%d%%</td>" % (colour, round(pct))
        body += "<tr><td style='padding:4px 6px;color:var(--muted)'>%s</td>%s</tr>" % (label, cells)
    best = min((occupancy_estimate(p, now.replace(hour=h, minute=0))[0], h) for h in range(6, 23))[1]
    with st.container(key="card_det_week"):
        md('<div class="pf-rowt" style="font-size:1.1rem">Typical busyness this week</div>'
           '<div class="pf-rowd">How full this kind of place usually is (percent of spaces taken). It is an ESTIMATE from a simple '
           'daily pattern, not a live count. When 3+ drivers report for the same weekday and hour, their average is used instead.</div>'
           '<div style="overflow-x:auto"><table style="width:100%%;font-size:.85rem;border-collapse:collapse"><tr><th></th>%s</tr>%s</table></div>'
           '<div class="pf-rowd" style="margin-top:6px">Usually quietest today around <b>%s</b>.</div>'
           % (head, body, datetime.time(best).strftime("%I %p").lstrip("0")))


def details_page(p):
    status, src = effective_status(p)
    km = dist_km(p)
    saved = p["id"] in SAVED
    st.button("← Back", key="det_back", on_click=cb_close)
    md('<div class="pf-cardhead"><div><div class="pf-title">%s</div><div class="pf-sub">%s · %s</div></div>%s</div>'
       % (esc(p["name"]), esc(p["area"]), esc(p["city"]), pill(status, src)))
    free = free_spaces(p)
    rows = [("Parking type", p["type"]), ("Price", price_text(p)), ("Distance", "%.1f km from %s" % (km, ss.ref["label"])),
            ("Walking time", walk_text(km)), ("Opening hours", p["hours"]),
            ("Spaces", "%d free of %d (%.1f%% occupied)" % (free, p["total"], p["occupied"] / p["total"] * 100) if free is not None
             else "About %d%% full now%s" % (round(occupancy_estimate(p, now_uae())[0]),
                                        " · mapped capacity %d" % p["capacity"] if p.get("capacity") else "")),
            ("Availability", "%s (%s)" % (PILL[status][1], src)), ("Location data", "Demo data (approximate coordinates)" if p.get("src") == "demo"
             else "OpenStreetMap contributors (real mapped location)")]
    with st.container(key="card_det_info"):
        md("".join('<div class="pf-info"><span>%s</span><b>%s</b></div>' % (esc(k), esc(v)) for k, v in rows))
        c1, c2 = st.columns(2)
        c1.link_button("Get Directions", directions_url(p), use_container_width=True)
        c2.button("Remove Saved" if saved else "Save Parking", key="det_save", on_click=cb_toggle_save, args=(p["id"],), use_container_width=True)
        c3, c4 = st.columns(2)
        c3.button("Start Parking", key="det_start", on_click=cb_start_parking, args=(p["id"],), type="primary", use_container_width=True)
        c4.button("Calculate Cost", key="det_calc", on_click=cb_calc_cost, args=(p["id"],), use_container_width=True)
    weekly_pattern(p)
    with st.container(key="card_det_report"):
        md('<div class="pf-rowt" style="font-size:1.1rem">Report current availability</div>'
           '<div class="pf-rowd">Community reports come from users like you. They are labelled and expire after 2 hours.</div>')
        with st.form("report_" + p["id"], clear_on_submit=True):
            labels = {"available": "Available", "almost_full": "Limited (almost full)", "full": "Full"}
            fb = st.radio("What is it like right now?", list(labels), format_func=labels.get, horizontal=True)
            av = st.radio("Is there a free space right now?", ["yes", "no"], horizontal=True)
            if st.form_submit_button("Submit report", type="primary"):
                reports = load_json("reports.json", [])
                reports.append({"parking_id": p["id"], "parking_name": p["name"], "feedback_type": fb,
                                "available": av, "timestamp": time.time()})
                save_json("reports.json", reports)
                st.toast("Thanks! Saved as a community report.")
                st.rerun()
    footer()


# ================================================================ 9. LOGIN ====
def auth_screen():
    view = ss.auth_view
    heads = {"login": ("➜", "Welcome back", "Log in to your account"),
             "signup": ("👤", "Create your account", "Sign up to get started"),
             "reset": ("✉️", "Reset password", "We'll send you a link to reset it")}
    icon, head, sub = heads[view]
    md('<div style="text-align:center;margin-top:1.5rem"><div style="display:inline-grid;place-items:center;width:62px;height:62px;'
       'border-radius:18px;background:#17181C;color:#fff;font-size:1.7rem">%s</div>'
       '<div class="pf-title" style="margin-top:.8rem">%s</div><div class="pf-lead">%s</div></div>' % (icon, head, sub))
    if ss.auth_msg:
        st.info(ss.auth_msg)
    with st.container(key="card_auth"):
        if view in ("login", "signup"):
            st.button("Continue with Google", key="g_btn", on_click=cb_google, use_container_width=True)
            md('<div style="text-align:center;color:var(--muted);margin:6px 0">— OR —</div>')
        if view == "login":
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                pw = st.text_input("Password", type="password", placeholder="••••••••")
                if st.form_submit_button("Log in", type="primary", use_container_width=True):
                    user = check_login(email, pw)
                    if user:
                        ss.user, ss.auth_msg = user, ""
                        st.rerun()
                    st.error("Email or password is incorrect.")
            st.button("Forgot password?", key="to_reset", on_click=cb_auth_view, args=("reset",))
        elif view == "signup":
            with st.form("signup_form"):
                name = st.text_input("Name", placeholder="Your name")
                email = st.text_input("Email", placeholder="you@example.com")
                pw = st.text_input("Password", type="password", placeholder="At least 8 characters")
                pw2 = st.text_input("Confirm Password", type="password", placeholder="Type it again")
                if st.form_submit_button("Create account", type="primary", use_container_width=True):
                    if pw != pw2:
                        st.error("The two passwords don't match.")
                    else:
                        user, error = make_account(name, email, pw)
                        if user:
                            ss.user = user
                            st.rerun()
                        st.error(error)
        else:
            with st.form("reset_form"):
                st.text_input("Email address", placeholder="you@example.com")
                if st.form_submit_button("Send reset link", type="primary", use_container_width=True):
                    st.info("This school prototype can't send emails, so no link was sent. You can create a new "
                            "account instead.")
    if view == "login":
        st.button("Don't have an account? Create one", key="to_signup", on_click=cb_auth_view, args=("signup",), use_container_width=True)
    else:
        st.button("← Back to log in", key="to_login", on_click=cb_auth_view, args=("login",), use_container_width=True)
    st.button("Continue as guest", key="guest_btn", on_click=cb_guest, use_container_width=True)
    st.caption("Accounts are stored only on this computer (prototype). Passwords are salted and hashed, never saved as typed.")


# =============================================================== 10. ROUTER ====
if ss.user is None:
    ss.user = google_user()
if ss.user is None:
    auth_screen()
    st.stop()

load_parkings()                     # refreshed from OpenStreetMap at most every 30 minutes
SAVED = get_saved()
PAGES = {"home": page_home, "search": page_search, "map": page_map, "saved": page_saved, "profile": page_profile,
         "nearby": page_nearby, "about": page_about, "timer": page_timer, "calc": page_calc}
if ss.detail in BY_ID:
    details_page(BY_ID[ss.detail])
else:
    PAGES[ss.page]()

with st.container(key="bottomnav"):
    for col, (page, label, icon) in zip(st.columns(5), [("home", "Home", "home"), ("search", "Search", "search"),
                                                         ("map", "Map", "map"), ("saved", "Saved", "favorite"),
                                                         ("profile", "Profile", "person")]):
        with col:
            st.button(label, key="nav_" + page, icon=":material/%s:" % icon, on_click=cb_go, args=(page,),
                      use_container_width=True)
