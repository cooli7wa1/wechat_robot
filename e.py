#coding:utf8
from bson import ObjectId

from wechat_config import *
from common_config import *
import pymongo

client = pymongo.MongoClient(MONGO_URL, connect=False)
table = client[MONGO_DB_WECHAT][MONGO_TABLE_WECHAT_USERS]
cursor = table.find({})
for user in cursor:
    p = user['Points']
    inner_id = user['InnerId']
    if inner_id != 'ltj_0':
        table.update_one({'InnerId':inner_id}, {"$set": {u'Points': p+10}})
# cursor = table.find({})
# print cursor.count()
# info = cursor.next()
# for good in info['goods']['goods_detail'].items():
#     path = good[1][u'主图存储路径']
#     if os.path.exists(path):
#         print path
#         # os.remove(path)
# if 'long_pic' in info['goods']:
#     for pic in info['goods']['long_pic'].items():
#         path = pic[1]
#         if os.path.exists(path):
#             print path
#             # os.remove(path)