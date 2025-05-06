import logging
import logging.config
import sys

import utils
from api import YadiskAPI


def initialize():
    log_format = "%(name)s %(asctime)s %(levelname)s %(message)s"
    try:
        config = utils.get_config()
    except FileNotFoundError as exc:
        logging.basicConfig(filename='config_load.log', format=log_format)
        logging.critical(exc)
        sys.exit(1)
    
    config = config['Yandex']
    log_path = config['log_path']
    logging.basicConfig(filename=log_path, format=log_format)

    yapi = YadiskAPI(token=config['token'], cloud_path=config['cloud_path'])
    cloud_dict = yapi.get_info(config['cloud_path'])
    local_dict = utils.get_info(config['local_path'])
    todo_dict = utils.compare_cloud_local(cloud_dict, local_dict)
    


if __name__ == '__main__':
    initialize()