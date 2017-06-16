#coding:utf-8
import itchat,time,shelve,re,os,codecs,threading,inspect,ctypes,wx
import wx.grid
import logging
from copy import deepcopy
from PIL import Image, ImageDraw, ImageFont
from lianmeng import *
from multiprocessing import Process, Queue

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

################ wechat 界面相关 #################

COMMAND_LIST = [u'看活动', u'查积分', u'签到', u'帮助', u'积分玩法', u'积分商品', u'兑换流程']
SEND_DELAY = 3  # 发送等待，秒
SEND_TIMES = 3  # 发送最大次数
CHECK_IN_POINTS = 10  # 签到奖励的积分
INTEGRAL_PROP = 10 # 积分 = 商品价格*INTEGRAL_PROP*佣金比例(佣金比例最高录入20%）
INTEGRAL_GOOD_PROP = 100 # 积分商品所需积分 = 商品实际价格*INTEGRAL_GOOD_PROP*（1-佣金比例）
database_mutex = threading.Lock() # 数据库的同步锁
member_record_mutex = threading.Lock() # 邀请记录的同步锁
integral_record_mutex = threading.Lock() # 积分记录的同步锁
send_picture_mutex = threading.Lock() # 发图片的同步锁，防止一起发太多图片被微信查封

INNER_ROOM_NICK_NAME = u'\u4e50\u6dd8\u5bb6\uff0c\u5185\u90e8\u4fe1\u606f\u7fa4'
ROOM_NICK_NAME = u'\U0001f49d\u3010\u4e50\u6dd8\u5bb6\u3011\u6dd8\u5929\u732b\u5185\u90e8\u4f18\u60e0\u7cbe\u9009\U0001f49d'

os_f = os.popen('uname')
os_system = os_f.read().replace('\n','')
print os_system
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
    if raw_input('Already sync data?(1:yes, other:no)') == '1':
        where_am_i = raw_input(u'master, where are you?(1:home,2:workplace)')
        if where_am_i == '2':
            ORDER_FILE_PATH = u'E:\\Documents\\robot_data\\xiaoyezi\\integral_record\\order_file.txt'
            GIT_DATA_FOLD =  u'E:\\Documents\\robot_data\\'
            GIT_CODE_FOLD =  u'E:\\Documents\\wechat_robot\\'
            DATABASE_FOLD = u'E:\\Documents\\robot_data\\xiaoyezi\\database\\'
            ACTIVITY_FOLD = u'E:\\Documents\\robot_data\\xiaoyezi\\activity\\'
            TEMPLATE_FOLD = u'E:\\Documents\\robot_data\\xiaoyezi\\template\\'
            LOG_FOLD = u'E:\\Documents\\robot_data\\xiaoyezi\\log\\'
            MEMBER_RECORD_PATH = u'E:\\Documents\\robot_data\\xiaoyezi\\member_record\\member_record.txt'
            INTEGRAL_GOOD_FOLD = u'E:\\Documents\\robot_data\\xiaoyezi\\integral_good\\'
            INTEGRAL_RECORD_FOLD = u'E:\\Documents\\robot_data\\xiaoyezi\\integral_record\\'
        elif where_am_i == '1':
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
        else:
            print 'place wrong'
            os._exit(0)
    else:
        os._exit(0)

def log_init():
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

def _async_raise(tid, exctype):
    """raises the exception, performs cleanup if needed"""
    logging.debug(u'==== 开始')
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")
    logging.debug(u'==== 结束')

def stop_thread(thread):
    _async_raise(thread.ident, SystemExit)

def SendMessage(msg, user):
    '''另起线程发送消息，默认等待3秒，如果还未结束，就强制结束，并重发，一共重发3次
    三次重发内成功，返回0，失败返回-1'''
    logging.debug(u'==== 开始')
    try:
        cnt1 = 0
        while True:
            cnt = 0
            cnt1 += 1
            logging.debug('==== cnt1 is ' + repr(cnt1))
            p = threading.Thread(target=itchat.send, args=(msg, user))
            p.name = 'SendMessage ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
            logging.debug('==== thread name is ' + p.name + ' user name is ' + str(user))
            p.setDaemon(True)
            p.start()
            while p.is_alive():
                if cnt >= SEND_DELAY*5 + 1:
                    stop_thread(p)
                    break
                cnt += 1
                time.sleep(0.2)
            if cnt < SEND_DELAY*5:
                logging.debug(u'==== 消息发送成功，循环次数：' + repr(cnt1) + u'  等待时间：' + repr(cnt*0.2))
                return
            if cnt1 >= SEND_TIMES:
                return
    finally:
        logging.debug(u'==== 结束')

class PictureException(Exception):
    def __init__(self, err='图片拼接错误'):
        Exception.__init__(self, err)

def StitchPictures(images, out_path, mode='V', quality=100):
    items = images.items()
    num = len(items)
    image_files = []
    for i in range(num):
        image_ori = Image.open(items[i][0])
        fnt = ImageFont.truetype('STXINWEI.TTF', 70)
        d = ImageDraw.Draw(image_ori)
        d.text((20, 50), items[i][1], font=fnt, fill=(0, 0, 0, 0))
        image_files.append(image_ori)
    per_image_size = image_files[0].size
    if mode == 'H':
        out_image_size = (per_image_size[0] * num, per_image_size[1])
    elif mode == 'V':
        out_image_size = (per_image_size[0], per_image_size[1] * num)
    else:
        raise PictureException
    target = Image.new('RGB', out_image_size)
    left = 0
    upper = 0
    right = per_image_size[0]
    lower = per_image_size[1]
    for i in range(num):
        target.paste(image_files[i], (left, upper, right, lower))
        if mode == 'H':
            left += per_image_size[0]
            right += per_image_size[0]
        else:
            upper += per_image_size[1]
            lower += per_image_size[1]
    target.save(out_path, quality=quality)

