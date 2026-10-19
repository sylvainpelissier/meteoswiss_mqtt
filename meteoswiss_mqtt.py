#!/usr/bin/env python
import csv
import io
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import paho.mqtt.client as mqtt

STATION = os.environ.get("METEOSWISS_STATION", "cdf").lower()

# measurement name -> CSV column, e.g. "temperature=tre200s0,humidity=ure200s0"
#   tre200s0: air temperature at 2 m in degC
#   ure200s0: relative humidity at 2 m in %
MEASUREMENTS = dict(
    item.strip().split("=", 1)
    for item in os.environ.get(
        "METEOSWISS_MEASUREMENTS", "temperature=tre200s0,humidity=ure200s0"
    ).split(",")
    if item.strip()
)

CSV_URL = (
    f"https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/"
    f"{STATION}/ogd-smn_{STATION}_t_now.csv"
)

# Create by systemd via CacheDirectory=meteoswiss
CACHE_DIR = Path(os.environ["CACHE_DIRECTORY"])
STATE_FILE = CACHE_DIR / "state"

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
# Placeholders: {station}, {measurement}
MQTT_TOPIC = os.environ.get("MQTT_TOPIC", "meteoswiss/{station}/{measurement}")


def fetch_csv(etag):
    req = urllib.request.Request(CSV_URL, headers={"User-Agent": "meteoswiss-mqtt/1.0"})
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

    ts = None
    values = {}
    for row in reader:
        ts = row.get("reference_timestamp")
        values = {name: row.get(col, "").strip() for name, col in MEASUREMENTS.items()}

    return ts, values


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
    ts, values = last_values(rsp)
    if ts is None:
        print("No value in the file", file=sys.stderr)
        return 1

    messages = [
        (MQTT_TOPIC.format(station=STATION, measurement=name), value)
        for name, value in values.items()
        if value
    ]

    publish_all(messages)
    for topic, payload in messages:
        print(f"[{ts} UTC] {topic} = {payload}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
