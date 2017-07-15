#coding:utf-8
import json
import random
import traceback
import schedule

import itchat,shelve,re,codecs,threading,inspect,ctypes,wx,sys
import pymongo
import wx.grid

import xlrd
from PIL import Image, ImageDraw, ImageFont
from bson import ObjectId
import Queue

from wechat_config import *
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

send_message_lock = threading.Lock()  # 发送wechat消息锁
# 保存UserName与InnerId的对应关系。每次重新登录，用户对应的UserName都会改变，
# 在用户第一次操作积分的时候，都需要重新对应下关系，InnerId与用户的支付宝账号对应
UserName_InnerId = {}

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
    send_message_lock.acquire()
    time.sleep(random.choice(SEND_MESSAGE_DELAY))
    logging.debug('==== 开始')
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
                logging.debug('==== 消息发送成功，循环次数：' + repr(cnt1) + u'  等待时间：' + repr(cnt*0.2))
                return 0
            if cnt1 >= SEND_TIMES:
                return -1
    finally:
        send_message_lock.release()
        logging.debug('==== 结束')

def StitchPictures(images, out_path, mode='V', quality=100):
    items = images.items()
    num = len(items)
    image_files = []
    per_image_size = Image.open(items[0][0]).size
    for i in range(num):
        image_ori = Image.open(items[i][0])
        fnt = ImageFont.truetype(FONT_PATH, 70)
        d = ImageDraw.Draw(image_ori)
        d.text((20, 50), items[i][1], font=fnt, fill=(0, 0, 0, 0))
        if image_ori.size != per_image_size:
            image_ori = image_ori.resize(per_image_size, Image.LANCZOS)
        image_files.append(image_ori)
    if mode == 'H':
        out_image_size = (per_image_size[0] * num, per_image_size[1])
    elif mode == 'V':
        out_image_size = (per_image_size[0], per_image_size[1] * num)
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

def log_and_send_error_msg(title='', detail='', reason=''):
    stack = inspect.stack()
    func_name = stack[1][3]
    lineno = stack[1][2]
    logging.error('[%s][%s]\r\nTitle: %s\r\nDetail: %s\r\nReason: %s' % (func_name, lineno, title, detail, reason))
    SendMessageToRoom(INNER_ROOM_NICK_NAME, '@msg@%s' % ('错误\nTitle: %s\nDetail: %s\nReason: %s' % (title, detail, reason)))

def username_link_to_db(user_name, nick_name):
    if user_name in UserName_InnerId:
        return UserName_InnerId[user_name]
    else:
        # 重新链接InnerId和UserName
        # 在数据库中查找NickName
        info = Database().DatabaseSearch(nick_name)
        if info < 0:
            return info
        # 如果支付宝为空，需要返回设置支付宝
        zhifubao = info[u'AliInfo'][u'ZhiFuBaoZH']
        if not zhifubao:
            logging.debug('==== 支付宝账号为空')
            return WECHAT_NO_ZHIFUBAOZH
        # 链接
        inner_id = info[u'InnerId']
        # 检测支付宝是否已经被连接过
        for user in UserName_InnerId:
            if UserName_InnerId[user][u'ZhiFuBaoZH'] == zhifubao:
                logging.debug('==== 支付宝账号已被链接过')
                return WECHAT_LINK_FAILED
        UserName_InnerId[user_name] = {u'InnerId': inner_id, u'ZhiFuBaoZH': zhifubao}
        return UserName_InnerId[user_name]

# def ReturnValue(result, value=None):
#     return_dict = {u'result':result, u'value':value}
#     return return_dict

class UserData:
    def __init__(self, NickName, InnerId, ZhiFuBaoZH=u'', Province=u'', City=u'',
                 Sex=u'', Group=u'user', Grade=0, Points=0, LastCheckIn=u'', Father=u''):
        self.user_data = {}
        self.user_data[u'NickName'] = NickName
        self.user_data[u'InnerId'] = InnerId
        self.user_data[u'Group'] = Group
        self.user_data[u'Grade'] = Grade
        self.user_data[u'Points'] = Points
        self.user_data[u'LastCheckIn'] = LastCheckIn
        self.user_data[u'Father'] = Father
        self.user_data[u'AliInfo'] = {u'ZhiFuBaoZH': ZhiFuBaoZH}
        self.user_data[u'WechatInfo'] = {u'Province': Province, u'City': City, u'Sex': Sex}

    def Get(self):
        return self.user_data

