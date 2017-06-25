#coding:utf8
import json
import itchat
from wechat_config import *
from common_config import *
import shelve, pymongo

data_path = DATABASE_FOLD + 'points_database.dat'
mongodb_client = pymongo.MongoClient(MONGO_URL, connect=False)
db_table_wechat_users = mongodb_client[MONGO_DB_WECHAT][MONGO_TABLE_WECHAT_USERS]

user_data = {}
user_total = {}
number = 0

def movedb(room_name):
    members_list = itchat.search_chatrooms(userName=room_name)[u'MemberList']
    database_old = shelve.open(data_path)
    for user in database_old:
        find_nick = False
        user_data = {}
        user_data_tmp = database_old[user]
        user_data[u'NickName'] = u''
        for i in range(len(members_list)):
            if members_list[i][u'NickName'] == user_data_tmp[u'nick_name']:
                user_data[u'NickName'] = members_list[i][u'DisplayName'] if members_list[i][u'DisplayName'] else members_list[i][u'NickName']
                find_nick = True
        if not find_nick:
            print u'未找到 %s' % user_data_tmp[u'nick_name']
        user_data[u'InnerId'] = user.decode('utf-8')
        user_data[u'Group'] = user_data_tmp[u'group']
        user_data[u'Grade'] = user_data_tmp[u'grade']
        user_data[u'Points'] = user_data_tmp[u'points']
        user_data[u'LastCheckIn'] = user_data_tmp[u'last_check_in']
        user_data[u'Father'] = user_data_tmp[u'father']
        user_data[u'AliInfo'] = {u'ZhiFuBaoZH':''}
        user_data[u'WechatInfo'] = {u'Province':'', u'City':'', u'Sex':''}
        # print json.dumps(user_data, ensure_ascii=False, encoding='utf-8')
        db_table_wechat_users.insert(user_data)

def GetRoomNameByNickName(nick_name):
    rooms = itchat.get_chatrooms()
    room_name = ''
    for i in range(len(rooms)):
        if rooms[i]['NickName'] == nick_name:
            room_name = rooms[i]['UserName']
            break
    return room_name

itchat.auto_login(hotReload=True)
for room in MONITOR_ROOM_LIST:
    monitor_room_user_name.append(GetRoomNameByNickName(room))
room_name = GetRoomNameByNickName(ROOM_NICK_NAME)
itchat.update_chatroom(userName=room_name, detailedMember=True)
movedb(room_name)
itchat.run()




