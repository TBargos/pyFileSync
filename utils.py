import logging
import os
import hashlib
from datetime import datetime, timezone

from configparser import ConfigParser, NoOptionError, NoSectionError


py_logger = logging.getLogger(__name__)


def get_config(filename: str = 'config.ini') -> ConfigParser:
    if not os.path.isfile(filename):
        raise FileNotFoundError(f'Конфигурационный файл "{filename}" не обнаружен!')
    config = ConfigParser()
    config.read(filename)
    return config

def raise_for_config(config: ConfigParser) -> None:
    not_null_keys = ('local_path', 'sync_period', 'log_path', 'token')
    may_null_keys = ('cloud_path',)

    if not config.has_section('Yandex'):
        raise KeyError('Секция "Yandex" отсутствует в конфигурационном файле')
    for key in not_null_keys:
        if not config['Yandex'].get(key, fallback=None):
            raise KeyError(f'Параметр {key} не инициализирован или отсутствует в конфигурационном файле')
    for key in may_null_keys:
        if config['Yandex'].get(key, fallback=None) is None:
            raise KeyError(f'Параметр {key} отсутствует в конфигурационном файле')

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

def calculate_hashes(file_path: str, chunk_size=8192):
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            md5.update(chunk)
            sha256.update(chunk)
    py_logger.debug('Расчёт суммы MD5 и хэша SHA256 завершён')
    return md5.hexdigest(), sha256.hexdigest()