class Database:
    def __init__(self):
        self.client = pymongo.MongoClient(MONGO_URL, connect=False)
        self.db_table_wechat_users = self.client[MONGO_DB_WECHAT][MONGO_TABLE_WECHAT_USERS]

    def DatebaseGetInfoByInnerId(self, inner_id):
        logging.debug('==== 开始')
        logging.debug('==== InnerId %s' % inner_id)
        cursor = self.db_table_wechat_users.find({u'InnerId': inner_id})
        count = cursor.count()
        if count == 0:
            log_and_send_error_msg('Mongodb没有找到用户', 'InnerId: %s' % inner_id, '此用户不存在')
            return WECHAT_DB_ERROR
        elif count > 1:
            log_and_send_error_msg('Mongodb同一ID找到多个用户', 'InnerId: %s' % inner_id, '数据库重复')
            return WECHAT_DB_ERROR
        else:
            return cursor.next()

    def DatabaseSearch(self, nick_name=u'', zhifubao=u''):
        ''' 通过nick_name或zhifubao来查找用户
            如果nick_name设置了，不会查找zhifubao
        '''
        logging.debug('==== 开始')
        logging.debug('==== NickName %s' % nick_name)
        try:
            if nick_name:
                cursor = self.db_table_wechat_users.find({u'NickName':nick_name})
                count = cursor.count()
                if count == 0:
                    logging.debug('==== 未找到NickName，%s' % nick_name)
                    return WECHAT_NOT_FIND
                elif count > 1:
                    log_and_send_error_msg('Mongodb同一昵称找到多个用户', 'NickName: %s' % nick_name, '数据库重复')
                    return WECHAT_MORE_THAN_ONE_FOUND
                elif count == 1:
                    logging.debug('==== NickName %s, 找到一个' % nick_name)
                    return cursor.next()
            elif zhifubao:
                cursor = self.db_table_wechat_users.find({u'AliInfo.ZhiFuBaoZH':zhifubao})
                count = cursor.count()
                if count == 0:
                    logging.debug('==== 未找到支付宝账号，%s' % zhifubao)
                    return WECHAT_NOT_FIND
                elif count > 1:
                    log_and_send_error_msg('Mongodb同一支付宝找到多个用户', 'ZhiFuBaoZH: %s' % zhifubao, '数据库重复')
                    return WECHAT_MORE_THAN_ONE_FOUND
                elif count == 1:
                    logging.debug('==== ZhiFuBaoZH %s, 找到一个' % zhifubao)
                    return cursor.next()
        finally:
            logging.debug('==== 结束')

    def DatabaseCheckNickZFBUnique(self, nick_name=u'', zhifubao=u''):
        is_nick_exist = False
        is_zhifubao_exist = False
        if nick_name:
            cursor = self.db_table_wechat_users.find({u'NickName':nick_name})
            if cursor.count() != 0:
                logging.debug('==== 昵称已存在, NickName: %s' % nick_name)
                is_nick_exist = True
        if zhifubao:
            cursor = self.db_table_wechat_users.find({u'AliInfo.ZhiFuBaoZH':zhifubao})
            if cursor.count() != 0:
                logging.debug('==== 支付宝账号已存在, ZhiFuBaoZH: %s' % zhifubao)
                is_zhifubao_exist = True
        if is_nick_exist and is_zhifubao_exist:
            return WECHAT_ZHIFUBAO_NICKNAME_BOTH_EXIST
        elif is_nick_exist:
            return WECHAT_NICKNAME_EXIST
        elif is_zhifubao_exist:
            return WECHAT_ZHIFUBAO_EXIST
        else:
            return SUCCESS

    def __DatabaseChangeFahterPoints(self, father_innerid, child_nick_name, child_change_points):
        logging.debug('==== 开始')
        father_info = self.DatebaseGetInfoByInnerId(father_innerid)
        father_nick_name = father_info[u'NickName']
        father_zhifubao = father_info[u'AliInfo'][u'ZhiFuBaoZH']
        father_zhifubao_mark = AccountMark(father_zhifubao)
        father_points_change = int(round(child_change_points * FATHER_REWARD_PROP / 100.0))
        father_points_old = father_info[u'Points']
        father_points_new = father_points_old + father_points_change
        self.db_table_wechat_users.update_one({u'InnerId': father_innerid},
                                              {"$set": {u'Points': father_points_new}})
        IntegralRecord().IntegralRecordAddRecord(father_innerid, u'好友奖励积分', 'None', 'None',
                                                 str(father_points_change), str(father_points_new))
        SendMessageToRoom(TARGET_ROOM, '@msg@%s' %
                          ('@%s 亲，您邀请的好友【%s】，给您带来了【%s】积分的奖励\n'
                           '您的支付宝账号(%s)的当前积分为：%s' % (
                               father_nick_name, child_nick_name, str(father_points_change), father_zhifubao_mark,
                               str(father_points_new))))
        logging.debug('==== 结束')

    def DatabaseChangePoints(self, inner_id, points):
        logging.debug('==== 开始')
        logging.debug('==== InnerId %s, Points %d' % (inner_id, points))
        try:
            info = self.DatebaseGetInfoByInnerId(inner_id)
            if info < 0:
                return info
            logging.debug('==== Before: %s' % info)
            p = info[u'Points'] + points
            if p < 0:
                p = 0
            self.db_table_wechat_users.update_one({u'InnerId': inner_id},
                                 {"$set": {u'Points': p}})
            logging.debug('==== After: %s' % self.db_table_wechat_users.find({u'InnerId':inner_id}).next())
            # add points to father
            if info[u'Father'] and points > 0:
                self.__DatabaseChangeFahterPoints(info[u'Father'], info[u'NickName'], points)
            return SUCCESS
        finally:
            logging.debug('==== 结束')

    def DatabaseCheckin(self, inner_id):
        logging.debug('==== 开始')
        logging.debug('==== InnerId %s' % inner_id)
        try:
            today = time.strftime('%Y-%m-%d', time.localtime(time.time()))
            info = self.DatebaseGetInfoByInnerId(inner_id)
            if info < 0:
                return info
            if info[u'LastCheckIn'] == today:
                logging.debug('==== 今日已签到，%s' % inner_id)
                return WECHAT_ALREADY_CHECKIN
            logging.debug('==== Before: %s' % info)
            p = info[u'Points'] + CHECK_IN_POINTS
            self.db_table_wechat_users.update_one({u'InnerId': inner_id},
                                                  {"$set": {u'Points': p, u'LastCheckIn':today}})
            logging.debug('==== After: %s' % self.db_table_wechat_users.find({u'InnerId':inner_id}).next())
            IntegralRecord().IntegralRecordAddRecord(inner_id, u'签到', 'None', 'None', str(CHECK_IN_POINTS), str(p))
            # add points to father
            if info[u'Father']:
                self.__DatabaseChangeFahterPoints(info[u'Father'], info[u'NickName'], CHECK_IN_POINTS)
            return SUCCESS
        finally:
            logging.debug('==== 结束')

    def DatabaseViewPoints(self, inner_id):
        logging.debug('==== 开始')
        logging.debug('==== InnerId %s' % inner_id)
        try:
            info = self.DatebaseGetInfoByInnerId(inner_id)
            if info < 0:
                return info
            return info['Points']
        finally:
            logging.debug('==== 结束')

    def DatabaseUserNextNumber(self, update=True):
        logging.debug('==== 开始')
        try:
            info = self.DatebaseGetInfoByInnerId(GROUP_USER_NUMBER_INNERID)
            if info < 0:
                return info
            p = info['Points']
            if update:
                self.db_table_wechat_users.update_one({u'InnerId': GROUP_USER_NUMBER_INNERID},
                                                      {"$set": {u'Points': p+1}})
            return p
        finally:
            logging.debug('==== 结束')

    def DatabaseAddUser(self, user_data):
        logging.debug('==== 开始')
        logging.debug('==== %s' % user_data)
        try:
            ret = self.DatabaseCheckNickZFBUnique(nick_name=user_data[u'NickName'],
                                            zhifubao=user_data[u'AliInfo'][u'ZhiFuBaoZH'])
            if ret < 0:
                return ret
            self.db_table_wechat_users.insert(user_data)
            if user_data[u'Father']:
                father_info = self.DatebaseGetInfoByInnerId(user_data[u'Father'])
                father_nick_name = father_info[u'NickName']
                SendMessageToRoom(TARGET_ROOM, '@msg@%s' %
                                  ('@%s 亲，您邀请的好友【%s】与您绑定成功\n'
                                   '每当好友获得积分，您也将会获得积分奖励' % (
                                       father_nick_name, user_data['NickName'])))
            return SUCCESS
        finally:
            logging.debug('==== 结束')

    def DatabaseUpdateNickName(self, nick_name, zhifubao):
        logging.debug('==== 开始')
        try:
            # 检测nick_name唯一
            ret = self.DatabaseCheckNickZFBUnique(nick_name=nick_name)
            if ret < 0:
                return ret
            # 检测支付宝账号存在
            ret = self.DatabaseSearch(zhifubao=zhifubao)
            if ret < 0:
                return ret
            self.db_table_wechat_users.update_one({u'AliInfo.ZhiFuBaoZH': zhifubao},
                                                  {"$set": {u'NickName': nick_name}})
            return SUCCESS
        finally:
            logging.debug('==== 结束')

    def DatabaseSetZhiFuBao(self, nick_name, zhifubao):
        logging.debug('==== 开始')
        try:
            # 检测支付宝账号唯一
            ret = self.DatabaseCheckNickZFBUnique(zhifubao=zhifubao)
            if ret < 0:
                return ret
            # 检测昵称存在
            ret = self.DatabaseSearch(nick_name=nick_name)
            if ret < 0:
                return ret
            if ret[u'AliInfo'][u'ZhiFuBaoZH']:
                logging.debug('==== 支付宝账号不为空，无法设置支付宝')
                return WECHAT_ZHIFUBAO_NOT_EMPTY
            self.db_table_wechat_users.update_one({u'NickName': nick_name},
                                                  {"$set": {u'AliInfo.ZhiFuBaoZH': zhifubao}})
            return SUCCESS
        finally:
            logging.debug('==== 结束')

    def DatabaseSetZFBNick(self, inner_id, nick_name, zhifubao):
        logging.debug('==== 开始')
        try:
            # 检测昵称和支付宝账号唯一
            ret = self.DatabaseCheckNickZFBUnique(nick_name=nick_name, zhifubao=zhifubao)
            if ret < 0:
                return ret
            # 检测InnerId存在
            ret = self.DatebaseGetInfoByInnerId(inner_id)
            if ret < 0:
                return ret
            # 检测ZFB账号未空
            if ret[u'AliInfo'][u'ZhiFuBaoZH']:
                logging.debug('==== 支付宝账号不为空，无法设置支付宝')
                return WECHAT_ZHIFUBAO_NOT_EMPTY
            self.db_table_wechat_users.update_one({u'InnerId': inner_id},
                                                  {"$set": {u'AliInfo.ZhiFuBaoZH': zhifubao,
                                                            u'NickName': nick_name}})
            return SUCCESS
        finally:
            logging.debug('==== 结束')

    def DatabaseDelUser(self, inner_id):
        logging.debug('==== 开始')
        try:
            info = self.DatebaseGetInfoByInnerId(inner_id)
            if info < 0:
                return info
            self.db_table_wechat_users.delete_one({u'InnerId':inner_id})
            return SUCCESS
        finally:
            logging.debug('==== 结束')

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

    def DatabaseViewData(self, inner_id):
        logging.debug('==== 开始')
        logging.debug('==== InnerId %s' % inner_id)
        try:
            info = self.DatebaseGetInfoByInnerId(inner_id)
            if info < 0:
                return info
            info[u'_id'] = u''
            return info
        finally:
            logging.debug('==== 结束')

    def DatabaseWriteData(self, inner_id, user_data):
        logging.debug('==== 开始')
        logging.debug('==== InnerId %s' % inner_id)
        try:
            info = self.DatebaseGetInfoByInnerId(inner_id)
            if info < 0:
                return info
            self.db_table_wechat_users.delete_one({u'InnerId':inner_id})
            self.db_table_wechat_users.insert(user_data)
            return SUCCESS
        finally:
            logging.debug('==== 结束')

class Template:
    def TemplateSendCommand(self, to):
        logging.debug('==== 开始')
        lines = ''
        for line in codecs.open(TEMPLATE_FOLD + u"命令模板.txt", 'rb', 'utf-8'):
            lines += line
        lines = lines.strip()
        logging.debug(lines)
        SendMessage('@msg@%s' % lines, to)
        logging.debug('==== 结束')

    def TemplateSendMasterCommand(self, to):
        logging.debug('==== 开始')
        lines = ''
        for line in codecs.open(TEMPLATE_FOLD + u"Master命令模板.txt", 'rb', 'utf-8'):
            lines += line
        lines = lines.strip()
        logging.debug(lines)
        SendMessage('@msg@%s' % lines, to)
        logging.debug('==== 结束')

    def TemplateSendIntegralregular(self, to):
        logging.debug('==== 开始')
        lines = ''
        for line in codecs.open(TEMPLATE_FOLD + u"积分玩法.txt", 'rb', 'utf-8'):
            lines += line
        lines = lines.strip()
        logging.debug(lines)
        SendMessage('@msg@%s' % lines, to)
        logging.debug('==== 结束')

    def TemplateSendActivity(self, to):
        logging.debug('==== 开始')
        files = os.listdir(ACTIVITY_FOLD)
        today = time.strftime('%Y-%m-%d', time.localtime(time.time()))
        has_activity = 0
        for file in files:
            if (re.match(u'活动_.*_.*\.txt$', file)):
                begin_date = file.split('_')[1]
                end_date = file.split('_')[2]
                if begin_date <= today and today <= end_date:
                    has_activity = 1
                    for line in codecs.open(ACTIVITY_FOLD + file, 'rb', 'utf-8'):
                        line = line.strip()
                        if not re.match(u'&图片&', line):
                            SendMessage('@msg@%s' % line, to)
                        else:
                            str_tmp = ACTIVITY_FOLD + line.split('&')[2]
                            SendMessage('@img@%s' % str_tmp, to)
        if not has_activity:
            SendMessage('@msg@%s' % "亲，当前没有进行中的活动", to)
        logging.debug('==== 结束')

    def __TemplateSendPicAndText(self, pic_path, text_path, to):
        SendMessage('@img@%s' % pic_path, to)
        for line in codecs.open(text_path, 'r', 'utf-8'):
            line = line.strip()
            SendMessage('@msg@%s' % line, to)

    def TemplateSendIntegralGood(self, to):
        logging.debug('==== 开始')
        try:
            f = codecs.open(INTEGRAL_GOOD_URL_FILE_PATH, 'rb', 'utf-8')
            line = f.readline().strip()
            url = line.split(' ')[1]
            SendMessage('@msg@%s' % ('亲，点击链接查看积分商品：\n%s' % url), to)
        finally:
            logging.debug('==== 结束')

    def TemplateSendExchangeProcess(self, to):
        logging.debug('==== 开始')
        lines = ''
        try:
            for line in codecs.open(TEMPLATE_FOLD + u"积分商品兑换流程.txt", 'rb', 'utf-8'):
                if not re.match(u'&图片&', line):
                    lines += line
                else:
                    if lines:
                        lines = lines.strip()
                        SendMessage('@msg@%s' % lines, to)
                    line = line.strip()
                    str_tmp = TEMPLATE_FOLD + line.split('&')[2]
                    SendMessage('@img@%s' % str_tmp, to)
                    lines = ''
            if lines:
                SendMessage('@msg@%s' % lines, to)
        finally:
            logging.debug('==== 结束')

