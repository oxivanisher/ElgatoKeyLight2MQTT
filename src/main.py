#!/usr/bin/env python3


import paho.mqtt.client as mqtt
import os
import logging
import leglight
import time

logging.basicConfig(level=logging.DEBUG)

class KeyLight2MQTT:

    def __init__(self):
        self.mqtt_server = os.getenv('MQTT_SERVER', 'localhost')
        self.mqtt_port = os.getenv('MQTT_PORT', 1883)
        self.mqtt_user = os.getenv('MQTT_USER', None)
        self.mqtt_password = os.getenv('MQTT_PASSWORD', None)
        self.mqtt_base_topic = os.getenv('MQTT_BASE_TOPIC', 'ElgatoKeyLights')

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.mqtt_on_connect
        self.mqtt_client.on_message = self.mqtt_on_message

        self.all_lights = []
        self.last_light_discover = 0

    def mqtt_on_connect(self, client, userdata, flags, rc):
        logging.info("MQTT: Connected with result code "+str(rc))

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe("%s/set" % self.mqtt_base_topic)

    # The callback for when a PUBLISH message is received from the server.
    def mqtt_on_message(self, client, userdata, msg):
        logging.info("MQTT: Msg recieved on <%s>: <%s>" % (msg.topic, str(msg.payload)))
        print(msg.payload)
        for light in self.all_lights:
            logging.info("Setting light to")
            # light.on()
            # light.brightness(5)
            # light.color(3400)

    def discover_lights(self):
        if time.time() - self.last_light_discover > 60:
            logging.debug("Discover lights...")
            self.all_lights = leglight.discover(2)
            logging.debug("found %s lights" % len(self.all_lights))
            self.last_light_discover = time.time()

    def run(self):
        if self.mqtt_user:
            self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_password)
        self.mqtt_client.connect(self.mqtt_server, int(self.mqtt_port), 60)

        self.mqtt_client.subscribe(self.mqtt_base_topic, qos=2)

        try:
            while True:
                self.discover_lights()
                self.mqtt_client.loop()
        finally:
            self.mqtt_client.loop_stop(force=False)


if __name__ == "__main__":
    kl = KeyLight2MQTT()
    kl.run()


# for _, ip := range elgatoKeyLights {
#     reqBody = strings.NewReader(string(ba))
#     s = fmt.Sprintf("http://%s:9123/elgato/lights", ip)
#     req, err = http.NewRequest("PUT", s, reqBody)
#     if err != nil {
#         fmt.Printf("ERROR preparing Elgato KeyLight request: %s\n", err.Error())
#     }
#     //resp, err = httpClient.Do(req)

#
# type elgatoKeylightControlLight struct {
#     On          int `json:"on"`
#     Brightness  int `json:"brightness"`
#     Temperature int `json:"temperature"`
# }
#
# type elgatoKeylightControl struct {
#     NumberOfLights int                          `json:"numberOfLights"`
#     Lights         []elgatoKeylightControlLight `json:"lights"`
# }
#
# type keyLightConfig struct {
#     On          int
#     Brightness  int
#     Temperature int
# }

