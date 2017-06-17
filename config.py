#coding:utf-8
MONGO_URL = 'localhost'
MONGO_DB = 'lianmeng'
MONGO_TABLE = 'lianmeng'
SERVICE_ARGS = ['--load-images=false', '--disk-cache=true', '--output-encoding=utf8', '--script-encoding=utf8']
DOWNLOAD_IMG_SIZE = '_400x400'
CODE_IMAGE_PATH = 'codeimage.jpg'
PICTURES_FOLD_PATH = 'pictures\\'
EXCEL_FOLD_PATH = 'excels\\'

# 查找商品相关设定
# 页数
SEARCH_PAGE = 1
# 店铺优惠券
SEARCH_DPYHJ = 1
# 每页商品数
SEARCH_PER_PAGE_SIZE = 9
# 包邮
SEARCH_FREE_SHIPMENT = 1
# 佣金比例下限
SEARCH_START_TK_RATE = 10
# 销量从高到低
SEARCH_QUERY_TYPE = 0
SEARCH_SORT_TYPE = 9