#coding:utf-8
from common_config import *

os_documents_path = os.popen('echo $HOME').read().replace('\n','') + u'/Documents/'
INTEGRAL_FOLD = os_documents_path + u'robot_data/xiaoyezi/integral/'
INTEGRAL_GOOD_URL_FILE_PATH = INTEGRAL_FOLD + u'integral_good/url.txt'
INTEGRAL_RECORD_FOLD = INTEGRAL_FOLD + u'integral_record/'
INTEGRAL_INPUT_FOLD = INTEGRAL_FOLD + u'integral_input/'
ORDER_FILE_PATH = INTEGRAL_FOLD + u'integral_record/order_file.txt'
GIT_DATA_FOLD = os_documents_path + u'robot_data/'
GIT_CODE_FOLD = os_documents_path + u'wechat_robot/'
MONGO_DB_DUMP_FOLD = os_documents_path + u'robot_data/xiaoyezi/mongodb/'
DATABASE_FOLD = os_documents_path + u'robot_data/xiaoyezi/database/'
ACTIVITY_FOLD = os_documents_path + u'robot_data/xiaoyezi/activity/'
TEMPLATE_FOLD = os_documents_path + u'robot_data/xiaoyezi/template/'
MEMBER_RECORD_PATH = os_documents_path + u'robot_data/xiaoyezi/member_record/member_record.txt'
FONT_PATH = os_documents_path + u'wechat_robot/STXINWEI.TTF'
WECHAT_QR_PATH = GIT_DATA_FOLD + u'/QR.png'
LOTTERY_FOLD = os_documents_path + u'robot_data/xiaoyezi/lottery_activity/'

NORMAL_COMMAND_LIST = [u'看活动', u'查积分', u'签到', u'帮助', u'积分玩法', u'积分商品', u'兑换流程']
SPECIAL_COMMAND_LIST = [u'抽奖', u'']

SEND_DELAY = 3  # 发送等待
SEND_TIMES = 3  # 发送最大次数
CHECK_IN_POINTS = 10  # 签到奖励的积分
INTEGRAL_PROP = 10  # 积分 = 商品价格*INTEGRAL_PROP*佣金比例(佣金比例最高录入20%）
INTEGRAL_GOOD_PROP = 100  # 积分商品所需积分 = 商品实际价格*INTEGRAL_GOOD_PROP*（1-佣金比例）
INTEGRAL_REWARD_MAX_PROP = 20  #奖励积分的最大比例，大于最大比例，按照最大比例计算
INNER_ROOM_NICK_NAME = u'乐淘家，内部信息群'
ROOM_NICK_NAME = u'\U0001f49d【乐淘家】淘天猫优惠精选\U0001f49d'
MONITOR_ROOM_LIST = [INNER_ROOM_NICK_NAME, ROOM_NICK_NAME]  # 监控的群的nick_name
monitor_room_user_name = []  # 监控的群的user_name
GOODS_PER_TIME = 2  # 找商品时每次发送的商品数量
MASTER_NAME = u'Rickey'  # MASTER，暂时不用
GROUP_USER_NUMBER_INNERID = u'ltj_0'  # 内部编号记录者
SEND_MESSAGE_DELAY = [1.5,1.6,1.7,1.8,1.9,2.0]  # 每次发送消息前的随机延迟
FATHER_REWARD_PROP = 20  # 父会员获得积分奖励的比例%
TARGET_ROOM = ROOM_NICK_NAME  # 非回复性消息的发送位置，也是群成员信息的获取位置，可以设成内部群或真实群
# TARGET_ROOM = INNER_ROOM_NICK_NAME
SEARCH_CLEAN_TIME_INTERVAL = 60*30  # 30分钟，超过时间间隔的搜索记录会被清楚，包括图片
LOG_CLEAN_TIME_INTERVAL = 60*60*24  # 1天，超过时间间隔的LOG会被清楚
CLEAN_THREAD_INTERVAL = 60*10  # 10分钟，CLEAN Thread 每隔一段唤醒一次
GIT_UPLOAD_INTERVAL = 60*60*2  # 2小时，GIT同步的频率
LOTTERY_TIME = '20:30 21:00'  # 抽奖开始时间,结束时间
LOTTERY_REWARD_POINTS = 100  # 抽奖奖励积分
LOTTERY_MAX_NUM = 5  # 最大参加人数
LOTTERY_POINTS = 10  # 抽奖所需积分

label_ddlr = u"会员名 订单编号 订单价格 佣金比例".split()
label_jfdh = u"会员名 商品编号 商品价格 佣金比例 订单编号".split()
label_jljf = u"会员名 奖励积分".split()



