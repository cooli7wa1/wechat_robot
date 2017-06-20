import os
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


