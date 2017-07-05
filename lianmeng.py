#coding:utf-8
import Queue
import threading
import traceback

import requests, pymongo, xlrd
import random
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotVisibleException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from lianmeng_config import *
from pyquery import PyQuery as pq
import Queue
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

browser_thread_list = []

class BrowserException(Exception):
    def __init__(self, err=u'错误过多，返回上级刷新重试'):
        Exception.__init__(self, err)

class browser:
    def __init__(self, name, q_lianmeng_wechat):
        self.q_in = Queue.Queue(3)
        self.q_out = q_lianmeng_wechat
        self.headers = {'User-Agent':'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
        self.msg = {}
        self.browser_name = name # room_user_name

    def invoke_cmd(self, package):
        '''subclasses should implement this method
        '''
        pass

    def init_qin_thread(self):
        t = threading.Thread(target=self.qin_thread, )
        t.setDaemon(True)
        t.start()
        t.name = 'browser qin thread name %s time %s' % (self.browser_name, time.strftime('%d_%H%M%S', time.localtime(time.time())))
        logging.debug('==== thread name is %s' % t.name)

    def qin_thread(self):
        while True:
            logging.info(u'浏览器【%s】开始接收' % self.browser_name)
            package = self.q_in.get()
            type, sub_type, msg = package
            logging.info(u'浏览器【%s】收到：%s %s %s' % (self.browser_name, type, sub_type, msg))
            self.invoke_cmd(package)

class browser_selenium(browser):
    def __init__(self, name, q_lianmeng_wechat):
        browser.__init__(self, name, q_lianmeng_wechat)
        self.options = webdriver.ChromeOptions()
        self.options.add_argument('headless')
        self.options.add_argument('disable-gpu')
        self.options.add_argument('window-size=1600x900')
        self.options.add_argument('no-sandbox')
        self.options.add_argument('disable-logging')
        self.browser = webdriver.Chrome(chrome_options=self.options)
        self.wait = WebDriverWait(self.browser, 5)
        self.retry_time = 0

    def qin_thread(self):
        try:
            while True:
                logging.info(u'浏览器【%s】开始接收' % self.browser_name)
                package = self.q_in.get()
                type, sub_type, msg = package
                logging.info(u'浏览器【%s】收到：%s %s %s' % (self.browser_name, type, sub_type, msg))
                self.invoke_cmd(package)
        finally:
            self.browser.close()
            self.browser.quit()

class browser_lianmeng(browser_selenium):
    def __init__(self, name, q_lianmeng_wechat):
        browser_selenium.__init__(self, name, q_lianmeng_wechat)
        self.client = pymongo.MongoClient(MONGO_URL, connect=False)
        self.db_table_search_goods = self.client[MONGO_DB_LIANMENG][MONGO_TABLE_LM_SEARCH_GOODS]
        self.db_table_search_history = self.client[MONGO_DB_LIANMENG][MONGO_TABLE_LM_SEARCH_HISTORY]
        self.heart_refresh_lock = threading.Lock()
        self.goods_num = 0

    def click_must_ok(self, button_class_name):
        find_button = self.browser.find_element_by_css_selector if button_class_name.startswith('#') else self.browser.find_element_by_class_name
        cnt = 0
        while True:
            time.sleep(0.5)
            try:
                cnt += 1
                if cnt > RETRY_TIMES:
                    raise RuntimeError
                find_button(button_class_name).click()
                logging.debug('one more click')
            except (NoSuchElementException, ElementNotVisibleException):
                break
            except Exception, e:
                logging.error(u'click出现错误，%s' % traceback.format_exc())

    def get_excel(self):
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
            self.click_must_ok('#J_global_dialog > div > div.dialog-ft > button.btn.btn-brand.w100.mr10')
            logging.debug(u'提取excel地址，并下载')
            url = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#magix_vf_code > div > div.dialog-ft.down-excel > a'))).get_attribute('href')
            cookies_ori = self.browser.get_cookies()
            cookies = {}
            for cookie in cookies_ori:
                cookies[cookie[u'name']] = cookie[u'value']
            self.download(url, EXCEL_FILE_PATH, cookies)
            data = xlrd.open_workbook(EXCEL_FILE_PATH)
            table = data.sheets()[0]
            title = table.row_values(0)
            goods_detail = {}
            for i in range(1, table.nrows):
                product = table.row_values(i)
                good = dict(zip(title, product))
                logging.debug(u'下载图片')
                path = self.download_main_pic(good[u'商品主图'] + DOWNLOAD_IMG_SIZE)
                good['主图存储路径'] = path
                goods_detail[str(i-1)] = good
            self.save_to_mongo(goods_detail)
            logging.debug(u'删除excel')
            os.remove(EXCEL_FILE_PATH)
            self.retry_time = 0
            logging.debug(u'获取excel成功')
            return SUCCESS
        except Exception,e:
            logging.error(u'页面出现错误，%s' % traceback.format_exc())
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + self.browser_name + 'browser_get_excel_err.png')
                return LM_RETRY_TIME_OUT
            return self.get_excel()

    def login(self):
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.login-menu')))
            logging.debug(u'判断是否需要重新登录')
            doc = pq(self.browser.page_source).remove_namespaces()
            if not doc('#J_menu_product > div.menu-hd > span').text().startswith(u'你好，'):
                code_image_path = u''
                logging.debug(u'需要重新登录，正在登录')
                menu = self.browser.find_element_by_css_selector("#J_menu_login")
                ActionChains(self.browser).move_to_element(menu).click(menu).perform()
                self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '#J_login_panel_taobao > iframe')))
                self.browser.switch_to.frame(self.browser.find_element_by_css_selector('#J_login_panel_taobao > iframe'))
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_Static2Quick')))
                # 如果是密码输入界面，那么切换到二维码界面
                if self.browser.find_element_by_id('J_Static2Quick').is_displayed():
                    self.browser.find_element_by_id('J_Static2Quick').click()
                # 判断登录方式是二维码还是手机登录
                doc = pq(self.browser.page_source).remove_namespaces()
                if doc('#J_AkeyLogin'):
                    button = self.browser.find_element_by_css_selector('#J_AkeyLogin > div.akey-mod > div.submit > button')
                    # 其他方法都不好用，scrollTo，location_once_scrolled_into_view
                    button.send_keys(Keys.DOWN)
                    button.click()
                    self.click_must_ok('#J_AkeyLogin > div.akey-mod > div.submit > button')
                    logging.debug(u'提示用户通过手机确认登录')
                    package = make_package(u'notice', room=self.browser_name, subtype=u'login_on_phone')
                    communicate_with_wechat().send_to_wechat(package)
                elif doc('#J_QRCodeLogin'):
                    img_url = self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '#J_QRCodeImg > img'))).get_attribute('src')
                    cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time()))
                    code_image_path = CODE_IMAGE_FOLD_PATH + 'codeimage_%s.jpg' % cur_time
                    self.download(img_url, code_image_path)
                    logging.debug(u'将二维码发送给用户登录')
                    package = make_package(u'notice', room=self.browser_name, subtype=u'login', content=code_image_path)
                    communicate_with_wechat().send_to_wechat(package)
                # 判断是否登录成功
                times = 0
                while True:
                    time.sleep(2)
                    doc = pq(self.browser.page_source).remove_namespaces()
                    if doc('#J_menu_login_out'):
                        logging.debug(u'登录成功')
                        if code_image_path and os.path.exists(code_image_path):
                            os.remove(code_image_path)
                        self.retry_time = 0
                        package = make_package(u'notice', room=self.browser_name, subtype=u'rlogin', content=u'success')
                        communicate_with_wechat().send_to_wechat(package)
                        return SUCCESS
                    else:
                        times +=1
                        if times >= 30:
                            logging.debug(u'超过一分钟未登录，登录失败')
                            if code_image_path and os.path.exists(code_image_path):
                                os.remove(code_image_path)
                            self.retry_time = 0
                            package = make_package(type=u'notice', room=self.browser_name, subtype=u'rlogin', content=u'fail')
                            communicate_with_wechat().send_to_wechat(package)
                            return LM_LOG_IN_TIME_OUT
            else:
                logging.debug(u'不用再次登录')
                self.retry_time = 0
                return SUCCESS
        except Exception, e:
            logging.error(u'页面出现错误，%s' % traceback.format_exc())
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + self.browser_name + 'broswer_login_err.png')
                return LM_RETRY_TIME_OUT
            self.browser.refresh()
            return self.login()

    def get_product_from_selection_room(self):
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
            self.goods_num += goods_num
            self.wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, '#J_bar_selected > strong'), str(goods_num)))
            logging.debug(u'点击“加入选品库”')
            self.browser.find_element_by_class_name('add-selection').click()
            logging.debug(u'等待推广窗口出现')
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_global_dialog')))
            logging.debug(u'点击“新建普通分组”')
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'w140'))).click()
            self.click_must_ok('w140')
            logging.debug(u'输入组名')
            cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time()))
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_groupTitle'))).send_keys(cur_time)
            logging.debug(u'点击“创建”')
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'w80'))).click()
            self.click_must_ok('w80')
            logging.debug(u'点击“加入”')
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'w100'))).click()
            self.click_must_ok('w100')
            ret = self.get_excel()
            if ret < 0:
                return ret
            logging.debug(u'获取商品成功')
            return SUCCESS
        except Exception, e:
            logging.error(u'页面出现错误，%s' % traceback.format_exc())
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + self.browser_name + '_browser_get_product_from_selection_room_err.png')
                return LM_RETRY_TIME_OUT
            self.browser.refresh()
            return self.get_product_from_selection_room()

    def record_search_history(self):
        cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time()))
        cursor = self.db_table_search_history.find({'user': self.msg['user']})
        if cursor.count() == 1:
            self.db_table_search_history.update_one({'user': self.msg['user']},
                                     {"$set": {cur_time: self.msg['content']}})
        elif cursor.count() == 0:
            new = {'user': self.msg['user'],
                   cur_time: self.msg['content']}
            self.db_table_search_history.insert(new)
        logging.debug(u'存储到MONGODB HISTORY成功')

    def save_to_mongo(self, goods_detail):
        goods = {}
        time_ori = int(time.time())
        cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time_ori))
        goods['search_time'] = cur_time
        goods['search_time_ori'] = time_ori
        goods['cursor'] = 0
        goods['goods_detail'] = goods_detail
        cursor = self.db_table_search_goods.find({'user': self.msg['user']})
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
            self.db_table_search_goods.update_one({'user': self.msg['user']},
                                     {"$set": {'nick': self.msg['nick'],
                                               'goods': goods}})
        elif cursor.count() == 0:
            new = {'user':self.msg['user'],
                   'nick':self.msg['nick'],
                   'goods':goods}
            self.db_table_search_goods.insert(new)
        logging.debug(u'存储到MONGODB成功')

    def download(self, url,path,cookies=None):
        logging.debug(u'开始下载 %s' % url)
        session = requests.Session()
        response = session.get(url, headers=self.headers, cookies=cookies)
        if response.status_code == 200:
            with open(path, 'wb') as f:
                f.write(response.content)
                f.close()
            logging.debug(u'下载成功')
        session.close()
    
    def download_main_pic(self, url):
        logging.debug(u'开始下载 %s' % url)
        session = requests.Session()
        response = session.get(url, headers=self.headers)
        if response.status_code == 200:
            cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time()))
            path = PICTURES_FOLD_PATH + '{0}.{1}'.format(self.msg['user'] + '_' + cur_time + '_'
                                                         + str(random.randint(1,10000)), 'jpg')
            with open(path, 'wb') as f:
                f.write(response.content)
                f.close()
            logging.debug(u'下载成功')
            return path
        session.close()
        
    def ali_search(self, search_dpyhj=SEARCH_DPYHJ, prop=SEARCH_START_TK_RATE, num=SEARCH_PER_PAGE_SIZE):
        try:
            keyword = self.msg['content']
            logging.debug(u'开始搜索[%s]' % keyword)
            begin_time = time.time()
            self.record_search_history()
            url = 'http://pub.alimama.com/promo/search/index.htm?q=' + keyword.encode('utf-8').replace(r'\x', '%') + \
                  '&toPage=' + str(SEARCH_PAGE) + '&dpyhq=' + str(search_dpyhj) + '&perPageSize=' + str(num) + \
                  '&freeShipment=' + str(SEARCH_FREE_SHIPMENT) + '&startTkRate=' + str(prop) + '&queryType=' + \
                  str(SEARCH_QUERY_TYPE) + '&sortType=' + str(SEARCH_SORT_TYPE)
            self.browser.get(url)
            logging.debug(u'等待商品加载')
            self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, '#J_search_results > div.search-result-wrap > div.block-search-box > div.pic-box')))
            ret = self.login()
            if ret < 0:
                return ret
            ret = self.get_product_from_selection_room()
            if ret < 0:
                return ret
            end_time = time.time()
            logging.debug(u'搜索结束，用时: %d' % (end_time-begin_time))
            self.retry_time = 0
            return SUCCESS
        except TimeoutException, e:
            logging.error(u'等待商品加载超时，%s' % traceback.format_exc())
            doc = pq(self.browser.page_source).remove_namespaces()
            if doc('div.no-data-list'):
                logging.debug(u'没有找到商品')
                return LM_NO_GOODS
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + self.browser_name + '_browser_ali_search_err.png')
                return LM_RETRY_TIME_OUT
            return self.ali_search(search_dpyhj)
        except Exception ,e:
            logging.error(u'页面出现错误，%s' % traceback.format_exc())
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + self.browser_name + '_browser_ali_search_err.png')
                return LM_RETRY_TIME_OUT
            return self.ali_search(search_dpyhj)

    def init_url(self):
        try:
            logging.info(u'开始初始化浏览器')
            url =  'http://pub.alimama.com/'
            self.browser.get(url)
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_menu_login > div'))).click()
            ret = self.login()
            if ret < 0:
                return ret
            logging.info(u'初始化成功')
            self.retry_time = 0
            return SUCCESS
        except Exception, e:
            logging.info(u'初始化失败，%s' % traceback.format_exc())
            self.retry_time +=1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + self.browser_name + '_browser_init_url_err.png')
                return LM_RETRY_TIME_OUT
            return self.init_url()

    def create_heart_thread(self):
        thread = threading.Thread(target=self.heart_thread,)
        thread.setDaemon(True)
        thread.start()
        thread.name = 'heart_thread thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
        logging.debug('==== thread name is ' + thread.name)

    def heart_thread(self):
        logging.debug(u'browser %s, heart_thread start' % self.browser_name)
        while True:
            time.sleep(HEART_DELAY)
            hour = int(time.strftime('%H', time.localtime()))
            if hour >= HEART_HOURS_BEGIN and hour <= HEART_HOURS_END:
                self.heart_refresh_lock.acquire()
                logging.debug(u'heart_thread: refresh browser')
                self.browser.get('http://pub.alimama.com/')
                self.login()
                self.heart_refresh_lock.release()

    def invoke_cmd(self, package):
        type, sub_type, msg = package
        if type == u'cmd':
            if sub_type == u'init_url':
                self.heart_refresh_lock.acquire()
                ret = self.init_url()
                package = make_package(u'response', room=self.browser_name, subtype=u'rinit', content=ret)
                communicate_with_wechat().send_to_wechat(package)
                self.heart_refresh_lock.release()
            elif sub_type == u'init_heart':
                self.create_heart_thread()
            elif sub_type == u'find':
                logging.info(u'browser %s: 收到命令来自用户【%s】，开始查找【%s】' % (self.browser_name, msg[u'nick'], msg[u'content']))
                self.heart_refresh_lock.acquire()
                self.msg = msg
                ret = self.ali_search()
                if ret == LM_NO_GOODS or self.goods_num < SEARCH_PER_PAGE_SIZE:
                    logging.debug(u'【默认比例】 【有优惠券】，未找到或未找全商品')
                    ret = self.ali_search(prop=5, num=SEARCH_PER_PAGE_SIZE-self.goods_num)
                if ret == LM_NO_GOODS or self.goods_num < SEARCH_PER_PAGE_SIZE:
                    logging.debug(u'【5%比例】 【有优惠券】，未找到或未找全商品')
                    ret = self.ali_search(search_dpyhj=0, num=SEARCH_PER_PAGE_SIZE-self.goods_num)
                if ret == LM_NO_GOODS or self.goods_num < SEARCH_PER_PAGE_SIZE:
                    logging.debug(u'【默认比例】 【无优惠券】，未找到或未找全商品')
                    ret = self.ali_search(search_dpyhj=0, prop=5, num=SEARCH_PER_PAGE_SIZE-self.goods_num)
                if ret == LM_NO_GOODS or self.goods_num < SEARCH_PER_PAGE_SIZE:
                    logging.debug(u'【5%比例】 【无优惠券】，未找到或未找全商品')
                self.goods_num = 0
                package = make_package(u'response', room=self.browser_name, subtype=u'rfind', user=msg[u'user'],
                                       nick=msg[u'nick'], content=ret)
                communicate_with_wechat().send_to_wechat(package)
                self.heart_refresh_lock.release()

