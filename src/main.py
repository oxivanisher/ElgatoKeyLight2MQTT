import paho.mqtt.client as mqtt
import os
import logging
import leglight
import time
import sys
import traceback
import socket

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

    def is_light_responsive(self, light):
        try:
            # First, try a socket connection
            with socket.create_connection((light.address, light.port), timeout=2):
                pass
            # If socket connection succeeds, try the API endpoint
            return light.ping()
        except Exception as e:
            logging.debug(f"Light {light.serialNumber} is unresponsive: {e}")
            return False

    def set_light_power(self, light, power="on"):
        try:
            if power == "on":
                light.on()
                logging.info(f"Light {light.serialNumber} turned on")
            else:
                light.off()
                logging.info(f"Light {light.serialNumber} turned off")
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
        
        light = self.all_lights.get(serial.lower())
        if not light:
            logging.warning(f"Light {serial} not found in known lights. Triggering discovery.")
            self.discover_lights()
            light = self.all_lights.get(serial.lower())
            if not light:
                logging.error(f"Light {serial} still not found after discovery.")
                return

        if not self.is_light_responsive(light):
            logging.warning(f"Light {serial} not responding. Attempting to reconnect...")
            self.reconnect_light(light)
            if not self.is_light_responsive(light):
                logging.error(f"Failed to reconnect to light {serial}. Skipping action.")
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

    def discover_lights(self):
        logging.info("Starting to discover lights...")
        try:
            discovered_lights = leglight.discover(2)
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
        except Exception as err:
            logging.error(f"Error in light discovery: {err}")
            logging.debug(traceback.format_exc())

    def reconnect_light(self, light):
        try:
            new_light = leglight.LegLight(light.address, light.port)
            self.all_lights[light.serialNumber.lower()] = new_light
            logging.info(f"Successfully reconnected to light {light.serialNumber}")
        except Exception as e:
            logging.error(f"Failed to reconnect to light {light.serialNumber}: {e}")
            logging.debug(traceback.format_exc())

    def _log_discovered_lights(self):
        logging.info(f"Current known lights ({len(self.all_lights)}):")
        for serial, light in self.all_lights.items():
            status = "responsive" if self.is_light_responsive(light) else "unresponsive"
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
