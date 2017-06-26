#coding:utf-8
import os
import re
import threading
import time
from common_config import *

from wechat import wechat_main
from lianmeng import lianmeng_main
from multiprocessing import Queue, Process

def make_package(room=u'', user=u'', remark=u'', nick=u'', keyword=u''):
    d = {'room':room, 'user':user, 'remark':remark, 'nick':nick, 'keyword':keyword}
    return d

class OtherProcess:
    q_main_wechat = Queue(3)
    q_wechat_main = Queue(3)
    q_wechat_lianmeng = Queue(3)
    q_lianmeng_wechat = Queue(3)
    p_wechat = None
    p_lianmeng = None

    def InitOtherProcess(self):
        OtherProcess.p_wechat = Process(target=wechat_main, name=u'wechat_main',
                           args=(OtherProcess.q_main_wechat, OtherProcess.q_wechat_main,
                                 OtherProcess.q_wechat_lianmeng, OtherProcess.q_lianmeng_wechat,))
        # p_wechat.daemon = True
        OtherProcess.p_wechat.start()
        logging.info('Init wechat 进程 ok')

        OtherProcess.p_lianmeng = Process(target=lianmeng_main, name=u'lianmeng_main',
                                          args=(OtherProcess.q_wechat_lianmeng, OtherProcess.q_lianmeng_wechat,))
        OtherProcess.p_lianmeng.daemon = True
        OtherProcess.p_lianmeng.start()
        logging.info('Init lianmeng 进程 ok')

    def TerminateProcess(self, p):
        p.terminate()
        while p.is_alive():
            time.sleep(0.5)
            logging.info('等待终止进程')
        logging.info('已经终止进程')

    def StartProcess(self, p_name):
        if p_name == u'wechat':
            OtherProcess.p_wechat = Process(target=wechat_main, name=u'wechat_main',
                                            args=(OtherProcess.q_main_wechat, OtherProcess.q_wechat_main,
                                                  OtherProcess.q_wechat_lianmeng, OtherProcess.q_lianmeng_wechat,))
            # p_wechat.daemon = True
            OtherProcess.p_wechat.start()
            logging.info('已重启wechat进程')
        elif p_name == u'lianmeng':
            OtherProcess.p_lianmeng = Process(target=lianmeng_main, name=u'lianmeng_main',
                                              args=(OtherProcess.q_wechat_lianmeng, OtherProcess.q_lianmeng_wechat,))
            OtherProcess.p_lianmeng.daemon = True
            OtherProcess.p_lianmeng.start()
            logging.info('已重启lianmeng进程')

class communicate_with_wechat:
    q_out = None
    q_in = None
    def create_receive_from_wechat_thread(self):
        thread = threading.Thread(target=self.receive_from_wechat_thread,)
        thread.setDaemon(True)
        thread.start()
        thread.name = 'receive_from_wechat thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
        logging.debug('==== thread name is ' + thread.name)

    def receive_from_wechat_thread(self):
        while True:
            logging.info('开始接收wechat进程命令')
            type, msg = self.q_in.get()
            logging.debug('收到wechat进程命令 %s %s' % (type, msg))
            if type == 'cmd':
                if msg == 'rs_lm_process':
                    logging.debug('开始重启liangmeng进程')
                    OtherProcess().TerminateProcess(OtherProcess.p_lianmeng)
                    OtherProcess().StartProcess(u'lianmeng')
                    communicate_with_wechat().send_to_wechat(u'response', u'rs_lm_process_ok')
    def send_to_wechat(self, type, msg):
        OtherProcess.q_main_wechat.put((type, msg))

if __name__ == '__main__':
    OtherProcess().InitOtherProcess()
    communicate_with_wechat.q_in = OtherProcess.q_wechat_main
    communicate_with_wechat.q_out = OtherProcess.q_main_wechat
    communicate_with_wechat().create_receive_from_wechat_thread()

    os_home = os.popen('echo $HOME').read().replace('\n', '')
    if not os_home == u'/root':
    # if 0:
        while True:
            input = raw_input('enter cmd: ').decode('utf-8')
            if input == u'UI':
                communicate_with_wechat().send_to_wechat(u'cmd', u'UI')
            elif input == u'RS':
                OtherProcess().TerminateProcess(OtherProcess.p_lianmeng)
                OtherProcess().StartProcess(u'lianmeng')
            else:
                pass
    else:
        while True:
            time.sleep(1000)
