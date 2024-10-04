import requests
import logging


class LegLight:
    def __init__(self, address: str, port: int, name: str = "", server: str = ""):
        # Init info from discovery, or user controlled
        self.address = address
        self.port = port

        # We don't currently use name or server, so they can be null
        self.name = name
        self.server = server

        # Create a session with connection pooling and timeouts
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
        self.session.mount('http://', adapter)
        self.timeout = 5  # Timeout for all requests

        # On init, go talk to the light and get the full product info
        try:
            res = self.session.get(f"http://{address}:{port}/elgato/accessory-info", timeout=self.timeout)
            res.raise_for_status()
            details = res.json()
            self.productName = details["productName"]
            self.hardwareBoardType = details["hardwareBoardType"]
            self.firmwareBuildNumber = details["firmwareBuildNumber"]
            self.firmwareVersion = details["firmwareVersion"]
            self.serialNumber = details["serialNumber"]
            self.display = details["displayName"]
        except requests.exceptions.RequestException as e:
            logging.error(f"Error retrieving accessory info from {self.address}: {e}")
            raise

        # On init, we'll also go get the current status of the light
        self.isOn = 0
        self.isBrightness = 0
        self.isTemperature = 0
        self.info()

    def __repr__(self):
        return f"Elgato Light {self.serialNumber} @ {self.address}:{self.port}"

    def on(self) -> None:
        """ Turns the light on """
        logging.debug(f"Turning on {self.display}")
        data = '{"numberOfLights":1,"lights":[{"on":1}]}'
        try:
            res = self.session.put(f"http://{self.address}:{self.port}/elgato/lights", data=data, timeout=self.timeout)
            res.raise_for_status()
            self.isOn = res.json()["lights"][0]["on"]
        except requests.exceptions.RequestException as e:
            logging.error(f"Error turning on light at {self.address}: {e}")

    def off(self) -> None:
        """ Turns the light off """
        logging.debug(f"Turning off {self.display}")
        data = '{"numberOfLights":1,"lights":[{"on":0}]}'
        try:
            res = self.session.put(f"http://{self.address}:{self.port}/elgato/lights", data=data, timeout=self.timeout)
            res.raise_for_status()
            self.isOn = res.json()["lights"][0]["on"]
        except requests.exceptions.RequestException as e:
            logging.error(f"Error turning off light at {self.address}: {e}")

    def brightness(self, level: int) -> None:
        """ Sets the light to a specific brightness (0-100) level """
        logging.debug(f"Setting brightness {level} on {self.display}")
        if 0 <= level <= 100:
            data = f'{{"numberOfLights":1,"lights":[{{"brightness":{level}}}]}}'
            try:
                res = self.session.put(f"http://{self.address}:{self.port}/elgato/lights", data=data, timeout=self.timeout)
                res.raise_for_status()
                self.isBrightness = res.json()["lights"][0]["brightness"]
            except requests.exceptions.RequestException as e:
                logging.error(f"Error setting brightness on light at {self.address}: {e}")
        else:
            logging.warning("INVALID BRIGHTNESS LEVEL - Must be 0-100")

    def incBrightness(self, amount: int) -> None:
        """ Increases the light brightness by a set amount """
        self.info()
        self.brightness(self.isBrightness + amount)

    def decBrightness(self, amount: int) -> None:
        """ Decreases the light brightness by a set amount """
        self.info()
        self.brightness(self.isBrightness - amount)

    def color(self, temp: int) -> None:
        """ Sets the light to a specific color temperature (2900-7000k) """
        logging.debug(f"Setting color {temp}k on {self.display}")
        if 2900 <= temp <= 7000:
            data = f'{{"numberOfLights":1,"lights":[{{"temperature":{self.colorFit(temp)}}}]}}'
            try:
                res = self.session.put(f"http://{self.address}:{self.port}/elgato/lights", data=data, timeout=self.timeout)
                res.raise_for_status()
                self.isTemperature = self.postFit(res.json()["lights"][0]["temperature"])
            except requests.exceptions.RequestException as e:
                logging.error(f"Error setting color temperature on light at {self.address}: {e}")
        else:
            logging.warning("INVALID COLOR TEMP - Must be 2900-7000")

    def incColor(self, amount: int) -> None:
        """ Increases the light's color temperature by a set amount """
        self.info()
        self.color(self.isTemperature + amount)

    def decColor(self, amount: int) -> None:
        """ Decreases the light's color temperature by a set amount """
        self.info()
        self.color(self.isTemperature - amount)

    def info(self) -> dict:
        """ Gets the current light status. """
        logging.debug(f"getting info for {self.display}")
        try:
            with requests.get(f"http://{self.address}:{self.port}/elgato/lights", timeout=5) as res:
                status = res.json().get("lights", [{}])[0]
                self.isOn = status.get("on", 0)
                self.isBrightness = status.get("brightness", 0)
                self.isTemperature = self.postFit(status.get("temperature", 2900))
                return {
                    "on": self.isOn,
                    "brightness": self.isBrightness,
                    "temperature": self.isTemperature,
                }
        except requests.exceptions.RequestException as e:
            logging.error(f"Error retrieving light info from {self.address}: {e}")
            return {
                "on": -1,
                "brightness": -1,
                "temperature": -1,
            }

    def ping(self) -> bool:
        """ Check if the light is reachable by sending a simple GET request. """
        try:
            # Send a HEAD request to check if the device is reachable without pulling all the data
            response = requests.head(f"http://{self.address}:{self.port}/elgato/accessory-info", timeout=5)
            # Check for a successful response code (200 OK)
            if response.status_code == 200:
                return True
            else:
                logging.warning(f"Received unexpected status code {response.status_code} from {self.address}")
                return False
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to ping light at {self.address}: {e}")
            return False
    
    def colorFit(self, val: int) -> int:
        """Take a color temp (in K) and convert it to the format the Elgato Light wants"""
        return int(round(987007 * val ** -0.999, 0))

    def postFit(self, val: int) -> int:
        """Take the int that the Elgato Light returns and convert it roughly back to color temp (in K)"""
        return int(round(1000000 * val ** -1, -2))

    def close(self):
        """Close the session to release resources"""
        self.session.close()
