"""
Утилиты для работы с конфигурацией, локальной файловой системой и синхронизацией.

Содержит функции для загрузки и проверки конфигурации, получения информации о локальных файлах,
сравнения локальных и облачных файлов, а также вычисления контрольных сумм файлов.

Функции:
    get_config(filename: str = 'config.ini') -> ConfigParser
        Загружает конфигурационный файл.

    raise_for_config(config: ConfigParser) -> None
        Проверяет наличие обязательных параметров в конфигурации.

    get_info(path: str) -> dict[str, dict[str]]
        Получает информацию о файлах в локальной директории.

    compare_cloud_local(cloud: dict[str, dict[str]], local: dict[str, dict[str]]) -> dict[str, set]
        Сравнивает списки файлов из облака и локальной папки, формирует задачи для синхронизации.

    calculate_hashes(file_path: str, chunk_size=8192) -> tuple[str, str]
        Вычисляет MD5 и SHA256 хэши файла.
"""

import logging
import os
import hashlib
from datetime import datetime, timezone

from configparser import ConfigParser, NoOptionError, NoSectionError


py_logger = logging.getLogger(__name__)


def get_config(filename: str = "config.ini") -> ConfigParser:
    """
    Загружает конфигурационный файл.

    Args:
        filename (str): Путь к конфигурационному файлу. По умолчанию 'config.ini'.

    Returns:
        ConfigParser: Объект с загруженной конфигурацией.

    Raises:
        FileNotFoundError: Если файл конфигурации не найден.
    """

    if not os.path.isfile(filename):
        raise FileNotFoundError(f'Конфигурационный файл "{filename}" не обнаружен!')
    config = ConfigParser()
    config.read(filename)
    return config


def raise_for_config(config: ConfigParser) -> None:
    """
    Выбрасывает ошибку, если нет секции 'Yandex', параметры конфигурационного файла не инициализированы или отсутствуют.

    Args:
        config (ConfigParser): Объект конфигурации.

    Raises:
        KeyError: Если отсутствует секция 'Yandex' или обязательные параметры не инициализированы.
    """

    not_null_keys = ("local_path", "sync_period", "log_path", "token")
    may_null_keys = ("cloud_path",)

    if not config.has_section("Yandex"):
        raise KeyError('Секция "Yandex" отсутствует в конфигурационном файле')
    for key in not_null_keys:
        if not config["Yandex"].get(key, fallback=None):
            raise KeyError(
                f"Параметр {key} не инициализирован или отсутствует в конфигурационном файле"
            )
    for key in may_null_keys:
        if config["Yandex"].get(key, fallback=None) is None:
            raise KeyError(f"Параметр {key} отсутствует в конфигурационном файле")


def get_info(path: str) -> dict[str, dict[str]]:
    """
    Получает информацию о файлах в локальной директории.

    Для каждого файла в директории собирает словарь с датой последнего изменения и размером файла.
    Игнорирует вложенные папки, при этом выводит предупреждение в лог.

    Args:
        path (str): Путь к локальной директории.

    Returns:
        dict[str, dict[str]]: Словарь, где ключ - имя файла, значение - словарь с ключами:
            'last_modified' (datetime): Время последнего изменения файла (UTC, без микросекунд).
            'size' (int): Размер файла в байтах.

    Raises:
        NotADirectoryError: Если указанный путь не является директорией.
    """

    if not os.path.isdir(path):
        raise NotADirectoryError(f'"{path}" не является папкой')
    result = dict()
    for file in os.listdir(path):
        if os.path.isdir(os.path.join(path, file)):
            message = (
                'Внимание: локальный объект "{name}" является папкой. '
                "Процесс синхронизации не предусмотрен для вложенных папок".format(
                    name=file
                )
            )
            py_logger.warning(message)
            continue

        file_info = os.stat(os.path.join(path, file))
        # Конвертирует время из системы в datetime, обрезая микросекунды
        dt_last_modified = datetime.fromtimestamp(
            file_info.st_mtime, timezone.utc
        ).replace(microsecond=0)
        # Собирает словарь для последующего сравнения с таким же от интерфейса для Яндекс Диска
        result[file] = {
            "last_modified": dt_last_modified,
            "size": int(file_info.st_size),
        }
    py_logger.debug(f"Обнаружено файлов в локальном хранилище: {len(result)}")
    return result


def compare_cloud_local(
    cloud: dict[str, dict[str]], local: dict[str, dict[str]]
) -> dict[str, set[str]]:
    """
    Сравнивает списки файлов из облака и локальной директории, формирует задачи для синхронизации.

    Определяет файлы, которые нужно загрузить в облако, обновить или удалить.

    Args:
        cloud (dict[str, dict[str]]): Информация о файлах в облаке.
        local (dict[str, dict[str]]): Информация о локальных файлах.

    Returns:
        dict[str, set[str]]: Словарь, содержащий сеты (множества) ключей:
            'load' (set): Файлы, которые есть локально, но отсутствуют в облаке.
            'reload' (set): Файлы, которые изменились локально и требуют обновления в облаке.
            'delete' (set): Файлы, которые есть в облаке, но отсутствуют локально.
    """

    # Первый тур: поиск файлов, которых нет или в облаке, или локально
    not_in_cloud = set(local.keys()) - set(cloud.keys())
    if not_in_cloud:
        py_logger.debug("Обнаружены файлы, отсутствующие в облаке")
    not_in_local = set(cloud.keys()) - set(local.keys())
    if not_in_local:
        py_logger.debug("Обнаружены файлы, которых нет локально")
    # Второй тур: сравнение файлов с одинаковыми именами
    same_names = set(cloud.keys()) & set(local.keys())
    reload = {
        name
        for name in same_names
        if cloud[name]["size"] != local[name]["size"]
        or cloud[name]["last_modified"] < local[name]["last_modified"]
    }
    if reload:
        py_logger.debug("Обнаружены файлы, которые нужно обновить в облаке")
    # Подготовка списка задач в формате словаря
    result = {"load": not_in_cloud, "reload": reload, "delete": not_in_local}
    py_logger.debug("Список задач для синхронизации подготовлен")
    return result


def calculate_hashes(file_path: str, chunk_size=8192) -> tuple[str, str]:
    """
    Вычисляет MD5 и SHA256 хэши файла.

    Читает файл по частям заданного размера и обновляет оба хэша.

    Args:
        file_path (str): Путь к файлу.
        chunk_size (int): Размер блока чтения в байтах. По умолчанию 8192, что исторически обусловлено
            оптимальным соотношением между частотой обращений к памяти и скоростью передачи

    Returns:
        tuple[str, str]: Кортеж из двух строк - MD5 и SHA256 хэши файла в шестнадцатеричном формате.
    """

    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            md5.update(chunk)
            sha256.update(chunk)
    py_logger.debug("Расчёт суммы MD5 и хэша SHA256 завершён")
    return md5.hexdigest(), sha256.hexdigest()
