"""Модуль, предоставляющий интерфейс для взаимодействия с облачным хранилищем файлов"""

import configparser
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
    BASE_URL = "https://webdav.yandex.ru"

    def __init__(self, token, cloud_path):
        self.__token = token
        self.__cloud_path = cloud_path

    def load(self, local_path: str, filename: str) -> None:
        """для загрузки файла в хранилище"""
        response = self._load(local_path, filename)
        if response.status_code == 201:
            py_logger.info(f'Файл "{filename}" успешно загружен.')
        else:
            py_logger.error(f'При загрузке файла "{filename}" возникли непредвиденные проблемы')

    def reload(self, local_path: str, filename: str) -> None:
        """для перезаписи файла в хранилище"""
        first_response = self._delete(filename)
        if first_response.status_code != 204:
            py_logger.error('Обновление файла невозможно: при удалении возникла непредвиденная ошибка')
            return
        py_logger.debug(f'Файл "{filename}" удалён в облачном хранилище')
        second_response = self._load(local_path, filename)
        if second_response.status_code == 201:
            py_logger.info(f'Файл "{filename}" успешно обновлён в облачном хранилище')
        else:
            py_logger.error('Обновление файла невозможно: при загрузке возникла непредвиденная ошибка')

    def delete(self, filename: str) -> None:
        """для удаления файла из хранилища"""
        response = self._delete(filename)
        if response.status_code == 204:
            py_logger.info(f'Файл "{filename}" успешно удалён.')
        else:
            py_logger.error(f'При удалении файла "{filename}" возникли непредвиденные проблемы')

    def get_info(self) -> dict[dict[str]] | None:
        """для получения информации о хранящихся в удалённом хранилище файлах"""
        return self._get_info()

    def _load(self, local_path: str, filename: str) -> Response:
        file_path = os.path.join(local_path, filename)
        py_logger.debug(f'Подготовка к загрузке файла "{filename}"')
        md5, sha256 = utils.calculate_hashes(file_path)
        headers = {
            'Accept': '*/*',
            'Authorization': self.__token,
            'Etag': md5,
            'Sha256': sha256,
            'Expect': '100-continue',
            'Content-Type': 'application/binary',
        }

        py_logger.debug(f'Открытие файла "{filename}" в двоичном режиме')
        with open(file_path, 'rb') as f:
            response = self._request("PUT", f'{self.__cloud_path}/{filename}', headers=headers, data=f)
        py_logger.debug(f'Файл "{filename}" в двоичном режиме закрыт')
        return response

    def _delete(self, filename: str) -> Response:
        headers = {
            'Accept': '*/*',
            'Authorization': self.__token,
            "Content-Type": "application/xml"
        }
        response = self._request("DELETE", f'{self.__cloud_path}/{filename}', headers=headers)
        return response

    def _get_info(self) -> dict[dict[str]] | None:
        headers = {
            'Accept': '*/*',
            'Depth': '1',
            'Authorization': self.__token,
            "Content-Type": "application/xml",
        }

        response = self._request("PROPFIND", self.__cloud_path, headers)
        if response.status_code == 207:
            py_logger.info('Получены XML-данные от Яндекс.Диска')
        return self._make_info_dict(response)
        
    def _request(self, method: str, endpoint: str, headers: dict[str], data=None) -> Response:
        try:
            response = request(method, f'{self.BASE_URL}/{endpoint}', headers=headers, data=data)
            py_logger.debug('Запрос отправлен на сервер Яндекс.Диска')
            response.raise_for_status()
            py_logger.debug('Получен ответ от Яндекс.Диска')
        except HTTPError:
            message = 'HTTP Error'
            if response.status_code == 401:
                message = 'Некорректный токен'
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
        result = dict()
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            py_logger.error("Тело ответа пустое, парсинг XML невозможен.")
            return
        
        py_logger.info('Начат парсинг XML-ответа.')
        for tag in root.findall('{DAV:}response/{DAV:}propstat/{DAV:}prop')[1:]:
            filename = tag.find('{DAV:}displayname').text
            py_logger.debug(f'Обнаружен объект "{filename}"')

            try:
                size = int(tag.find('{DAV:}getcontentlength').text)
                py_logger.debug(f'"{filename}" имеет размер ({size} байт), значит "{filename}" - файл')
            except AttributeError:
                message = ('Внимание: объект "{name}" в облачном хранилище является папкой. ' 
                'Процесс синхронизации не предусмотрен для вложенных папок'.format(
                    name=tag.find('{DAV:}displayname').text
                ))
                py_logger.warning(message)
                continue

            yandex_last_modified = tag.find('{DAV:}getlastmodified').text
            dt_last_modified = datetime.strptime(
                yandex_last_modified,
                "%a, %d %b %Y %H:%M:%S GMT"
            ).replace(tzinfo=timezone.utc)
            
            result[filename] = {
                'last_modified': dt_last_modified,
                'size': size
            }

        py_logger.info('Завершён парсинг XML-ответа от Яндекс.Диска')
        py_logger.debug(f'Обнаружено файлов в облачном хранилище: {len(result)}')
        return result