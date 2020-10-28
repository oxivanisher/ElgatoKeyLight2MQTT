# ElgatoKeyLigt2MQTT
A connector for the Elgato Lights to MQTT, so they can be controlled easily.

It detects the elgato lights automatically and applies the requested values to all of them.

## MQTT

Per default, it subscribes to the following topic: `ElgatoKeyLights/set/+`

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
