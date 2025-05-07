import logging
import sys
import time

import utils
from api import YadiskAPI


def initialize():
    log_format = "%(name)s %(asctime)s %(levelname)s %(message)s"
    try:
        config = utils.get_config()
        utils.raise_for_config(config)
    except (FileNotFoundError, KeyError) as exc:
        logging.basicConfig(filename='config_load.log', format=log_format)
        logging.critical(exc)
        sys.exit(1)
    else:
        config = config['Yandex']

    log_path = config['log_path']
    logging.basicConfig(filename=log_path, format=log_format, level=logging.DEBUG)
    
    sync_period = float(config['sync_period']) * 60
    yapi = YadiskAPI(token=config['token'], cloud_path=config['cloud_path'])
    infinite_sync(yapi, config['local_path'], sync_period)
    
def infinite_sync(yapi: YadiskAPI, local_path: str, sync_period: float):
    logging.info('Первая синхронизация')
    while True:
        logging.info('Синхронизация начата')
        cloud_dict = yapi.get_info()
        logging.info('Получен список облачных файлов')
        local_dict = utils.get_info(local_path)
        logging.info('Получен список локальных файлов')
        todo_dict = utils.compare_cloud_local(cloud_dict, local_dict)
        logging.info('Получен список задач для синхронизации')

        for file in todo_dict['delete']:
            yapi.delete(file)
        for file in todo_dict['load']:
            yapi.load(local_path, file)
        for file in todo_dict['reload']:
            yapi.reload(local_path, file)

        logging.info('Синхронизация завершена')
        time.sleep(sync_period)


if __name__ == '__main__':
    initialize()