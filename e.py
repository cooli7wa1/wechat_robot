#coding:utf8
from bson import ObjectId

from wechat_config import *
from common_config import *
import pymongo

client = pymongo.MongoClient(MONGO_URL, connect=False)
table = client[MONGO_DB_LIANMENG][MONGO_TABLE_LM_SEARCH_GOODS]
cursor = table.find({'_id': ObjectId("594f9ea3d6936b1110f0dc7e")})
info = cursor.next()
table.delete_one({'_id': ObjectId(info['_id'])})
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