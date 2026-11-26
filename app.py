from flask import Flask, jsonify, request
from dotenv import load_dotenv
import time, requests
import os
import socket
load_dotenv ()
API_KEY = os.getenv("RESTCOUNTRIES_API_KEY")
COUNTRIES_URL= "https://api.restcountries.com/countries/v5"

app = Flask(__name__, static_folder="static", static_url_path="")

cache = {}
countries_cache ={"time":0, "data":None}


@app.route("/")
def index():
        return app.send_static_file("index.html")


def cached_get(url, params=None, ttl=3600):
        key =url+str(params)
        hit = cache.get(key)
        if hit and time.time() - hit[0] < ttl:
                return hit[1]
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        cache[key] = (time.time(), data)
        return data
def fetch_all_countries():
        headers ={"Authorization": f"Bearer {API_KEY}"}
        fields= "names.common,capitals,region,population,area.miles,flag.url_png,coordinates"
        results = []
        offset = 0
        while True:
                r = requests.get(
                        COUNTRIES_URL,
                        headers=headers,
                        params={"limit": 100, "offset": offset, "response_fields": fields},
                        timeout=10,
                )
                r.raise_for_status()
                data = r.json()["data"]
                results.extend(data["objects"])
                if not data["meta"]["more"]:
                        break
                offset += 100
                return results
def simplify(c):
        caps = c.get("capitals") or []
        cap = caps[0] if caps else {}
        coords = cap.get("coordinates") or c.get("coordinates") or {}
        return {
                "name": c["names"]["common"],
                "capital": cap.get("name"),
                "region": c.get("region"),
                "population": c.get("population") or 0,
                "area": (c.get("area") or {}) .get("miles") or 0,
                "flag": (c.get("flag") or {}).get("url_png"),
                "lat": coords.get("lat"),
                "lng": coords.get("lng"),
        }

@app.route("/api/countries")
def countries():
        if not API_KEY:
                return jsonify(error="Server is lacking its API key."), 500
        if countries_cache["data"] and time.time() - countries_cache["time"] < 86400:
                return jsonify(countries_cache["data"])
        try:
                data = [simplify(c) for c in fetch_all_countries()]
        except (requests.RequestException, KeyError):
                return jsonify(error="Country serivice is offline try again after one hour!"), 502
        countries_cache["data"] = data
        countries_cache["time"] = time.time()
        return jsonify(data)

@app.route("/api/weather")
def weather():
        try:
                lat = float(request.args["lat"])
                lon = float(request.args["lon"])
        except (KeyError, ValueError):
                return jsonify(error="Wrong coordinates"), 400
        try:
                data = cached_get(
                        "https://api.open-meteo.com/v1/forecast",
                        {"latitude": lat, "longitude": lon, "current_weather": "true"},
                        ttl= 600,
                )
                return jsonify(data)
        except requests.RequestException:
                return jsonify(error="Weather service is offline."), 502

@app.route("/api/server")
def server():
        return jsonify(server= socket.gethostname())
if __name__=="__main__":
        app.run(port=8000, debug=True)