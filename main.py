#coding:utf-8
import re
import time

from wechat import wechat_main
from lianmeng import lianmeng_main
from multiprocessing import Queue, Process

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

    # while True:
    #     msg = raw_input('enter cmd: ')
    #     if msg == 'UI':
    #         print u'输入了UI命令，将命令发送到wechat进程'
    #         q_main_wechat.put(('cmd', 'UI'))
    #     elif re.match(u'找.*', msg):
    #         print msg
    #         q_wechat_lianmeng.put(('find', msg))
    #     else:
    #         pass
    for i in '哈衣 隔尿垫 纸尿裤 口水巾 情趣内衣'.split(' '):
        q_wechat_lianmeng.put((i, 'ltj_1'))
    while True:
        time.sleep(10)
