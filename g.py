#coding:utf8
import re

def mark(zhanghao):
    zhanghao_mark= u''
    if re.match(r'\d{11}', zhanghao):
        zhanghao_mark = zhanghao[0:3] + u'xxxxx' + zhanghao[-4:]
    elif re.match(r'(.{3}).*(@.*\.com)', zhanghao):
        match = re.match(r'(.{3}).*(@.*\.com)', zhanghao)
        zhanghao_mark = match.group(1) + u'xxxxx' + match.group(2)
    return zhanghao_mark

zhanghao = raw_input('input zhanghao: ')
print mark(zhanghao)