class IntegralRecord:
    integral_record_mutex = threading.Lock()  # 积分记录的同步锁

    def IntegralRecordAddRecord(self, inner_id, type_message, price, prop, c_points, points):
        logging.debug('==== 开始')
        try:
            time_now = time.strftime('%Y-%m-%d_%H%M%S', time.localtime(time.time()))
            with codecs.open(INTEGRAL_RECORD_FOLD + inner_id + '.txt', 'a', 'utf-8') as f:
                f.write('%s %s %s %s %s %s\r\n' % (time_now, type_message, price, prop, c_points, points))
        finally:
            logging.debug('==== 结束')

    def IntegralRecordOrderRecord(self, inner_id, order, jp_num=''):
        IntegralRecord.integral_record_mutex.acquire()
        logging.debug('==== 开始')
        try:
            time_now = time.strftime('%Y-%m-%d_%H%M%S', time.localtime(time.time()))
            with codecs.open(ORDER_FILE_PATH, 'a', 'utf-8') as f:
                f.write('%s %s %s %s\r\n' % (time_now, order, inner_id, jp_num))
        finally:
            IntegralRecord.integral_record_mutex.release()
            logging.debug('==== 结束')

    def IntegralRecordCheckOrder(self, order):
        IntegralRecord.integral_record_mutex.acquire()
        logging.debug('==== 开始')
        try:
            for line in codecs.open(ORDER_FILE_PATH, 'r', 'utf-8'):
                if line:
                    l = line.split(' ')
                    if l[1] == order:
                        logging.info('==== 订单已经被会员【%s】于【%s】录入过' % (l[2], l[0]))
                        return -1
            return 0
        finally:
            IntegralRecord.integral_record_mutex.release()
            logging.debug('==== 结束')

class IntegralGoods:
    def inputInteral(self, inner_id, number, price, prop):
        logging.debug('==== 开始')
        if not (inner_id and number and price and prop):
            logging.error("==== 输入数据有误")
            return -1
        ret = IntegralRecord().IntegralRecordCheckOrder(number)
        if ret < 0:
            return -1
        logging.debug('==== 订单录入，会员：%s，订单编号：%s，价格：%s， 佣金比例：%s' % (inner_id, number, price, prop))
        if eval(prop) > INTEGRAL_REWARD_MAX_PROP:
            prop = str(INTEGRAL_REWARD_MAX_PROP)
        c_points = int(round(eval(price)*INTEGRAL_PROP*(eval(prop)/100.0)))
        ret = Database().DatabaseChangePoints(inner_id, c_points)
        if ret == 0:
            cur_points = Database().DatabaseViewPoints(inner_id)
            IntegralRecord().IntegralRecordAddRecord(inner_id, number, price, prop, c_points, str(cur_points))
            IntegralRecord().IntegralRecordOrderRecord(inner_id, number)
            info = Database().DatebaseGetInfoByInnerId(inner_id)
            nick_name = info[u'NickName']
            zhifubao_mark = AccountMark(info[u'AliInfo'][u'ZhiFuBaoZH'])
            SendMessageToRoom(TARGET_ROOM,
                              '@msg@%s' % ('@%s 亲，您的订单【%s】积分已录入\n'
                                           '您的支付宝账号(%s)的当前积分为：%s' % (nick_name, number, zhifubao_mark, repr(cur_points))))
        logging.debug('==== 结束')
        return 0

    def exchangeGoods(self, inner_id, jp_num, price, prop, number):
        logging.debug('==== 开始')
        if not (inner_id and jp_num and price and number and prop):
            logging.error('==== 输入数据有误')
            return -1
        ret = IntegralRecord().IntegralRecordCheckOrder(number)
        if ret < 0:
            return -1
        logging.debug('==== 积分兑换，会员：%s，积分商品：%s，价格：%s， 佣金比例：%s，订单编号：%s' %
                      (inner_id, jp_num, price, prop, number))

        integral = int(round(float(price) * (1 - (eval(prop)-5)/100.0) * INTEGRAL_GOOD_PROP))
        c_points = 0 - integral
        ret = Database().DatabaseChangePoints(inner_id, c_points)
        if ret == 0:
            cur_points = Database().DatabaseViewPoints(inner_id)
            IntegralRecord().IntegralRecordAddRecord(inner_id, jp_num, price, prop, str(c_points), str(cur_points))
            IntegralRecord().IntegralRecordOrderRecord(inner_id, number, jp_num)
            info = Database().DatebaseGetInfoByInnerId(inner_id)
            nick_name = info[u'NickName']
            zhifubao_mark = AccountMark(info[u'AliInfo'][u'ZhiFuBaoZH'])
            SendMessageToRoom(TARGET_ROOM,
                              '@msg@%s' % ('@%s 亲，您已成功兑换积分商品【%s】\n'
                                           '您的支付宝账号(%s)的当前积分为：%s' % (nick_name, jp_num, zhifubao_mark, repr(cur_points))))
        logging.debug('==== 结束')
        return 0

class MemberRecord:
    member_record_mutex = threading.Lock()  # 邀请记录的同步锁

    #TODO: 应该判断，邀请记录中的群名是否是当前的群
    def MemberRecordFindFather(self, nick_name):
        logging.debug('==== 开始')
        try:
            for line in codecs.open(MEMBER_RECORD_PATH, 'r', 'utf-8'):
                line_list = line.split('"')
                if line_list[3] == nick_name:
                    father = line_list[1]
                    if father.startswith(u'ltj_'):
                        return father
                    else:
                        ret = Database().DatabaseSearch(father)
                        if ret < 0:
                            logging.debug('==== 未找到father，nick_name: %s' % nick_name)
                            return WECHAT_NOT_FIND_FATHER
                        return ret['InnerId']
            logging.debug('==== 未找到father，nick_name: %s' % nick_name)
            return WECHAT_NOT_FIND_FATHER
        finally:
            logging.debug('==== 结束')

    def MemberRecordAddRecord(self, record):
        MemberRecord.member_record_mutex.acquire()
        logging.debug('==== 开始')
        try:
            time_now = time.strftime('%Y-%m-%d_%H%M%S', time.localtime(time.time()))
            with codecs.open(MEMBER_RECORD_PATH, 'a', 'utf-8') as f:
                f.write(time_now + ' ' + record)
        finally:
            MemberRecord.member_record_mutex.release()
            logging.debug('==== 结束')

class LotteryActivity:
    is_start = False
    join_lock = threading.Lock()
    user_num = 0
    file_name = '0.txt'
    def __init__(self):
        l = LOTTERY_TIME.split(' ')
        self.time_s = l[0]
        self.time_e = l[1]

    def sendRemNotice(self):
        '''timing send notice to group
        '''
        SendMessageToRoom(TARGET_ROOM, u'抽奖活动将于今天【%s】开始哦' % self.time_s)

    def sendBeginNotice(self):
        '''when begin, send notice every 5 minutes
        '''
        logging.debug('==== 开始')
        while True:
            cur_time = time.strftime('%H:%M', time.localtime())
            h, m= [int(i) for i in cur_time.split(':')]
            h_e, m_e = [int(i) for i in self.time_e.split(':')]
            if h*60+m >= h_e*60+m_e:
                break
            if LotteryActivity.is_start == False:
                break
            SendMessageToRoom(TARGET_ROOM, u'[啤酒]抽奖活动开始喽\n'
                                           u'[啤酒]输入【抽奖】报名参加\n'
                                           u'[咖啡]奖励%d积分\n'
                                           u'[咖啡]门票%d积分\n'
                                           u'[咖啡]报名人数限制【%d】\n'
                                           u'[咖啡]报名截止时间【%s】'
                              % (LOTTERY_REWARD_POINTS, LOTTERY_POINTS, LOTTERY_MAX_NUM, self.time_e))
            time.sleep(5*60)
        logging.debug('==== 结束')

    def beginActivity(self):
        logging.debug('==== 开始')
        LotteryActivity.user_num = 0
        files = os.listdir(LOTTERY_FOLD)
        l = []
        for f in files:
            if re.match('\d+\.txt', f):
                l.append(int(f.split('.')[0]))
        if not l:
            LotteryActivity.file_name = '0.txt'
        else:
            LotteryActivity.file_name = str(sorted(l)[len(l)-1] + 1) + '.txt'
        LotteryActivity.is_start = True
        thread = threading.Thread(target=self.sendBeginNotice)
        thread.setDaemon(True)
        thread.start()
        thread.name = u'sendBeginNotice thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
        logging.debug('==== 结束')

    def endActivity(self):
        logging.debug('==== 开始')
        if LotteryActivity.is_start == False:
            return
        LotteryActivity.is_start = False
        try:
            if LotteryActivity.user_num >= LOTTERY_MAX_NUM:
                msg = u'抽奖报名人数已满，开始计算抽奖结果'
                SendMessageToRoom(TARGET_ROOM, msg)
            else:
                msg = u'抽奖报名人数不足【%d】人，无法开奖，活动结束' % LOTTERY_MAX_NUM
                SendMessageToRoom(TARGET_ROOM, msg)
                return
            self.calResult()
        finally:
            LotteryActivity.user_num = 0
            logging.debug('==== 结束')

    def calResult(self):
        '''we should check user_numbers, and choose one as a lucky boy
        '''
        logging.debug('==== 开始')
        # get users, choose lucy boy
        users = []
        luck_boy = u''
        with codecs.open(LOTTERY_FOLD+LotteryActivity.file_name, 'r+', 'utf-8') as f:
            line = f.readline()
            users = line.strip().split(' ')
            luck_boy = random.choice(users)
            f.write('\n'+luck_boy)
        # deduce points
        for user in users:
            points = 0 - LOTTERY_POINTS
            Database().DatabaseChangePoints(user, points)
        # add points to lucky boy
        points = LOTTERY_REWARD_POINTS
        Database().DatabaseChangePoints(luck_boy, points)
        # send result to group
        nick_name = Database().DatebaseGetInfoByInnerId(luck_boy)[u'NickName']
        SendMessageToRoom(TARGET_ROOM, u'恭喜【%s】获得奖励积分【%d】' % (nick_name, LOTTERY_REWARD_POINTS))
        logging.debug('==== 结束')

    def join(self, user_name, to_name, nick_name):
        '''someone join into the activity
        '''
        LotteryActivity.join_lock.acquire()
        try:
            logging.debug('==== 开始')
            # multhread, so we should check if activity is end
            if LotteryActivity.is_start == False:
                SendMessage('@msg@%s' % (u'@%s, 活动刚刚结束了， 下次再参加吧' % nick_name), to_name)
                return
            # check current user number
            if LotteryActivity.user_num >= LOTTERY_MAX_NUM:
                SendMessage('@msg@%s' % (u'@%s, 当前报名人数已满, 下次再参加吧' % nick_name), to_name)
                return
            # check user points
            points = user_view_points(user_name, nick_name)
            if points < 0:
                if points == WECHAT_NOT_FIND:
                    SendMessage('@msg@%s' % ('@%s 亲，数据库中未找到昵称\n可能您是新用户或者更改了昵称\n请私聊联系小叶子处理') % nick_name, to_name)
                elif points == WECHAT_NO_ZHIFUBAOZH:
                    SendMessage('@msg@%s' % ('@%s 您还未设置支付宝\n请私聊联系小叶子处理' % nick_name), to_name)
                else:
                    SendMessage('@msg@%s' % ('@%s O，NO，发生了一些错误，稍后再试吧' % nick_name), to_name)
                return
            elif points < LOTTERY_POINTS:
                SendMessage('@msg@%s' % (u'@%s, 您的积分不足,无法参加抽奖,所需积分【%d】' % (nick_name, LOTTERY_POINTS)), to_name)
                return
            # join in
            with codecs.open(LOTTERY_FOLD+LotteryActivity.file_name, 'a', 'utf-8') as f:
                inner_id = UserName_InnerId[user_name][u'InnerId']
                f.write(inner_id + ' ')
            LotteryActivity.user_num += 1
            # send message to user
            SendMessage('@msg@%s' % (u'@%s 抽奖报名成功, 当前参加人数【%d】' % (nick_name, LotteryActivity.user_num)), to_name)
            if LotteryActivity.user_num >= LOTTERY_MAX_NUM:
                self.endActivity()
        finally:
            logging.debug('==== 结束')
            LotteryActivity.join_lock.release()

    def scheduleThread(self):
        # schedule.every(1).minutes.do(self.beginActivity)
        schedule.every().day.at(self.time_s).do(self.beginActivity)
        schedule.every().day.at(self.time_e).do(self.endActivity)
        while True:
            schedule.run_pending()
            time.sleep(5)

    def createSchedule(self):
        thread = threading.Thread(target=self.scheduleThread)
        thread.setDaemon(True)
        thread.start()
        thread.name = u'Lottery thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
        logging.debug('==== thread name is ' + thread.name.encode('utf-8'))

