import os
import datetime as dt
import requests
import math
from flask import Flask, request, jsonify
from flask_cors import CORS
# from dotenv import load_dotenv

# load_dotenv()

app = Flask(__name__)
CORS(app)

WINDY_KEY = os.environ.get("WINDY_KEY")
WINDY_URL = "https://api.windy.com/api/point-forecast/v2"
MODEL = "gfs"
IST = dt.timedelta(hours=5, minutes=30)


def k_to_c(k):
    return round(k - 273.15, 1) if k is not None else None

def wind_to_speed_dir(u, v):
    """Windy ke wind_u, wind_v (m/s) se speed (km/h) + compass direction."""
    if u is None or v is None:
        return None, None
    speed_kmph = round(math.sqrt(u*u + v*v) * 3.6, 1)
    deg = (math.degrees(math.atan2(-u, -v)) + 360) % 360
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    compass = dirs[round(deg / 45) % 8]
    return speed_kmph, compass

def find_key(data, must_contain, must_not=None):
    """data ki keys mein se wo dhoondho jisme 'must_contain' ho.
       Naam exact pata na ho to ye bachata hai."""
    must_not = must_not or []
    for k in data.keys():
        kl = k.lower()
        if must_contain in kl and not any(x in kl for x in must_not):
            return k
    return None


@app.route("/")
def home():
    return "Windy backend chal raha hai. Use:  /forecast?lat=17.385&lon=78.486"


@app.route("/debug")
def debug():
    """Raw Windy keys + precip samples dikhata hai."""
    lat = float(request.args.get("lat", 25.30))
    lon = float(request.args.get("lon", 91.58))
    payload = {"lat": lat, "lon": lon, "model": MODEL,
               "parameters": ["temp", "precip", "wind"], "levels": ["surface"], "key": WINDY_KEY}
    r = requests.post(WINDY_URL, json=payload, timeout=20)
    data = r.json()
    out = {"status_code": r.status_code, "all_keys": list(data.keys()), "units": data.get("units", {})}
    for k in data.keys():
        if "precip" in k.lower():
            v = data[k]
            out["sample__" + k] = v[:8] if isinstance(v, list) else v
    return jsonify(out)


@app.route("/forecast")
def forecast():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "lat aur lon dono chahiye"}), 400

    if not WINDY_KEY:
        return jsonify({"error": "WINDY_KEY server pe set nahi hai"}), 500

    payload = {"lat": lat, "lon": lon, "model": MODEL,
               "parameters": ["temp", "precip", "wind"], "levels": ["surface"], "key": WINDY_KEY}
    try:
        r = requests.post(WINDY_URL, json=payload, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        return jsonify({"error": "Windy API fail: " + str(e)}), 502

    data = r.json()
    ts = data.get("ts", [])

    temp_key = find_key(data, "temp")
    precip_key = find_key(data, "precip", must_not=["snow", "conv"])

    temp = data.get(temp_key, []) if temp_key else []
    precip = data.get(precip_key, []) if precip_key else []

    if not ts:
        return jsonify({"location": {"lat": lat, "lon": lon}, "hourly": [], "daily": [], "note": "no data"}), 200

    points = []
    for i, t in enumerate(ts):
        d = dt.datetime.fromtimestamp(t / 1000, tz=dt.timezone.utc).replace(tzinfo=None)
        p_val = 0.0
        if i < len(precip) and precip[i] is not None:
            p_val = round(precip[i] * 1000, 2)   # meters → mm
        points.append({
            "dt": d,
            "temp": k_to_c(temp[i]) if i < len(temp) else None,
            "precip": p_val,
        })

    local_now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + IST

    def nearest(target):
        return min(points, key=lambda p: abs((p["dt"] - target).total_seconds()))

    hourly = []
    for label, hrs in [("+3 hr", 3), ("+6 hr", 6), ("+12 hr", 12)]:
        p = nearest(local_now + dt.timedelta(hours=hrs))
        hourly.append({"label": label, "time": p["dt"].strftime("%d %b, %I:%M %p"),
                       "temp": p["temp"], "precip": p["precip"]})

    daily_map = {}
    for p in points:
        key = p["dt"].date()
        slot = daily_map.setdefault(key, {"temps": [], "precip": 0.0})
        if p["temp"] is not None:
            slot["temps"].append(p["temp"])
        slot["precip"] += p["precip"]

    daily = []
    for key in sorted(daily_map.keys())[:7]:
        v = daily_map[key]
        if not v["temps"]:
            continue
        daily.append({"date": key.strftime("%a, %d %b"),
                      "min": round(min(v["temps"]), 1),
                      "max": round(max(v["temps"]), 1),
                      "precip": round(v["precip"], 1)})

    return jsonify({
        "location": {"lat": lat, "lon": lon},
        "model": MODEL,
        "precip_key_used": precip_key,
        "hourly": hourly,
        "daily": daily,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
