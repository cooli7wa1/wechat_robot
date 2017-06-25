import os
import logging,time,sys

MONGO_URL = 'localhost'
MONGO_DB_LIANMENG = 'lianmeng'
MONGO_DB_WECHAT = 'wechat'
MONGO_TABLE_WECHAT_USERS = 'wechat_users'
MONGO_TABLE_LM_SEARCH_GOODS = 'lm_search_goods'
MONGO_TABLE_LM_SEARCH_HISTORY = 'lm_search_history'

# ERROR
SUCCESS = 0
COMMON_ERROR = -1
LM_NO_GOODS = -2
LM_RETRY_TIME_OUT = -3
LM_LOG_IN_TIME_OUT = -4
WECHAT_ALREADY_CHECKIN = -5
WECHAT_LINK_FAILED = -6
WECHAT_NOT_FIND = -7
WECHAT_MORE_THAN_ONE_FOUND = -8
WECHAT_ZHIFUBAO_EXIST = -9
WECHAT_NICKNAME_EXIST = -10
WECHAT_ZHIFUBAO_NICKNAME_BOTH_EXIST = -11
WECHAT_NO_ZHIFUBAOZH = -12
WECHAT_DB_ERROR = -13
WECHAT_ZHIFUBAO_NOT_EMPTY = -14
WECHAT_NOT_FIND_FATHER = -15

os_documents_path = os.popen('echo $HOME').read().replace('\n','') + u'/Documents/'
PICTURES_FOLD_PATH = os_documents_path + u'robot_data/xiaoyezi/pictures/'
EXCEL_FILE_PATH = os_documents_path + u'robot_data/xiaoyezi/goods_excel.xls'
CODE_IMAGE_FOLD_PATH = os_documents_path + u'robot_data/xiaoyezi/'

LOG_FOLD = os_documents_path + u'robot_data/xiaoyezi/log/'
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(funcName)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a %d %b %Y %H:%M:%S',
                    filename='%slog_%d_%s.txt' % (LOG_FOLD, int(time.time()), time.strftime('%Y-%m-%d-%H%M%S', time.localtime(time.time()))),
                    filemode='w')

console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(funcName)s[line:%(lineno)d] %(levelname)s %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)