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

os_f = os.popen('uname')
os_system = os_f.read().replace('\n','')
if os_system == 'Linux':
    PICTURES_FOLD_PATH = u'/root/robot_data/xiaoyezi/pictures/'
    EXCEL_FILE_PATH = u'/root/robot_data/xiaoyezi/goods_excel.xls'
    CODE_IMAGE_FOLD_PATH = u'/root/robot_data/xiaoyezi/'
else:
    PICTURES_FOLD_PATH = u'F:\\robot_data\\xiaoyezi\\pictures\\'
    EXCEL_FILE_PATH = u'F:\\robot_data\\xiaoyezi\\goods_excel.xls'
    CODE_IMAGE_FOLD_PATH = u'F:\\robot_data\\xiaoyezi\\'


