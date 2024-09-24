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

        # On init, go talk to the light and get the full product info
        with requests.get(f"http://{address}:{port}/elgato/accessory-info") as res:
            details = res.json()
            self.productName = details["productName"]
            self.hardwareBoardType = details["hardwareBoardType"]
            self.firmwareBuildNumber = details["firmwareBuildNumber"]
            self.firmwareVersion = details["firmwareVersion"]
            self.serialNumber = details["serialNumber"]
            self.display = details["displayName"]

        # On init, we'll also go get the current status of the light
        self.isOn = 0
        self.isBrightness = 0
        self.isTemperature = 0
        self.info()

    def __repr__(self):
        return f"Elgato Light {self.serialNumber} @ {self.address}:{self.port}"

    def on(self) -> None:
        """ Turns the light on """
        logging.debug(f"turning on {self.display}")
        data = '{"numberOfLights":1,"lights":[{"on":1}]}'
        with requests.put(f"http://{self.address}:{self.port}/elgato/lights", data=data) as res:
            self.isOn = res.json()["lights"][0]["on"]

    def off(self) -> None:
        """ Turns the light off """
        logging.debug(f"turning off {self.display}")
        data = '{"numberOfLights":1,"lights":[{"on":0}]}'
        with requests.put(f"http://{self.address}:{self.port}/elgato/lights", data=data) as res:
            self.isOn = res.json()["lights"][0]["on"]

    def brightness(self, level: int) -> None:
        """ Sets the light to a specific brightness (0-100) level """
        logging.debug(f"setting brightness {level} on {self.display}")
        if 0 <= level <= 100:
            data = f'{{"numberOfLights":1,"lights":[{{"brightness":{level}}}]}}'
            with requests.put(f"http://{self.address}:{self.port}/elgato/lights", data=data) as res:
                self.isBrightness = res.json()["lights"][0]["brightness"]
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
        logging.debug(f"setting color {temp}k on {self.display}")
        if 2900 <= temp <= 7000:
            data = f'{{"numberOfLights":1,"lights":[{{"temperature":{self.colorFit(temp)}}}]}}'
            with requests.put(f"http://{self.address}:{self.port}/elgato/lights", data=data) as res:
                self.isTemperature = self.postFit(res.json()["lights"][0]["temperature"])
        else:
            logging.warning("INVALID COLOR TEMP - Must be 2900-7000")

    def incColor(self, amount: int) -> None:
        """ Increases the lights color temperature by a set amount """
        self.info()
        self.color(self.isTemperature + amount)

    def decColor(self, amount: int) -> None:
        """ Decreases the lights color temperature by a set amount """
        self.info()
        self.color(self.isTemperature - amount)

    def info(self) -> dict:
        """ Gets the current light status. """
        logging.debug(f"getting info for {self.display}")
        with requests.get(f"http://{self.address}:{self.port}/elgato/lights") as res:
            status = res.json()["lights"][0]
            self.isOn = status["on"]
            self.isBrightness = status["brightness"]
            self.isTemperature = self.postFit(status["temperature"])
            return {
                "on": self.isOn,
                "brightness": self.isBrightness,
                "temperature": self.isTemperature,
            }

    def colorFit(self, val: int) -> int:
        """Take a color temp (in K) and convert it to the format the Elgato Light wants"""
        return int(round(987007 * val ** -0.999, 0))

    def postFit(self, val: int) -> int:
        """Take the int that the Elgato Light returns and convert it roughly back to color temp (in K)"""
        return int(round(1000000 * val ** -1, -2))
