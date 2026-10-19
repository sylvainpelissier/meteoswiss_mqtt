# Meteoswiss MQTT publication

Publish MeteoSwiss weather values to [Gladys Assistant](https://gladysassistant.com/) over MQTT.

`meteosuisse_to_gladys.py` downloads the latest measurements of a MeteoSwiss SwissMetNet
station (default: `cdf`, La Chaux-de-Fonds) from the
[open data CSV](https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/), takes the most recent
row and publishes, as retained messages:

| Value              | CSV column | MQTT topic                                                                                                     |
|--------------------|------------|----------------------------------------------------------------------------------------------------------------|
| Temperature (°C)   | `tre200s0` | `gladys/master/device/mqtt:external:meteosuisse-cdf/feature/mqtt:external:meteosuisse-cdf:temperature/state` |
| Humidity (%)       | `ure200s0` | `gladys/master/device/mqtt:external:meteosuisse-cdf/feature/mqtt:external:meteosuisse-cdf:humidity/state`    |

The `ETag` of the last download is stored in `$CACHE_DIRECTORY/state`; when the file has not
changed on the server, nothing is published.

In Gladys, create an MQTT device with external ID `mqtt:external:meteosuisse-cdf` and two
features with the external IDs above.

## Configuration

Edit the constants at the top of the script:

- `STATION`: SwissMetNet station abbreviation (lowercase)
- `MQTT_HOST`, `MQTT_PORT`, `MQTT_USER`, `MQTT_PASSWORD`: Gladys MQTT broker

## Requirements

- Production: Python 3 with `paho-mqtt` installed system-wide
  (`apt install python3-paho-mqtt` on Debian/Ubuntu).
- Local testing: [uv](https://docs.astral.sh/uv/). The dependency is declared inline in the
  script and installed automatically by `uv run`.

## Testing locally

Start a throwaway broker that accepts any credentials:

```bash
docker run --rm -p 1883:1883 --ulimit nofile=1024:1024 \
    eclipse-mosquitto:2 mosquitto -c /mosquitto-no-auth.conf
```

Watch the published messages in another terminal:

```bash
docker run --rm --network host eclipse-mosquitto:2 \
    mosquitto_sub -h localhost -t 'gladys/#' -v
```

Run the script (`CACHE_DIRECTORY` is normally provided by systemd):

```bash
CACHE_DIRECTORY=/tmp/meteosuisse uv run meteosuisse_to_gladys.py
```

Remove `/tmp/meteosuisse/state` to force a new download and publication.

## Running every 20 minutes with systemd

Install the script:

```bash
sudo install -Dm755 meteosuisse_to_gladys.py /opt/meteoswiss_mqtt/meteosuisse_to_gladys.py
```

Create `/etc/systemd/system/meteosuisse.service`:

```ini
[Unit]
Description=Publish MeteoSwiss values to Gladys MQTT
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
DynamicUser=yes
CacheDirectory=meteosuisse
ExecStart=/usr/bin/python /opt/meteoswiss_mqtt/meteosuisse_to_gladys.py
```

Create `/etc/systemd/system/meteosuisse.timer`:

```ini
[Unit]
Description=Run meteosuisse.service every 20 minutes

[Timer]
OnCalendar=*:0/20
Persistent=true

[Install]
WantedBy=timers.target
```

Enable the timer and check that it works:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now meteosuisse.timer
sudo systemctl start meteosuisse.service     # run once now
systemctl list-timers meteosuisse.timer
journalctl -u meteosuisse.service
```

## License

See [LICENSE](LICENSE).
