from wechat_config import *
from common_config import *
import pymongo

client = pymongo.MongoClient(MONGO_URL, connect=False)
table = client[MONGO_DB_WECHAT][MONGO_TABLE_WECHAT_USERS]

print table.find({'WechatInfo.Sex':''})
