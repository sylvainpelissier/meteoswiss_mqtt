# Meteoswiss MQTT publication

Publish MeteoSwiss weather values over MQTT, e.g. to [Gladys Assistant](https://gladysassistant.com/) or Home Assistant.

`meteoswiss_mqtt.py` downloads the latest measurements of a MeteoSwiss SwissMetNet
station (default: `cdf`, La Chaux-de-Fonds) from the
[open data CSV](https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/), takes the most recent
row and publishes, as retained messages.

The `ETag` of the last download is stored in `$CACHE_DIRECTORY/state`; when the file has not
changed on the server, nothing is published.

## Configuration

The script is configured with environment variables:

| Variable | Default | Description |
|---|---|---|
| `METEOSWISS_STATION` | `cdf` | SwissMetNet station abbreviation |
| `METEOSWISS_MEASUREMENTS` | `temperature=tre200s0,humidity=ure200s0` | `name=column` pairs to publish, comma separated |
| `MQTT_HOST` | `localhost` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_USER`, `MQTT_PASSWORD` | unset | Broker credentials (no authentication if unset) |
| `MQTT_TOPIC` | `meteoswiss/{station}/{measurement}` | Topic template |

Column names are listed in the MeteoSwiss
[parameter description](https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/ogd-smn_meta_parameters.csv).

### Gladys Assistant

To publish to [Gladys Assistant](https://gladysassistant.com/), use:

```bash
MQTT_TOPIC='gladys/master/device/mqtt:external:meteosuisse-{station}/feature/mqtt:external:meteosuisse-{station}:{measurement}/state'
```

and create in Gladys an MQTT device with the external ID `mqtt:external:meteosuisse-cdf` and
one feature per measurement with the external ID `mqtt:external:meteosuisse-cdf:temperature`,
`mqtt:external:meteosuisse-cdf:humidity`, ...

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
    mosquitto_sub -h localhost -t '#' -v
```

Run the script (`CACHE_DIRECTORY` is normally provided by systemd):

```bash
CACHE_DIRECTORY=/tmp/meteosuisse uv run meteoswiss_mqtt.py
```

Remove `/tmp/meteoswiss/state` to force a new download and publication.

## Running every 20 minutes with systemd

Install the script:

```bash
sudo install -Dm755 meteoswiss_mqtt.py /opt/meteoswiss_mqtt/meteoswiss_mqtt.py
```

Create `/etc/meteoswiss_mqtt.env` with your configuration and restrict its permissions
(`sudo chmod 600 /etc/meteoswiss_mqtt.env`), since it contains the broker password:

```bash
METEOSWISS_STATION=cdf
MQTT_HOST=localhost
MQTT_USER=gladys
MQTT_PASSWORD=...
```

Create `/etc/systemd/system/meteoswiss.service`:

```ini
[Unit]
Description=Publish MeteoSwiss values over MQTT
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
DynamicUser=yes
CacheDirectory=meteoswiss
EnvironmentFile=/etc/meteoswiss_mqtt.env
ExecStart=/usr/bin/python /opt/meteoswiss_mqtt/meteoswiss_mqtt.py
```

Create `/etc/systemd/system/meteoswiss.timer`:

```ini
[Unit]
Description=Run meteoswiss.service every 20 minutes

[Timer]
OnCalendar=*:0/20
Persistent=true

[Install]
WantedBy=timers.target
```

Enable the timer and check that it works:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now meteoswiss.timer
sudo systemctl start meteoswiss.service     # run once now
systemctl list-timers meteoswiss.timer
journalctl -u meteoswiss.service
```

## License

See [LICENSE](LICENSE).
