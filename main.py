#coding:utf-8
import re
import time

from wechat import wechat_main
from lianmeng import lianmeng_main
from multiprocessing import Queue, Process

def make_package(room=u'', user=u'', remark=u'', nick=u'', keyword=u''):
    d = {'room':room, 'user':user, 'remark':remark, 'nick':nick, 'keyword':keyword}
    return d

if __name__ == '__main__':
    q_main_wechat = Queue(3)
    q_wechat_main = Queue(3)
    q_wechat_lianmeng = Queue(3)
    q_lianmeng_wechat = Queue(3)

    p_wechat = Process(target=wechat_main, name='wechat_main', args=(q_main_wechat, q_wechat_main, q_wechat_lianmeng, q_lianmeng_wechat,))
    p_wechat.daemon = True
    p_wechat.start()

    p_lianmeng = Process(target=lianmeng_main, name='lianmeng_main', args=(q_wechat_lianmeng, q_lianmeng_wechat,))
    p_lianmeng.daemon = True
    p_lianmeng.start()

    while True:
        msg = raw_input('enter cmd: ').decode('utf-8')
        if msg == 'UI':
            print u'输入了UI命令，将命令发送到wechat进程'
            q_main_wechat.put(('cmd', msg))
        elif re.match(u'找.*', msg):
            print u'输入了找..命令，将命令发送到lianmeng进程'
            find_package = make_package(room=u'default', user=u'123456', remark=u'ltj_1', nick=u'Rickey', keyword=msg[1:])
            q_wechat_lianmeng.put(('find', find_package))
        elif msg == u'下一个':
            print u'输入了，下一个，将命令发送到wechat进程'
            q_main_wechat.put(('cmd', msg))
        else:
            pass

    # for i in u'哈衣 隔尿垫 纸尿裤 口水巾 婴儿纸巾'.split(' '):
    #     find_package = make_package(room=u'default', user=u'123456', remark=u'ltj_1', nick=u'Rickey', keyword=i)
    #     q_wechat_lianmeng.put(('find', find_package))
    # while True:
    #     time.sleep(10)
