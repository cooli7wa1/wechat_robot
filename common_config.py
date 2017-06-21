import os
import logging,time

MONGO_URL = 'localhost'
MONGO_DB = 'lianmeng'
MONGO_TABLE = 'lianmeng'
MONGO_TABLE_SEARCH = 'search'

# ERROR
SUCCESS = 0
NO_GOODS = -1
RETRY_TIME_OUT = -2
LOG_IN_TIME_OUT = -3

os_documents_path = os.popen('echo $HOME').read().replace('\n','') + u'/Documents/'
PICTURES_FOLD_PATH = os_documents_path + u'robot_data/xiaoyezi/pictures/'
EXCEL_FILE_PATH = os_documents_path + u'robot_data/xiaoyezi/goods_excel.xls'
CODE_IMAGE_FOLD_PATH = os_documents_path + u'robot_data/xiaoyezi/'

LOG_FOLD = os_documents_path + u'robot_data/xiaoyezi/log/'
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(funcName)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S',
                    filename=LOG_FOLD + 'log_' + time.strftime('%Y-%m-%d_%H%M%S', time.localtime(time.time())) + '.txt',
                    filemode='w')

console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(funcName)s[line:%(lineno)d] %(levelname)s %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)