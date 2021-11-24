#!/usr/bin/env python3


import paho.mqtt.client as mqtt
import os
import logging
import leglight
import time


log_level = logging.INFO
if os.getenv('DEBUG', False):
  log_level = logging.DEBUG

logging.basicConfig(
  format='%(asctime)s %(levelname)-7s %(message)s',
  datefmt='%Y-%d-%m %H:%M:%S',
  level=log_level
)


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

    def set_light_power(self, light, state, power="on"):
        if power == "on":
            if not state['on']:
                light.on()
                logging.debug("Light on")
        else:
            if state['on']:
                light.off()
                logging.debug("Light off")

    def mqtt_on_connect(self, client, userdata, flags, rc):
        logging.info("MQTT: Connected with result code "+str(rc))

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        topic = "%s/set/#" % self.mqtt_base_topic
        logging.info("MQTT: Subscribing to %s" % topic)
        client.subscribe(topic)

    def mqtt_on_message(self, client, userdata, msg):
        logging.debug("MQTT: Msg recieved on <%s>: <%s>" % (msg.topic, str(msg.payload)))
        what = msg.topic.split("/")[-1]
        serial = msg.topic.split("/")[-2]
        value = msg.payload.decode("utf-8")
        logging.info("Setting %s on elgato light %s to %s" % (what, serial, value))
        for light in self.all_lights:
            if serial.lower() != light.serialNumber.lower():
                # do nothing if we are the wrong light
                continue

            # fetch current light state
            state = light.info()

            if what == "power":
                self.set_light_power(light, state, value)
            elif what == "brightness":
                value = int(value)
                if state['brightness'] != value:
                    light.brightness(value)
                    logging.debug("Brightness to %s" % value)
            elif what == "color":
                value = int(value)
                if state['temperature'] != value:
                    light.color(value)
                    logging.debug("Temperature to %s" % value)

    def discover_lights(self):
        lights_before = len(self.all_lights)
        if time.time() - self.last_light_discover > 60:
            logging.debug("Starting to discover lights...")
            try:
                self.all_lights = leglight.discover(2)
                self.last_light_discover = time.time()

                if lights_before != len(self.all_lights):
                    logging.info("Found %s Elgato lights:" % len(self.all_lights))
                    for light in self.all_lights:
                        logging.info("  %s" % light)

            except OSError as err:
                self.last_light_discover = time.time() - 30
                logging.error("OS error: {0}".format(err))

    def run(self):
        if self.mqtt_user:
            self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_password)

        connected = False
        while not connected:
            try:
                self.mqtt_client.connect(self.mqtt_server, int(self.mqtt_port), 60)
                connected = True
            except ConnectionRefusedError:
                logging.warning("Unable to connect to MQTT server. Will retry in 3 seconds.")
                time.sleep(3)

        # self.mqtt_client.subscribe(self.mqtt_base_topic, qos=2)

        try:
            while True:
                self.discover_lights()
                self.mqtt_client.loop()
        finally:
            self.mqtt_client.loop_stop(force=True)


if __name__ == "__main__":
    kl = KeyLight2MQTT()
    kl.run()
