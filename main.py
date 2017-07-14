#coding:utf-8
import os
import re
import threading
import time
from common_config import *

from wechat import wechat_main
from lianmeng import lianmeng_main
from multiprocessing import Queue, Process

def make_package(type, room=u'', content=u'', subtype=u'', user=u'', nick=u''):
    d = (type, subtype, {u'room':room, u'content':content, u'user':user, u'nick':nick})
    return d

class OtherProcess:
    q_main_wechat = Queue(3)
    q_wechat_main = Queue(3)
    q_main_lianmeng = Queue(3)
    q_lianmeng_main = Queue(3)
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

        #OtherProcess.p_lianmeng = Process(target=lianmeng_main, name=u'lianmeng_main',
        #                                  args=(OtherProcess.q_main_lianmeng, OtherProcess.q_lianmeng_main,
        #                                        OtherProcess.q_wechat_lianmeng, OtherProcess.q_lianmeng_wechat,))
        #OtherProcess.p_lianmeng.daemon = True
        #OtherProcess.p_lianmeng.start()
        #logging.info('Init lianmeng 进程 ok')

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
                                              args=(OtherProcess.q_main_lianmeng, OtherProcess.q_lianmeng_main,
                                                OtherProcess.q_wechat_lianmeng, OtherProcess.q_lianmeng_wechat,))
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
            package = self.q_in.get()
            type, subtype, msg = package
            logging.debug('收到wechat进程命令 %s %s' % (type, subtype))
            if type == u'cmd':
                if subtype == u'rs':
                    logging.debug('开始重启liangmeng进程')
                    send_package = make_package(type=u'cmd', subtype=u'close_all')
                    communicate_with_lianmeng().send_to_lianmeng(send_package)

    def send_to_wechat(self, package):
        communicate_with_wechat.q_out.put(package)


class communicate_with_lianmeng:
    q_out = None
    q_in = None

    def create_receive_from_lianmeng_thread(self):
        thread = threading.Thread(target=self.receive_from_lianmeng_thread, )
        thread.setDaemon(True)
        thread.start()
        thread.name = 'receive_from_lianmeng thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
        logging.debug('==== thread name is ' + thread.name)

    def receive_from_lianmeng_thread(self):
        while True:
            logging.info('开始接收lianmeng进程命令')
            package = self.q_in.get()
            type, subtype, msg = package
            logging.debug('收到lianmeng进程命令 %s %s' % (type, subtype))
            if type == u'response':
                if subtype == u'rclose_all':
                    if msg[u'content'] == u'success':
                        OtherProcess().TerminateProcess(OtherProcess.p_lianmeng)
                        OtherProcess().StartProcess(u'lianmeng')
                        logging.debug('重启liangmeng进程成功')
                        send_package = make_package(type=u'response', subtype=u'rrs', content=u'success')
                        communicate_with_wechat().send_to_wechat(send_package)

    def send_to_lianmeng(self, package):
        communicate_with_lianmeng.q_out.put(package)

if __name__ == '__main__':
    OtherProcess().InitOtherProcess()
    communicate_with_wechat.q_in = OtherProcess.q_wechat_main
    communicate_with_wechat.q_out = OtherProcess.q_main_wechat
    communicate_with_wechat().create_receive_from_wechat_thread()

    #communicate_with_lianmeng.q_in = OtherProcess.q_lianmeng_main
    #communicate_with_lianmeng.q_out = OtherProcess.q_main_lianmeng
    #communicate_with_lianmeng().create_receive_from_lianmeng_thread()

    os_home = os.popen('echo $HOME').read().replace('\n', '')
    if not os_home == u'/root':
    # if 0:
        while True:
            input = raw_input('enter cmd: ').decode('utf-8')
            if input == u'UI':
                logging.info(u'正在启动UI')
                package = make_package(type=u'cmd', subtype=u'UI')
                communicate_with_wechat().send_to_wechat(package)
            elif input == u'RS':
                logging.info(u'正在重启联盟')
                send_package = make_package(type=u'cmd', subtype=u'close_all')
                communicate_with_lianmeng().send_to_lianmeng(send_package)
            else:
                pass
    else:
        while True:
            time.sleep(1000)
