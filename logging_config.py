import logging
import config

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(config.FLIGHT_LOG_FILE),
            logging.StreamHandler()
        ]
    )