def user_check_in(user_name, nick_name):
    try:
        logging.debug('==== 开始')
        ret = username_link_to_db(user_name, nick_name)
        if ret < 0:
            return ret
        inner_id = ret[u'InnerId']
        ret = Database().DatabaseCheckin(inner_id)
        if ret < 0:
            return ret
        logging.debug('==== 签到成功')
        return SUCCESS
    finally:
        logging.debug('==== 结束')

def user_view_points(user_name, nick_name):
    try:
        logging.debug('==== 开始')
        ret  = username_link_to_db(user_name, nick_name)
        if ret < 0:
            return ret
        inner_id = ret[u'InnerId']
        if inner_id < 0:
            return inner_id
        cur_points = Database().DatabaseViewPoints(inner_id)
        if cur_points < 0:
            return cur_points
        logging.debug('==== 查积分成功')
        return cur_points
    finally:
        logging.debug('==== 结束')

def fix_unicode(unicode):
    unicode_dict = {u'\U0001f33f':u'\U0001f340', u'&':u'&amp;'}
    for key in unicode_dict:
        unicode = unicode.replace(key, unicode_dict[key])
    return unicode

def get_member_info(room_user_name, member_user_name=u'', member_nick_name=u''):
    ''' 通过用户的nick_name或者user_name来从群内获得用户所有信息
        member_nick_name: 用户真实昵称，注意不是群内昵称，也不是备注
        member_user_name: 用户的user_name
        如果user_name已经设置，那么不会查找nick_name
    '''
    try:
        logging.debug('==== 开始')
        if member_nick_name:
            member_nick_name = fix_unicode(member_nick_name)
        logging.debug('==== user_name: %s, nick_name: %s', member_user_name, member_nick_name)
        itchat.update_chatroom(userName=room_user_name, detailedMember=True)
        room = itchat.search_chatrooms(userName=room_user_name)
        member_list = room[u'MemberList']
        nick_names = []
        for i in range(len(member_list)):
            nick_names.append(member_list[i][u'NickName'])
            if member_user_name:
                if member_list[i][u'UserName'] == member_user_name:
                    logging.debug('==== 找到群用户信息')
                    return member_list[i]
            elif member_nick_name:
                if member_list[i][u'NickName'] == member_nick_name:
                    logging.debug('==== 找到群用户信息')
                    return member_list[i]
        logging.debug('==== nick_names_utf8: %s' % json.dumps(nick_names, ensure_ascii=False, encoding='utf-8'))
        logging.debug('==== nick_names_unic: %s' % nick_names)
        logging.debug('==== 未找到群用户信息')
        return None
    finally:
        logging.debug('==== 结束')

def AccountMark(name):
    name_mark = u''
    if re.match(r'\d{11}', name):
        name_mark = name[0:3] + u'xxxxx' + name[-4:]
    elif re.match(r'(.{3}).*(@.*\.com)', name):
        match = re.match(r'(.{3}).*(@.*\.com)', name)
        name_mark = match.group(1) + u'xxxxx' + match.group(2)
    return name_mark

def normal_command_router(msg, nick_name):
    try:
        logging.debug('==== 开始')
        to_name = msg['FromUserName']
        user_name = msg['ActualUserName']
        text = msg['Text'].strip()
        if text == u'看活动':
            Template().TemplateSendActivity(to_name)
        elif text == u'查积分':
            ret = user_view_points(user_name, nick_name)
            if ret < 0:
                if ret == WECHAT_NOT_FIND:
                    SendMessage('@msg@%s' % ('@%s 亲，数据库中未找到昵称\n可能您是新用户或者更改了昵称\n请私聊联系小叶子处理') % nick_name, to_name)
                    pass
                elif ret == WECHAT_NO_ZHIFUBAOZH:
                    SendMessage('@msg@%s' % ('@%s 您还未设置支付宝\n请私聊联系小叶子处理' % nick_name), to_name)
                    pass
                else:
                    SendMessage('@msg@%s' % ('@%s O，NO，发生了一些错误，稍后再试吧' % nick_name), to_name)
            else:
                zhifubao_mark = AccountMark(UserName_InnerId[user_name][u'ZhiFuBaoZH'])
                SendMessage('@msg@%s' % ('@%s 亲，您的支付宝账号(%s)的当前积分为：%s' % (nick_name, zhifubao_mark, ret)), to_name)
        elif text == u'签到':
            ret = user_check_in(user_name, nick_name)
            if ret < 0:
                if ret == WECHAT_ALREADY_CHECKIN:
                    zhifubao_mark = AccountMark(UserName_InnerId[user_name][u'ZhiFuBaoZH'])
                    SendMessage('@msg@%s' % ('@%s 亲，您今天已签到过一次\n支付宝账号(%s)的当前积分为：%s' % (nick_name, zhifubao_mark, user_view_points(user_name, nick_name))), to_name)
                elif ret == WECHAT_NOT_FIND:
                    SendMessage('@msg@%s' % ('@%s 亲，数据库中未找到昵称\n可能您是新用户或者更改了昵称\n请私聊联系小叶子处理') % nick_name, to_name)
                elif ret == WECHAT_NO_ZHIFUBAOZH:
                    SendMessage('@msg@%s' % ('@%s 亲，您还未设置支付宝\n请私聊联系小叶子处理' % nick_name), to_name)
                else:
                    SendMessage('@msg@%s' % ('@%s O，NO，发生了一些错误，稍后再试吧' % nick_name), to_name)
            else:
                zhifubao_mark = AccountMark(UserName_InnerId[user_name][u'ZhiFuBaoZH'])
                SendMessage('@msg@%s' % ('@%s 亲，签到成功\n您的支付宝账号(%s)的当前积分为：%s' % (nick_name, zhifubao_mark, user_view_points(user_name, nick_name))), to_name)
                # Template().TemplateSendCommand(msg[to_name])
        elif text == u'帮助':
            Template().TemplateSendCommand(to_name)
        elif text == u'积分玩法':
            Template().TemplateSendIntegralregular(to_name)
        elif text == u'积分商品':
            Template().TemplateSendIntegralGood(to_name)
        elif text == u'兑换流程':
            Template().TemplateSendExchangeProcess(to_name)
        logging.debug('==== 结束')
        return
    except Exception, e:
        log_and_send_error_msg('Exception occur', 'See log', repr(e))
        logging.error('Exception!!\nmsg: %s\nnick_name: %s\ne: %s' % (msg, nick_name, traceback.format_exc()))
        raise

