import logging
import colorlog
from typing import Literal




class Logger:
    """
    Logger class provides a modular and customizable logging system for console output.

    This class utilizes the `colorlog` library, allowing the user to create
    visually distinct log messages with color-coded outputs based on the log levels.
    The class enables configuring log profiles and levels dynamically, enhancing
    logging visibility and readability. It is suitable for debugging and error
    tracking in applications by managing and formatting log messages across different
    scopes.

    :ivar log: The primary logger instance for handling logs.
    :type log: colorlog.RootLogger
    :ivar console: Handler for directing log messages to the console output.
    :type console: logging.StreamHandler
    """
    def __init__(self, name:str, profile:str="lowvis", loglevel: Literal["DEBUG", "INFO", "WARNING", "ERROR"]="DEBUG"):
        """
        Represents a logger object that initializes a logging instance with customized
        configurations such as log level, output format, and coloring profile.

        :param name: Name of the logger instance, used for labeling log messages.
        :type name: str
        :param profile: The color profile that determines log color formatting. Default is "lowvis".
        :type profile: str, optional
        :param loglevel: Minimum log level for console messages. Default is "DEBUG".
        :type loglevel: Literal["DEBUG", "INFO", "WARNING", "ERROR"], optional
        """
        self.log = colorlog.getLogger(name)
        self.log.setLevel("DEBUG")

        # Let's create our handlers
        self.console = logging.StreamHandler()
        self.console.setLevel(loglevel)
        log_format = colorlog.ColoredFormatter(
            fmt="{log_color}{asctime} - {name:10s} - {levelname:10s} - {message}",
            style="{",
            datefmt="%H:%M:%S",
            log_colors=self.get_profile(profile),
        )
        self.console.setFormatter(log_format)
        self.log.addHandler(self.console)

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
    def warning(self, msg):
        self.log.warning(msg)
    def info(self, msg):
        self.log.info(msg)
    def debug(self, msg):
        self.log.debug(msg)
    def error(self, msg):
        self.log.error(msg)
    def get_profile(self, profile):
        profiles = {
            "highvis": {
                "DEBUG": "cyan",
                "INFO": "light_green",
                "WARNING": "light_yellow",
                "ERROR": "light_red",
                "CRITICAL": "light_red,bg_white"
            },
            "lowvis": {
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white"
            }
        }
        return profiles[profile]



if __name__ == "__main__":
    log = Logger("LOGGER", loglevel="DEBUG")
    log.info("This is info")
    log.warning("This is warning")
    log.error("This is error")
    log.debug("This is debug")

