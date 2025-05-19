"""Модуль, предоставляющий интерфейс для взаимодействия с облачным хранилищем файлов"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import sys

from requests import request, put, Response
from requests.exceptions import HTTPError

import utils
import os


py_logger = logging.getLogger(__name__)


class YadiskAPI:
    """
    Интерфейс для взаимодействия с облачным хранилищем Яндекс.Диска через WebDAV API.

    Класс YadiskAPI инкапсулирует методы для загрузки, удаления, обновления файлов
    и получения информации о файлах в облачном хранилище.

    Attributes:
        BASE_URL (str): Базовый URL для WebDAV API Яндекс.Диска.

    Methods:
        load(local_path: str, filename: str) -> None
            Загружает файл из локальной директории в облачное хранилище.

        reload(local_path: str, filename: str) -> None
            Обновляет файл в облаке, предварительно удаляя старую версию.

        delete(filename: str) -> None
            Удаляет файл из облачного хранилища.

        get_info() -> dict[dict[str]] | None
            Возвращает метаинформацию о файлах в облаке.
    """

    BASE_URL = "https://webdav.yandex.ru"

    def __init__(self, token, cloud_path):
        """
        Инициализирует объект для работы с Яндекс.Диском.

        Args:
            token (str): Токен авторизации для доступа к API.
            cloud_path (str): Путь к директории в облачном хранилище.
        """

        self.__token = token
        self.__cloud_path = cloud_path

    def load(self, local_path: str, filename: str) -> None:
        """
        Загружает файл из локальной директории в облачное хранилище.

        Логирование:
            - INFO при успешной загрузке
            - ERROR при ошибках загрузки

        Args:
            local_path (str): Путь к локальной директории с файлом.
            filename (str): Имя файла для загрузки.
        """

        response = self._load(local_path, filename)
        if response.status_code == 201:
            py_logger.info(f'Файл "{filename}" успешно загружен.')
        else:
            py_logger.error(
                f'При загрузке файла "{filename}" возникли непредвиденные проблемы'
            )

    def reload(self, local_path: str, filename: str) -> None:
        """
        Обновляет файл в облаке: удаляет старую версию и загружает новую.

        Логирование:
            - DEBUG при успешном удалении старой версии
            - INFO при успешной загрузке новой версии
            - ERROR при ошибках на любом этапе

        Args:
            local_path (str): Путь к локальной директории с файлом.
            filename (str): Имя обновляемого файла.
        """

        first_response = self._delete(filename)
        if first_response.status_code != 204:
            py_logger.error(
                "Обновление файла невозможно: при удалении возникла непредвиденная ошибка"
            )
            return
        py_logger.debug(f'Файл "{filename}" удалён в облачном хранилище')
        second_response = self._load(local_path, filename)
        if second_response.status_code == 201:
            py_logger.info(f'Файл "{filename}" успешно обновлён в облачном хранилище')
        else:
            py_logger.error(
                "Обновление файла невозможно: при загрузке возникла непредвиденная ошибка"
            )

    def delete(self, filename: str) -> None:
        """
        Удаляет файл из облачного хранилища.

        Логирование:
            - INFO при успешном удалении
            - ERROR при ошибках удаления

        Args:
            filename (str): Имя удаляемого файла.
        """

        response = self._delete(filename)
        if response.status_code == 204:
            py_logger.info(f'Файл "{filename}" успешно удалён.')
        else:
            py_logger.error(
                f'При удалении файла "{filename}" возникли непредвиденные проблемы'
            )

    def get_info(self) -> dict[dict[str]] | None:
        """
        Получает метаданные о файлах в облачном хранилище.

        Логирование:
            - INFO при успешном получении данных
            - WARNING при обнаружении папок
            - ERROR при ошибках парсинга

        Returns:
            dict[dict[str]]: Словарь с ключами-именами файлов и значениями:
                'last_modified' (datetime): Время последнего изменения (UTC)
                'size' (int): Размер файла в байтах
        """
        return self._get_info()

    def _load(self, local_path: str, filename: str) -> Response:
        """
        Выполняет загрузку файла в облачное хранилище через HTTP PUT запрос.

        Логика работы:
            - Вычисляет MD5 и SHA256 хэши файла.
            - Формирует заголовки с авторизацией и хэшами.
            - Открывает файл в бинарном режиме и отправляет PUT-запрос.
            - Возвращает ответ сервера.

        Логирование:
            - DEBUG при подготовке к загрузке файла.
            - DEBUG при открытии и закрытии файла в двоичном режиме.
            - DEBUG при отправке запроса и получении ответа.

        Args:
            local_path (str): Путь к локальной директории.
            filename (str): Имя файла для загрузки.

        Returns:
            Response: Объект ответа HTTP.
        """

        file_path = os.path.join(local_path, filename)
        py_logger.debug(f'Подготовка к загрузке файла "{filename}"')
        md5, sha256 = utils.calculate_hashes(file_path)
        headers = {
            "Accept": "*/*",
            "Authorization": self.__token,
            "Etag": md5,
            "Sha256": sha256,
            "Expect": "100-continue",
            "Content-Type": "application/binary",
        }

        py_logger.debug(f'Открытие файла "{filename}" в двоичном режиме')
        with open(file_path, "rb") as f:
            response = self._request(
                "PUT", f"{self.__cloud_path}/{filename}", headers=headers, data=f
            )
        py_logger.debug(f'Файл "{filename}" в двоичном режиме закрыт')
        return response

    def _delete(self, filename: str) -> Response:
        """
        Выполняет удаление файла из облачного хранилища через HTTP DELETE запрос.

        Логирование:
            - DEBUG при отправке запроса на удаление.
            - DEBUG при получении ответа от сервера.

        Args:
            filename (str): Имя файла для удаления.

        Returns:
            Response: Объект ответа HTTP.
        """

        headers = {
            "Accept": "*/*",
            "Authorization": self.__token,
            "Content-Type": "application/xml",
        }
        response = self._request(
            "DELETE", f"{self.__cloud_path}/{filename}", headers=headers
        )
        return response

    def _get_info(self) -> dict[dict[str]] | None:
        """
        Получает информацию о файлах в облачном хранилище через PROPFIND запрос.

        Логика работы:
            - Формирует заголовки запроса.
            - Отправляет PROPFIND-запрос.
            - При успешном ответе (207) парсит XML и формирует словарь с именами файлов,
            временем последнего изменения и размером.
            - Игнорирует папки, давая предупреждения в логе.

        Логирование:
            - INFO при получении XML-данных.
            - INFO при начале и окончании парсинга XML.
            - DEBUG при обнаружении каждого объекта.
            - WARNING при обнаружении папок.
            - ERROR при ошибках парсинга XML.

        Returns:
            dict[dict[str]] | None: Словарь с метаданными файлов или None при ошибке.
        """

        headers = {
            "Accept": "*/*",
            "Depth": "1",
            "Authorization": self.__token,
            "Content-Type": "application/xml",
        }

        response = self._request("PROPFIND", self.__cloud_path, headers)
        if response.status_code == 207:
            py_logger.info("Получены XML-данные от Яндекс.Диска")
        return self._make_info_dict(response)

    def _request(
        self, method: str, endpoint: str, headers: dict[str], data=None
    ) -> Response:
        """
        Универсальный метод для отправки HTTP-запросов к API Яндекс.Диска.

        Логика работы:
            - Формирует полный URL, отправляет запрос.
            - Проверяет статус ответа, при ошибках логирует и завершает программу с сообщением.
            - Возвращает объект ответа при успешном выполнении.

        Логирование:
            - DEBUG при отправке запроса и получении ответа.
            - CRITICAL при ошибках HTTP с указанием типа ошибки.
            - ERROR с трассировкой стека при неизвестных ошибках.

        Args:
            method (str): HTTP-метод (GET, PUT, DELETE, PROPFIND и т.д.).
            endpoint (str): Относительный путь к ресурсу в облаке.
            headers (dict[str]): Заголовки запроса.
            data (optional): Тело запроса (для PUT и др.).

        Returns:
            Response: Объект ответа HTTP.

        Raises:
            SystemExit: Завершает программу с кодом 1 при непредвиденных HTTP-ошибках.
        """

        try:
            response = request(
                method, f"{self.BASE_URL}/{endpoint}", headers=headers, data=data
            )
            py_logger.debug("Запрос отправлен на сервер Яндекс.Диска")
            response.raise_for_status()
            py_logger.debug("Получен ответ от Яндекс.Диска")
        except HTTPError:
            message = "HTTP Error"
            if response.status_code == 401:
                message = "Некорректный токен"
            elif response.status_code == 404:
                message = f'Объекта "{endpoint}" не существует в облачном хранилище'
            else:
                py_logger.exception(message)
                return response
            py_logger.critical(message, exc_info=True)
            sys.exit(1)

        return response

    @staticmethod
    def _make_info_dict(response: Response) -> dict[dict[str]] | None:
        """
        Парсит XML-ответ от PROPFIND запроса и формирует словарь с информацией о файлах.

        Логика работы:
            - Парсит XML с помощью ElementTree.
            - Пропускает первый элемент (корневой каталог).
            - Для каждого файла извлекает имя, размер и дату последнего изменения.
            - Логирует предупреждения для папок.

        Логирование:
            - INFO при начале и завершении парсинга XML.
            - DEBUG при обнаружении каждого объекта.
            - WARNING при обнаружении папок.
            - ERROR при ошибках парсинга XML.

        Args:
            response (Response): HTTP-ответ с XML телом.

        Returns:
            dict[dict[str]] | None: Словарь с ключами-именами файлов и значениями:
                'last_modified' (datetime): Время последнего изменения (UTC).
                'size' (int): Размер файла в байтах.
            Возвращает None, если парсинг невозможен.
        """

        result = dict()
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            py_logger.error("Тело ответа пустое, парсинг XML невозможен.")
            return

        py_logger.info("Начат парсинг XML-ответа.")
        for tag in root.findall("{DAV:}response/{DAV:}propstat/{DAV:}prop")[1:]:
            filename = tag.find("{DAV:}displayname").text
            py_logger.debug(f'Обнаружен объект "{filename}"')

            try:
                size = int(tag.find("{DAV:}getcontentlength").text)
                py_logger.debug(
                    f'"{filename}" имеет размер ({size} байт), значит "{filename}" - файл'
                )
            except AttributeError:
                message = (
                    'Внимание: объект "{name}" в облачном хранилище является папкой. '
                    "Процесс синхронизации не предусмотрен для вложенных папок".format(
                        name=tag.find("{DAV:}displayname").text
                    )
                )
                py_logger.warning(message)
                continue

            yandex_last_modified = tag.find("{DAV:}getlastmodified").text
            dt_last_modified = datetime.strptime(
                yandex_last_modified, "%a, %d %b %Y %H:%M:%S GMT"
            ).replace(tzinfo=timezone.utc)

            result[filename] = {"last_modified": dt_last_modified, "size": size}

        py_logger.info("Завершён парсинг XML-ответа от Яндекс.Диска")
        py_logger.debug(f"Обнаружено файлов в облачном хранилище: {len(result)}")
        return result