def make_package(type, room=u'', content=u'', subtype=u'', user=u'', nick=u''):
    d = (type, subtype, {u'room':room, u'content':content, u'user':user, u'nick':nick})
    return d

class communicate_with_main:
    q_out = None
    q_in = None
    def create_receive_from_main_thread(self):
        thread = threading.Thread(target=self.receive_from_main_thread,)
        thread.setDaemon(True)
        thread.start()
        thread.name = 'receive_from_main thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
        logging.debug('==== thread name is ' + thread.name)

    def receive_from_main_thread(self):
        global browser_thread_list
        logging.info('开始接收Main进程命令')
        while True:
            try:
                package = self.q_in.get_nowait()
                type, subtype, msg = package
            except Queue.Empty:
                time.sleep(1)
                continue
            else:
                logging.debug('收到Main进程命令 %s %s %s' % (type, subtype, msg))
                if type == u'cmd':
                    if subtype == u'close_all':
                        logging.info(u'receive_from_main_thread: 收到关闭浏览器命令')
                        for b in browser_thread_list:
                            browser = b[u'handle']
                            logging.info(u'正在关闭browser %s' % browser.browser_name)
                            for handle in browser.browser.window_handles:
                                browser.browser.switch_to.window(handle)
                                browser.browser.close()
                            browser.browser.quit()
                        browser_thread_list = []
                        time.sleep(3)
                        send_package = make_package(type=u'response', subtype=u'rclose_all', content=u'success')
                        self.send_to_main(send_package)

    def send_to_main(self, package):
        self.q_out.put(package)

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
        global browser_thread_list
        logging.info('开始接收wechat进程命令')
        while True:
            try:
                package = self.q_in.get_nowait()
                type, subtype, msg = package
                room = msg[u'room']
            except Queue.Empty:
                time.sleep(1)
                continue
            else:
                logging.debug(u'receive_from_wechat_thread: 收到命令 %s, %s, %s' % (type, subtype, msg))
                if type == u'cmd':
                    if subtype == u'init':
                        for b in browser_thread_list:
                            if b[u'room'] == room:
                                logging.error(u'浏览器已经存在 %s' % room)
                                continue
                        # 初始化browser参数和queue相关线程，浏览器也已经打开
                        browser = browser_lianmeng(msg[u'room'], self.q_out)
                        browser.init_qin_thread()
                        # 初始化url和检查登录
                        package = make_package(type=u'cmd', subtype=u'init_url', room=room)
                        browser.q_in.put(package)
                        # 初始化heart进程
                        package = make_package(type=u'cmd', subtype=u'init_heart', room=room)
                        browser.q_in.put(package)
                        # 将浏览器添加到列表
                        browser_thread_list.append({u'room': msg[u'room'], u'handle': browser})
                    elif subtype == u'find':
                        for b in browser_thread_list:
                            if b[u'room'] == room:
                                b[u'handle'].q_in.put(package)
                                continue
                        logging.error(u'lianmeng_main: not find browser %s' % room)
                    else:
                        logging.error(u'unknown sub_type %s' % subtype)
                else:
                    logging.error(u'unknown type %s' % type)

    def send_to_wechat(self, package):
        self.q_out.put(package)

