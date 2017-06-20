#coding:utf-8
import platform, requests, time, pymongo, xlrd, subprocess
import random
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from lianmeng_config import *
from pyquery import PyQuery as pq
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

class BrowserException(Exception):
    def __init__(self, err=u'错误过多，返回上级刷新重试'):
        Exception.__init__(self, err)

class browser:
    def __init__(self, q_lianmeng_wechat, q_wechat_lianmeng):
        self.client = pymongo.MongoClient(MONGO_URL, connect=False)
        self.db_table = self.client[MONGO_DB][MONGO_TABLE]
        self.db_table_search = self.client[MONGO_DB][MONGO_TABLE_SEARCH]
        self.options = webdriver.ChromeOptions()
        self.options.add_argument('headless')
        self.options.add_argument('disable-gpu')
        self.options.add_argument('window-size=1400x900')
        self.browser = webdriver.Chrome(chrome_options=self.options)
        self.wait = WebDriverWait(self.browser, 5)
        self.headers = {'User-Agent':'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
        self.q_in = q_wechat_lianmeng
        self.q_out = q_lianmeng_wechat
        self.package = {}
        self.retry_time = 0

    def __print_qr(self, fileDir):
        if platform.system() == 'Linux':
            subprocess.call(['xdg-open', fileDir])
        else:
            os.startfile(fileDir)
    
    def __click_must_ok(self, button_class_name):
        # 确保button本身在点击后消失
        find_button = self.browser.find_element_by_css_selector if button_class_name.startswith('#') else self.browser.find_element_by_class_name
        while True:
            time.sleep(0.5)
            try:
                find_button(button_class_name).click()
                print('one more click')
            except NoSuchElementException:
                break
            except Exception,e:
                print e

    def __get_excel(self):
        try:
            print '开始获取excel'
            print '切换到选品库网页'
            self.browser.get('http://pub.alimama.com/manage/selection/list.htm')
            print '点击“批量推广”'
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#sList > div:nth-child(2) > div > button'))).click()
            self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'block-dialog')))
            print '点击“确定”'
            self.wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '#J_global_dialog > div > div.dialog-ft > button.btn.btn-brand.w100.mr10'))).click()
            self.__click_must_ok('#J_global_dialog > div > div.dialog-ft > button.btn.btn-brand.w100.mr10')
            print '提取excel地址，并下载'
            url = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#magix_vf_code > div > div.dialog-ft.down-excel > a'))).get_attribute('href')
            cookies_ori = self.browser.get_cookies()
            cookies = {}
            for cookie in cookies_ori:
                cookies[cookie[u'name']] = cookie[u'value']
            self.__download(url, EXCEL_FILE_PATH, cookies)
            print '提取数据'
            data = xlrd.open_workbook(EXCEL_FILE_PATH)
            table = data.sheets()[0]
            title = table.row_values(0)
            goods_detail = {}
            for i in range(1, table.nrows):
                product = table.row_values(i)
                good = dict(zip(title, product))
                print '下载图片'
                path = self.__download_main_pic(good[u'商品主图'] + DOWNLOAD_IMG_SIZE)
                good['主图存储路径'] = path
                goods_detail[str(i-1)] = good
            self.__save_to_mongo(goods_detail)
            print '删除excel'
            os.remove(EXCEL_FILE_PATH)
            self.retry_time = 0
            print '获取excel成功'
            return SUCCESS
        except Exception,e:
            print '页面出现错误，%s' % e
            self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + '__get_excel_err.png')
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                return RETRY_TIME_OUT
            return self.__get_excel()

    def __login(self):
        try:
            print '判断是否需要重新登录'
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.login-menu')))
            doc = pq(self.browser.page_source).remove_namespaces()
            if not doc('#J_menu_product > div.menu-hd > span').text().startswith(u'你好，'):
                print '需要重新登录，正在登录'
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
                # 显示二维码，待扫描
                # self.__print_qr(code_image_path)
                # print('将二维码发送给用户登录')
                self.__send_msg_to_wechat('login', code_image_path)
                print('等待用户登录')
                # 判断是否登录成功
                times = 0
                while True:
                    time.sleep(2)
                    doc = pq(self.browser.page_source).remove_namespaces()
                    if doc('#J_menu_login_out'):
                        print('登录成功')
                        os.remove(code_image_path)
                        self.retry_time = 0
                        return SUCCESS
                    else:
                        times +=1
                        if times >= 30:
                            print('超过一分钟未登录，登录失败')
                            self.retry_time = 0
                            return LOG_IN_TIME_OUT
            else:
                print('不用再次登录')
                self.retry_time = 0
                return SUCCESS
        except Exception, e:
            print '页面出现错误，%s' % e
            self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + '__login_err.png')
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                return RETRY_TIME_OUT
            self.browser.refresh()
            return self.__login()

    def __send_msg_to_wechat(self, type, package):
        self.q_out.put((type, package))

    def __get_product_from_selection_room(self):
        try:
            print '开始获取商品'
            print '点击“选取全页商品”'
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'select-all'))).click()
            print '等待数量更新'
            self.wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, '#J_bar_selected > strong'), str(SEARCH_PER_PAGE_SIZE)))
            print '点击“加入选品库”'
            self.browser.find_element_by_class_name('add-selection').click()
            print '等待推广窗口出现'
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_global_dialog')))
            print '点击“新建普通分组”'
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'w140'))).click()
            self.__click_must_ok('w140')
            print '输入组名'
            cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time()))
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_groupTitle'))).send_keys(cur_time)
            print '点击“创建”'
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'w80'))).click()
            self.__click_must_ok('w80')
            print '点击“加入”'
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'w100'))).click()
            self.__click_must_ok('w100')
            ret = self.__get_excel()
            if ret < 0:
                return ret
            print '获取商品成功'
            return SUCCESS
        except Exception, e:
            print '页面出现错误，%s' % e
            self.browser.get_screenshot_as_file(PICTURES_FOLD_PATH + '__get_product_from_selection_room_err.png')
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                return RETRY_TIME_OUT
            self.browser.refresh()
            return self.__get_product_from_selection_room()

    def __record_search_history(self):
        cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time()))
        cursor = self.db_table_search.find({'user': self.package['user']})
        if cursor.count() == 1:
            self.db_table_search.update_one({'user': self.package['user']},
                                     {"$set": {cur_time: self.package['keyword']}})
        elif cursor.count() == 0:
            new = {'user': self.package['user'],
                   cur_time: self.package['keyword']}
            self.db_table_search.insert(new)
        print('存储到MONGODB HISTORY成功')

    def __save_to_mongo(self, goods_detail):
        goods = {}
        cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time()))
        goods['search_time'] = cur_time
        goods['cursor'] = 0
        goods['goods_detail'] = goods_detail
        cursor = self.db_table.find({'user': self.package['user']})
        if cursor.count() == 1:
            self.db_table.update_one({'user': self.package['user']},
                                     {"$set": {'nick': self.package['nick'],
                                               'goods': goods}})
        elif cursor.count() == 0:
            new = {'user':self.package['user'],
                   'remark':self.package['remark'],
                   'nick':self.package['nick'],
                   'goods':goods}
            self.db_table.insert(new)
        print('存储到MONGODB成功')

    def __download(self, url,path,cookies=None):
        print '开始下载', url
        session = requests.Session()
        response = session.get(url, headers=self.headers, cookies=cookies)
        if response.status_code == 200:
            with open(path, 'wb') as f:
                f.write(response.content)
                f.close()
            print('下载成功')
        session.close()
    
    def __download_main_pic(self, url):
        print '开始下载', url
        session = requests.Session()
        response = session.get(url, headers=self.headers)
        if response.status_code == 200:
            cur_time = time.strftime('%Y%m%d-%H%M%S', time.localtime(time.time()))
            path = PICTURES_FOLD_PATH + '{0}.{1}'.format(self.package['user'] + '_' + cur_time + '_'
                                                         + str(random.randint(1,10000)), 'jpg')
            with open(path, 'wb') as f:
                f.write(response.content)
                f.close()
            print('下载成功')
            return path
        session.close()
        
    def ali_search(self, keyword):
        try:
            print('开始搜索[%s]' % keyword)
            begin_time = time.time()
            self.__record_search_history()
            url = 'http://pub.alimama.com/promo/search/index.htm?q=' + keyword.encode('utf-8').replace(r'\x', '%') + \
                  '&toPage=' + str(SEARCH_PAGE) + '&dpyhq=' + str(SEARCH_DPYHJ) + '&perPageSize=' + str(SEARCH_PER_PAGE_SIZE) + \
                  '&freeShipment=' + str(SEARCH_FREE_SHIPMENT) + '&startTkRate=' + str(SEARCH_START_TK_RATE) + '&queryType=' + \
                  str(SEARCH_QUERY_TYPE) + '&sortType=' + str(SEARCH_SORT_TYPE)
            self.browser.get(url)
            print '等待商品加载'
            self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, '#J_search_results > div.search-result-wrap > div.block-search-box > div.pic-box')))
            ret = self.__login()
            if ret < 0:
                return ret
            ret = self.__get_product_from_selection_room()
            if ret < 0:
                return ret
            end_time = time.time()
            print '搜索结束，用时: %d' % (end_time-begin_time)
            self.retry_time = 0
            return SUCCESS
        except TimeoutException, e:
            print '等待商品加载超时，%s' % e
            doc = pq(self.browser.page_source).remove_namespaces()
            if doc('div.no-data-list'):
                print '没有找到商品'
                return NO_GOODS
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                return RETRY_TIME_OUT
            return self.ali_search(keyword)
        except Exception ,e:
            print '页面出现错误，%s' % e
            self.retry_time += 1
            if self.retry_time >= RETRY_TIMES:
                self.retry_time = 0
                return RETRY_TIME_OUT
            return self.ali_search(keyword)

    def init_browser(self):
        try:
            print u'开始初始化浏览器'
            url =  'http://pub.alimama.com/'
            self.browser.get(url)
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_menu_login > div'))).click()
            ret = self.__login()
            if ret < 0:
                return ret
            print u'初始化成功'
            # self.retry_time = 0
            return 0
        except Exception, e:
            print u'初始化失败，%s' % e
            # self.retry_time +=1
            # if self.retry_time >= RETRY_TIME:
            #     return -1
            return self.init_browser()

def make_package(room=u'', user=u'', nick=u'', result=SUCCESS):
    d = {'room':room, 'user':user, 'nick':nick, 'result':result}
    return d

def lianmeng_main(q_wechat_lianmeng, q_lianmeng_wechat):
    print u'lianmeng_main: 进程开始'
    print u'lianmeng_main: 开始初始化浏览器'
    browser_1 = browser(q_lianmeng_wechat, q_wechat_lianmeng)
    browser_1.init_browser()
    try:
        print u'lianmeng_main: 开始接收来自wechat的命令'
        while True:
            type, msg = browser_1.q_in.get()
            if type == 'find':
                browser_1.package = msg
                print u'lianmeng_main: 收到命令来自用户【%s】，开始查找【%s】' % (msg['nick'], msg['keyword'])
                result = browser_1.ali_search(msg['keyword'])
                response_package = make_package(room=msg['room'], user=msg['user'], nick=msg['nick'], result=result)
                browser_1.q_out.put(('response', response_package))
            elif type == 'cmd':
                print u'lianmeng_main: 收到cmd'
                pass
    finally:
        browser_1.browser.close()
