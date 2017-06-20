#coding:utf-8
import logging, time
from common_config import *

os_documents_path = os.popen('echo $HOME').read().replace('\n','') + u'/Documents/'
ORDER_FILE_PATH = os_documents_path + u'robot_data/xiaoyezi/integral_record/order_file.txt'
GIT_DATA_FOLD = os_documents_path + u'robot_data/'
GIT_CODE_FOLD = os_documents_path + u'wechat_robot/'
MONGO_DB_DUMP_FOLD = os_documents_path + u'robot_data/xiaoyezi/mongodb/'
DATABASE_FOLD = os_documents_path + u'robot_data/xiaoyezi/database/'
ACTIVITY_FOLD = os_documents_path + u'robot_data/xiaoyezi/activity/'
TEMPLATE_FOLD = os_documents_path + u'robot_data/xiaoyezi/template/'
LOG_FOLD = os_documents_path + u'robot_data/xiaoyezi/log/'
MEMBER_RECORD_PATH = os_documents_path + u'robot_data/xiaoyezi/member_record/member_record.txt'
INTEGRAL_GOOD_FOLD = os_documents_path + u'robot_data/xiaoyezi/integral_good/'
INTEGRAL_RECORD_FOLD = os_documents_path + u'robot_data/xiaoyezi/integral_record/'

COMMAND_LIST = [u'看活动', u'查积分', u'签到', u'帮助', u'积分玩法', u'积分商品', u'兑换流程']
SEND_DELAY = 3  # 发送等待
SEND_TIMES = 3  # 发送最大次数
CHECK_IN_POINTS = 10  # 签到奖励的积分
INTEGRAL_PROP = 10  # 积分 = 商品价格*INTEGRAL_PROP*佣金比例(佣金比例最高录入20%）
INTEGRAL_GOOD_PROP = 100  # 积分商品所需积分 = 商品实际价格*INTEGRAL_GOOD_PROP*（1-佣金比例）
INNER_ROOM_NICK_NAME = u'乐淘家，内部信息群'
ROOM_NICK_NAME = u'\U0001f49d【乐淘家】淘天猫内部优惠精选\U0001f49d'
GOODS_PER_TIME = 3

label_ddlr = u"会员名 订单编号 订单价格 佣金比例".split()
label_jfdh = u"会员名 商品编号 商品价格 订单编号".split()
label_jljf = u"会员名 奖励积分".split()

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