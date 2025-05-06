import logging
import os

from configparser import ConfigParser


py_logger = logging.getLogger(__name__)
py_logger.setLevel(logging.INFO)


def get_config(filename: str = 'config.ini') -> ConfigParser:
    if not os.path.isfile(filename):
        raise OSError(f'Конфигурационный файл "{filename}" не обнаружен!')
    config = ConfigParser()
    config.read(filename)
    return config