class Database:
    data_path = DATABASE_FOLD + 'points_database.dat'
    user_data = {}

    def __init__(self):
        self.user_data['grade'] = 0
        self.user_data['group'] = 'user'
        self.user_data['points'] = 0
        self.user_data['last_check_in'] = 0
        self.user_data['nick_name'] = ''
        self.user_data['father'] = ''

    def DatabaseGetLabels(self):
        database_mutex.acquire()
        logging.debug(u'==== 开始')
        try:
            database = shelve.open(self.data_path)
            row_labels = database.keys()
            row_labels.sort(key=lambda a: int(a[4:]))
            col_labels = database['ltj_0'].keys()
            labels = ((row_labels),(col_labels))
            database.close()
            return labels
        finally:
            database_mutex.release()
            logging.debug(u'==== 结束')

    def DatabaseGetAllData(self):
        database_mutex.acquire()
        logging.debug(u'==== 开始')
        try:
            data = {}
            database = shelve.open(self.data_path)
            data.update(database)
            database.close()
            return data
        finally:
            database_mutex.release()
            logging.debug(u'==== 结束')

    def DatabaseChangePoints(self, remark_name, points):
        '''
        更改会员积分
        :param remark_name:
        :param points:
        :return:
        '''
        database_mutex.acquire()
        logging.debug(u'==== 开始')
        logging.debug('==== remark_name ' + remark_name)
        try:
            database = shelve.open(self.data_path)
            if remark_name in database:
                # 更改当前会员积分
                tmp = database[remark_name]
                tmp['points'] += points
                if tmp['points'] < 0:
                    tmp['points'] = 0
                database[remark_name] = tmp
                # 更改父会员的积分
                if points > 0:
                    father = self.__DatabaseFindFather(database, remark_name)
                    if father:
                        tmp = database[father]
                        father_points = int(round(points/5.0))
                        tmp['points'] += father_points
                        database[father] = tmp
                        cur_points = self.__DatabaseViewPoints(database, father)
                        IntegralRecord().IntegralRecordAddRecord(father, u'好友奖励积分',  'None', 'None', str(father_points), str(cur_points))
                        # 将积分变更通知给父会员
                        SendMessage('@msg@%s' % (u'亲，您邀请的朋友 ' + itchat.search_friends(remarkName=remark_name)[0]['NickName'] +
                                                 u' 给您带来了 ' + repr(int(round(points/5.0))) + u' 积分的奖励， 当前积分为：' + str(cur_points)),
                                    (itchat.search_friends(remarkName=father)[0]['UserName']))
                        # SendMessageToRoom(ROOM_NICK_NAME,
                        #                   u'@' + itchat.search_friends(remarkName=father)[0]['NickName'] +
                        #                   u' 您邀请的好友积分提升，恭喜您同时获得【' + repr(father_points) + u'】积分的奖励')
                        logging.debug('==== father: ' + repr(database[father]))
                logging.debug('==== self:' + repr(database[remark_name]))
                database.close()
                return 0
            else:
                logging.error(u'==== 没找到用户')
                SendMessage('@msg@%s' % (u'报告主人：Database没有找到用户, remark_name: ' + remark_name),
                            (itchat.search_friends(remarkName=u'ltj_1')[0]['UserName']))
                database.close()
                return -1
        finally:
            database_mutex.release()
            logging.debug(u'==== 结束')

    def DatabaseCheckin(self, remark_name):
        '''
        @param：remark_name: 会员名
        @return： 0：签到成功
                 -1：已经签到过
                 -2：未找到会员，重要错误，通知主人
        '''

        database_mutex.acquire()
        logging.debug(u'==== 开始')
        logging.debug('==== remark_name ' + remark_name)
        try:
            database = shelve.open(self.data_path)
            today = time.strftime('%Y-%m-%d', time.localtime(time.time()))
            logging.debug('==== today ' + today)
            if remark_name in database:
                # 更改当前会员积分
                tmp = database[remark_name]
                if tmp['last_check_in'] == today:
                    logging.debug(u'==== 今天已经签到')
                    database.close()
                    return -1
                tmp['points'] += CHECK_IN_POINTS
                if tmp['points'] < 0:
                    tmp['points'] = 0
                tmp['last_check_in'] = today
                database[remark_name] = tmp
                cur_points = self.__DatabaseViewPoints(database, remark_name)
                IntegralRecord().IntegralRecordAddRecord(remark_name, u'签到', 'None', 'None', str(CHECK_IN_POINTS), str(cur_points))
                # 更改父会员积分
                father = self.__DatabaseFindFather(database, remark_name)
                if father:
                    tmp = database[father]
                    father_points = int(round(CHECK_IN_POINTS / 5.0))
                    tmp['points'] += father_points
                    database[father] = tmp
                    cur_points = self.__DatabaseViewPoints(database, father)
                    IntegralRecord().IntegralRecordAddRecord(father, u'好友奖励积分', 'None', 'None', str(father_points), str(cur_points))
                    # 通知父会员
                    SendMessage('@msg@%s' % (u'亲，您邀请的朋友 ' + itchat.search_friends(remarkName=remark_name)[0]['NickName'] +
                                             u' 给您带来了 ' + repr(int(round(CHECK_IN_POINTS / 5.0))) + u' 积分的奖励，当前积分为：' + str(cur_points)),
                                (itchat.search_friends(remarkName=father)[0]['UserName']))
                    # SendMessageToRoom(ROOM_NICK_NAME,
                    #                   u'@' + itchat.search_friends(remarkName=father)[0]['NickName'] +
                    #                   u' 您邀请的好友积分提升，恭喜您同时获得【' + repr(father_points) + u'】积分的奖励')
                    logging.debug('==== father: ' + repr(database[father]))
                logging.debug(u'==== 签到成功')
                logging.debug('==== self: ' + repr(database[remark_name]))
                database.close()
                return 0
            else:
                logging.error(u'==== 没找到用户')
                SendMessage('@msg@%s' % (u'报告主人：Database没有找到用户, remark_name: ' + remark_name),
                            (itchat.search_friends(remarkName=u'ltj_1')[0]['UserName']))
                database.close()
                return -2
        finally:
            database_mutex.release()
            logging.debug(u'==== 结束')

    def DatabaseViewPoints(self, remark_name, nick_name):
        '''
        查看会员积分
        :param remark_name:
        :param nick_name:
        :return:
        '''
        database_mutex.acquire()
        logging.debug(u'==== 开始')
        try:
            database = shelve.open(self.data_path)
            points = 0
            if remark_name in database:
                points = database[remark_name]['points']
            else:
                logging.error(u'==== 没找到用户')
                SendMessage('@msg@%s' % (u'报告主人：Database没有找到用户, remark_name: ' + remark_name),
                            (itchat.search_friends(remarkName=u'ltj_1')[0]['UserName']))
            database.close()
            return points
        finally:
            database_mutex.release()
            logging.debug(u'==== 结束')

    def __DatabaseViewPoints(self, database, remark_name):
        '''
        不带锁，只能在打开数据库的情况下使用
        :param database:
        :param remark_name:
        :return:
        '''
        logging.debug(u'==== 开始')
        try:
            points = 0
            if remark_name in database:
                points = database[remark_name]['points']
            else:
                logging.error(u'==== 没找到用户')
                SendMessage('@msg@%s' % (u'报告主人：Database没有找到用户, remark_name: ' + remark_name),
                            (itchat.search_friends(remarkName=u'ltj_1')[0]['UserName']))
            return points
        finally:
            logging.debug(u'==== 结束')

    def DatabaseUserNextNumber(self):
        '''
        返回下一个会员编号
        :return:
        '''
        database_mutex.acquire()
        logging.debug(u'==== 开始')
        try:
            database = shelve.open(self.data_path)
            next_num = database['ltj_0']['points']
            database.close()
            return next_num
        finally:
            database_mutex.release()
            logging.debug(u'==== 结束')

    def DatabaseAddUser(self, remark_name, nick_name, father=''):
        '''
        增加新用户，会增加会员编号，并出发father绑定
        :param remark_name:
        :param nick_name:
        :param father:
        :return:
        '''
        database_mutex.acquire()
        logging.debug(u'==== 开始')
        try:
            self.user_data['nick_name'] = nick_name
            self.user_data['father'] = father
            database = shelve.open(self.data_path)
            database[remark_name] = self.user_data
            tmp = database['ltj_0']
            tmp['points'] += 1
            database['ltj_0'] = tmp
            if father != '':
                child_nick_name = itchat.search_friends(remarkName=remark_name)[0]['NickName']
                SendMessage('@msg@%s' % (u'亲，好友【' + child_nick_name + u'】与您绑定成功，每当好友获得积分，您也会得到奖励积分哦'),
                        (itchat.search_friends(remarkName=father)[0]['UserName']))
            logging.debug('==== mark ' + remark_name + 'next_number' + str(database['ltj_0']['points']))
            logging.debug('==== ' + repr(database[remark_name]))
            database.close()
        finally:
            database_mutex.release()
            logging.debug(u'==== 结束')

    # 删除用户
    def DatabaseDelUser(self, remark_name):
        database_mutex.acquire()
        logging.debug(u'==== 开始')
        try:
            database = shelve.open(self.data_path)
            if remark_name in database:
                del database[remark_name]
                logging.debug('==== delete user, mark ' + remark_name)
                database.close()
                return 0
            else:
                logging.error(u'==== 没找到用户')
                SendMessage('@msg@%s' % (u'报告主人：Database没有找到用户, remark_name: ' + remark_name),
                            (itchat.search_friends(remarkName=u'ltj_1')[0]['UserName']))
                database.close()
                return -1
        finally:
            database_mutex.release()
            logging.debug(u'==== 结束')

    # TODO
    def DatabaseCheckNickName(self, remark_name, nick_name):
        """
        用来检查会员的昵称是否有变化，以后用来追溯问题用
        @param: remark_name 会员名
        @param: nick_name 当前昵称
        @return: 0 昵称没有变化
                 -1 昵称有变化，已经增加到数据库内
        """
        pass

    def DatabaseFindFather(self, remark_name):
        ''' 
        检测当前会员，是否有父会员
        @param: remark_name 当前会员名
        @return: 父会员名，可能是None
        '''
        database_mutex.acquire()
        logging.debug(u'==== 开始')
        try:
            father = ''
            database = shelve.open(self.data_path)
            if remark_name in database:
                if 'father' in database[remark_name]:
                    father = database[remark_name]['father']
            else:
                logging.error(u'==== 没找到用户')
                SendMessage('@msg@%s' % (u'报告主人：Database没有找到用户, remark_name: ' + remark_name),
                            (itchat.search_friends(remarkName=u'ltj_1')[0]['UserName']))
            database.close()
            return father
        finally:
            database_mutex.release()
            logging.debug(u'==== 结束')

    def __DatabaseFindFather(self, database, remark_name):
        ''' 
        检测当前会员，是否有父会员
        @param: remark_name 当前会员名
        @return: 父会员名，可能是None
        '''
        logging.debug(u'==== 开始')
        father = ''
        if 'father' in database[remark_name]:
            father = database[remark_name]['father']
        logging.debug(u'==== 结束')
        return father

    def DatabaseViewData(self, remark_name):
        ''' 
        查看会员的所有数据
        @param: ramark_name 会员名
        @return: 会员数据(dict)
        '''
        database_mutex.acquire()
        logging.debug(u'==== 开始')
        user_data = {}
        try:
            database = shelve.open(self.data_path)
            if remark_name in database:
                user_data = deepcopy(database[remark_name])
            else:
                logging.error(u'==== 没找到用户')
                SendMessage('@msg@%s' % (u'报告主人：Database没有找到用户, remark_name: ' + remark_name),
                            (itchat.search_friends(remarkName=u'ltj_1')[0]['UserName']))
            database.close()
            return user_data
        finally:
            database_mutex.release()
            logging.debug(u'==== 结束')

    def DatabaseWriteData(self, remark_name, user_data):
        ''' 
        查看会员的所有数据
        @param: ramark_name 会员名
        @param: user_data 会员数据
        @return: 会员数据(dict)
        '''
        database_mutex.acquire()
        logging.debug(u'==== 开始')
        try:
            need_notify = False
            database = shelve.open(self.data_path)
            if remark_name not in database:
                if user_data['father']:
                    need_notify = True
            else:
                tmp = database[remark_name]
                if tmp['father'] != user_data['father'] and user_data['father']:
                    need_notify = True
            database[remark_name] = deepcopy(user_data)
            if need_notify:
                friend_info = itchat.search_friends(remarkName=remark_name)
                if friend_info:
                    child_nick_name = itchat.search_friends(remarkName=remark_name)[0]['NickName']
                    father_name = database[remark_name]['father']
                    SendMessage('@msg@%s' % (u'亲，好友【' + child_nick_name + u'】与您绑定成功，每当好友获得积分，您也会得到奖励积分哦'),
                            (itchat.search_friends(remarkName=father_name)[0]['UserName']))
                else:
                    logging.info(u'==== 用户不存在于好友列表')
                    SendMessage('@msg@%s' % (u'报告主人：用户不存在于好友列表, remark_name: ' + remark_name),
                                (itchat.search_friends(remarkName=u'ltj_1')[0]['UserName']))
            database.close()
            return
        finally:
            database_mutex.release()
            logging.debug(u'==== 结束')

    # 数据库格式更新用
    def DatabaseUpdateDatabase(self):
        database_mutex.acquire()
        logging.debug(u'==== 开始更新数据库')
        database = shelve.open(self.data_path)
        for user in database:
            if not 'father' in database[user]:
                tmp = database[user]
                tmp['father'] = ''
                database[user] = tmp
            elif database[user]['father'] == None:
                tmp = database[user]
                tmp['father'] = ''
                database[user] = tmp
            if 'nick_names' in database[user]:
                tmp = database[user]
                tmp['nick_name'] = tmp['nick_names']
                del tmp['nick_names']
                database[user] = tmp
            print database[user]
        database.close()
        database_mutex.release()
        logging.debug(u'==== 更新数据库结束')

