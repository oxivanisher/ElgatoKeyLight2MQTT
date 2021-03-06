# ElgatoKeyLigt2MQTT
A connector for the Elgato Lights to MQTT, so they can be controlled easily.

It detects the elgato lights automatically and applies the requested values to the light with the corresponding serial.

## MQTT

Per default, it subscribes to the following topic: `ElgatoKeyLights/set/<SERIAL>/+`

The following parameters are known:

| name       | values       |
|------------|--------------|
| power      | on, off      |
| color      | 3000 - 7000  |
| brightness | 0 - 100      |

## Parameter
The tool knows the following parameters, set as environment variable:

| env variable    | default value   |
|-----------------|-----------------|
| MQTT_SERVER     | localhost       |
| MQTT_PORT       | 1883            |
| MQTT_USER       | None            |
| MQTT_PASSWORD   |                 |
| MQTT_BASE_TOPIC | ElgatoKeyLights |
| DEBUG           |                 |

Set `DEBUG` to anything but empty to enable debug logging.

## Docker
Although this repository supplies a `Dockerfile` as well as a `docker-compose.yml`, it will only work when you ensure
that the mdns packages are forwarded. For this reason, the host network is used in the `docker-compose.yml` which works
at least in my environment. Another possible solution from
[stack overflow](https://stackoverflow.com/questions/30646943/how-to-avahi-browse-from-a-docker-container) is to use
`mdns-repeater`:

`mdns-repeater eth1 docker0`
