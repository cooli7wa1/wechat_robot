#coding:utf-8
import os, platform, requests, time, pymongo, subprocess
from hashlib import md5
from requests import RequestException
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

options = webdriver.ChromeOptions()
options.add_argument('window-size=1400x900')
options.add_argument('disable-gpu')
options.add_argument('headless')
browser = webdriver.Chrome(chrome_options=options)
wait = WebDriverWait(browser, 10)


browser.get('http://www.baidu.com')
wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#kw'))).send_keys(u'哈哈')
browser.get_screenshot_as_file('a.png')