class Template:
    def TemplateSendCommand(self, to):
        logging.debug(u'==== 开始')
        lines = ''
        for line in codecs.open(TEMPLATE_FOLD + u"命令模板.txt", 'rb', 'utf-8'):
            lines += line
        lines = lines.strip()
        logging.debug(lines)
        SendMessage('@msg@%s' % lines, to)
        logging.debug(u'==== 结束')

    def TemplateSendIntegralregular(self, to):
        logging.debug(u'==== 开始')
        lines = ''
        for line in codecs.open(TEMPLATE_FOLD + u"积分玩法.txt", 'rb', 'utf-8'):
            lines += line
        lines = lines.strip()
        logging.debug(lines)
        SendMessage('@msg@%s' % lines, to)
        logging.debug(u'==== 结束')

    def TemplateSendActivity(self, to):
        logging.debug(u'==== 开始')
        files = os.listdir(ACTIVITY_FOLD)
        today = time.strftime('%Y-%m-%d', time.localtime(time.time()))
        has_activity = 0
        for file in files:
            if (re.match(u'活动_.*_.*\.txt$', file)):
                begin_date = file.split('_')[1]
                end_date = file.split('_')[2]
                if begin_date <= today and today <= end_date:
                    logging.debug('==== match file name is ' + file)
                    has_activity = 1
                    for line in codecs.open(ACTIVITY_FOLD + file, 'rb', 'utf-8'):
                        time.sleep(1)
                        line = line.strip()
                        if not re.match(u'&图片&', line):
                            logging.debug('==== send text: ' + line)
                            SendMessage('@msg@%s' % line, to)
                        else:
                            str_tmp = ACTIVITY_FOLD + line.split('&')[2]
                            logging.debug('==== send picture: ' + str_tmp)
                            SendMessage('@img@%s' % str_tmp, to)
        if not has_activity:
            SendMessage('@msg@%s' % u"亲，当前没有进行中的活动", to)
        logging.debug(u'==== 结束')

    def __TemplateSendPicAndText(self, pic_path, text_path, to):
        logging.debug('==== send stitch picture')
        SendMessage('@img@%s' % pic_path, to)
        for line in codecs.open(text_path, 'r', 'utf-8'):
            line = line.strip()
            logging.debug('==== send text: ' + line)
            time.sleep(1)
            SendMessage('@msg@%s' % line, to)

    def TemplateSendIntegralGood(self, to):
        send_picture_mutex.acquire()
        logging.debug(u'==== 开始')
        try:
            today = time.strftime('%Y%m%d', time.localtime(time.time()))
            pic_path = INTEGRAL_GOOD_FOLD + today + '_stitch.jpg'
            text_path = INTEGRAL_GOOD_FOLD + today + '_stitch.txt'
            if os.path.exists(pic_path) and os.path.exists(text_path):
                self.__TemplateSendPicAndText(pic_path, text_path, to)
                return
            else:
                files = os.listdir(INTEGRAL_GOOD_FOLD)
                picture_names = []
                for name in files:
                    if re.match('^.*@.*\.jpg', name):
                        if name.split('@')[1] >= today:
                            picture_names.append(name)
                nums = len(picture_names)
                if nums == 0:
                    SendMessage('@msg@%s' % u"亲，当前没有可积分兑换商品", to)
                    return
                f = codecs.open(text_path, 'w', 'utf-8')
                f.write(u'亲，今天可兑换积分商品有【' + str(nums) + u'】种，长图在上面哦，口令如下：\r\n')
                pictures_path = {}
                for pic_name in picture_names:
                    pic_head = pic_name[:-4]
                    pic_name_list = pic_head.split('@')
                    integral = int(round(float(pic_name_list[2])*(1-(float(pic_name_list[3])-5)/100)*INTEGRAL_GOOD_PROP))
                    taokouling = pic_name_list[4]
                    bianhao = pic_name_list[0]
                    pictures_path[INTEGRAL_GOOD_FOLD + pic_name] = u'编号:%s, 所需积分:%s' % (bianhao, integral)
                    text = u'【商品编号】' + bianhao + u'【所需积分】'+ repr(integral) + u'【淘口令】' + taokouling + '\r\n'
                    f.write(text)
                f.close()
                StitchPictures(pictures_path, pic_path, quality=20)
                self.__TemplateSendPicAndText(pic_path, text_path, to)
        finally:
            send_picture_mutex.release()
            logging.debug(u'==== 结束')

    def TemplateSendExchangeProcess(self, to):
        send_picture_mutex.acquire()
        logging.debug(u'==== 开始')
        lines = ''
        try:
            for line in codecs.open(TEMPLATE_FOLD + u"积分商品兑换流程.txt", 'rb', 'utf-8'):
                if not re.match(u'&图片&', line):
                    lines += line
                else:
                    if lines:
                        lines = lines.strip()
                        logging.debug('==== send text: ' + lines)
                        SendMessage('@msg@%s' % lines, to)
                        time.sleep(1)
                    line = line.strip()
                    str_tmp = TEMPLATE_FOLD + line.split('&')[2]
                    logging.debug('==== send picture: ' + str_tmp)
                    SendMessage('@img@%s' % str_tmp, to)
                    lines = ''
                    time.sleep(1.5)
            if lines:
                logging.debug('==== send text: ' + lines)
                SendMessage('@msg@%s' % lines, to)
        finally:
            send_picture_mutex.release()
            logging.debug(u'==== 结束')