def master_command_router(msg):
    try:
        logging.debug('==== 开始')
        to_name = msg['FromUserName']
        text = msg['Text'].strip()
        if text == u'命令':
            Template().TemplateSendMasterCommand(to_name)
        elif text == u'上传数据':
            SendMessage('@msg@%s' % ('主人您好，当前命令是： %s' % text), to_name)
            if UpdateToGit(is_robot=False, is_data=True) == 0:
                SendMessage('@msg@%s' % (text + u' 成功'), to_name)
            else:
                SendMessage('@msg@%s' % (text + u' 失败'), to_name)
        elif text == u'上传代码':
            SendMessage('@msg@%s' % ('主人您好，当前命令是： %s' % text), to_name)
            if UpdateToGit(is_robot=False, is_data=False) == 0:
                SendMessage('@msg@%s' % (text + u' 成功'), to_name)
            else:
                SendMessage('@msg@%s' % (text + u' 失败'), to_name)
        elif text == u'查看线程':
            SendMessage('@msg@%s' % ('主人您好，当前命令是：%s' % text), to_name)
            logging.debug(str(threading.enumerate()))
            SendMessage('@msg@%s' % (str(threading.enumerate())), to_name)
        elif text == u'查看邀请':
            SendMessage('@msg@%s' % ('主人您好，当前命令是：%s' % text), to_name)
            lines = u''
            for line in codecs.open(MEMBER_RECORD_PATH, 'rb', 'utf-8'):
                lines = lines + line
            lines = lines.strip()
            SendMessage('@msg@%s' % lines, to_name)
        elif re.match(u'查看数据#.*', text):
            ''' 通过支付宝或者昵称来查找用户信息
                默认按昵称查找
            '''
            msg_list = text.split('#')
            m = msg_list[1]
            if re.match('\d{11}', m) or re.match('.*@.*\.com', m):
                SendMessage('@msg@%s' % ('主人您好，当前命令是：%s，支付宝：%s' % (msg_list[0], m)), to_name)
                user_data = Database().DatabaseSearch(zhifubao=m)
                if user_data < 0:
                    SendMessage('@msg@%s' % '寻找用户信息出错，详情查看LOG', to_name)
                    return
            else:
                SendMessage('@msg@%s' % ('主人您好，当前命令是：%s，昵称：%s' % (msg_list[0], m)), to_name)
                room_user_name = GetRoomUserNameByNickName(TARGET_ROOM)
                info = get_member_info(room_user_name, member_nick_name=m)
                nick_name = info[u'DisplayName'] if info[u'DisplayName'] else info[u'NickName']
                user_data = Database().DatabaseSearch(nick_name=nick_name)
                if not user_data:
                    SendMessage('@msg@%s' % '寻找用户信息出错，详情查看LOG', to_name)
                    return
            user_data['_id'] = str(user_data['_id'])
            SendMessage('@msg@%s' % json.dumps(user_data, ensure_ascii=False, encoding='utf-8'), to_name)
        elif re.match(u'计算兑换积分#.*#.*', text):
            ''' 计算积分商品所需积分
            '''
            msg_list = text.split('#')
            price = msg_list[1]
            prop = msg_list[2]
            SendMessage('@msg@%s' % ('主人您好，当前命令是：%s，价格：%s，佣金比例：%s' % (msg_list[0], price, prop)), to_name)
            integral = int(round(float(price) * (1 - (eval(prop)-5)/100.0) * INTEGRAL_GOOD_PROP))
            SendMessage('@msg@%s' % ('主人您好，所需积分为：%s' % integral), to_name)
        elif re.match(u'计算奖励积分#.*#.*', text):
            ''' 计算购买商品所奖励积分
            '''
            msg_list = text.split('#')
            price = msg_list[1]
            prop = msg_list[2]
            SendMessage('@msg@%s' % ('主人您好，当前命令是：%s，价格：%s，佣金比例：%s' % (msg_list[0], price, prop)), to_name)
            integral = int(round(float(price) * INTEGRAL_PROP * eval(prop) / 100.0))
            SendMessage('@msg@%s' % ('主人您好，奖励积分为：%s' % integral), to_name)
        elif text == u'重启联盟':
            SendMessage('@msg@%s' % ('主人您好，当前命令是：%s' % text), to_name)
            package = make_package(type=u'cmd', subtype=u'rs')
            communicate_with_main().send_to_main(package)
        elif re.match(u'.*#.*#.*#ltj_.*', text):
            cmd, zhifubao, real_nick_name, inner_id = text.split('#')
            SendMessage('@msg@%s' % ('主人您好，收到命令：%s，正在处理..' % text), to_name)
            # 获取群内显示的nick_name
            room_user_name = GetRoomUserNameByNickName(TARGET_ROOM)
            info = get_member_info(room_user_name, member_nick_name=real_nick_name)
            nick_name = info[u'DisplayName'] if info[u'DisplayName'] else info[u'NickName']
            if cmd == u'更新设置':
                # 用户确定存在，但是昵称和支付宝都需要更新
                # 发生在未设置支付宝，且数据库中昵称与现在的不符
                # 需提供InnerId来设置
                ret = Database().DatabaseSetZFBNick(inner_id, nick_name, zhifubao)
                if ret < 0:
                    if ret == WECHAT_ZHIFUBAO_EXIST:
                        owner_nick_name = Database().db_table_wechat_users.find({u'AliInfo.ZhiFuBaoZH':zhifubao}).next()[u'NickName']
                        SendMessage('@msg@%s' % ('更新设置失败，支付宝重复，支付宝：%s 所属用户：%s' % (zhifubao, owner_nick_name)), to_name)
                    elif ret == WECHAT_NICKNAME_EXIST:
                        SendMessage('@msg@%s' % ('更新设置失败，群内昵称重复，群内昵称：%s' % nick_name), to_name)
                    elif ret == WECHAT_ZHIFUBAO_NICKNAME_BOTH_EXIST:
                        owner_nick_name = Database().db_table_wechat_users.find({u'AliInfo.ZhiFuBaoZH': zhifubao}).next()[u'NickName']
                        SendMessage('@msg@%s' % ('更新设置失败，支付宝和群内昵称均重复，支付宝：%s 所属用户：%s，群内昵称：%s'
                                                 % (zhifubao, owner_nick_name, nick_name)), to_name)
                    elif ret == WECHAT_ZHIFUBAO_NOT_EMPTY:
                        SendMessage('@msg@%s' % ('更新设置失败，支付宝不为空：%s' % nick_name), to_name)
                    else:
                        SendMessage('@msg@%s' % '更新设置失败，非正常原因，请查看日志', to_name)
                    return
                SendMessage('@msg@%s' % ('更新设置成功，群内昵称：%s，支付宝：%s，内部ID：%s' % (nick_name, zhifubao, inner_id)), to_name)
                zhifubao_mark = AccountMark(zhifubao)
                SendMessageToRoom(TARGET_ROOM, '@msg@%s' % ('@%s 您的账号已经激活，重新输入命令吧\n支付宝：%s' % (nick_name, zhifubao_mark)))
                pass
        # 更新支付宝昵称, 设置支付宝账号，录入新用户
        elif re.match(u'.*#.*#.*', text):
            cmd, zhifubao, real_nick_name = text.split('#')
            SendMessage('@msg@%s' % ('主人您好，收到命令：%s，正在处理..' % text), to_name)
            # 获取群内显示的nick_name
            room_user_name = GetRoomUserNameByNickName(TARGET_ROOM)
            info = get_member_info(room_user_name, member_nick_name=real_nick_name)
            if not info:
                SendMessage('@msg@%s' % ('获取群内昵称失败，输入的应该是真实昵称，不是群内或者备注昵称：%s' % real_nick_name), to_name)
                return
            nick_name = info[u'DisplayName'] if info[u'DisplayName'] else info[u'NickName']
            if cmd == u'更新':
                '''更新昵称
                '''
                ret = Database().DatabaseUpdateNickName(nick_name, zhifubao)
                if ret < 0:
                    if ret == WECHAT_NICKNAME_EXIST:
                        SendMessage('@msg@%s' % ('更新失败，群内昵称重复，群内昵称：%s' % nick_name), to_name)
                    elif ret == WECHAT_NOT_FIND:
                        SendMessage('@msg@%s' % ('更新失败，未找到支付宝，支付宝：%s' % zhifubao), to_name)
                    else:
                        SendMessage('@msg@%s' % '更新失败，非正常原因，请查看日志', to_name)
                    return
                SendMessage('@msg@%s' % ('更新成功，群内昵称：%s，支付宝：%s' % (nick_name, zhifubao)), to_name)
                zhifubao_mark = AccountMark(zhifubao)
                SendMessageToRoom(TARGET_ROOM, '@msg@%s' % ('@%s 您的账号已经激活，重新输入命令吧\n支付宝：%s' % (nick_name, zhifubao_mark)))
            elif cmd == u'新':
                ''' 新用户
                '''
                next_id_num = Database().DatabaseUserNextNumber()
                inner_id = u'ltj_' + str(next_id_num)
                father = MemberRecord().MemberRecordFindFather(nick_name)
                if father < 0:
                    father = u''
                user_data = UserData(NickName=nick_name, InnerId=inner_id, ZhiFuBaoZH=zhifubao, Father=father).Get()
                ret = Database().DatabaseAddUser(user_data)
                if ret < 0:
                    if ret == WECHAT_ZHIFUBAO_NICKNAME_BOTH_EXIST:
                        owner_nick_name = Database().db_table_wechat_users.find({u'AliInfo.ZhiFuBaoZH': zhifubao}).next()[u'NickName']
                        SendMessage('@msg@%s' % ('录入新用户失败，支付宝和群内昵称均重复，支付宝：%s 所属用户：%s，群内昵称：%s'
                                                 % (zhifubao, owner_nick_name, nick_name)), to_name)
                    elif ret == WECHAT_NICKNAME_EXIST:
                        SendMessage('@msg@%s' % ('录入新用户失败，群内昵称重复，群内昵称：%s' % nick_name), to_name)
                    elif ret == WECHAT_ZHIFUBAO_EXIST:
                        owner_nick_name = Database().db_table_wechat_users.find({u'AliInfo.ZhiFuBaoZH':zhifubao}).next()[u'NickName']
                        SendMessage('@msg@%s' % ('录入新用户失败，支付宝重复，支付宝：%s 所属用户：%s' % (zhifubao, owner_nick_name)), to_name)
                    return
                SendMessage('@msg@%s' % ('录入新用户成功，群内昵称：%s，支付宝：%s' % (nick_name, zhifubao)), to_name)
                zhifubao_mark = AccountMark(zhifubao)
                SendMessageToRoom(TARGET_ROOM, '@msg@%s' % ('@%s 您的账号已经激活，重新输入命令吧\n支付宝：%s' % (nick_name, zhifubao_mark)))
            elif cmd == u'设置':
                ''' 设置支付宝
                '''
                ret = Database().DatabaseSetZhiFuBao(nick_name, zhifubao)
                if ret < 0:
                    if ret == WECHAT_ZHIFUBAO_EXIST:
                        owner_nick_name = Database().db_table_wechat_users.find({u'AliInfo.ZhiFuBaoZH':zhifubao}).next()[u'NickName']
                        SendMessage('@msg@%s' % ('设置失败，支付宝重复，支付宝：%s 所属用户：%s' % (zhifubao, owner_nick_name)), to_name)
                    elif ret == WECHAT_NOT_FIND:
                        SendMessage('@msg@%s' % ('设置失败，未找到群内昵称，群内昵称：%s' % nick_name), to_name)
                    elif ret == WECHAT_ZHIFUBAO_NOT_EMPTY:
                        SendMessage('@msg@%s' % ('设置失败，支付宝不为空：%s' % nick_name), to_name)
                    else:
                        SendMessage('@msg@%s' % '设置失败，非正常原因，请查看日志', to_name)
                    return
                SendMessage('@msg@%s' % ('设置成功，群内昵称：%s，支付宝：%s' % (nick_name, zhifubao)), to_name)
                zhifubao_mark = AccountMark(zhifubao)
                SendMessageToRoom(TARGET_ROOM, '@msg@%s' % ('@%s 您的账号已经激活，重新输入命令吧\n支付宝：%s' % (nick_name, zhifubao_mark)))

        elif text == u'测试':
            pass
            pass
        logging.debug('==== 结束')
        return
    except Exception, e:
        log_and_send_error_msg('Exception occur', 'See log', repr(e))
        logging.error('Exception!!\nmsg: %s\ne: %s' % (msg, traceback.format_exc()))
        raise

