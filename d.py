#coding:utf8
import inspect

import itchat
import json
from io import BytesIO, StringIO
from wechat_config import *
from hashlib import md5

def GetRoomNameByNickName(nick_name):
    rooms = itchat.get_chatrooms()
    room_name = ''
    for i in range(len(rooms)):
        if rooms[i]['NickName'] == nick_name:
            room_name = rooms[i]['UserName']
            break
    return room_name

def log_and_send_error_msg(title=u'', detail=u'', reason=u''):
    stack = inspect.stack()
    func_name = stack[1][3]
    lineno = stack[1][2]
    logging.error(u'[%s][%s]\r\n%s\r\n%s\r\n%s' % (func_name, lineno, title, detail, reason))
    itchat.send('@msg@%s' % (u'错误\nTitle: %s\nDetail: %s' % (title, detail)), 'filehelper')




@itchat.msg_register(itchat.content.SHARING, isGroupChat=True)
def ItchatMessageTextGroup(msg):
    if msg['FromUserName'] not in monitor_room_user_name:
        return
    print 'SHARING'
    print json.dumps(msg, ensure_ascii=False, encoding='utf-8')
    # user_name = itchat.search_friends(nickName=u'杨思')[0]['UserName']
    # a = itchat.get_head_img(userName=user_name)
    # itchat.get_head_img(userName=user_name, picDir='head_rickey.jpg')
    # print md5(a).hexdigest()
    # user_name = itchat.search_friends(nickName=u'小叶子')[0]['UserName']
    # a = itchat.get_head_img(userName=user_name)
    # itchat.get_head_img(userName=user_name, picDir='head_xiaoyezi.jpg')
    # print md5(a).hexdigest()
    # itchat.send('haha', 'filehelper')
    # itchat.send('@img@/home/cooli7wa/Documents/robot_data/QR.png', 'filehelper')
    # f = StringIO(u'head_img')
    # itchat.send('@img@head.jpg', 'filehelper')
    # itchat.update_chatroom(userName=msg['FromUserName'], detailedMember=True)
    # print json.dumps(itchat.search_chatrooms(userName=msg['FromUserName']), ensure_ascii=False, encoding='utf-8')
    # print json.dumps(msg, ensure_ascii=False, encoding='utf-8')
@itchat.msg_register(itchat.content.TEXT, isGroupChat=True)
def ItchatMessageTextGroup(msg):
    if msg['FromUserName'] not in monitor_room_user_name:
        return
    print 'TEXT'
    print json.dumps(msg, ensure_ascii=False, encoding='utf-8')

itchat.auto_login()
for room in MONITOR_ROOM_LIST:
    monitor_room_user_name.append(GetRoomNameByNickName(room))
itchat.run()