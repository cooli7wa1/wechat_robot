#coding:utf8
from wxpy import *
bot = Bot(cache_path=True)

group = bot.groups().search(u'内部信息')[0]
group.update_group(members_details=True)
for member in group:
    print member.raw
embed()

