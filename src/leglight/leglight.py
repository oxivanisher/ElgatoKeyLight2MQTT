import requests
import logging
import socket

class LegLight:
    def __init__(self, address: str, port: int, name: str = "", server: str = ""):
        self.address = address
        self.port = port
        self.name = name
        self.server = server
        self.base_url = f"http://{address}:{port}"
        
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=3)
        self.session.mount('http://', adapter)
        self.timeout = 5

        self._get_accessory_info()

    def _get_accessory_info(self):
        try:
            res = self.session.get(f"{self.base_url}/elgato/accessory-info", timeout=self.timeout)
            res.raise_for_status()
            details = res.json()
            for key in ['productName', 'hardwareBoardType', 'firmwareBuildNumber', 'firmwareVersion', 'serialNumber', 'displayName']:
                setattr(self, key, details.get(key))
        except requests.exceptions.RequestException as e:
            logging.error(f"Error retrieving accessory info from {self.address}: {e}")
            raise

    def __repr__(self):
        return f"Elgato Light {getattr(self, 'serialNumber', 'Unknown')} @ {self.address}:{self.port}"

    def _send_request(self, endpoint: str, data: dict = None, method: str = 'GET') -> dict:
        url = f"{self.base_url}/{endpoint}"
        try:
            if method == 'GET':
                res = self.session.get(url, timeout=self.timeout)
            elif method == 'PUT':
                res = self.session.put(url, json=data, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            res.raise_for_status()
            return res.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error sending {method} request to {url}: {e}")
            raise

    def on(self) -> None:
        logging.debug(f"Turning on {self.displayName}")
        data = {"lights": [{"on": 1}]}
        response = self._send_request("elgato/lights", data, method='PUT')
        self.isOn = response["lights"][0]["on"]

    def off(self) -> None:
        logging.debug(f"Turning off {self.displayName}")
        data = {"lights": [{"on": 0}]}
        response = self._send_request("elgato/lights", data, method='PUT')
        self.isOn = response["lights"][0]["on"]

    def brightness(self, level: int) -> None:
        if 0 <= level <= 100:
            logging.debug(f"Setting brightness {level} on {self.displayName}")
            data = {"lights": [{"brightness": level}]}
            response = self._send_request("elgato/lights", data, method='PUT')
            self.isBrightness = response["lights"][0]["brightness"]
        else:
            logging.warning("INVALID BRIGHTNESS LEVEL - Must be 0-100")

    def color(self, temp: int) -> None:
        if 2900 <= temp <= 7000:
            logging.debug(f"Setting color {temp}k on {self.displayName}")
            data = {"lights": [{"temperature": self.colorFit(temp)}]}
            response = self._send_request("elgato/lights", data, method='PUT')
            self.isTemperature = self.postFit(response["lights"][0]["temperature"])
        else:
            logging.warning("INVALID COLOR TEMP - Must be 2900-7000")

    def info(self) -> dict:
        logging.debug(f"Getting info for {self.displayName}")
        try:
            status = self._send_request("elgato/lights")["lights"][0]
            self.isOn = status["on"]
            self.isBrightness = status["brightness"]
            self.isTemperature = self.postFit(status["temperature"])
            return {
                "on": self.isOn,
                "brightness": self.isBrightness,
                "temperature": self.isTemperature,
            }
        except requests.exceptions.RequestException as e:
            logging.error(f"Error retrieving light info from {self.address}: {e}")
            return {"on": 0, "brightness": 0, "temperature": 2900}

    def ping(self) -> bool:
        try:
            with socket.create_connection((self.address, self.port), timeout=2):
                return True
        except (socket.error, requests.exceptions.RequestException) as e:
            logging.debug(f"Ping failed for light at {self.address}: {e}")
            return False

    def colorFit(self, val: int) -> int:
        return int(round(987007 * val ** -0.999, 0))

    def postFit(self, val: int) -> int:
        return int(round(1000000 * val ** -1, -2))

    def close(self):
        self.session.close()

# The discover function remains the same as in your current implementation