def init_thread(q_main_lianmeng, q_lianmeng_main, q_wechat_lianmeng, q_lianmeng_wechat):
    logging.info('init_thread: 创建接收main进程命令的线程')
    communicate_with_main.q_out = q_lianmeng_main
    communicate_with_main.q_in = q_main_lianmeng
    communicate_with_main().create_receive_from_main_thread()
    logging.info('init_thread: 创建接收wechat进程命令的线程')
    communicate_with_wechat.q_out = q_lianmeng_wechat
    communicate_with_wechat.q_in = q_wechat_lianmeng
    communicate_with_wechat().create_receive_from_wechat_thread()

def create_init_thread(q_main_lianmeng, q_lianmeng_main, q_wechat_lianmeng, q_lianmeng_wechat):
    thread = threading.Thread(target=init_thread, args=(q_main_lianmeng, q_lianmeng_main, q_wechat_lianmeng, q_lianmeng_wechat))
    thread.setDaemon(True)
    thread.start()
    thread.name = 'init_thread thread ' + time.strftime('%d_%H%M%S', time.localtime(time.time()))
    logging.debug('==== thread name is ' + thread.name)

def lianmeng_main(q_main_lianmeng, q_lianmeng_main, q_wechat_lianmeng, q_lianmeng_wechat):
    logging.info(u'lianmeng_main: 进程开始，开始初始化接收main和wechat命令的线程')
    create_init_thread(q_main_lianmeng, q_lianmeng_main, q_wechat_lianmeng, q_lianmeng_wechat)
    logging.info(u'lianmeng_main: 初始化线程结束，进入休眠')
    while True:
        time.sleep(5000)

