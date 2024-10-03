#!/usr/bin/env python3

import paho.mqtt.client as mqtt
import os
import logging
import leglight
import time
import sys

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
        self.mqtt_port = int(os.getenv('MQTT_PORT', 1883))
        self.mqtt_user = os.getenv('MQTT_USER', None)
        self.mqtt_password = os.getenv('MQTT_PASSWORD', None)
        self.mqtt_base_topic = os.getenv('MQTT_BASE_TOPIC', 'ElgatoKeyLights')

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.mqtt_on_connect
        self.mqtt_client.on_message = self.mqtt_on_message
        self.mqtt_client.on_disconnect = self.mqtt_on_disconnect

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

    def mqtt_on_connect(self, client, userdata, flags, rc, properties=None):
        logging.info(f"MQTT: Connected with result code {rc}")

        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        topic = f"{self.mqtt_base_topic}/set/#"
        logging.info(f"MQTT: Subscribing to {topic}")
        client.subscribe(topic)

    def mqtt_on_message(self, client, userdata, msg):
        logging.debug(f"MQTT: Msg received on <{msg.topic}>: <{msg.payload}>")
        what = msg.topic.split("/")[-1]
        serial = msg.topic.split("/")[-2]
        value = msg.payload.decode("utf-8")
        logging.info(f"Setting {what} on elgato light {serial} to {value}")
        for light in self.all_lights:
            if serial.lower() != light.serialNumber.lower():
                continue  # Skip if wrong light

            # Fetch current light state
            state = light.info()

            if what == "power":
                self.set_light_power(light, state, value)
            elif what == "brightness":
                value = int(value)
                if state['brightness'] != value:
                    light.brightness(value)
                    logging.debug(f"Brightness to {value}")
            elif what == "color":
                value = int(value)
                if state['temperature'] != value:
                    light.color(value)
                    logging.debug(f"Temperature to {value}")

    def mqtt_on_disconnect(self, client, userdata, rc):
        logging.warning(f"MQTT: Disconnected with result code {rc}")

    def discover_lights(self):
        # Cache results, discover only when needed (e.g., every 10 minutes)
        lights_before = len(self.all_lights)
        cache_duration = 300  # Cache results for 5 minutes

        # Only discover if cache is empty or older than cache_duration
        if not self.all_lights or time.time() - self.last_light_discover > cache_duration:
            logging.debug("Starting to discover lights...")
            try:
                discovered_lights = leglight.discover(2)  # Time to wait for discovery
                self.last_light_discover = time.time()

                # Merge new lights with existing lights, removing duplicates based on serial number
                all_serials = {light.serialNumber.lower() for light in self.all_lights}
                for new_light in discovered_lights:
                    if new_light.serialNumber.lower() not in all_serials:
                        self.all_lights.append(new_light)
                        all_serials.add(new_light.serialNumber.lower())

                    # Check if existing lights have new infos
                    for existing_light in self.all_lights:
                        if existing_light.serialNumber.lower() == new_light.serialNumber.lower():
                            run_serial = new_light.serialNumber.lower()
                            logging.debug(f"Checking existing light infos for serial {run_serial}")
                            replace_light = False
                            if existing_light.address != new_light.address:
                                logging.debug(f"Address for {run_serial} changed from {existing_light.address} to {new_light.address}")
                                replace_light = True
                            if existing_light.port != new_light.port:
                                logging.debug(f"Port for {run_serial} changed from {existing_light.port} to {new_light.port}")
                                replace_light = True

                            if replace_light:
                                logging.info(f"Infos for {run_serial} changed, updating light")
                                self.all_lights.pop(existing_light)
                                self.all_lights.append(new_light)

                if lights_before != len(self.all_lights):
                    logging.info(f"Found {len(self.all_lights)} Elgato lights:")
                    for light in self.all_lights:
                        logging.info(f"  {light}")

            except OSError as err:
                self.last_light_discover = time.time() - 30  # Retry sooner if error occurs
                logging.error(f"OS error: {err}")
                logging.error("Critical error in light discovery, exiting...")
                sys.exit(1)  # Exit to trigger restart in systemd
        else:
            logging.debug("Using cached lights, skipping discovery.")

    def run(self):
        if self.mqtt_user:
            self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_password)

        while True:
            logging.info("Waiting for MQTT server...")

            connected = False
            while not connected:
                try:
                    self.mqtt_client.connect(self.mqtt_server, self.mqtt_port, 60)
                    connected = True
                    logging.info("Connection successful")
                except ConnectionRefusedError:
                    logging.error("Failed to connect to MQTT server, retrying in 3 seconds...")
                    time.sleep(3)
                except OSError as e:
                    logging.error(f"MQTT connection OSError: {e.message}, retrying in 3 seconds...")
                    time.sleep(3)
                except Exception as e:
                    logging.error(f"Unknown exception caught:\n{traceback.format_exc()}\n retrying in 3 seconds...")
                    time.sleep(3)

            try:
                while True:
                    self.discover_lights()
                    return_value = self.mqtt_client.loop_forever()
                    if return_value:
                        logging.error(f"MQTT client loop returned <{return_value}>. Exiting...")
                        sys.exit(1)  # Exit on critical MQTT loop errors
            except Exception as e:
                logging.error(f"Unhandled exception occurred: {e}")
                sys.exit(1)  # Exit on unexpected exceptions
            finally:
                self.mqtt_client.disconnect()
                connected = False


if __name__ == "__main__":
    kl = KeyLight2MQTT()
    kl.run()