def special_command_router(msg, nick_name):
    try:
        logging.debug('==== 开始')
        to_name = msg['FromUserName']
        user_name = msg['ActualUserName']
        text = msg['Text'].strip()
        if text == u'抽奖':
            if LotteryActivity.is_start:
                LotteryActivity().join(user_name, to_name, nick_name)
            else:
                time_s, time_e = LOTTERY_TIME.split(' ')
                cur_time = time.strftime('%H:%M', time.localtime())
                h, m = [int(i) for i in cur_time.split(':')]
                h_e, m_e = [int(i) for i in time_e.split(':')]
                if h*60+m > h_e*60+m_e:
                    SendMessage('@msg@%s' % (u'@%s 亲，抽奖活动已经结束，抽奖活动于每天【%s】开始'
                                             % (nick_name, time_s)), to_name)
                else:
                    SendMessage('@msg@%s' % (u'@%s 亲，抽奖活动将于%s开始' % (nick_name, time_s)), to_name)

        logging.debug('==== 结束')
        return
    except Exception, e:
        log_and_send_error_msg('Exception occur', 'See log', repr(e))
        logging.error('Exception!!\nmsg: %s\nnick_name: %s\ne: %s' % (msg, nick_name, traceback.format_exc()))
        raise

def group_text_reply(msg):
    try:
        logging.debug('==== 开始')
        member_info = get_member_info(msg[u'FromUserName'], msg[u'ActualUserName'])
        if not member_info:
            log_and_send_error_msg('未找到群内用户信息', 'UserName: %s' % msg[u'ActualUserName'])
            SendMessage('@msg@%s' % ('@%s O，NO，出了一些问题，稍后再试吧' % msg[u'ActualNickName']), msg[u'FromUserName'])
            return
        nick_name = member_info[u'DisplayName'] if member_info[u'DisplayName'] else member_info[u'NickName']
        text = msg[u'Text'].strip()
        if text in NORMAL_COMMAND_LIST:
            logging.debug('==== 来自：%s，聊天内容：%s' % (nick_name, msg[u'Text']))
            normal_command_router(msg, nick_name)
        if text in SPECIAL_COMMAND_LIST:
            logging.debug('==== 来自：%s，聊天内容：%s' % (nick_name, msg[u'Text']))
            special_command_router(msg, nick_name)
        # elif re.match(u'找 .*', text):
        #     key_word = text[2:].strip()
        #     logging.debug('==== 来自：%s，收到查找商品命令: %s' % (nick_name, text))
        #     package = make_package(room=msg[u'FromUserName'], user=msg[u'ActualUserName'], nick=nick_name,
        #                            content=key_word, type=u'cmd', subtype=u'find')
        #     ret = communicate_with_lianmeng().send_msg_to_lianmeng(package)
        #     if ret == QUEUE_FULL:
        #         SendMessage('@msg@%s' % ('@%s 当前查找人数太多，请稍后再试' % nick_name), msg[u'FromUserName'])
        #         return
        #     SendMessage('@msg@%s' % ('@%s 正在为您查找商品【%s】，请稍等...' % (nick_name, key_word)), msg[u'FromUserName'])
        # elif text == u'下一页':
        #     logging.debug('==== 收到命令，下一页')
        #     communicate_with_lianmeng().send_goods_to_user({u'room': msg[u'FromUserName'], u'user': msg[u'ActualUserName'], u'nick': nick_name})
        elif GetRoomUserNameByNickName(INNER_ROOM_NICK_NAME) == msg[u'FromUserName']:
            master_command_router(msg)
        logging.debug('==== 结束')
        return
    except Exception, e:
        log_and_send_error_msg('Exception occur', 'See log', repr(e))
        logging.error('Exception!!\nmsg: %s\ne: %s' % (msg, traceback.format_exc()))
        raise

def huanying(msg):
    try:
        logging.debug('==== 开始')
        str_list = msg['Content'].split('"')
        if len(str_list) < 4:  # 去除红包消息
            return
        if str_list[4].find(u'加入了群聊') == -1 and str_list[4].find(u'分享的二维码加入群聊') == -1:
            return
        logging.debug('==== ' + msg['Content'] + ' ' + GetRoomNickNameByUserName(msg[u'FromUserName']))
        SendMessage('@msg@%s' % ('欢迎亲加入【乐淘家】'), msg['FromUserName'])
        Template().TemplateSendCommand(msg['FromUserName'])
        record_t = msg['Content'] + ' ' + GetRoomNickNameByUserName(msg[u'FromUserName']) + '\r\n'
        MemberRecord().MemberRecordAddRecord(record_t)
        logging.debug('==== 结束')
        return
    except Exception, e:
        log_and_send_error_msg('Exception occur', 'See log', repr(e))
        logging.error('Exception!!\nmsg: %s\ne: %s' % (msg, traceback.format_exc()))
        raise

def GetRoomUserNameByNickName(room_nick_name):
    logging.debug('==== 开始')
    rooms = itchat.get_chatrooms()
    room_user_name = ''
    for i in range(len(rooms)):
        # print json.dumps(rooms[i][u'NickName'], ensure_ascii=False, encoding='utf-8')
        if rooms[i][u'NickName'] == room_nick_name:
            room_user_name = rooms[i][u'UserName']
            break
    logging.debug('==== 结束')
    return room_user_name

def GetRoomNickNameByUserName(room_user_name):
    logging.debug('==== 开始')
    rooms = itchat.get_chatrooms()
    room_nick_name = ''
    for i in range(len(rooms)):
        if rooms[i][u'UserName'] == room_user_name:
            room_nick_name = rooms[i][u'NickName']
            break
    logging.debug('==== 结束')
    return room_nick_name

def SendMessageToRoom(nick_name, msg):
    logging.debug('==== 开始')
    room_name = GetRoomUserNameByNickName(nick_name)
    if room_name == '':
        logging.error('==== 没找到群')
        SendMessage('报告主人：没有找到群, nick_name: ' + nick_name, u'filehelper')
        return
    else:
        SendMessage(msg, room_name)
    logging.debug('==== 结束')
    return

def make_text(dict):
    name = dict[u'商品名称']
    price = eval(dict[u'商品价格(单位：元)'])
    youhuiyuan_msg = dict[u'优惠券面额']
    if re.search(u'满(\d+)元减(\d+)元', youhuiyuan_msg):
        youhuiyuan = eval(re.search(u'满(\d+)元减(\d+)元', youhuiyuan_msg).group(2))
    elif re.search(u'(\d+)元无条件券', youhuiyuan_msg):
        youhuiyuan = eval(re.search(u'(\d+)元无条件券', youhuiyuan_msg).group(1))
    else:
        youhuiyuan = 0
    if youhuiyuan:
        kouling = dict[u'优惠券淘口令(30天内有效)']
        url = dict[u'优惠券短链接(300天内有效)']
    else:
        kouling = dict[u'淘口令(30天内有效)']
        url = dict[u'淘宝客短链接(300天内有效)']
    prop = eval(dict[u'收入比率(%)'])
    if prop > INTEGRAL_REWARD_MAX_PROP:
        prop = INTEGRAL_REWARD_MAX_PROP
    jifen = int(round((price-youhuiyuan)*INTEGRAL_PROP*prop/100.0))
    if youhuiyuan:
        text = u'%s\n【优惠券】%d 【积分】%d\n【卷后价】%d\n【领卷下单】%s\n%s,复制这条信息,打开【手机淘宝】即可下单' % \
           (name, youhuiyuan, jifen, price-youhuiyuan, url, kouling)
    else:
        text = u'%s\n【售价】%d\n【积分】%d\n【领卷下单】%s\n%s,复制这条信息,打开【手机淘宝】即可下单' % \
           (name, price, jifen, url, kouling)
    return text

def SendGoodsToUser(room_name, user_name, nick_name):
    # 制作长图和文案
    cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time())).decode('utf-8')
    db_table = pymongo.MongoClient(MONGO_URL, connect=False)[MONGO_DB_LIANMENG][MONGO_TABLE_LM_SEARCH_GOODS]
    table_cursor = db_table.find({u'user': user_name})
    if table_cursor.count() == 0:
        SendMessage('@msg@%s' % (('@%s 没有商品记录，重新搜索吧') % nick_name), room_name)
        return
    goods = table_cursor.next()[u'goods']
    goods_detail = goods[u'goods_detail']
    cursor = goods[u'cursor'] # 下一个要发送的商品
    num = len(goods_detail)
    if cursor >= num:
        SendMessage('@msg@%s' % (('@%s 没有其他商品了') % nick_name), room_name)
        return
    range_end = cursor + GOODS_PER_TIME
    if range_end > num:
        range_end = num
    pictures = {}
    for i in range(cursor, range_end):
        pictures[goods_detail[str(i)][u'主图存储路径']] = u'商品序号:%d' % i
    out_long_pic_path = PICTURES_FOLD_PATH + u'%s.jpg' % (user_name + '_longpic_' + cur_time + '_' + str(random.randint(1,1000)))
    StitchPictures(pictures, out_long_pic_path, quality=70)
    # 将长图路径更新到数据库
    db_table.update_one({u'user': user_name}, {"$set": {u'goods.long_pic.%s' % cur_time: out_long_pic_path}})
    # 发送文案和长图
    to_name = room_name
    if range_end != num:
        SendMessage('@msg@%s' % (('@%s 共找到%d个商品，当前%d/%d页\n回复【下一页】，查看下页商品') %
                    (nick_name, num, (cursor/GOODS_PER_TIME)+1, ((num-1)/GOODS_PER_TIME)+1)), to_name)
    else:
        SendMessage('@msg@%s' % (('@%s 共找到%d个商品，当前%d/%d页') %
                    (nick_name, num, (cursor / GOODS_PER_TIME)+1, (num / GOODS_PER_TIME)+1)), to_name)
    SendMessage('@img@%s' % out_long_pic_path, to_name)
    for i in range(cursor, range_end):
        SendMessage('@msg@%s' % (('商品序号:%d\n' % i) + make_text(goods_detail[str(i)])), to_name)
    # 发送成功之后，更新cursor
    db_table.update_one({'user': user_name}, {"$set": {u'goods.cursor': range_end}})
    # 删除用过的图片
    for pic in pictures:
        os.remove(pic)
    os.remove(out_long_pic_path)

