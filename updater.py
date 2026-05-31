import os, time, requests
from datetime import datetime, timezone
import warnings
warnings.filterwarnings("ignore")
from arcgis.gis import GIS

BACKEND  = "https://ghmc-weather-backend.onrender.com/forecast"
PORTAL   = "https://gis.ghmc.gov.in/portal"
ITEM_ID  = "f340491507324c878593d4c5c0a97d61"

USER = os.environ["PORTAL_USER"]
PWD  = os.environ["PORTAL_PASS"]

# ---------- CONNECT + DIAGNOSTICS ----------
print("1. Connecting to portal...", flush=True)
try:
    gis = GIS(PORTAL, USER, PWD, verify_cert=False, timeout=60)
    print("2. Connected as:", gis.users.me.username, flush=True)
except Exception as e:
    print("CONNECTION FAILED:", repr(e), flush=True)
    raise
gis = GIS(PORTAL, USER, PWD, verify_cert=False)
print("2. Connected as:", gis.users.me.username, flush=True)

item = gis.content.get(ITEM_ID)
print("3. Item found:", item.title, flush=True)

layer = item.layers[0]
print("4. Layer URL:", layer.url, flush=True)

oid_field = layer.properties.objectIdField

fset = layer.query(out_fields=oid_field, return_geometry=True, out_sr=4326)
print("5. Queried features:", len(fset.features), flush=True)

# ---------- FORECAST FETCH ----------
def get_forecast(lat, lon):
    r = requests.get(BACKEND, params={"lat": lat, "lon": lon}, timeout=90)
    r.raise_for_status()
    d = r.json()
    hourly = {h["label"].strip(): h.get("precip", 0) for h in d.get("hourly", [])}
    daily  = d.get("daily", [])
    day = lambda i: (daily[i].get("precip", 0) if len(daily) > i else 0)
    return {
        "rain_3h":  hourly.get("+3 hr", 0),
        "rain_6h":  hourly.get("+6 hr", 0),
        "rain_12h": hourly.get("+12 hr", 0),
        "rain_d1":  day(0),
        "rain_d3":  day(2),
        "rain_d5":  day(4),
        "rain_d7":  day(6),
    }

# ---------- BUILD UPDATES (sparse cache) ----------
cache, updates = {}, []
now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

for f in fset.features:
    lon, lat = f.geometry["x"], f.geometry["y"]
    cell = (round(lat, 1), round(lon, 1))
    if cell not in cache:
        print(f"   fetching forecast for cell {cell}...", flush=True)
        cache[cell] = get_forecast(cell[0], cell[1])
        time.sleep(1)
    attrs = {oid_field: f.attributes[oid_field], "updated_utc": now}
    attrs.update(cache[cell])
    updates.append({"attributes": attrs})

print("6. Built updates for", len(updates), "stations |", len(cache), "API calls", flush=True)

# ---------- PUSH (batches of 100) ----------
ok = 0
for i in range(0, len(updates), 100):
    batch = updates[i:i+100]
    res = layer.edit_features(updates=batch)
    ok += sum(1 for r in res.get("updateResults", []) if r.get("success"))
    print(f"   pushed batch {i//100 + 1}: {ok} ok so far", flush=True)

print(f"7. DONE. Updated {ok}/{len(updates)} stations", flush=True)