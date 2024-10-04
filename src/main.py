import paho.mqtt.client as mqtt
import os
import logging
import time
import sys
import traceback
from leglight import LegLight, discover
import gc
from threading import Lock

log_level = logging.DEBUG if os.getenv('DEBUG', False) else logging.INFO

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

        self.all_lights = {}
        self.last_light_discover = 0
        self.discovery_interval = 60  # Discover lights every 1 minute
        self.discovery_lock = Lock()
        self.last_discovery_attempt = {}

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
        
        light = self.all_lights.get(serial.lower())
        if not light:
            current_time = time.time()
            if current_time - self.last_discovery_attempt.get(serial.lower(), 0) > 10:
                logging.warning(f"Light {serial} not found in known lights. Triggering discovery.")
                self.discover_lights()
                light = self.all_lights.get(serial.lower())
                self.last_discovery_attempt[serial.lower()] = current_time
            if not light:
                logging.error(f"Light {serial} still not found after discovery.")
                return

        try:
            if what == "power":
                self.set_light_power(light, value)
            elif what == "brightness":
                value = int(value)
                light.brightness(value)
                logging.info(f"Brightness for {light.serialNumber} set to {value}")
            elif what == "color":
                value = int(value)
                light.color(value)
                logging.info(f"Temperature for {light.serialNumber} set to {value}")
        except Exception as e:
            logging.error(f"Error processing light {light.serialNumber}: {e}")
            logging.debug(traceback.format_exc())

    def mqtt_on_disconnect(self, client, userdata, rc):
        logging.warning(f"MQTT: Disconnected with result code {rc}. Reconnecting...")
        while True:
            try:
                client.reconnect()
                break
            except Exception as e:
                logging.error(f"Reconnection failed: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    def set_light_power(self, light, power="on"):
        try:
            if power.lower() == "on":
                light.on()
                logging.info(f"Light {light.serialNumber} turned on")
            else:
                light.off()
                logging.info(f"Light {light.serialNumber} turned off")
        except Exception as e:
            logging.error(f"Error setting light {light.serialNumber} power: {e}")

    def discover_lights(self):
        with self.discovery_lock:
            logging.info("Starting to discover lights...")
            try:
                discovered_lights = discover(timeout=5, retry_count=3)
                for light in discovered_lights:
                    if light.serialNumber.lower() not in self.all_lights:
                        self.all_lights[light.serialNumber.lower()] = light
                        logging.info(f"New light discovered: {light}")
                    else:
                        existing_light = self.all_lights[light.serialNumber.lower()]
                        if existing_light.address != light.address or existing_light.port != light.port:
                            logging.info(f"Updating info for light {light.serialNumber}")
                            self.all_lights[light.serialNumber.lower()] = light
                
                self.last_light_discover = time.time()
                self._log_discovered_lights()
                
                # Remove lights that are no longer discovered
                current_serials = set(light.serialNumber.lower() for light in discovered_lights)
                for serial in list(self.all_lights.keys()):
                    if serial not in current_serials:
                        removed_light = self.all_lights.pop(serial)
                        logging.info(f"Removed light: {removed_light}")
                        removed_light.close()
                
            except Exception as err:
                logging.error(f"Error in light discovery: {err}")
                logging.debug(traceback.format_exc())
            finally:
                gc.collect()

    def _log_discovered_lights(self):
        logging.info(f"Current known lights ({len(self.all_lights)}):")
        for serial, light in self.all_lights.items():
            status = "responsive" if light.ping() else "unresponsive"
            logging.info(f"  {light} - {status}")

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
                if time.time() - self.last_light_discover > self.discovery_interval:
                    self.discover_lights()
                self.mqtt_client.loop(timeout=1.0)
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received. Exiting...")
        except Exception as e:
            logging.error(f"Unhandled exception occurred: {e}")
            logging.debug(traceback.format_exc())
        finally:
            self.mqtt_client.disconnect()
            for light in self.all_lights.values():
                light.close()

if __name__ == "__main__":
    kl = KeyLight2MQTT()
    kl.run()
