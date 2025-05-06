"""Модуль, предоставляющий интерфейс для взаимодействия с облачным хранилищем файлов"""

import configparser
import logging
import xml.etree.ElementTree as ET

from requests import request, Response
from requests.exceptions import HTTPError


py_logger = logging.getLogger(__name__)
py_logger.setLevel(logging.INFO)


class YadiskAPI:
    BASE_URL = "https://webdav.yandex.ru"

    def __init__(self, token, cloud_path):
        self.__token = token
        self.__cloud_path = cloud_path

    def load(self, path: str):
        """для загрузки файла в хранилище"""
        # TODO добавить реализацию
        pass

    def reload(self, path: str):
        """для перезаписи файла в хранилище"""
        # TODO добавить реализацию
        pass

    def delete(self, filename: str):
        """для удаления файла из хранилища"""
        # TODO добавить реализацию
        pass

    def get_info(self, endpoint: str):
        """для получения информации о хранящихся в удалённом хранилище файлах"""
        return self._get_info(endpoint)

    def _get_info(self, endpoint: str) -> dict[dict[str] | None]:
        headers = {
            'Accept': '*/*',
            'Depth': '1',
            'Authorization': self.__token,
            "Content-Type": "application/xml",
        }

        try:
            response = request("PROPFIND", f'{self.BASE_URL}/{endpoint}', headers=headers)
            py_logger.info('Запрос отправлен на сервер Яндекс.Диска')
            response.raise_for_status()
        except HTTPError as exc:
            message = 'HTTP Error'
            if exc.response.reason == 'Unauthorized':
                message = 'Некорректный токен'
            py_logger.exception(message)
            return {}
        else:
            py_logger.info('Получен ответ от Яндекс.Диска')
        return self._make_info_dict(response)
        
    @staticmethod
    def _make_info_dict(response: Response) -> dict[dict[str]]:
        result = dict()
        root = ET.fromstring(response.text)
        
        py_logger.debug('Начат парсинг XML-ответа.')
        for tag in root.findall('{DAV:}response/{DAV:}propstat/{DAV:}prop')[1:]:
            last_modified = tag.find('{DAV:}getlastmodified').text
            filename = tag.find('{DAV:}displayname').text
            py_logger.debug(f'Обнаружен объект "{filename}".')

            try:
                size = tag.find('{DAV:}getcontentlength').text
                py_logger.debug(f'"{filename}" имеет размер ({size} байт), значит "{filename}" - файл.')
            except AttributeError:
                message = ('Внимание: объект "{name}" в облачном хранилище является папкой. ' 
                'Процесс синхронизации не предусмотрен для вложенных папок.'.format(
                    name=tag.find('{DAV:}displayname').text
                ))
                py_logger.warning(message)
                continue
            
            result[filename] = {
                'last_modified': last_modified,
                'size': size
            }
        
        py_logger.debug('Завершён парсинг XML-ответа.')
        py_logger.debug(f'Обнаружено файлов: {len(result)}')
        return result