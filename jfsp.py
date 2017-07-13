#coding:utf8
import os
import requests
import xlrd, openpyxl, re

INTEGRAL_GOOD_PROP = 100
DOWNLOAD_IMG_SIZE = u'_400x400'

JFSP_PATH = u'F:\\积分商品\\'
JFSP_EXCEL = JFSP_PATH + u'积分商品.xlsx'
label_no_yhj = [u'商品名称', u'淘宝客短链接(300天内有效)', u'淘口令(30天内有效)', u'活动结束时间',
                u'商品价格(单位：元)', u'活动收入比率(%)']
lalel_yhj = [u'商品名称', u'优惠券短链接(300天内有效)', u'优惠券淘口令(30天内有效)', u'活动结束时间',
             u'商品价格(单位：元)', u'活动e收入比率(%)']

def download_pic(url, file_name):
    url = url + DOWNLOAD_IMG_SIZE
    print u'开始下载, %s, %s' % (file_name, url)
    headers = {'User-Agent':'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
    session = requests.Session()
    response = session.get(url, headers=headers)
    if response.status_code == 200:
        path = JFSP_PATH + file_name
        with open(path, 'wb') as f:
            f.write(response.content)
            f.close()
        print u'下载成功'
    session.close()

def get_next_number():
    wb = openpyxl.load_workbook(JFSP_EXCEL)
    ws = wb.get_sheet_by_name(u'Sheet1')
    rows = ws.rows
    cur_number = 0
    for row in rows:
        if not row[0].value:
            break
        cur_number = row[0].value
    wb.close()
    return int(cur_number) + 1

def find_new_excel():
    files = os.listdir(JFSP_PATH)
    for file in files:
        if re.match('a-.*.xls', file):
            return file
    return None

def copy_goods_to_jfsp(new_excel):
    print u'开始复制商品到积分商品表格，并下载图片'
    wb_new = xlrd.open_workbook(JFSP_PATH + new_excel)
    ws_new = wb_new.sheets()[0]
    wb = openpyxl.load_workbook(JFSP_EXCEL)
    ws = wb.get_sheet_by_name(u'Sheet1')
    title = ws_new.row_values(0)
    next_number = get_next_number()
    for i in range(1, ws_new.nrows):
        detail = ws_new.row_values(i)
        good = dict(zip(title, detail))
        detail_new = []
        detail_new.append(next_number)
        if good[u'优惠券面额'] == u'无':
            for a in label_no_yhj:
                if a == u'活动结束时间':
                    detail_new.append(good[a].split(' ')[0])
                else:
                    detail_new.append(good[a])
            detail_new.append('0')
            real_price = good[u'商品价格(单位：元)']
            detail_new.append(real_price)
            integral = int(round(float(real_price) * (1 - (float(good[u'活动收入比率(%)']) - 5) / 100) * INTEGRAL_GOOD_PROP))
            detail_new.append(integral)
        else:
            yhj_msg = good[u'优惠券面额']
            if re.search(u'满(\d+)元减(\d+)元', yhj_msg):
                yhj = eval(re.search(u'满(\d+)元减(\d+)元', yhj_msg).group(2))
            elif re.search(u'(\d+)元无条件券', yhj_msg):
                yhj = eval(re.search(u'(\d+)元无条件券', yhj_msg).group(1))
            for a in lalel_yhj:
                if a == u'活动结束时间':
                    detail_new.append(good[a].split(' ')[0])
                else:
                    detail_new.append(good[a])
            detail_new.append(yhj)
            real_price = float(good[u'商品价格(单位：元)']) - yhj
            detail_new.append(real_price)
            integral = int(round(float(real_price) * (1 - (float(good[u'活动收入比率(%)']) - 5) / 100) * INTEGRAL_GOOD_PROP))
            detail_new.append(integral)
        download_pic(good[u'商品主图'], u'JP%d.jpg' % next_number)
        ws.append(detail_new)
        next_number += 1
    wb.save(JFSP_EXCEL)
    print u'处理结束'
    print u'删除临时表格'
    os.remove(JFSP_PATH + new_excel)

if __name__ == '__main__':
    new_excel = find_new_excel()
    if not new_excel:
        print u'没有找到新下载的excel'
    copy_goods_to_jfsp(new_excel)
