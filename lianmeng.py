#coding:utf-8
import Queue
import threading

import requests, pymongo, xlrd
import random
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from lianmeng_config import *
from pyquery import PyQuery as pq
import Queue
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

class BrowserException(Exception):
    def __init__(self, err=u'错误过多，返回上级刷新重试'):
        Exception.__init__(self, err)

class browser:
    def __init__(self, name, q_lianmeng_wechat):
        self.q_in = Queue.Queue(3)
        self.q_out = q_lianmeng_wechat
        self.headers = {'User-Agent':'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
        self.package = {}
        self.browser_name = name # room_user_name
        # self.__init_qin_thread()

    def __invoke_cmd(self, package):
        '''subclasses should implement this method
        '''
        pass

    def __init_qin_thread(self):
        t = threading.Thread(target=self.__qin_thread(), )
        t.setDaemon(True)
        t.start()
        t.name = 'browser qin thread name %s time %d' % (self.browser_name, time.strftime('%d_%H%M%S', time.localtime(time.time())))
        logging.debug('==== thread name is %s' % t.name)

    def __qin_thread(self):
        while True:
            logging.info(u'浏览器【%s】开始接收' % self.browser_name)
            package = self.q_in.get()
            self.__invoke_cmd(package)

    def __send_msg_to_q(self, package):
        type = package[0]
        sub_type = package[1]
        msg = package[2]
        logging.info(u'浏览器【%s】开始发送，type:%s， subtype:%s，msg:%s' %
                     (self.browser_name, type, sub_type, msg))
        self.q_out.put(package)

class browser_selenium(browser):
    def __init__(self, name, q_lianmeng_wechat):
        browser.__init__(self, name, q_lianmeng_wechat)
        print 'hahahahaha'
        self.options = webdriver.ChromeOptions()
        self.options.add_argument('headless')
        self.options.add_argument('disable-gpu')
        self.options.add_argument('window-size=1600x900')
        self.browser = webdriver.Chrome(chrome_options=self.options)
        self.wait = WebDriverWait(self.browser, 5)
        self.retry_time = 0

    def __qin_thread(self):
        try:
            while True:
                logging.info(u'浏览器【%s】开始接收' % self.browser_name)
                package = self.q_in.get()
                self.__invoke_cmd(package)
        finally:
            self.browser.quit()

class browser_lianmeng(browser_selenium):
    def __init__(self, name, q_lianmeng_wechat):
        browser_selenium.__init__(self, name, q_lianmeng_wechat)
        self.client = pymongo.MongoClient(MONGO_URL, connect=False)
        self.db_table_search_goods = self.client[MONGO_DB_LIANMENG][MONGO_TABLE_LM_SEARCH_GOODS]
        self.db_table_search_history = self.client[MONGO_DB_LIANMENG][MONGO_TABLE_LM_SEARCH_HISTORY]
        ret = self.__init_url()
        package = make_package(u'response', room=self.browser_name, subtype=u'rinit', content=ret)
        self.__send_msg_to_q(package)

    def __click_must_ok(self, button_class_name):
        find_button = self.browser.find_element_by_css_selector if button_class_name.startswith('#') else self.browser.find_element_by_class_name
        cnt = 0
        while True:
            time.sleep(0.5)
            try:
                find_button(button_class_name).click()
                logging.debug('one more click')
                cnt += 1
                if cnt >= RETRY_TIMES:
                    raise RuntimeError
            except NoSuchElementException:
                break
            except Exception,e:
                print e

    def __get_excel(self):
        try:
            logging.debug(u'开始获取excel')
            logging.debug(u'切换到选品库网页')
            self.browser.get('http://pub.alimama.com/manage/selection/list.htm')
            logging.debug(u'点击“批量推广”')
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#sList > div:nth-child(2) > div > button'))).click()
            self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'block-dialog')))
            logging.debug(u'点击“确定”')
            self.wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '#J_global_dialog > div > div.dialog-ft > button.btn.btn-brand.w100.mr10'))).click()
            self.__click_must_ok('#J_global_dialog > div > div.dialog-ft > button.btn.btn-brand.w100.mr10')
            logging.debug(u'提取excel地址，并下载')
            url = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#magix_vf_code > div > div.dialog-ft.down-excel > a'))).get_attribute('href')
            cookies_ori = self.browser.get_cookies()
            cookies = {}
            for cookie in cookies_ori:
                cookies[cookie[u'name']] = cookie[u'value']
            self.__download(url, EXCEL_FILE_PATH, cookies)
            data = xlrd.open_workbook(EXCEL_FILE_PATH)
            table = data.sheets()[0]
            title = table.row_values(0)
            goods_detail = {}
            for i in range(1, table.nrows):
                product = table.row_values(i)
                good = dict(zip(title, product))
                logging.debug(u'下载图片')
                path = self.__download_main_pic(good[u'商品主图'] + DOWNLOAD_IMG_SIZE)
                good['主图存储路径'] = path
                goods_detail[str(i-1)] = good
            self.__save_to_mongo(goods_detail)
            logging.debug(u'删除excel')
            os.remove(EXCEL_FILE_PATH)
            self.retry_time = 0
            logging.debug(u'获取excel成功')
            return SUCCESS
        except Exception,e:
            logging.error(u'页面出现错误，%s' % e)
            self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + self.browser_name + 'browser_get_excel_err.png')
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                return LM_RETRY_TIME_OUT
            return self.__get_excel()

    def __login(self):
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.login-menu')))
            logging.debug(u'判断是否需要重新登录')
            doc = pq(self.browser.page_source).remove_namespaces()
            if not doc('#J_menu_product > div.menu-hd > span').text().startswith(u'你好，'):
                logging.debug(u'需要重新登录，正在登录')
                menu = self.browser.find_element_by_css_selector("#J_menu_login")
                ActionChains(self.browser).move_to_element(menu).click(menu).perform()
                self.wait.until(EC.visibility_of_element_located((By.NAME, 'taobaoLoginIfr')))
                self.browser.switch_to.frame(self.browser.find_element_by_name('taobaoLoginIfr'))
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_Static2Quick')))
                # 如果是密码输入界面，那么切换到二维码界面
                if self.browser.find_element_by_id('J_Static2Quick').is_displayed():
                    self.browser.find_element_by_id('J_Static2Quick').click()
                # 提取出二维码
                img_url = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '#J_QRCodeImg > img'))).get_attribute('src')
                cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time()))
                code_image_path = CODE_IMAGE_FOLD_PATH + 'codeimage_%s.jpg' % cur_time
                self.__download(img_url, code_image_path)
                logging.debug(u'将二维码发送给用户登录')
                package = make_package(u'notice', room=self.browser_name, subtype=u'login', content=code_image_path)
                self.__send_msg_to_q(package)
                # 判断是否登录成功
                times = 0
                while True:
                    time.sleep(2)
                    doc = pq(self.browser.page_source).remove_namespaces()
                    if doc('#J_menu_login_out'):
                        logging.debug(u'登录成功')
                        os.remove(code_image_path)
                        self.retry_time = 0
                        package = make_package(u'notice', room=self.browser_name, subtype=u'rlogin', content=u'success')
                        self.__send_msg_to_q(package)
                        return SUCCESS
                    else:
                        times +=1
                        if times >= 30:
                            logging.debug(u'超过一分钟未登录，登录失败')
                            os.remove(code_image_path)
                            self.retry_time = 0
                            package = make_package(u'notice', room=self.browser_name, subtype=u'rlogin', content=u'fail')
                            self.__send_msg_to_q(package)
                            return LM_LOG_IN_TIME_OUT
            else:
                logging.debug(u'不用再次登录')
                self.retry_time = 0
                return SUCCESS
        except Exception, e:
            logging.error(u'页面出现错误，%s' % e)
            self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + self.browser_name + 'broswer_login_err.png')
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                return LM_RETRY_TIME_OUT
            self.browser.refresh()
            return self.__login()

    def __get_product_from_selection_room(self):
        try:
            logging.debug(u'判断选取商品是否未空')
            cur_num = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_bar_selected > strong'))).text
            if cur_num != '0':
                self.browser.find_element_by_css_selector('#J_bar_selected').click()
                self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,
                    '#J_selection_bar > div > div.selection-selected > div.selection-tab-wrap.wrap.clearfix > a'))).click()
                self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,
                    '#J_global_dialog > div > div.dialog-ft.dialog-add-ok > span.btn.btn-brand.w110.mr20'))).click()
                self.browser.find_element_by_css_selector('#J_bar_selected').click()
            logging.debug(u'点击“选取全页商品”')
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'select-all'))).click()
            logging.debug(u'等待数量更新')
            doc = pq(self.browser.page_source).remove_namespaces()
            goods_num = doc('div.search-result-wrap').find('.block-search-box').length
            self.wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, '#J_bar_selected > strong'), str(goods_num)))
            logging.debug(u'点击“加入选品库”')
            self.browser.find_element_by_class_name('add-selection').click()
            logging.debug(u'等待推广窗口出现')
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_global_dialog')))
            logging.debug(u'点击“新建普通分组”')
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'w140'))).click()
            self.__click_must_ok('w140')
            logging.debug(u'输入组名')
            cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time()))
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_groupTitle'))).send_keys(cur_time)
            logging.debug(u'点击“创建”')
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'w80'))).click()
            self.__click_must_ok('w80')
            logging.debug(u'点击“加入”')
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'w100'))).click()
            self.__click_must_ok('w100')
            ret = self.__get_excel()
            if ret < 0:
                return ret
            logging.debug(u'获取商品成功')
            return SUCCESS
        except Exception, e:
            logging.error(u'页面出现错误，%s' % e)
            self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + self.browser_name + '_browser_get_product_from_selection_room_err.png')
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                return LM_RETRY_TIME_OUT
            self.browser.refresh()
            return self.__get_product_from_selection_room()

    def __record_search_history(self):
        cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time()))
        cursor = self.db_table_search_history.find({'user': self.package['user']})
        if cursor.count() == 1:
            self.db_table_search_history.update_one({'user': self.package['user']},
                                     {"$set": {cur_time: self.package['keyword']}})
        elif cursor.count() == 0:
            new = {'user': self.package['user'],
                   cur_time: self.package['keyword']}
            self.db_table_search_history.insert(new)
        logging.debug(u'存储到MONGODB HISTORY成功')

    def __save_to_mongo(self, goods_detail):
        goods = {}
        time_ori = int(time.time())
        cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time_ori))
        goods['search_time'] = cur_time
        goods['search_time_ori'] = time_ori
        goods['cursor'] = 0
        goods['goods_detail'] = goods_detail
        cursor = self.db_table_search_goods.find({'user': self.package['user']})
        if cursor.count() == 1:
            # del old pic
            info = cursor.next()
            for good in info['goods']['goods_detail'].items():
                path = good[1][u'主图存储路径']
                if os.path.exists(path):
                    os.remove(path)
            if 'long_pic' in info['goods']:
                for pic in info['goods']['long_pic'].items():
                    path = pic[1]
                    if os.path.exists(path):
                        os.remove(path)
            self.db_table_search_goods.update_one({'user': self.package['user']},
                                     {"$set": {'nick': self.package['nick'],
                                               'goods': goods}})
        elif cursor.count() == 0:
            new = {'user':self.package['user'],
                   'nick':self.package['nick'],
                   'goods':goods}
            self.db_table_search_goods.insert(new)
        logging.debug(u'存储到MONGODB成功')

    def __download(self, url,path,cookies=None):
        logging.debug(u'开始下载 %s' % url)
        session = requests.Session()
        response = session.get(url, headers=self.headers, cookies=cookies)
        if response.status_code == 200:
            with open(path, 'wb') as f:
                f.write(response.content)
                f.close()
            logging.debug(u'下载成功')
        session.close()
    
    def __download_main_pic(self, url):
        logging.debug(u'开始下载 %s' % url)
        session = requests.Session()
        response = session.get(url, headers=self.headers)
        if response.status_code == 200:
            cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time()))
            path = PICTURES_FOLD_PATH + '{0}.{1}'.format(self.package['user'] + '_' + cur_time + '_'
                                                         + str(random.randint(1,10000)), 'jpg')
            with open(path, 'wb') as f:
                f.write(response.content)
                f.close()
            logging.debug(u'下载成功')
            return path
        session.close()
        
    def __ali_search(self, search_dpyhj):
        try:
            keyword = self.package['keyword']
            logging.debug(u'开始搜索[%s]' % keyword)
            begin_time = time.time()
            self.__record_search_history()
            url = 'http://pub.alimama.com/promo/search/index.htm?q=' + keyword.encode('utf-8').replace(r'\x', '%') + \
                  '&toPage=' + str(SEARCH_PAGE) + '&dpyhq=' + str(search_dpyhj) + '&perPageSize=' + str(SEARCH_PER_PAGE_SIZE) + \
                  '&freeShipment=' + str(SEARCH_FREE_SHIPMENT) + '&startTkRate=' + str(SEARCH_START_TK_RATE) + '&queryType=' + \
                  str(SEARCH_QUERY_TYPE) + '&sortType=' + str(SEARCH_SORT_TYPE)
            self.browser.get(url)
            logging.debug(u'等待商品加载')
            self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, '#J_search_results > div.search-result-wrap > div.block-search-box > div.pic-box')))
            ret = self.__login()
            if ret < 0:
                return ret
            ret = self.__get_product_from_selection_room()
            if ret < 0:
                return ret
            end_time = time.time()
            logging.debug(u'搜索结束，用时: %d' % (end_time-begin_time))
            self.retry_time = 0
            return SUCCESS
        except TimeoutException, e:
            logging.error(u'等待商品加载超时，%s' % e)
            doc = pq(self.browser.page_source).remove_namespaces()
            if doc('div.no-data-list'):
                logging.debug(u'没有找到商品')
                return LM_NO_GOODS
            self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + self.browser_name + '_browser_ali_search_err.png')
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                return LM_RETRY_TIME_OUT
            return self.__ali_search(search_dpyhj)
        except Exception ,e:
            logging.error(u'页面出现错误，%s' % e)
            self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + self.browser_name + '_browser_ali_search_err.png')
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                return LM_RETRY_TIME_OUT
            return self.__ali_search(search_dpyhj)

    def __init_url(self):
        try:
            logging.info(u'开始初始化浏览器')
            url =  'http://pub.alimama.com/'
            self.browser.get(url)
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_menu_login > div'))).click()
            ret = self.__login()
            if ret < 0:
                return ret
            logging.info(u'初始化成功')
            self.retry_time = 0
            return SUCCESS
        except Exception, e:
            logging.info(u'初始化失败，%s' % e)
            self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + self.browser_name + '_browser_init_url_err.png')
            self.retry_time +=1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                return LM_RETRY_TIME_OUT
            return self.__init_url()

    def __invoke_cmd(self, package):
        type = package[0]
        sub_type = package[1]
        msg = package[2]
        if type == u'cmd':
            if sub_type == u'find':
                self.package = package
                logging.info(u'browser %s: 收到命令来自用户【%s】，开始查找【%s】' % (self.browser_name, msg[u'nick'], msg[u'keyword']))
                self.package = msg
                ret = self.__ali_search(SEARCH_DPYHJ)
                if ret == LM_NO_GOODS and SEARCH_DPYHJ == 1:
                    logging.debug(u'未找到优惠券商品，转为查找没有优惠券的商品')
                    ret = self.__ali_search(0)
                package = make_package(u'response', room=self.browser_name, subtype=u'rfind', user=msg[u'user'],
                                       nick=msg[u'nick'], content=ret)
                self.__send_msg_to_q(package)
            if sub_type == u'close' or sub_type == u'close_all':
                self.browser.quit()

