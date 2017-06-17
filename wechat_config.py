#coding:utf-8
import os, logging, time

os_f = os.popen('uname')
os_system = os_f.read().replace('\n','')
if os_system == 'Linux':
    ORDER_FILE_PATH = u'/root/robot_data/xiaoyezi/integral_record/order_file.txt'
    GIT_DATA_FOLD = u'/root/robot_data/'
    GIT_CODE_FOLD = u'/root/wechat_robot/'
    DATABASE_FOLD = u'/root/robot_data/xiaoyezi/database/'
    ACTIVITY_FOLD = u'/root/robot_data/xiaoyezi/activity/'
    TEMPLATE_FOLD = u'/root/robot_data/xiaoyezi/template/'
    LOG_FOLD = u'/root/robot_data/xiaoyezi/log/'
    MEMBER_RECORD_PATH = u'/root/robot_data/xiaoyezi/member_record/member_record.txt'
    INTEGRAL_GOOD_FOLD = u'/root/robot_data/xiaoyezi/integral_good/'
    INTEGRAL_RECORD_FOLD = u'/root/robot_data/xiaoyezi/integral_record/'
else:
    # if raw_input('Already sync data?(1:yes, other:no)') == '1':
    #     where_am_i = raw_input(u'master, where are you?(1:home,2:workplace)')
    #     if where_am_i == '2':
    #         ORDER_FILE_PATH = u'E:\\Documents\\robot_data\\xiaoyezi\\integral_record\\order_file.txt'
    #         GIT_DATA_FOLD = u'E:\\Documents\\robot_data\\'
    #         GIT_CODE_FOLD = u'E:\\Documents\\wechat_robot\\'
    #         DATABASE_FOLD = u'E:\\Documents\\robot_data\\xiaoyezi\\database\\'
    #         ACTIVITY_FOLD = u'E:\\Documents\\robot_data\\xiaoyezi\\activity\\'
    #         TEMPLATE_FOLD = u'E:\\Documents\\robot_data\\xiaoyezi\\template\\'
    #         LOG_FOLD = u'E:\\Documents\\robot_data\\xiaoyezi\\log\\'
    #         MEMBER_RECORD_PATH = u'E:\\Documents\\robot_data\\xiaoyezi\\member_record\\member_record.txt'
    #         INTEGRAL_GOOD_FOLD = u'E:\\Documents\\robot_data\\xiaoyezi\\integral_good\\'
    #         INTEGRAL_RECORD_FOLD = u'E:\\Documents\\robot_data\\xiaoyezi\\integral_record\\'
    #     elif where_am_i == '1':
    ORDER_FILE_PATH = u'F:\\robot_data\\xiaoyezi\\integral_record\\order_file.txt'
    GIT_DATA_FOLD = u'F:\\robot_data\\'
    GIT_CODE_FOLD = u'E:\\PycharmProjects\\wechat_robot\\'
    DATABASE_FOLD = u'F:\\robot_data\\xiaoyezi\\database\\'
    ACTIVITY_FOLD = u'F:\\robot_data\\xiaoyezi\\activity\\'
    TEMPLATE_FOLD = u'F:\\robot_data\\xiaoyezi\\template\\'
    LOG_FOLD = u'F:\\robot_data\\xiaoyezi\\log\\'
    MEMBER_RECORD_PATH = u'F:\\robot_data\\xiaoyezi\\member_record\\member_record.txt'
    INTEGRAL_GOOD_FOLD = u'F:\\robot_data\\xiaoyezi\\integral_good\\'
    INTEGRAL_RECORD_FOLD = u'F:\\robot_data\\xiaoyezi\\integral_record\\'
    #     else:
    #         print 'place wrong'
    #         os._exit(0)
    # else:
    #     os._exit(0)

COMMAND_LIST = [u'看活动', u'查积分', u'签到', u'帮助', u'积分玩法', u'积分商品', u'兑换流程']
SEND_DELAY = 3  # 发送等待
SEND_TIMES = 3  # 发送最大次数
CHECK_IN_POINTS = 10  # 签到奖励的积分
INTEGRAL_PROP = 10  # 积分 = 商品价格*INTEGRAL_PROP*佣金比例(佣金比例最高录入20%）
INTEGRAL_GOOD_PROP = 100  # 积分商品所需积分 = 商品实际价格*INTEGRAL_GOOD_PROP*（1-佣金比例）
INNER_ROOM_NICK_NAME = u'乐淘家，内部信息群'
ROOM_NICK_NAME = u'\U0001f49d【乐淘家】淘天猫内部优惠精选\U0001f49d'

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