@itchat.msg_register(itchat.content.NOTE, isGroupChat=True)
def ItchatMessageNoteGroup(msg):
    if msg['FromUserName'] not in monitor_room_user_name:
        return
    p = threading.Thread(target=huanying, args=(msg,))
    p.name = 'ItchatMessageNoteGroup ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
    p.setDaemon(True)
    p.start()
    logging.debug('==== thread name is ' + p.name)
    return

@itchat.msg_register(itchat.content.TEXT, isGroupChat=True)
def ItchatMessageTextGroup(msg):
    if msg['FromUserName'] not in monitor_room_user_name:
        return
    p = threading.Thread(target=group_text_reply, args=(msg,))
    p.name = 'ItchatMessageTextGroup ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
    p.setDaemon(True)
    p.start()
    logging.debug('==== thread name is ' + p.name + ' nick name is ' + msg['ActualNickName'])
    return

@itchat.msg_register(itchat.content.TEXT)
def ItchatMessageTextSingle(msg):
    pass

################ UI界面相关 #################

class TextWindow(wx.TextCtrl):
    def __init__(self, parent, id=-1, value=u'', pos=wx.DefaultPosition, size=(300, 25)):
        wx.TextCtrl.__init__(self, parent, id, value, pos, size)
        self.SetMinSize(size)

class StaticWindow(wx.StaticText):
    def __init__(self, parent, id=-1, label=u'', pos=wx.DefaultPosition, size=(100, 25)):
        wx.StaticText.__init__(self, parent, id, label, pos, size)
        self.SetMinSize(size)

# class MyTable(wx.grid.PyGridTableBase):
#     def __init__(self):
#         wx.grid.PyGridTableBase.__init__(self)
#         self.database_data = Database().DatabaseGetAllData()
#         self.labels = Database().DatabaseGetLabels()
#         self.col_labels = self.labels[1]
#         self.row_labels = self.labels[0]
#
#     def GetNumberRows(self):
#         return len(self.row_labels)
#
#     def GetNumberCols(self):
#         return len(self.col_labels)
#
#     def GetColLabelValue(self, col):
#         return self.col_labels[col]
#
#     def GetRowLabelValue(self, row):
#         return self.row_labels[row]
#
#     def IsEmptyCell(self,row,col):
#         return False
#
#     def GetValue(self,row,col):
#         value = self.database_data[self.row_labels[row]][self.col_labels[col]]
#         return value
#
#     def SetValue(self,row,col,value):
#         pass
#
#     def GetAttr(self,row,col,kind):
#         pass

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
        self.panel_l.SetBackgroundColour('White')
        mbox.Add(self.panel_l, 0, flag=wx.ALL, border=10)

        box_l_1 = self.MakeStaticBoxSizer(self.panel_l, u"订单录入", label_ddlr)
        box_l_2 = self.MakeStaticBoxSizer(self.panel_l, u"积分兑换", label_jfdh)
        box_1_5 = self.MakeStaticBoxSizer(self.panel_l, u"奖励积分", label_jljf)
        button_normal_lr = wx.Button(self.panel_l, -1, u'普通录入', size=(100,30))
        self.panel_l.Bind(wx.EVT_BUTTON, self.OnNLRClick, button_normal_lr)
        button_search_lr = wx.Button(self.panel_l, -1, u'查找录入', size=(100,30))
        self.panel_l.Bind(wx.EVT_BUTTON, self.OnSLRClick, button_search_lr)
        button_dh = wx.Button(self.panel_l, -1, u'确认', size=(80, 30))
        self.panel_l.Bind(wx.EVT_BUTTON, self.OnDHClick, button_dh)
        button_bak = wx.Button(self.panel_l, -1, u'备份数据', size=(80, 30))
        self.panel_l.Bind(wx.EVT_BUTTON, self.OnBAKClick, button_bak)
        button_jl = wx.Button(self.panel_l, -1, u'确认', size=(80, 30))
        self.panel_l.Bind(wx.EVT_BUTTON, self.OnJLClick, button_jl)

        box_l_1_1 = wx.BoxSizer(wx.HORIZONTAL)
        box_l_1_1.Add(button_normal_lr, 0, wx.ALL | wx.ALIGN_RIGHT, 5)
        box_l_1_1.Add(button_search_lr, 0, wx.ALL | wx.ALIGN_RIGHT, 5)

        box_l_4 = wx.BoxSizer(wx.HORIZONTAL)

        box_l = wx.BoxSizer(wx.VERTICAL)
        box_l.Add(button_bak, 0, wx.ALL | wx.ALIGN_RIGHT, 5)
        box_l.Add(box_l_1, 0, wx.ALL, 5)
        box_l.Add(box_l_1_1, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 5)
        box_l.Add((-1,5))
        box_l.Add(box_l_2, 0, wx.ALL, 5)
        box_l.Add(button_dh, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 5)
        box_l.Add(box_l_4, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 5)
        box_l.Add(box_1_5, 0, wx.ALL, 5)
        box_l.Add(button_jl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 5)

        self.panel_l.SetSizer(box_l)

        panel.SetSizer(mbox)
        mbox.Fit(self)

    def OnNLRClick(self, event):
        logging.debug('==== 开始')
        inner_id = self.ddlr_objs[u'会员名'].GetValue().strip()
        number = self.ddlr_objs[u'订单编号'].GetValue().strip()
        price = self.ddlr_objs[u'订单价格'].GetValue().strip()
        prop = self.ddlr_objs[u'佣金比例'].GetValue().strip()
        ret = IntegralGoods().inputInteral(inner_id, number, price, prop)
        if ret < 0:
            return
        logging.debug('==== 结束')

    def OnSLRClick(self, event):
        logging.debug('==== 开始')
        inner_id = self.ddlr_objs[u'会员名'].GetValue().strip()
        number = self.ddlr_objs[u'订单编号'].GetValue().strip()
        files = os.listdir(INTEGRAL_INPUT_FOLD)
        for f in files:
            if re.match('TaokeDetail-.*\.xls', f):
                file = os.path.join(INTEGRAL_INPUT_FOLD, f)
                break
        else:
            print(u'没有找到报表文件')
            return
        wb = xlrd.open_workbook(file)
        ws = wb.sheets()[0]
        title = ws.row_values(0)
        for i in range(1, ws.nrows):
            if number in ws.row_values(i):
                info = dict(zip(title, ws.row_values(i)))
                name, status, price, prop = [str(info[i]) for i in (u'商品信息', u'订单状态', u'结算金额', u'佣金比率')]
                if status != u'订单结算':
                    print(u'订单未结算, 当前状态为%s' % status)
                    return
                break
        else:
            print(u'没有找到订单, %s' % number)
            return
        self.ddlr_objs[u'订单价格'].SetValue(price)
        self.ddlr_objs[u'佣金比例'].SetValue(prop)
        self.ddlr_objs[u'商品名称'].SetValue(name)
        prop = prop.split(' ')[0]
        ret = IntegralGoods().inputInteral(inner_id, number, price, prop)
        if ret < 0:
            return
        logging.debug('==== 结束')


    def OnDHClick(self, event):
        logging.debug('==== 开始')
        inner_id = self.jfdh_objs[u'会员名'].GetValue().strip()
        jp_num = self.jfdh_objs[u'商品编号'].GetValue().strip()
        price = self.jfdh_objs[u'商品价格'].GetValue().strip()
        #TODO 应该从积分商品列表中获取当前商品的佣金比例，如果未找到此商品则返回错
        prop = self.jfdh_objs[u'佣金比例'].GetValue().strip()
        number = self.jfdh_objs[u'订单编号'].GetValue().strip()
        ret = IntegralGoods().exchangeGoods(inner_id, jp_num, price, prop, number)
        if ret < 0:
            return
        logging.debug('==== 结束')

    def OnBAKClick(self, event):
        logging.debug('==== 开始')
        logging.debug('==== 备份数据')
        UpdateToGit(is_data=True, is_robot=False)
        logging.debug('==== 结束')

    def OnJLClick(self, event):
        logging.debug('==== 开始')
        inner_id = self.jljf_objs[u'会员名'].GetValue().encode('utf-8').strip()
        integral = self.jljf_objs[u'奖励积分'].GetValue().strip()
        logging.debug('==== 会员：%s，奖励积分：%s' % (inner_id, integral))
        if not (inner_id and integral):
            logging.error("==== 输入数据有误")
            return
        ret = Database().DatabaseChangePoints(inner_id, eval(integral))
        if ret == 0:
            cur_points = Database().DatabaseViewPoints(inner_id)
            IntegralRecord().IntegralRecordAddRecord(inner_id, u'奖励积分', 'None', 'None', integral, str(cur_points))
            info = Database().DatebaseGetInfoByInnerId(inner_id)
            nick_name = info[u'NickName']
            zhifubao_mark = AccountMark(info[u'AliInfo'][u'ZhiFuBaoZH'])
            SendMessageToRoom(TARGET_ROOM,
                              '@msg@%s' % ('@%s 亲，活动奖励积分【%s】已录入\n'
                              '您的支付宝账号(%s)的当前积分为：%s' % (nick_name, integral, zhifubao_mark, repr(cur_points))))
        logging.debug('==== 结束')

    def MakeStaticBoxSizer(self, parent, boxlabel, labels):
        box = wx.StaticBox(parent, -1, boxlabel)
        sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        sizer2_1 = wx.BoxSizer(wx.VERTICAL)
        sizer2_2 = wx.BoxSizer(wx.VERTICAL)
        for a in labels:
            bw1 = StaticWindow(parent, label=a)
            sizer2_2.Add(bw1, 0, wx.ALL, 2)
            bw = TextWindow(parent)
            if labels == label_ddlr:
                self.ddlr_objs[a] = bw
            elif labels == label_jfdh:
                self.jfdh_objs[a] = bw
            elif labels == label_jljf:
                self.jljf_objs[a] = bw
            sizer2_1.Add(bw, 0, wx.ALL, 2)
        if labels == label_ddlr:
            bw2 = wx.TextCtrl(parent, -1, u'商品名称', size=(400,50), style=wx.TE_MULTILINE)
            self.ddlr_objs[u'商品名称'] = bw2
            sizer1 = wx.BoxSizer(wx.HORIZONTAL)
            sizer1.Add(bw2, 0, wx.ALL, 10)
            sizer.Add(sizer1, 0, wx.ALL, 10)
        sizer2.Add(sizer2_2, 0, wx.ALL, 10)
        sizer2.Add(sizer2_1, 0, wx.ALL, 10)
        sizer.Add(sizer2, 0, wx.ALL, 10)
        return sizer

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

