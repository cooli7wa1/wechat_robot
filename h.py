#coding:utf-8
import os, platform, requests, time, pymongo, xlrd, subprocess
from hashlib import md5
from requests import RequestException
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from lianmeng_config import *
from multiprocessing import Queue
from pyquery import PyQuery as pq

options = webdriver.ChromeOptions()
options.add_argument('window-size=1400x900')
browser = webdriver.Chrome(chrome_options=options)
wait = WebDriverWait(browser, 10)


browser.get('http://pub.alimama.com/promo/search/index.htm?q=%E7%99%BD%E8%89%B2%E7%8E%A9%E5%85%B7%E7%86%8A&_t=1498372757011&toPage=1&dpyhq=1&freeShipment=1&startTkRate=10')
wait.until(EC.presence_of_element_located(
    (By.CSS_SELECTOR, '#J_search_results > div.search-result-wrap > div.block-search-box > div.pic-box')))
doc = pq(browser.page_source).remove_namespaces()
print doc('div.search-result-wrap').find('.block-search-box').length