class IntegralRecord:
    def IntegralRecordAddRecord(self, remark_name, type_message, price, prop, c_points, points):
        logging.debug(u'==== 开始')
        try:
            time_now = time.strftime('%Y-%m-%d_%H%M%S', time.localtime(time.time()))
            with codecs.open(INTEGRAL_RECORD_FOLD + remark_name + '.txt', 'a', 'utf-8') as f:
                f.write('%s %s %s %s %s %s\r\n' % (time_now, type_message, price, prop, c_points, points))
        finally:
            logging.debug(u'==== 结束')

    def IntegralRecordOrderRecord(self, remark_name, order, jp_num=''):
        integral_record_mutex.acquire()
        logging.debug(u'==== 开始')
        try:
            time_now = time.strftime('%Y-%m-%d_%H%M%S', time.localtime(time.time()))
            with codecs.open(ORDER_FILE_PATH, 'a', 'utf-8') as f:
                f.write('%s %s %s %s\r\n' % (time_now, order, remark_name, jp_num))
        finally:
            integral_record_mutex.release()
            logging.debug(u'==== 结束')

    def IntegralRecordCheckOrder(self, order):
        integral_record_mutex.acquire()
        logging.debug(u'==== 开始')
        try:
            for line in codecs.open(ORDER_FILE_PATH, 'r', 'utf-8'):
                if line and line.split(' ')[1] == order:
                    logging.info(u'==== 订单已经被会员 ' + line.split(' ')[2] + u' 录入过')
                    return -1
            return 0
        finally:
            integral_record_mutex.release()
            logging.debug(u'==== 结束')

class MemberRecord:
    def MemberRecordAddRecord(self, record):
        member_record_mutex.acquire()
        logging.debug(u'==== 开始')
        try:
            time_now = time.strftime('%Y-%m-%d_%H%M%S', time.localtime(time.time()))
            with codecs.open(MEMBER_RECORD_PATH, 'a', 'utf-8') as f:
                f.write(time_now + ' ' + record)
        finally:
            member_record_mutex.release()
            logging.debug(u'==== 结束')

    def MemberRecordFindFather(self, nick_name):
        '''
        这个函数在member_record文件中查找记录，来确认是否此用户是被某个会员邀请的
        @param：nick_name 此用户的昵称，这个昵称应该和此用户进去群时的昵称一致，如果用户改过昵称，那么可能找不到father
        @return: ① -1：没有找到father
                 ② -2：找到多个father（昵称同名，或者多次进出群）的情况，且名字不同
                 ③ father: 找到一个father，或者多个father但是名字相同
        '''
        member_record_mutex.acquire()
        logging.debug(u'==== 开始')
        logging.debug('==== ' + nick_name)
        try:
            fathers = []
            for line in codecs.open(MEMBER_RECORD_PATH, 'r', 'utf-8'):
                line_list = line.split('"')
                if line_list[3].encode('utf-8') == nick_name.encode('utf-8') and line_list[1].startswith('ltj_'): # father必须已经是乐淘家会员
                    fathers.append(line_list[1].encode('utf-8'))
            fathers = list(set(fathers))
            nums = len(fathers)
            if nums == 0:
                logging.debug('==== not find father')
                return -1
            elif nums == 1:
                logging.debug('==== father is ' + fathers[0])
                return fathers[0]
            else:
                logging.debug('==== many fathers: ' + ''.join(fathers))
                SendMessage('@msg@%s' % (u'报告主人：找到多个father, nick_name: ' + nick_name + 'fathers: ' + ''.join(fathers)),
                            (itchat.search_friends(remarkName=u'ltj_1')[0]['UserName']))
                return -2
        finally:
            member_record_mutex.release()
            logging.debug(u'==== 结束')

def IsFriend(usr_name):
    ''' 
    判断用户是否是好友
    无法通过itchat.search_friends的返回值是否是None来判断，这里采用判断remark_name的方式
    默认认为加上的好友都设置了remark_name，如果没有设置，那么只能来自群内的人，那么就认为
    不是好友，那么就返回-1
    如果有设置remark_name，那么就检查下设置是否正确，如果不正确，就重新设置并新添加到数据库
    '''
    try:
        logging.debug(u'==== 开始')
        itchat.update_friend(usr_name)
        ret = itchat.search_friends(None, usr_name)
        logging.debug(u'==== search friends return: %s', ret)
        if ret:
            if ret['RemarkName']:
                CheckAndSetRemarkName(usr_name)
                return 0
            else:
                logging.debug("==== is not friend, remark_name is none")
                return -1
        else:
            logging.debug("==== is not friend, search_friends find none")
            return -1
    finally:
        logging.debug(u'==== 结束')

def CheckAndSetRemarkName(user_name):
    '''
    检查私聊好友的remarkname是否设置上了且格式正确
    如果检查失败，那么重新设置下备注名称，并往数据库添加新用户
    '''
    logging.debug(u'==== 开始')
    itchat.update_friend(user_name)
    remark_name = (itchat.search_friends(None, user_name))['RemarkName']
    nick_name = (itchat.search_friends(None, user_name))['NickName']
    logging.debug('==== remark_name_in is %s nick_name is %s', remark_name, nick_name)
    if not re.search('ltj_.*', remark_name):
        remark_name_new = 'ltj_' + str(Database().DatabaseUserNextNumber())
        itchat.set_alias(user_name, remark_name_new)
        itchat.update_friend(user_name)
        logging.debug('==== remark_name_new is ' + (itchat.search_friends(None, user_name))['RemarkName'])
        father_name = MemberRecord().MemberRecordFindFather(nick_name)
        if father_name < 0:
            father_name = ''
        Database().DatabaseAddUser(remark_name_new, nick_name, father_name)
    logging.debug(u'==== 结束')
    return 0

def user_check_in(remark_name, nick_name):
    logging.debug(u'==== 开始')
    remark_name_utf8 = remark_name.encode('utf-8')
    database = Database()
    ret = database.DatabaseCheckin(remark_name_utf8)
    logging.debug(u'==== 结束')
    return ret

def user_view_points(remark_name, nick_name):
    logging.debug(u'==== 开始')
    remark_name_utf8 = remark_name.encode('utf-8')
    nick_name_utf8 = nick_name.encode('utf-8')
    database = Database()
    points = database.DatabaseViewPoints(remark_name_utf8, nick_name_utf8)
    logging.debug(u'==== 结束')
    return points

