#!/usr/bin/env python
import csv
import io
import os
import sys
import urllib.request
from pathlib import Path

import paho.mqtt.client as mqtt

STATION = "cdf"
DEVICE_ID = f"mqtt:external:meteosuisse-{STATION}"
FEATURE_TEMP_ID = f"{DEVICE_ID}:temperature"
FEATURE_HUM_ID = f"{DEVICE_ID}:humidity"

CSV_URL = (
    f"https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/"
    f"{STATION}/ogd-smn_{STATION}_t_now.csv"
)
COL_TEMP = "tre200s0"        # air temperature at 2 in meters
COL_HUM = "ure200s0"         # humidity at 2 m in %

# Create by systemd via CacheDirectory=meteosuisse
CACHE_DIR = Path(os.environ["CACHE_DIRECTORY"])
STATE_FILE = CACHE_DIR / "state"

MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_USER = "gladys"
MQTT_PASSWORD = "mypassword"
TOPIC_TEMP = f"gladys/master/device/{DEVICE_ID}/feature/{FEATURE_TEMP_ID}/state"
TOPIC_HUM = f"gladys/master/device/{DEVICE_ID}/feature/{FEATURE_HUM_ID}/state"


def fetch_csv(etag):
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "gladys-smn/1.0"})
    if etag:
        req.add_header("If-None-Match", etag)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            etag = resp.headers.get("ETag", etag)
            return resp.read().decode("cp1252"), etag
    except urllib.error.HTTPError as exc:
            if exc.code == 304:
                return None, etag
            raise
    
def last_values(text):
    reader = csv.DictReader(io.StringIO(text), delimiter=";")

    temp = hum = ts = None
    for row in reader:
        temp = row.get(COL_TEMP, "").strip()
        hum = row.get(COL_HUM, "").strip()
        ts = row.get("reference_timestamp")

    return ts, temp, hum

def read_state():
    try:
        with open(STATE_FILE, "r") as f:
            etag = f.read()
        return etag
    except (FileNotFoundError):
        return None

def write_state(etag):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(etag)

def publish_all(messages):
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)  # paho >= 2.0
    except AttributeError:
        client = mqtt.Client()                                  # paho 1.x
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()
    try:
        for topic, payload in messages:
            client.publish(topic, payload, retain=True).wait_for_publish(timeout=10)
    finally:
        client.loop_stop()
        client.disconnect()

def main():
    etag = read_state()
    rsp, etag = fetch_csv(etag)

    if rsp is None:
        print("File did not change")
        return 0

    write_state(etag)
    ts, temp, hum = last_values(rsp)
    if ts is None:
        print("No value in the file", file=sys.stderr)
        return 1

    messages = []
    if temp is not None:
        messages.append((TOPIC_TEMP, temp))
    if hum is not None:
        messages.append((TOPIC_HUM, hum)) 

    publish_all(messages)
    print(f"[{ts} UTC] {temp} degC / {hum} % publie")
    return 0


if __name__ == "__main__":
    sys.exit(main())
