"""Главный модуль синхронизации локальной папки с облачным хранилищем Яндекс.Диск.

Содержит функции для инициализации конфигурации, настройки логирования и
периодической синхронизации файлов между локальной директорией и облаком.

Функции:
    initialize() -> None
        Инициализирует конфигурацию, настраивает логирование и запускает бесконечный цикл синхронизации.

    infinite_sync(yapi: YadiskAPI, local_path: str, sync_period: float) -> None
        Запускает бесконечный цикл синхронизации файлов между локальной папкой и облаком с заданным периодом.
"""

import logging
import sys
import time

import utils
from api import YadiskAPI


def initialize() -> None:
    """
    Инициализирует конфигурацию и логирование, запускает бесконечный цикл синхронизации.

    Выполняет следующие действия:
        - Загружает конфигурацию из файла с помощью utils.get_config().
        - Проверяет корректность конфигурации через utils.raise_for_config().
        - При ошибках загрузки конфигурации записывает критическую ошибку в лог и завершает программу.
        - Настраивает логирование в файл, путь к которому указан в конфигурации.
        - Создаёт объект API для работы с Яндекс.Диском.
        - Запускает бесконечный цикл синхронизации с указанным периодом.

    Raises:
        SystemExit: Завершает программу с кодом 1 при ошибках загрузки или проверки конфигурации.
    """

    log_format = "%(name)s %(asctime)s %(levelname)s %(message)s"
    try:
        config = utils.get_config()
        utils.raise_for_config(config)
    except (FileNotFoundError, KeyError) as exc:
        logging.basicConfig(filename="config_load.log", format=log_format)
        logging.critical(exc)
        sys.exit(1)
    else:
        config = config["Yandex"]

    log_path = config["log_path"]
    logging.basicConfig(filename=log_path, format=log_format, level=logging.DEBUG)

    sync_period = float(config["sync_period"]) * 60
    yapi = YadiskAPI(token=config["token"], cloud_path=config["cloud_path"])
    infinite_sync(yapi, config["local_path"], sync_period)


def infinite_sync(yapi: YadiskAPI, local_path: str, sync_period: float) -> None:
    """
    Запускает бесконечный цикл синхронизации локальной папки с облачным хранилищем.

    Логика работы:
        - Получает список файлов в облаке и локальной папке.
        - Сравнивает списки и формирует задачи для удаления, загрузки и перезагрузки файлов.
        - Выполняет соответствующие операции через API.
        - Ждёт заданный период и повторяет процесс.

    Args:
        yapi (YadiskAPI): Объект API для взаимодействия с Яндекс.Диском.
        local_path (str): Путь к локальной директории для синхронизации.
        sync_period (float): Период синхронизации в секундах.
    """

    logging.info("Первая синхронизация")
    while True:
        logging.info("Синхронизация начата")
        cloud_dict = yapi.get_info()
        logging.info("Получен список облачных файлов")
        local_dict = utils.get_info(local_path)
        logging.info("Получен список локальных файлов")
        todo_dict = utils.compare_cloud_local(cloud_dict, local_dict)
        logging.info("Получен список задач для синхронизации")

        for file in todo_dict["delete"]:
            yapi.delete(file)
        for file in todo_dict["load"]:
            yapi.load(local_path, file)
        for file in todo_dict["reload"]:
            yapi.reload(local_path, file)

        logging.info("Синхронизация завершена")
        time.sleep(sync_period)


if __name__ == "__main__":
    initialize()
