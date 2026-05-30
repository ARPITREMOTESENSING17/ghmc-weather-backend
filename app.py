import os
import datetime as dt
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()  # local .env se WINDY_KEY uthata hai

app = Flask(__name__)
CORS(app)  # browser (Experience Builder widget) ko call karne deta hai

WINDY_KEY = os.environ.get("WINDY_KEY")
WINDY_URL = "https://api.windy.com/api/point-forecast/v2"
MODEL = "gfs"                                  # India ke liye best global coverage
IST = dt.timedelta(hours=5, minutes=30)        # Windy ts local-shifted hote hain


def k_to_c(k):
    """Kelvin -> Celsius (Windy temp Kelvin mein deta hai)."""
    return round(k - 273.15, 1) if k is not None else None


@app.route("/")
def home():
    return "Windy backend chal raha hai. Use:  /forecast?lat=17.385&lon=78.486"


@app.route("/forecast")
def forecast():
    # --- 1) widget se aaye lat/lon ---
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "lat aur lon dono chahiye"}), 400

    if not WINDY_KEY:
        return jsonify({"error": "WINDY_KEY server pe set nahi hai"}), 500

    # --- 2) Windy ko call ---
    payload = {
        "lat": lat,
        "lon": lon,
        "model": MODEL,
        "parameters": ["temp", "precip"],
        "levels": ["surface"],
        "key": WINDY_KEY,
    }
    try:
        r = requests.post(WINDY_URL, json=payload, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        return jsonify({"error": f"Windy API fail: {e}"}), 502

    data = r.json()
    ts = data.get("ts", [])
    temp = data.get("temp-surface", [])
    precip = data.get("past3hprecip-surface", [])  # <-- precip ki response key yahi hai

    if not ts:
        return jsonify({"location": {"lat": lat, "lon": lon},
                        "hourly": [], "daily": [], "note": "no data"}), 200

    # --- 3) har timestamp ko ek clean point banao ---
    points = []
    for i, t in enumerate(ts):
        d = dt.datetime.fromtimestamp(t / 1000, tz=dt.timezone.utc).replace(tzinfo=None)
        points.append({
            "dt": d,
            "temp": k_to_c(temp[i]) if i < len(temp) else None,
            "precip": round(precip[i], 2) if i < len(precip) and precip[i] is not None else 0.0,
        })

    # --- 4) HOURLY: now+3h, +6h, +12h ke sabse paas wale points ---
    local_now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + IST

    def nearest(target):
        return min(points, key=lambda p: abs((p["dt"] - target).total_seconds()))

    hourly = []
    for label, hrs in [("+3 hr", 3), ("+6 hr", 6), ("+12 hr", 12)]:
        p = nearest(local_now + dt.timedelta(hours=hrs))
        hourly.append({
            "label": label,
            "time": p["dt"].strftime("%d %b, %I:%M %p"),
            "temp": p["temp"],
            "precip": p["precip"],
        })

    # --- 5) DAILY: date pe group, agle 7 din (precip = din bhar ka total) ---
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
        daily.append({
            "date": key.strftime("%a, %d %b"),
            "min": round(min(v["temps"]), 1),
            "max": round(max(v["temps"]), 1),
            "precip": round(v["precip"], 1),
        })

    return jsonify({
        "location": {"lat": lat, "lon": lon},
        "model": MODEL,
        "hourly": hourly,   # 3h, 6h, 12h
        "daily": daily,     # next 7 days
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
