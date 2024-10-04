#!/usr/bin/env python3

import paho.mqtt.client as mqtt
import os
import logging
import leglight
import time
import sys
import traceback
from urllib3 import exceptions

log_level = logging.INFO if not os.getenv('DEBUG', False) else logging.DEBUG

logging.basicConfig(
    format='%(asctime)s %(levelname)-7s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
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
        self.last_light_cleanup = 0

        self.discovery_interval = 60  # Cache results for 1 Minute
        self.cleanup_interval = 300  # Try to connect to lights and remove unavailable ones every 5 minutes

    def set_light_power(self, light, state, power="on"):
        try:
            if power == "on" and not state['on']:
                light.on()
                logging.debug(f"Light {light.serialNumber} turned on")
            elif power == "off" and state['on']:
                light.off()
                logging.debug(f"Light {light.serialNumber} turned off")
        except Exception as e:
            logging.error(f"Error setting light {light.serialNumber} power: {e}")

    def mqtt_on_connect(self, client, userdata, flags, rc, properties=None):
        logging.info(f"MQTT: Connected with result code {rc}")
        topic = f"{self.mqtt_base_topic}/set/#"
        logging.info(f"MQTT: Subscribing to {topic}")
        client.subscribe(topic)

    def mqtt_on_message(self, client, userdata, msg):
        logging.debug(f"MQTT: Msg received on <{msg.topic}>: <{msg.payload}>")
        what, serial = msg.topic.split("/")[-1], msg.topic.split("/")[-2]
        value = msg.payload.decode("utf-8")
        logging.info(f"MQTT ordered to change setting on {serial}: {what} to {value}")
        
        for light in self.all_lights:
            if serial.lower() != light.serialNumber.lower():
                continue

            try:
                if not light.ping():
                    logging.warning(f"Light {light.serialNumber} not responding to ping, skipping...")
                    continue

                state = light.info()

                if what == "power":
                    self.set_light_power(light, state, value)
                elif what == "brightness":
                    value = int(value)
                    if state['brightness'] != value:
                        light.brightness(value)
                        logging.debug(f"Brightness for {light.serialNumber} set to {value}")
                elif what == "color":
                    value = int(value)
                    if state['temperature'] != value:
                        light.color(value)
                        logging.debug(f"Temperature for {light.serialNumber} set to {value}")
            except Exception as e:
                logging.error(f"Error processing light {light.serialNumber}: {e}")
                logging.error(traceback.format_exc())
                # Don't remove the light, just log the error and continue

    def mqtt_on_disconnect(self, client, userdata, rc):
        logging.warning(f"MQTT: Disconnected with result code {rc}. Reconnecting...")
        while True:
            try:
                client.reconnect()
                break
            except Exception as e:
                logging.error(f"Reconnection failed: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def discover_lights(self):
        if (not self.all_lights or 
            time.time() - self.last_light_discover > self.discovery_interval):
            logging.debug("Starting to discover lights...")
            try:
                discovered_lights = leglight.discover(2)
                self.last_light_discover = time.time()

                all_serials = {light.serialNumber.lower() for light in self.all_lights}
                for new_light in discovered_lights:
                    if new_light.serialNumber.lower() not in all_serials:
                        self.all_lights.append(new_light)
                        all_serials.add(new_light.serialNumber.lower())
                    else:
                        self._update_existing_light(new_light)

                self._log_discovered_lights()
            except Exception as err:
                self.last_light_discover = time.time() - 30
                logging.error(f"Error in light discovery: {err}")
        else:
            logging.debug("Using cached lights, skipping discovery.")

    def _update_existing_light(self, new_light):
        for existing_light in self.all_lights:
            if existing_light.serialNumber.lower() == new_light.serialNumber.lower():
                if (existing_light.address != new_light.address or 
                    existing_light.port != new_light.port):
                    logging.info(f"Updating info for light {new_light.serialNumber}")
                    self.all_lights.remove(existing_light)
                    self.all_lights.append(new_light)

    def _log_discovered_lights(self):
        logging.info(f"Found {len(self.all_lights)} Elgato lights:")
        for light in self.all_lights:
            logging.info(f"  {light}")

    def cleanup_lights(self):
        if time.time() - self.last_light_cleanup > self.cleanup_interval:
            logging.info("Cleaning up disconnected lights")
            lights_to_remove = []
            for light in self.all_lights:
                try:
                    if not light.ping():
                        lights_to_remove.append(light)
                except Exception as e:
                    logging.error(f"Error pinging light {light.serialNumber}: {e}")
                    lights_to_remove.append(light)
            
            for light in lights_to_remove:
                logging.info(f"Removing unresponsive light {light.serialNumber}")
                self.all_lights.remove(light)
            
            self.last_light_cleanup = time.time()

    def run(self):
        if self.mqtt_user:
            self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_password)

        while True:
            logging.info("Connecting to MQTT server...")
            try:
                self.mqtt_client.connect(self.mqtt_server, self.mqtt_port, 60)
                logging.info("Connection successful")
                break
            except Exception as e:
                logging.error(f"Failed to connect to MQTT server: {e}. Retrying in 5 seconds...")
                time.sleep(5)

        try:
            while True:
                self.discover_lights()
                self.cleanup_lights()
                self.mqtt_client.loop(timeout=1.0)
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received. Exiting...")
        except Exception as e:
            logging.error(f"Unhandled exception occurred: {e}\n{traceback.format_exc()}")
        finally:
            self.mqtt_client.disconnect()
            for light in self.all_lights:
                light.close()

if __name__ == "__main__":
    kl = KeyLight2MQTT()
    kl.run()
