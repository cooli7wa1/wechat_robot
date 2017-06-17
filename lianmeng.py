#coding:utf-8
import os, platform, requests, time, pymongo, xlrd, subprocess
from hashlib import md5
from requests import RequestException
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from lianmeng_config import *
from multiprocessing import Queue
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

class browser:
    def __init__(self):
        self.client = pymongo.MongoClient(MONGO_URL, connect=False)
        self.db_table = self.client[MONGO_DB][MONGO_TABLE]
        self.options = webdriver.ChromeOptions()
        # self.options.add_argument('headless')
        self.options.add_argument('window-size=1400x900')
        self.browser = webdriver.Chrome(chrome_options=self.options)
        self.wait = WebDriverWait(self.browser, 5)
        self.headers = {'User-Agent':'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
        self.q_in = Queue()
        self.q_out = Queue()
        self.package = {}

    def __print_qr(self, fileDir):
        if platform.system() == 'Linux':
            subprocess.call(['xdg-open', fileDir])
        else:
            os.startfile(fileDir)
    
    def __stop_here(self):
        while True:
            pass

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

    def __get_excel(self, excel_file_path):
        try:
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
            while True:
                try:
                    self.__download(url, excel_file_path, cookies)
                    time.sleep(1)
                    if os.path.exists(excel_file_path):
                        print('下载excel成功')
                        break
                    print 'excel下载失败'
                except TimeoutException:
                    print 'excel未开始下载，重新下载'
                    pass
        except TimeoutException:
            self.browser.get_screenshot_as_file(time.asctime() + '__get_excel_error.png')
            self.browser.refresh()
            self.__get_excel(excel_file_path)

    def __login(self):
        try:
            print '需要重新登录，正在登录'
            self.wait.until(EC.visibility_of_element_located((By.NAME, 'taobaoLoginIfr')))
            self.browser.switch_to.frame(self.browser.find_element_by_name('taobaoLoginIfr'))
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_Static2Quick')))
            # 如果是密码输入界面，那么切换到二维码界面
            if self.browser.find_element_by_id('J_Static2Quick').is_displayed():
                self.browser.find_element_by_id('J_Static2Quick').click()
            # 提取出二维码
            img_url = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '#J_QRCodeImg > img'))).get_attribute('src')
            self.__download(img_url, CODE_IMAGE_PATH)
            # 显示二维码，待扫描
            self.__print_qr(CODE_IMAGE_PATH)
            print('等待用户登录')
            # 判断是否登录成功
            while True:
                try:
                    self.browser.find_element_by_css_selector('#J_menu_login_out > div > span')
                    break
                except NoSuchElementException:
                    time.sleep(2)
                    pass
            print('登录成功')
        except Exception, e:
            print('登录失败, %s' % e)
            raise
    
    def __get_product_from_selection_room(self):
        try:
            print '点击“选取全页商品”'
            self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'select-all'))).click()
            print '等待数量更新'
            self.wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, '#J_bar_selected > strong'), str(SEARCH_PER_PAGE_SIZE)))
            print '点击“加入选品库”'
            self.browser.find_element_by_class_name('add-selection').click()
            print '判断是否需要重新登录'
            if self.browser.find_element_by_class_name('login-panel').is_displayed():
                self.__login()
                # 等待商品加载
                self.wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '#J_search_results .search-result-wrap .block-search-box .pic-box')))
                # 点击“加入选品库”
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
            excel_file_name = cur_time + time.strftime('-%Y-%m-%d.xls', time.localtime(time.time()))
            excel_file_path = EXCEL_FOLD_PATH + excel_file_name
            self.__get_excel(excel_file_path)
            print '提取数据'
            data = xlrd.open_workbook(excel_file_path)
            table = data.sheets()[0]
            title = table.row_values(0)
            goods = {}
            for i in range(1, table.nrows):
                product = table.row_values(i)
                good = dict(zip(title, product))
                print '下载图片'
                path = self.__download_main_pic(good[u'商品主图'] + DOWNLOAD_IMG_SIZE)
                good['主图存储路径'] = path
                goods[str(i)] = good
            self.__save_to_mongo(goods)
            print '删除excel'
            os.remove(excel_file_path)
        except Exception, e:
            print('页面加载有问题，重新加载, %s' % e)
            self.browser.get_screenshot_as_file(time.asctime() + '__get_product_from_selection_room_error.png')
            self.browser.refresh()
            return self.__get_product_from_selection_room()
    
    def __save_to_mongo(self, goods):
        try:
            cur_time = time.strftime('_%Y%m%d%H%M%S', time.localtime(time.time()))
            goods_name = 'goods' + cur_time
            cursor = self.db_table.find({'user': self.package['user']})
            if cursor.count() == 1:
                self.db_table.update_one({'user': self.package['user']},
                                         {"$set": {'cursor.cur_goods': goods_name,
                                                   'cursor.cur_num': 0,
                                                   'nick': self.package['nick'],
                                                   goods_name: goods}})
            elif cursor.count() == 0:
                new = {'user':self.package['user'],
                       'remark':self.package['remark'],
                       'nick':self.package['nick'],
                       'cursor':{'cur_goods':goods_name, 'cur_num':0},
                       goods_name:goods}
                self.db_table.insert(new)
            else:
                print u'错误，MONGGODB找到多个用户，%s' % self.package['user']
                return -1
            print('存储到MONGODB成功')
            return 0
        except Exception, e:
            print('存储到MONGODB失败, %s' % e)
            return -1
    
    def __download(self, url,path,cookies=None):
        print '开始下载', url
        session = requests.Session()
        try:
            response = session.get(url, headers=self.headers, cookies=cookies)
            if response.status_code == 200:
                with open(path, 'wb') as f:
                    f.write(response.content)
                    f.close()
                print('下载成功')
        except RequestException, e:
            print '下载失败',url, e
        finally:
            session.close()
    
    def __download_main_pic(self, url):
        print '开始下载', url
        session = requests.Session()
        try:
            response = session.get(url, headers=self.headers)
            if response.status_code == 200:
                path = PICTURES_FOLD_PATH + '{0}.{1}'.format(md5(response.content).hexdigest(), 'jpg')
                if not os.path.exists(path):
                    with open(path, 'wb') as f:
                        f.write(response.content)
                        f.close()
                    print('下载成功')
                    return path
                else:
                    print '图片已存在'
                    return path
            print('获取图片失败')
            return None
        except RequestException, e:
            print '获取图片失败',url, e
            return None
        finally:
            session.close()
        
    def ali_search(self, keyword):
        try:
            print('开始搜索[%s]' % keyword)
            begin_time = time.time()
            url = 'http://pub.alimama.com/promo/search/index.htm?q=' + keyword.encode('utf-8').replace(r'\x', '%') + \
                  '&toPage=' + str(SEARCH_PAGE) + '&dpyhq=' + str(SEARCH_DPYHJ) + '&perPageSize=' + str(SEARCH_PER_PAGE_SIZE) + \
                  '&freeShipment=' + str(SEARCH_FREE_SHIPMENT) + '&startTkRate=' + str(SEARCH_START_TK_RATE) + '&queryType=' + \
                  str(SEARCH_QUERY_TYPE) + '&sortType=' + str(SEARCH_SORT_TYPE)
            self.browser.get(url)
            print '等待商品加载'
            self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, '#J_search_results > div.search-result-wrap > div.block-search-box > div.pic-box')))
            # self.browser.get_screenshot_as_file('a.png')
            self.__get_product_from_selection_room()
            end_time = time.time()
            print '搜索结束，用时: %d' % (end_time-begin_time)
            return 0
        except TimeoutException:
            try:
                self.browser.find_element_by_css_selector('#J_item_list > div.no-data-list')
                print '没有找到商品'
                return -1
            except NoSuchElementException:
                return self.ali_search(keyword)

    def init_browser(self):
        try:
            print u'开始初始化浏览器'
            url =  'http://pub.alimama.com/'
            self.browser.get(url)
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_menu_login > div'))).click()
            self.__login()
            print u'初始化成功'
        except Exception, e:
            print u'初始化失败，%s' % e
            return self.init_browser()

def make_package(room=u'', user=u'', result=u''):
    d = {'room':room, 'user':user, 'result':result}
    return d

def lianmeng_main(q_wechat_lianmeng, q_lianmeng_wechat):
    print u'lianmeng_main: 进程开始'
    print u'lianmeng_main: 开始初始化浏览器'
    browser_1 = browser()
    browser_1.init_browser()
    print u'lianmeng_main: 开始接收来自wechat的命令'
    while True:
        type, msg = q_wechat_lianmeng.get()
        if type == 'find':
            browser_1.package = msg
            print u'lianmeng_main: 收到命令来自用户【%s】，开始查找【%s】' % (msg['nick'], msg['keyword'])
            result = u'SUCESS' if browser_1.ali_search(msg['keyword']) == 0 else u'FAILED'
            response_package = make_package(room=msg['room'], user=msg['user'], result=result)
            q_lianmeng_wechat.put(('response', response_package))
        elif type == 'cmd':
            print u'lianmeng_main: 收到cmd'
            pass