def UpdateToGit(is_robot=True, is_data=True):
    logging.debug('==== GIT开始上传数据')
    cnt = 0
    if is_data:
        os.chdir(MONGO_DB_DUMP_FOLD)
        os.system('mongodump')
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
            logging.debug('==== GIT上传成功')
            return 0
        else:
            cnt += 1
            logging.debug('==== GIT本次上传失败， cnt: %d' % cnt)
            if cnt >= 3:
                log_and_send_error_msg('GIT上传失败')
                return -1

def CleanThread():
    while True:
        logging.debug('==== CLEAN THREAD 开始清理数据')
        # clean pic
        logging.debug('==== CLEAN THREAD 正在清理过期搜索记录和图片')
        time_ori = int(time.time())
        db_table = pymongo.MongoClient(MONGO_URL, connect=False)[MONGO_DB_LIANMENG][MONGO_TABLE_LM_SEARCH_GOODS]
        cursor = db_table.find({})
        if cursor.count() != 0:
            for info in cursor:
                if info['goods']['search_time_ori'] <= time_ori - SEARCH_CLEAN_TIME_INTERVAL:
                    # del pic in old info
                    for good in info['goods']['goods_detail'].items():
                        path = good[1][u'主图存储路径']
                        if os.path.exists(path):
                            os.remove(path)
                    if 'long_pic' in info['goods']:
                        for pic in info['goods']['long_pic'].items():
                            path = pic[1]
                            if os.path.exists(path):
                                os.remove(path)
                    # del info self
                    db_table.delete_one({'_id': ObjectId(info['_id'])})
        # clean log
#        logging.debug('==== CLEAN THREAD 正在清理过期LOG')
#        log_files = os.listdir(LOG_FOLD)
#        for file in log_files:
#            if int(file.split('_')[1]) < time_ori - LOG_CLEAN_TIME_INTERVAL:
#                os.remove(LOG_FOLD+file)
        # clean codeimage, 只保留最后一个
        logging.debug('==== CLEAN THREAD 正在清理残留的codeimage')
        image_files = os.listdir(CODE_IMAGE_FOLD_PATH)
        reserve_file = ''
        for file in image_files:
            if file.startswith('codeimage'):
                if not reserve_file:
                    reserve_file = file
                    continue
                if file > reserve_file:
                    os.remove(CODE_IMAGE_FOLD_PATH + reserve_file)
                    reserve_file = file
        # TODO:clean err img


        logging.debug('==== CLEAN THREAD 结束')
        time.sleep(CLEAN_THREAD_INTERVAL)

def CreateCleanThread():
    git_thread = threading.Thread(target=CleanThread)
    git_thread.setDaemon(True)
    git_thread.start()
    git_thread.name = u'Clean thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
    logging.debug('==== thread name is ' + git_thread.name.encode('utf-8'))

def GitUpdateThread():
    while True:
        UpdateToGit()
        time.sleep(GIT_UPLOAD_INTERVAL)

def CreateGitThread():
    git_thread = threading.Thread(target=GitUpdateThread)
    git_thread.setDaemon(True)
    git_thread.start()
    git_thread.name = u'GIT thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
    logging.debug('==== thread name is ' + git_thread.name.encode('utf-8'))

def make_package(type, room=u'', content=u'', subtype=u'', user=u'', nick=u''):
    d = (type, subtype, {u'room': room, u'content': content, u'user': user, u'nick': nick})
    return d

class communicate_with_lianmeng:
    q_out = None
    q_in = None

    def send_msg_to_lianmeng(self,package):
        try:
            self.q_out.put_nowait(package)
            return SUCCESS
        except Queue.Full:
            return QUEUE_FULL

    def browser_init(self):
        # 根据LIST来初始化相应的browser
        for room in MONITOR_ROOM_LIST:
            room_name = GetRoomUserNameByNickName(room)
            package = make_package(type=u'cmd', subtype=u'init', room=room_name)
            ret = self.send_msg_to_lianmeng(package)
            if ret == QUEUE_FULL:
                log_and_send_error_msg('browser init failed', '', 'Queue full')

    def send_goods_to_user(self, msg):
        p = threading.Thread(target=SendGoodsToUser, args=(msg[u'room'], msg[u'user'], msg[u'nick']))
        p.name = u'SendGoodsToUser, %s, %s' % (time.strftime('%d_%H%M%S', time.localtime(time.time())), msg[u'nick'])
        p.setDaemon(True)
        p.start()
        logging.debug('==== thread name is ' + p.name)

    def receive_from_lianmeng_thread(self):
        while True:
            logging.info('开始接收来自lianmeng进程命令')
            package = self.q_in.get()
            type = package[0]
            sub_type = package[1]
            msg = package[2]
            logging.debug('收到lianmeng进程命令, %s %s %s' % (type, sub_type, msg))
            if type == u'response':
                if sub_type == u'rfind':
                    if msg[u'content'] == SUCCESS:
                        self.send_goods_to_user(msg)
                    elif msg[u'content'] == LM_NO_GOODS:
                        SendMessage('@msg@%s' % (('@%s 没有找到商品，换个搜索词试试吧') % msg[u'nick']), msg[u'room'])
                    elif msg[u'content'] == LM_RETRY_TIME_OUT:
                        SendMessage('@msg@%s' % (('@%s 网络出了些问题，稍后再试吧') % msg[u'nick']), msg[u'room'])
                elif sub_type == u'rinit':
                    if msg[u'content'] == SUCCESS:
                        pass
                    elif msg[u'content'] == LM_RETRY_TIME_OUT:
                        log_and_send_error_msg('浏览器初始化失败', '', 'RETRY TIME OUT')
            elif type == u'notice':
                if sub_type == u'login':
                    SendMessageToRoom(INNER_ROOM_NICK_NAME, '@msg@%s' % '请登录淘宝账号')
                    SendMessageToRoom(INNER_ROOM_NICK_NAME, '@img@%s' % msg[u'content'])
                elif sub_type == u'login_on_phone':
                    SendMessageToRoom(INNER_ROOM_NICK_NAME, '@msg@%s' % '请在手机上点击确认来登录淘宝账号')
                elif sub_type == u'rlogin':
                    if msg[u'content'] == u'success':
                        SendMessageToRoom(INNER_ROOM_NICK_NAME, '@msg@%s' % '淘宝登录成功')
                    elif msg[u'content'] == u'fail':
                        SendMessageToRoom(INNER_ROOM_NICK_NAME, '@msg@%s' % '淘宝登录失败')

    def create_receive_from_lianmeng_thread(self):
        thread = threading.Thread(target=self.receive_from_lianmeng_thread,)
        thread.setDaemon(True)
        thread.start()
        thread.name = u'receive_from_lianmeng thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
        logging.debug('==== thread name is ' + thread.name.encode('utf-8'))

class communicate_with_main:
    q_out = None
    q_in = None
    def create_receive_from_main_thread(self):
        thread = threading.Thread(target=self.receive_from_main_thread,)
        thread.setDaemon(True)
        thread.start()
        thread.name = 'receive_from_main thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
        logging.debug('==== thread name is ' + thread.name)

    def receive_from_main_thread(self):
        while True:
            logging.info('开始接收Main进程命令')
            package = self.q_in.get()
            type, subtype, msg = package
            logging.debug('收到Main进程命令 %s %s %s' % (type, subtype, msg))
            if type == u'cmd':
                if subtype == u'UI':
                    logging.debug('开始创建UI线程')
                    CreateUiThread()
            elif type == u'response':
                if subtype == u'rrs':
                    if msg[u'content'] == u'success':
                        communicate_with_lianmeng().browser_init()
                        SendMessageToRoom(INNER_ROOM_NICK_NAME, '重启联盟进程OK')
    def send_to_main(self, package):
        communicate_with_main.q_out.put(package)

def init_thread(q_main_wechat, q_wechat_main, q_wechat_lianmeng, q_lianmeng_wechat):
    logging.info('init_thread: 创建GIT线程')
    CreateGitThread()
    logging.info('init_thread: 创建CLEAN线程')
    CreateCleanThread()
    logging.info('init_thread: 创建接收main进程命令的线程')
    communicate_with_main.q_out = q_wechat_main
    communicate_with_main.q_in = q_main_wechat
    communicate_with_main().create_receive_from_main_thread()
    # 等待微信初始化
    time.sleep(2)
    for room in MONITOR_ROOM_LIST:
        monitor_room_user_name.append(GetRoomUserNameByNickName(room))
    logging.info('init_thread: 创建接收lianmeng进程命令的线程')
    #communicate_with_lianmeng.q_out = q_wechat_lianmeng
    #communicate_with_lianmeng.q_in = q_lianmeng_wechat
    #communicate_with_lianmeng().create_receive_from_lianmeng_thread()
    #communicate_with_lianmeng().browser_init()
    logging.info('init_thread: 创建抽奖线程')
    LotteryActivity().createSchedule()

def create_init_thread(q_main_wechat, q_wechat_main, q_wechat_lianmeng, q_lianmeng_wechat):
    thread = threading.Thread(target=init_thread, args=(q_main_wechat, q_wechat_main, q_wechat_lianmeng, q_lianmeng_wechat))
    thread.setDaemon(True)
    thread.start()
    thread.name = 'init_thread thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
    logging.debug('==== thread name is ' + thread.name)

def wechat_main(q_main_wechat, q_wechat_main, q_wechat_lianmeng, q_lianmeng_wechat):
    logging.info('wechat_main: 进程开始')
    # itchat.auto_login(picDir=WECHAT_QR_PATH, hotReload=False)
    itchat.auto_login(picDir=WECHAT_QR_PATH, hotReload=True)
    logging.info('wechat_main: 创建init进程开始')
    create_init_thread(q_main_wechat, q_wechat_main, q_wechat_lianmeng, q_lianmeng_wechat)
    itchat.run()
