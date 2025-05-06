import logging
import os
from datetime import datetime, timezone

from configparser import ConfigParser


py_logger = logging.getLogger(__name__)
py_logger.setLevel(logging.INFO)


def get_config(filename: str = 'config.ini') -> ConfigParser:
    if not os.path.isfile(filename):
        raise FileNotFoundError(f'Конфигурационный файл "{filename}" не обнаружен!')
    config = ConfigParser()
    config.read(filename)
    return config

def get_info(path: str) -> dict[str]:
    if not os.path.isdir(path):
        raise NotADirectoryError
    result = dict()
    for file in os.listdir(path):
        file_info = os.stat(os.path.join(path, file))
        # Конвертирует время из системы в datetime, обрезая микросекунды
        dt_last_modified = datetime.fromtimestamp(
            file_info.st_mtime,
            timezone.utc
        ).replace(microsecond=0)
        # Собирает словарь для последующего сравнения с таким же от интерфейса для Яндекс Диска
        result[file] = {
            'last_modified': dt_last_modified,
            'size': int(file_info.st_size)
        }
    return result

def check_config():
    # TODO написать проверку конфига на заполненность или убрать объявление
    pass

def compare_cloud_local(cloud: dict[str], local: dict[str]):
    # Первый тур: поиск файлов, которых нет или в облаке, или локально
    not_in_cloud = set(local.keys()) - set(cloud.keys())
    not_in_local = set(cloud.keys()) - set(local.keys())
    # Второй тур: сравнение файлов с одинаковыми именами
    same_names = set(cloud.keys()) & set(local.keys())
    reload = {
        name for name in same_names
        if cloud[name]['size'] != local[name]['size'] or
            cloud[name]['last_modified'] < local[name]['last_modified']
    }
    # Подготовка списка задач в формате словаря
    result = {
        'load': not_in_cloud,
        'reload': reload,
        'delete': not_in_local
    }
    return result