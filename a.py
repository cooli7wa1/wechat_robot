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

options = webdriver.ChromeOptions()
options.add_argument('window-size=1600x900')
browser = webdriver.Chrome(chrome_options=options)
wait = WebDriverWait(browser, 50)


# browser.get('http://pub.alimama.com/manage/selection/list.htm?spm=a219t.7900221/1.1998910419.d3d9c63c9.y6J0zy')
# while True:
#     hidden_close = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#sList > div:nth-child(2) > a.close > i')))
#     ActionChains(browser).move_to_element(hidden_close).perform()
#     while True:
#         time.sleep(5)
#     wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#sList > div:nth-child(3) > a.close'))).click()
#     wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'body > div.table - operation - mask > div.operation > button.btn.btn - brand.w100'))).click()
browser.get('http://pub.alimama.com/promo/search/index.htm?q=%E5%93%88%E8%A1%A3&_t=1498492710352')
wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, '#J_bar_selected > strong'), '40'))
cur_num = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#J_bar_selected > strong'))).text
if cur_num != '0':
    browser.find_element_by_css_selector('#J_bar_selected').click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,
                                                '#J_selection_bar > div > div.selection-selected > div.selection-tab-wrap.wrap.clearfix > a'))).click()
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR,
                                                '#J_global_dialog > div > div.dialog-ft.dialog-add-ok > span.btn.btn-brand.w110.mr20'))).click()
    browser.find_element_by_css_selector('#J_bar_selected').click()
import requests