def text_command_router(msg, to_name):
    logging.debug(u'==== 开始')
    if to_name == 'ActualUserName':
        nick_name = (itchat.search_friends(None, msg['ActualUserName']))['NickName']
        remark_name = (itchat.search_friends(None, msg['ActualUserName']))['RemarkName']
    else:
        remark_name = (itchat.search_friends(None, msg['FromUserName']))['RemarkName']
        nick_name = (itchat.search_friends(None, msg['FromUserName']))['NickName']

    if msg['Text'] == u'看活动':
        if to_name == 'ActualUserName':
            SendMessage('@msg@%s%s' % (u'@' + nick_name, u' 亲，活动信息已经私聊发送'), msg['FromUserName'])
        template = Template()
        template.TemplateSendActivity(msg[to_name])
    elif msg['Text'] == u'查积分':
        if to_name == 'ActualUserName':
            SendMessage('@msg@%s%s' % (u'@' + nick_name, u' 亲，积分已经私聊发送'), msg['FromUserName'])
        SendMessage('@msg@%s%s' % (u'亲，您的当前积分为：', user_view_points(remark_name, nick_name)), msg[to_name])
    elif msg['Text'] == u'签到':
        if to_name == 'ActualUserName':
            SendMessage('@msg@%s%s' % (u'@' + nick_name, u' 亲，签到成功，当前积分已经私聊发送'), msg['FromUserName'])
        if user_check_in(remark_name, nick_name) < 0:
            SendMessage('@msg@%s%s' % (u'亲，您今天已签到过一次，当前积分为：', user_view_points(remark_name, nick_name)), msg[to_name])
        else:
            SendMessage('@msg@%s%s' % (u'亲，签到成功，当前积分为：', user_view_points(remark_name, nick_name)), msg[to_name])
            Template().TemplateSendCommand(msg[to_name])
    elif msg['Text'] == u'帮助':
        if to_name == 'ActualUserName':
            SendMessage('@msg@%s%s' % (u'@' + nick_name, u' 亲，帮助信息已经私聊发送'), msg['FromUserName'])
        template = Template()
        template.TemplateSendCommand(msg[to_name])
    elif msg['Text'] == u'积分玩法':
        if to_name == 'ActualUserName':
            SendMessage('@msg@%s%s' % (u'@' + nick_name, u' 亲，积分玩法已经私聊发送'), msg['FromUserName'])
        template = Template()
        template.TemplateSendIntegralregular(msg[to_name])
    elif msg['Text'] == u'积分商品':
        if to_name == 'ActualUserName':
            SendMessage('@msg@%s%s' % (u'@' + nick_name, u' 亲，积分商品已经私聊发送'), msg['FromUserName'])
        Template().TemplateSendIntegralGood(msg[to_name])
    elif msg['Text'] == u'兑换流程':
        if to_name == 'ActualUserName':
            SendMessage('@msg@%s%s' % (u'@' + nick_name, u' 亲，兑换流程已经私聊发送'), msg['FromUserName'])
        Template().TemplateSendExchangeProcess(msg[to_name])
    logging.debug(u'==== 结束')
    return

def single_text_reply(msg):
    logging.debug(u'==== 开始')
    if msg['FromUserName'] == 'newsapp':
        logging.debug(u'==== 收到腾讯新闻消息，已屏蔽')
        return
    if not itchat.search_friends(None, msg['FromUserName']):
        logging.error(u'==== 好友列表中没有找到此人, user_name:' + msg['FromUserName'] + ' text: ' + msg['Text'])
        return
    logging.debug('==== nick_name is ' + (itchat.search_friends(None, msg['FromUserName']))['NickName'])
    logging.debug(u'==== 聊天内容：' + msg['Text'])
    if (itchat.search_friends(None, msg['FromUserName']))['NickName'] == u'小叶子':
        logging.debug(u'==== 是小叶子自己发送的消息哦')
        logging.debug(u'==== 结束')
        return
    CheckAndSetRemarkName(msg['FromUserName'])
    if msg['Text'] in COMMAND_LIST:
        text_command_router(msg, 'FromUserName')
    elif re.match(u'.*通过.*朋友验证请求.*可以开始聊天了.*', msg['Text']):
        SendMessage('@msg@%s' % (u'亲，祝你每天都有好心情 [害羞]'), msg['FromUserName'])
        Template().TemplateSendCommand(msg['FromUserName'])
        SendMessage('@msg@%s' % (u'重新输入下上面命令哦'), msg['FromUserName'])
    elif (itchat.search_friends(None, msg['FromUserName']))['RemarkName'] == 'ltj_1':
        if msg['Text'] == u'上传数据':
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg['Text']), msg['FromUserName'])
            if UpdateToGit(is_robot=False, is_data=True) == 0:
                SendMessage('@msg@%s' % (msg['Text'] + u' 成功'), msg['FromUserName'])
            else:
                SendMessage('@msg@%s' % (msg['Text'] + u' 失败'), msg['FromUserName'])
        elif msg['Text'] == u'上传代码':
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg['Text']), msg['FromUserName'])
            if UpdateToGit(is_robot=False, is_data=False) == 0:
                SendMessage('@msg@%s' % (msg['Text'] + u' 成功'), msg['FromUserName'])
            else:
                SendMessage('@msg@%s' % (msg['Text'] + u' 失败'), msg['FromUserName'])
        elif msg['Text'] == u'更新':
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg['Text']), msg['FromUserName'])
            database = Database()
            database.DatabaseUpdateDatabase()
            SendMessage('@msg@%s' % (u'更新结束'), msg['FromUserName'])
        elif msg['Text'] == u'测试':
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg['Text']), msg['FromUserName'])
            rooms = itchat.get_chatrooms()
            logging.debug(rooms)
            for i in range(len(rooms)):
                logging.debug(rooms[i]['NickName'])
                if rooms[i]['NickName'] == u'\u4e50\u6dd8\u5bb6\uff0c\u5185\u90e8\u4fe1\u606f\u7fa4':
                    logging.debug(rooms[i]['UserName'])
                    SendMessage('@msg@%s' % u'测试', rooms[i]['UserName'])
            SendMessage('@msg@%s' % u'测试结束', msg['FromUserName'])
        elif re.match(u'更改父亲@.*', msg['Text']):
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg['Text']), msg['FromUserName'])
            msg_list = msg['Text'].split('@')
            remark_name = ('ltj_' + msg_list[1]).encode('utf-8')
            father_name = msg_list[2].encode('utf-8')
            database = shelve.open(DATABASE_FOLD + 'points_database.dat')
            tmp = database[remark_name]
            tmp['father'] = father_name
            database[remark_name] = tmp
            database.close()
            SendMessage('@msg@%s' % (u'更改结束'), msg['FromUserName'])
        elif re.match(u'更改昵称@.*', msg['Text']):
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg['Text']), msg['FromUserName'])
            msg_list = msg['Text'].split('@')
            remark_name = ('ltj_' + msg_list[1]).encode('utf-8')
            nick_name = msg_list[2]
            database = shelve.open(DATABASE_FOLD + 'points_database.dat')
            tmp = database[remark_name]
            tmp['nick_name'] = nick_name
            database[remark_name] = tmp
            database.close()
            SendMessage('@msg@%s' % (u'调整结束'), msg['FromUserName'])
        elif re.match(u'增加用户@.*', msg['Text']):
            '''增加用户@ltj_xxx@昵称[@ltj_xxx（邀请人）]'''
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg['Text']), msg['FromUserName'])
            msg_list = msg['Text'].split('@')
            argc = len(msg_list)
            remark_name = ('ltj_' + msg_list[1]).encode('utf-8')
            nick_name = msg_list[2]
            father_name = ''
            if argc == 3:
                father_name = MemberRecord().MemberRecordFindFather(nick_name)
                if father_name < 0:
                    father_name = ''
                else:
                    father_name = father_name.encode('utf-8')
            elif argc == 4:
                father_name = msg_list[3].encode('utf-8')
            Database().DatabaseAddUser(remark_name, nick_name, father_name)
            SendMessage('@msg@%s' % (u'增加用户完成'), msg['FromUserName'])
        elif re.match(u'删除用户@.*', msg['Text']):
            '''删除用户@ltj_xxx'''
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg['Text']), msg['FromUserName'])
            msg_list = msg['Text'].split('@')
            remark_name = ('ltj_' + msg_list[1]).encode('utf-8')
            Database().DatabaseDelUser(remark_name)
            SendMessage('@msg@%s' % (u'删除用户完成'), msg['FromUserName'])
        elif msg['Text'] == u'查看线程':
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg['Text']), msg['FromUserName'])
            logging.debug(str(threading.enumerate()))
            SendMessage('@msg@%s' % (str(threading.enumerate())), msg['FromUserName'])
        elif msg['Text'] == u'查看邀请':
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg['Text']), msg['FromUserName'])
            lines = u''
            for line in codecs.open(MEMBER_RECORD_PATH, 'rb', 'utf-8'):
                lines = lines + line
            lines = lines.strip()
            SendMessage('@msg@%s' % lines, msg['FromUserName'])
        elif re.match(u'查看数据@.*', msg['Text']):
            msg_list = msg['Text'].split('@')
            remark_name = 'ltj_' + msg_list[1]
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg_list[0] + u' 会员是：' + remark_name), msg['FromUserName'])
            data_user = Database().DatabaseViewData(remark_name.encode('utf-8'))
            if data_user:
                SendMessage('@msg@%s' % repr(data_user), msg['FromUserName'])
        elif msg['Text'] == u'查看用户数':
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg['Text']), msg['FromUserName'])
            next_number = Database().DatabaseUserNextNumber()
            SendMessage('@msg@%s' % (u'下一个用户编号是：' + repr(next_number)), msg['FromUserName'])
        elif msg['Text'] == u'打开界面':
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg['Text']), msg['FromUserName'])
            ui_thread = threading.Thread(target=UiMainThread)
            ui_thread.setDaemon(True)
            ui_thread.start()
            ui_thread.name = 'UI thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
            logging.debug('==== thread name is ' + ui_thread.name)
            SendMessage('@msg@%s' % u'UI界面开启结束', msg['FromUserName'])
        elif re.match(u'找.*',msg['Text']):
            keyword = msg['Text'][1:]
            SendMessage('@msg@%s' % (u'主人您好，当前命令是：' + msg['Text']), msg['FromUserName'])
            send_to_browser_worker(keyword.encode('utf-8'))
            SendMessage('@msg@%s' % (u'找商品结束'), msg['FromUserName'])

    logging.debug(u'==== 结束')
    return

