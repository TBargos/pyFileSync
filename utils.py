import logging
import os
from datetime import datetime, timezone

from configparser import ConfigParser


py_logger = logging.getLogger(__name__)


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
        if os.path.isdir(os.path.join(path, file)):
            message = ('Внимание: локальный объект "{name}" является папкой. ' 
                'Процесс синхронизации не предусмотрен для вложенных папок'.format(name=file))
            py_logger.warning(message)
            continue

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
    py_logger.debug(f'Обнаружено файлов в локальном хранилище: {len(result)}')
    return result

def check_config() -> bool:
    # TODO написать проверку конфига на заполненность или убрать объявление
    pass

def compare_cloud_local(cloud: dict[str], local: dict[str]) -> dict[str]:
    # Первый тур: поиск файлов, которых нет или в облаке, или локально
    not_in_cloud = set(local.keys()) - set(cloud.keys())
    if not_in_cloud:
        py_logger.debug('Обнаружены файлы, отсутствующие в облаке')
    not_in_local = set(cloud.keys()) - set(local.keys())
    if not_in_local:
        py_logger.debug('Обнаружены файлы, которых нет локально')
    # Второй тур: сравнение файлов с одинаковыми именами
    same_names = set(cloud.keys()) & set(local.keys())
    reload = {
        name for name in same_names
        if cloud[name]['size'] != local[name]['size'] or
            cloud[name]['last_modified'] < local[name]['last_modified']
    }
    if reload:
        py_logger.debug('Обнаружены файлы, которые нужно обновить в облаке')
    # Подготовка списка задач в формате словаря
    result = {
        'load': not_in_cloud,
        'reload': reload,
        'delete': not_in_local
    }
    py_logger.debug('Список задач для синхронизации подготовлен')
    return result