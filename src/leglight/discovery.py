from zeroconf import ServiceBrowser, Zeroconf
from time import sleep, time
import socket
from typing import cast
from . import LegLight
import logging
import threading

def discover(timeout: int = 5, retry_count: int = 3) -> list:
    lights = []
    discovery_complete = threading.Event()

    class TheListener:
        def remove_service(self, zeroconf, type, name):
            pass
        def update_service(self):
            pass
        def add_service(self, zeroconf, type, name):
            try:
                info = zeroconf.get_service_info(type, name)
                if info:
                    ip = socket.inet_ntoa(info.addresses[0])
                    port = cast(int, info.port)
                    lname = info.name
                    server = info.server
                    logging.debug(f"Found light @ {ip}:{port}")
                    light = LegLight(address=ip, port=port, name=lname, server=server)
                    if light not in lights:
                        lights.append(light)
                        logging.info(f"Added new light: {light}")
                    discovery_complete.set()
            except Exception as e:
                logging.error(f"Error adding service: {e}")

    for attempt in range(retry_count):
        zc = None
        browser = None
        try:
            zc = Zeroconf()
            listener = TheListener()
            browser = ServiceBrowser(zc, "_elg._tcp.local.", listener)

            start = time()
            while time() - start < timeout:
                if discovery_complete.wait(0.1):
                    break

            if lights:
                logging.info(f"Discovery completed. Found {len(lights)} lights.")
                break
            else:
                logging.warning(f"No lights found in attempt {attempt + 1}. Retrying...")
        except Exception as e:
            logging.error(f"Error during discovery: {e}")
        finally:
            if browser:
                browser.cancel()
            if zc:
                zc.close()

        sleep(1)  # Wait a bit before retrying

    if not lights:
        logging.error("No lights found after all retry attempts.")

    return lights
