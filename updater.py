import os, time, requests
from datetime import datetime, timezone
from arcgis.gis import GIS

BACKEND   = "https://ghmc-weather-backend.onrender.com/forecast"
PORTAL    = "https://gis.ghmc.gov.in/portal"
ITEM_ID   = "f340491507324c878593d4c5c0a97d61"

USER = os.environ["PORTAL_USER"]
PWD  = os.environ["PORTAL_PASS"]

# 1. Enterprise portal se connect. SSL error aaye to verify_cert=False add karna.
gis = GIS(PORTAL, USER, PWD)
layer = gis.content.get(ITEM_ID).layers[0]
oid_field = layer.properties.objectIdField

# 2. Saare stations (geometry + oid) lat/lon degrees mein
fset = layer.query(out_fields=oid_field, return_geometry=True, out_sr=4326)

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
        "rain_d1":  day(0),   # day 1 = pehla forecast din
        "rain_d3":  day(2),
        "rain_d5":  day(4),
        "rain_d7":  day(6),
    }

# 3. ~0.1 deg cell pe cache — taaki 250 calls na ho, sirf ~6-10 calls
cache, updates = {}, []
now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

for f in fset.features:
    lon, lat = f.geometry["x"], f.geometry["y"]
    cell = (round(lat, 1), round(lon, 1))
    if cell not in cache:
        cache[cell] = get_forecast(cell[0], cell[1])
        time.sleep(1)
    attrs = {oid_field: f.attributes[oid_field], "updated_utc": now}
    attrs.update(cache[cell])
    updates.append({"attributes": attrs})

# 4. Push
res = layer.edit_features(updates=updates)
ok = sum(1 for r in res.get("updateResults", []) if r.get("success"))
print(f"Updated {ok}/{len(updates)} stations | API calls: {len(cache)}")