def group_text_reply(msg):
    logging.debug(u'==== 开始')
    if msg['Text'] in COMMAND_LIST:
        logging.debug(u'==== 聊天内容： ' + msg['Text'])
        if itchat.search_friends(None, msg['ActualUserName']):
            if (itchat.search_friends(None, msg['ActualUserName']))['NickName'] == u'小叶子':
                logging.debug(u'==== 是小叶子自己发送的消息哦')
                logging.debug(u'==== 结束')
                return
        if IsFriend(msg['ActualUserName']) == -1:
            logging.debug('==== ' + msg['ActualNickName'] + u' 不是好友，备注名称检查失败')
            SendMessage('@msg@%s%s' % (u'@' + msg['ActualNickName'], u' 亲还不是我的好友，无法将信息私聊发送给您，我会加您好友哦'), msg['FromUserName'])
            itchat.add_friend(msg['ActualUserName'], 2, u'我是小叶子 ^o^', autoUpdate=False)
            SendMessage('@msg@%s%s' % (u'@' + msg['ActualNickName'], u' 已经加您，通过好友邀请后，重新输入命令即可'), msg['FromUserName'])
            logging.debug(u'==== 结束')
            return
        else:
            logging.debug('==== nick_name is ' + (itchat.search_friends(None, msg['ActualUserName']))['NickName'])
            text_command_router(msg, 'ActualUserName')
    logging.debug(u'==== 结束')
    return

def huanying(msg):
    logging.debug(u'==== 开始')
    str_list = msg['Content'].split('"')
    if len(str_list) < 4:  # 去除红包消息
        return
    if str_list[4].find(u'加入了群聊') == -1 and str_list[4].find(u'分享的二维码加入群聊') == -1:
        return
    logging.debug('==== ' + msg['Content'] + ' ' + msg['User']['NickName'])
    logging.debug(msg)
    SendMessage('@msg@%s' % (u'欢迎亲加入【乐淘家】'), msg['FromUserName'])

    record_t = msg['Content'] + ' ' + msg['User']['NickName'] + '\r\n'
    MemberRecord().MemberRecordAddRecord(record_t)

    time.sleep(1)
    template = Template()
    template.TemplateSendCommand(msg['FromUserName'])
    logging.debug(u'==== 结束')
    return

def be_add_friend(msg):
    logging.debug(u'==== 开始')
    itchat.add_friend(**msg['Text'])
    CheckAndSetRemarkName(msg['RecommendInfo']['UserName'])
    SendMessage('@msg@%s' % u'欢迎回到【乐淘家】，祝您每天都有好心情 [害羞]', msg['RecommendInfo']['UserName'])
    # 发送群邀请
    itchat.add_member_into_chatroom(GetRoomNameByNickName(ROOM_NICK_NAME), [{'UserName':msg['RecommendInfo']['UserName']}], True)
    Template().TemplateSendCommand(msg['RecommendInfo']['UserName'])
    logging.debug(u'==== 结束')
    return

def GetRoomNameByNickName(nick_name):
    logging.debug(u'==== 开始')
    rooms = itchat.get_chatrooms()
    room_name = ''
    for i in range(len(rooms)):
        logging.debug(rooms[i]['NickName'])
        if rooms[i]['NickName'] == nick_name:
            logging.debug('find room')
            room_name = rooms[i]['UserName']
            break
    logging.debug(u'==== 结束')
    return room_name

def SendMessageToRoom(nick_name, msg):
    logging.debug(u'==== 开始')
    room_name = GetRoomNameByNickName(nick_name)
    if room_name == '':
        logging.error(u'==== 没找到群')
        SendMessage('@msg@%s' % (u'报告主人：没有找到群, nick_name: ' + nick_name),
                    (itchat.search_friends(remarkName=u'ltj_1')[0]['UserName']))
        return
    else:
        SendMessage('@msg@%s' % msg, room_name)
    logging.debug(u'==== 结束')
    return

@itchat.msg_register(itchat.content.FRIENDS)
def ItchatMessageFriend(msg):
    p = threading.Thread(target=be_add_friend, args=(msg,))
    p.name = 'ItchatMessageFriend ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
    p.setDaemon(True)
    p.start()
    logging.debug('==== thread name is ' + p.name + ' nick name is ' + msg['RecommendInfo']['NickName'])
    return

@itchat.msg_register(itchat.content.NOTE, isGroupChat=True)
def ItchatMessageNoteGroup(msg):
    p = threading.Thread(target=huanying, args=(msg,))
    p.name = 'ItchatMessageNoteGroup ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
    p.setDaemon(True)
    p.start()
    logging.debug('==== thread name is ' + p.name + ' nick name is ' + msg['ActualNickName'])
    return

@itchat.msg_register(itchat.content.TEXT, isGroupChat=True)
def ItchatMessageTextGroup(msg):
    p = threading.Thread(target=group_text_reply, args=(msg,))
    p.name = 'ItchatMessageTextGroup ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
    p.setDaemon(True)
    p.start()
    logging.debug('==== thread name is ' + p.name + ' nick name is ' + msg['ActualNickName'])
    return

@itchat.msg_register(itchat.content.TEXT)
def ItchatMessageTextSingle(msg):
    p = threading.Thread(target=single_text_reply, args=(msg,))
    p.name = 'ItchatMessageTextSingle ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
    p.setDaemon(True)
    p.start()
    if 'NickName' in msg['User']:
        logging.debug('==== thread name is ' + p.name + ' nick name is ' + msg['User']['NickName'])
    else:
        logging.debug('==== thread name is ' + p.name + ' no nick name')
    return

################ UI界面相关 #################

label_ddlr = u"会员名 订单编号 订单价格 佣金比例".split()
label_jfdh = u"会员名 商品编号 商品价格 订单编号".split()
label_jljf = u"会员名 奖励积分".split()

database_data = Database().DatabaseGetAllData()
labels = Database().DatabaseGetLabels()
col_labels = labels[1]
row_labels = labels[0]

class TextWindow(wx.TextCtrl):
    def __init__(self, parent, id=-1, value="", pos=wx.DefaultPosition, size=(300, 25)):
        wx.TextCtrl.__init__(self, parent, id, value, pos, size)
        self.SetMinSize(size)

class StaticWindow(wx.StaticText):
    def __init__(self, parent, id=-1, label="", pos=wx.DefaultPosition, size=(100, 25)):
        wx.StaticText.__init__(self, parent, id, label, pos, size)
        self.SetMinSize(size)

class MyTable(wx.grid.PyGridTableBase):
    def __init__(self):
        wx.grid.PyGridTableBase.__init__(self)

    def GetNumberRows(self):
        return len(row_labels)

    def GetNumberCols(self):
        return len(col_labels)

    def GetColLabelValue(self, col):
        return col_labels[col]

    def GetRowLabelValue(self, row):
        return row_labels[row]

    def IsEmptyCell(self,row,col):
        return False

    def GetValue(self,row,col):
        value = database_data[row_labels[row]][col_labels[col]]
        return value

    def SetValue(self,row,col,value):
        pass

    def GetAttr(self,row,col,kind):
        pass

    def UpdateMyData(self):
        global database_data
        global labels, col_labels, row_labels
        database_data = Database().DatabaseGetAllData()
        labels = Database().DatabaseGetLabels()
        col_labels = labels[1]
        row_labels = labels[0]

class MyFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, -1, u"【乐淘家】积分系统")
        self.Centre()
        self.ddlr_objs = {}
        self.jfdh_objs = {}
        self.user_objs = {}
        self.user_search_obj = {}
        self.jljf_objs = {}

        panel = wx.Panel(self)
        mbox = wx.BoxSizer(wx.HORIZONTAL)
        self.panel_l = wx.Panel(panel)
        self.panel_r = wx.Panel(panel)
        self.panel_l.SetBackgroundColour('Green')
        self.panel_r.SetBackgroundColour('Blue')
        mbox.Add(self.panel_l, 0, flag=wx.ALL, border=10)
        mbox.Add(self.panel_r, 0, flag=wx.ALL, border=10)

        # panel_l
        box_l_1 = self.MakeStaticBoxSizer(self.panel_l, u"订单录入", label_ddlr)
        box_l_2 = self.MakeStaticBoxSizer(self.panel_l, u"积分兑换", label_jfdh)
        box_l_3 = self.MakeStaticBoxSizer(self.panel_l, u"会员明细", col_labels)
        box_1_5 = self.MakeStaticBoxSizer(self.panel_l, u"奖励积分", label_jljf)
        button1 = wx.Button(self.panel_l, -1, u'确认', size=(80,30))
        self.panel_l.Bind(wx.EVT_BUTTON, self.OnButton1Click, button1)
        button2 = wx.Button(self.panel_l, -1, u'确认', size=(80, 30))
        self.panel_l.Bind(wx.EVT_BUTTON, self.OnButton2Click, button2)
        button3 = wx.Button(self.panel_l, -1, u'备份数据', size=(80, 30))
        self.panel_l.Bind(wx.EVT_BUTTON, self.OnButton3Click, button3)
        button5 = wx.Button(self.panel_l, -1, u'确定修改', size=(80, 30))
        self.panel_l.Bind(wx.EVT_BUTTON, self.OnButton5Click, button5)
        button6 = wx.Button(self.panel_l, -1, u'删除用户', size=(80, 30))
        self.panel_l.Bind(wx.EVT_BUTTON, self.OnButton6Click, button6)
        button7 = wx.Button(self.panel_l, -1, u'确认', size=(80, 30))
        self.panel_l.Bind(wx.EVT_BUTTON, self.OnButton7Click, button7)

        box_l_4 = wx.BoxSizer(wx.HORIZONTAL)
        box_l_4.Add(button6, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_LEFT, 5)
        box_l_4.Add(button5, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 5)

        box_l = wx.BoxSizer(wx.VERTICAL)
        box_l.Add(button3, 0, wx.ALL | wx.ALIGN_RIGHT, 5)
        box_l.Add(box_l_1, 0, wx.ALL, 5)
        box_l.Add(button1, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.ALIGN_RIGHT, 5)
        box_l.Add((-1,5))
        box_l.Add(box_l_2, 0, wx.ALL, 5)
        box_l.Add(button2, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 5)
        box_l.Add(box_l_3, 0, wx.ALL, 5)
        box_l.Add(box_l_4, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 5)
        box_l.Add(box_1_5, 0, wx.ALL, 5)
        box_l.Add(button7, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 5)

        self.panel_l.SetSizer(box_l)

        # panel_r
        box_r = wx.BoxSizer(wx.VERTICAL)
        self.grid = wx.grid.Grid(self.panel_r)
        self.table = MyTable()
        self.grid.SetTable(self.table,True)
        # self.grid.Enable(False)
        self.grid.AutoSize()
        button4 = wx.Button(self.panel_r, -1, u'更新', size=(80, 30))
        self.panel_r.Bind(wx.EVT_BUTTON, self.OnButton4Click, button4)
        box_r.Add(button4, 0, wx.ALL | wx.ALIGN_RIGHT, 5)
        box_r.Add(self.grid, 0, wx.ALL, 5)
        self.panel_r.SetSizer(box_r)
        box_r.Fit(self.panel_r)

        panel.SetSizer(mbox)
        mbox.Fit(self)

    def OnButton1Click(self, event):
        logging.debug(u'==== 开始')
        remark = self.ddlr_objs[u'会员名'].GetValue().encode('utf-8')
        number = self.ddlr_objs[u'订单编号'].GetValue()
        price = self.ddlr_objs[u'订单价格'].GetValue()
        prop = self.ddlr_objs[u'佣金比例'].GetValue()
        logging.debug(u'==== 订单录入，会员：%s，订单编号：%s，价格：%s， 佣金比例：%s' % (remark, number, price, prop))
        if not (remark and number and price and prop):
            logging.error(u"==== 输入数据有误")
            return
        if eval(prop) > 20:
            prop = '20'
        c_points = int(round(eval(price)*INTEGRAL_PROP*(eval(prop)/100.0)))
        ret = IntegralRecord().IntegralRecordCheckOrder(number)
        if ret == 0:
            ret = Database().DatabaseChangePoints(remark, c_points)
            if ret == 0:
                cur_points = Database().DatabaseViewPoints(remark, None)
                IntegralRecord().IntegralRecordAddRecord(remark, number, price, prop, c_points, str(cur_points))
                IntegralRecord().IntegralRecordOrderRecord(remark, number)
                SendMessage('@msg@%s' % (u'亲，您的订单【' + number + u'】积分已录入，当前积分为：' + repr(cur_points)),
                            (itchat.search_friends(remarkName=remark)[0]['UserName']))
                self.table.UpdateMyData()
                self.table = MyTable()
                self.grid.SetTable(self.table, True)
                self.grid.AutoSize()
                self.grid.ForceRefresh()
        logging.debug(u'==== 结束')

    def OnButton2Click(self, event):
        logging.debug(u'==== 开始')
        remark = self.jfdh_objs[u'会员名'].GetValue().encode('utf-8')
        jp_num = self.jfdh_objs[u'商品编号'].GetValue()
        price = self.jfdh_objs[u'商品价格'].GetValue()
        number = self.jfdh_objs[u'订单编号'].GetValue()
        logging.debug(u'==== 积分兑换，会员：%s，积分商品：%s，订单编号：%s' % (remark, jp_num, number))
        if not (remark and jp_num and number):
            logging.error(u'==== 输入数据有误')
            return
        files = os.listdir(INTEGRAL_GOOD_FOLD)
        for name in files:
            if name.startswith(jp_num + '@'):
                name_list = name.split('@')
                integral = int(round(float(price) * (1 - (float(name_list[3])-5) / 100) * INTEGRAL_GOOD_PROP))
                c_points = 0 - integral
                ret = Database().DatabaseChangePoints(remark, c_points)
                if ret == 0:
                    cur_points = Database().DatabaseViewPoints(remark, None)
                    IntegralRecord().IntegralRecordAddRecord(remark, jp_num, price, name_list[3], str(c_points), str(cur_points))
                    IntegralRecord().IntegralRecordOrderRecord(remark, number, jp_num)
                    SendMessage('@msg@%s' % (u'亲，您已成功兑换积分商品【' + jp_num + u'】，当前积分为: ' + repr(cur_points)),
                                (itchat.search_friends(remarkName=remark)[0]['UserName']))
                    SendMessageToRoom(ROOM_NICK_NAME,
                                      u'@' + itchat.search_friends(remarkName=remark)[0]['NickName'] +
                                      u' 成功兑换积分商品')
                    self.table.UpdateMyData()
                    self.table = MyTable()
                    self.grid.SetTable(self.table, True)
                    self.grid.AutoSize()
                    self.grid.ForceRefresh()
        logging.debug(u'==== 结束')

    def OnButton3Click(self, event):
        logging.debug(u'==== 开始')
        logging.debug(u'==== 备份数据')
        UpdateToGit(is_data=True, is_robot=False)
        logging.debug(u'==== 结束')

    def OnButton4Click(self, event):
        logging.debug(u'==== 开始')
        self.table.UpdateMyData()
        self.table = MyTable()
        self.grid.SetTable(self.table, True)
        self.grid.AutoSize()
        self.grid.ForceRefresh()
        logging.debug(u'==== 结束')

    def OnButton5Click(self, event):
        logging.debug(u'==== 开始')
        remark_name = self.user_search_obj[u'会员名'].GetValue().encode('utf-8')
        logging.debug(u'==== 更改会员信息，会员：%s' % remark_name)
        ilabels = self.user_objs.keys()
        user_data = {}
        for a in ilabels:
            tmp = self.user_objs[a].GetValue()
            if a == 'nick_name':
                user_data[a] = tmp
            elif a in ('grade', 'points'):
                user_data[a] = int(tmp)
            else:
                user_data[a] = tmp.encode('utf-8')
        Database().DatabaseWriteData(remark_name, user_data)
        self.table.UpdateMyData()
        self.table = MyTable()
        self.grid.SetTable(self.table, True)
        self.grid.AutoSize()
        self.grid.ForceRefresh()
        logging.debug(u'==== 结束')

    def OnButton6Click(self, event):
        logging.debug(u'==== 开始')
        remark = self.user_search_obj[u'会员名'].GetValue().encode('utf-8')
        msg_dialog = wx.MessageDialog(self, u'确定删除用户【' + remark + u'】?', u'删除用户')
        ret = msg_dialog.ShowModal()
        msg_dialog.Destroy()
        if ret == wx.ID_OK:
            ret = Database().DatabaseDelUser(remark)
            if ret == 0:
                logging.info(u'==== 用户删除成功')
            else:
                logging.info(u'==== 删除用户失败')
            MyTable().UpdateMyData()
            self.grid.SetTable(self.table, True)
            self.grid.AutoSize()
            self.grid.ForceRefresh()
        logging.debug(u'==== 结束')

    def OnButton7Click(self, event):
        logging.debug(u'==== 开始')
        remark = self.jljf_objs[u'会员名'].GetValue().encode('utf-8')
        integral = self.jljf_objs[u'奖励积分'].GetValue()
        logging.debug(u'==== 会员：%s，奖励积分：%s' % (remark, integral))
        if not (remark and integral):
            logging.error(u"==== 输入数据有误")
            return
        ret = Database().DatabaseChangePoints(remark, eval(integral))
        if ret == 0:
            cur_points = Database().DatabaseViewPoints(remark, None)
            IntegralRecord().IntegralRecordAddRecord(remark, u'奖励积分', 'None', 'None', integral, str(cur_points))
            SendMessage('@msg@%s' % (u'亲，活动奖励积分【' + integral + u'】已经录入，当前积分为：' + repr(cur_points)),
                        (itchat.search_friends(remarkName=remark)[0]['UserName']))
            SendMessageToRoom(ROOM_NICK_NAME,
                              u'@' + itchat.search_friends(remarkName=remark)[0]['NickName'] +
                              u' 活动奖励积分已录入')
            MyTable().UpdateMyData()
            self.grid.SetTable(self.table, True)
            self.grid.AutoSize()
            self.grid.ForceRefresh()
        logging.debug(u'==== 结束')

    def EnterText(self, event):
        logging.debug(u'==== 开始')
        remark_name = self.user_search_obj[u'会员名'].GetValue().encode('utf-8')
        user_data = Database().DatabaseViewData(remark_name)
        ilabels = self.user_objs.keys()
        if user_data:
            for a in ilabels:
                self.user_objs[a].SetValue(str(user_data[a]))
        else:
            logging.info(u'==== 数据库中没有此用户信息， 输入的会员名不正确')
            for a in ilabels:
                self.user_objs[a].SetValue('')
        logging.debug(u'==== 结束')

    def MakeStaticBoxSizer(self, parent, boxlabel, labels):
        box = wx.StaticBox(parent, -1, boxlabel)
        sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)
        sizer1 = wx.BoxSizer(wx.VERTICAL)
        sizer2 = wx.BoxSizer(wx.VERTICAL)
        if labels == col_labels:
            bw1 = StaticWindow(parent, label=u'会员名')
            sizer2.Add(bw1, 0, wx.ALL, 2)
            bw = wx.TextCtrl(parent, -1, '', wx.DefaultPosition, (200,25), style=wx.TE_PROCESS_ENTER)
            bw.Bind(wx.EVT_TEXT_ENTER, self.EnterText, bw)
            self.user_search_obj[u'会员名'] = bw
            sizer1.Add(bw, 0, wx.ALL, 2)
        for a in labels:
            bw1 = StaticWindow(parent, label=a)
            sizer2.Add(bw1, 0, wx.ALL, 2)
            bw = TextWindow(parent)
            if labels == label_ddlr:
                self.ddlr_objs[a] = bw
            elif labels == label_jfdh:
                self.jfdh_objs[a] = bw
            elif labels == col_labels:
                self.user_objs[a] = bw
            elif labels == label_jljf:
                self.jljf_objs[a] = bw
            sizer1.Add(bw, 0, wx.ALL, 2)

        sizer.Add(sizer2, 0, wx.ALL, 10)
        sizer.Add(sizer1, 0, wx.ALL, 10)
        return sizer

