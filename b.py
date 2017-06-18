#coding:utf8
import random
import re

import pymongo
import time

from lianmeng_config import *

def make_text(dict):
    name = dict[u'商品名称']
    price = eval(dict[u'商品价格(单位：元)'])
    youhuiyuan = eval(re.search(r'(\d+)',dict[u'优惠券面额']).group(1)) # 如果没有优惠券是'无'，这里返回''
    if youhuiyuan:
        kouling = dict[u'优惠券淘口令(30天内有效)']
    else:
        kouling = dict[u'淘口令(30天内有效)']
    prop = eval(dict[u'收入比率(%)'])
    jifen = int(round(price*10*prop/100.0))
    text = u'%s\n【在售价】%d【卷后价】%d【积分】%d\n【领卷下单】%s\n复制这条信息,打开【手机淘宝】即可下单' % \
           (name, price, price-youhuiyuan, jifen, kouling)
    return text


# client = pymongo.MongoClient(MONGO_URL, connect=False)
# db_table = client[MONGO_DB][MONGO_TABLE]
# cursor = db_table.find({'user':'123456'})
# for i in cursor:
#     dict =  i['goods_20170617235646']['1']
#     print dict
#     print make_text(dict)

a = []
for i in range(100):
    cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time()))
    name = cur_time + '_' + str(random.randint(1,1000))
    print name
    a.append(name)

b = list(set(a))
print len(b)