def make_package(type, room, content=u'', subtype=u'', user=u'', nick=u''):
    d = (type, subtype, {u'room':room, u'content':content, u'user':user, u'nick':nick})
    return d

browser_thread_list = []

def lianmeng_main(q_wechat_lianmeng, q_lianmeng_wechat):
    global browser_thread_list
    logging.info(u'lianmeng_main: 进程开始')
    try:
        logging.info(u'lianmeng_main: 开始接收来自wechat的命令')
        while True:
            try:
                package = q_wechat_lianmeng.get_nowait()
                type = package[0]
                sub_type = package[1]
                msg = package[2]
                room = msg[u'room']
            except Queue.Empty:
                time.sleep(1)
                continue
            else:
                logging.debug(u'lianmeng_main: 收到命令 %s, %s, %s' % (type, sub_type, msg))
                if type == u'cmd':
                    if sub_type == u'init':
                        for b in browser_thread_list:
                            if b[u'room'] == room:
                                logging.error(u'浏览器已经存在 %s' % room)
                                continue
                        browser = browser_lianmeng(msg[u'room'], q_lianmeng_wechat)
                        browser_thread_list.append({u'room':msg[u'room'], u'handle':browser})
                    elif sub_type == u'find':
                        for b in browser_thread_list:
                            if b[u'room'] == room:
                                b[u'handle'].q_in.put(package)
                                continue
                        logging.error(u'lianmeng_main: not find browser %s' % room)
                    elif sub_type == u'close_all':
                        for b in browser_thread_list:
                            b[u'handle'].q_in.put(package)
                        browser_thread_list = []
                    else:
                        logging.error(u'unknown sub_type %s' % sub_type)
                else:
                    logging.error(u'unknown type %s' % type)
    finally:
        pass
        # make close package for Ctrl+C
        # package = make_package(u'cmd', u'', u'', u'close')
        # for b in browser_thread_list:
        #     b[u'handle'].q_in.put(package)