################ thread 相关 #################

def UiMainThread():
    app = wx.App(redirect=False)
    MyFrame().Show()
    app.MainLoop()

def CreateUiThread():
    ui_thread = threading.Thread(target=UiMainThread)
    ui_thread.setDaemon(True)
    ui_thread.start()
    ui_thread.name = 'UI thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
    logging.debug('==== thread name is ' + ui_thread.name)

def ReceiveCmdThread():
    while True:
        cmd = raw_input('Enter cmd(UI):')
        if cmd == 'UI':
            CreateUiThread()
        else:
            print 'can not realize cmd'

def CreateReceiveCmdThread():
    cmd_thread = threading.Thread(target=ReceiveCmdThread)
    cmd_thread.setDaemon(True)
    cmd_thread.start()
    cmd_thread.name = 'CMD thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
    logging.debug('==== thread name is ' + cmd_thread.name)

def UpdateToGit(is_robot=True, is_data=True):
    logging.debug(u'==== GIT开始上传数据')
    cnt = 0
    if is_data:
        os.chdir(GIT_DATA_FOLD)
    else:
        os.chdir(GIT_CODE_FOLD)
    os.system('git add --all')
    if is_robot:
        os.system('git commit -m "robot update"')
    else:
        os.system('git commit -m "man update"')
    while True:
        ret = os.system('git push origin master')
        if ret == 0:
            logging.debug(u'==== GIT上传成功')
            return 0
        else:
            cnt += 1
            logging.error(u'==== 上传失败 error:' + repr(ret) + u' cnt:' + repr(cnt))
            if cnt >= 3:
                logging.error(u'==== GIT上传失败')
                SendMessage('@msg@%s' % u'报告主人：GIT上传失败', (itchat.search_friends(remarkName=u'ltj_1')[0]['UserName']))
                return -1

def GitUpdateThread():
    while True:
        UpdateToGit()
        time.sleep(1800)

def CreateGitThread():
    git_thread = threading.Thread(target=GitUpdateThread)
    git_thread.setDaemon(True)
    git_thread.start()
    git_thread.name = 'GIT thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
    logging.debug('==== thread name is ' + git_thread.name)

################ 初始化 #################
log_init()
if not os_system == 'Linux':
    CreateReceiveCmdThread()
CreateGitThread()

q_w2b_input = Queue(3)
q_b2w_output = Queue(3)
q_b2w_input = Queue(3)

def send_to_browser_worker(msg):
    q_w2b_input.put(msg)
    ret = q_b2w_output.get()
    print 'send_to_browser_worker, ret: ' + ret

def browser_master(q_in, q_out):
    browser_1 = browser()
    p = Process(target=browser_1.worker, args=(browser_1.q_in, browser_1.q_out))
    p.daemon = True
    p.start()
    while True:
        msg = q_in.get()
        browser_1.q_in.put(msg)
        ret = browser_1.q_out.get()
        q_out.put(ret)
        print 'browser_master, ret: ' + ret

p = Process(target=browser_master, name='broser_worker', args=(q_w2b_input, q_b2w_output))
p.daemon = True
p.start()

itchat.auto_login()
itchat.run()