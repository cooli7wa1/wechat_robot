#!/bin/bash

ROBOT_DATA_PATH=$HOME/Documents/robot_data/
MONGODB_BACKUP_PATH=$ROBOT_DATA_PATH/xiaoyezi/mongodb

echo -e "\033[31m 上传 \033[0m"
echo 'are you sure?'
read tmp
if [ u$tmp != u'yes' ];then
	exit 1
fi

echo -e "\033[34m ==> enter mongodb fold \033[0m"
cd $MONGODB_BACKUP_PATH
echo -e "\033[34m ==> mongodump \033[0m"
mongodump -d wechat
mongodump -d lianmeng
if [ $? -ne 0 ];then
	echo -e "\033[31m something wrong \033[0m"
	exit 1
fi
echo -e "\033[34m ==> enter robot data fold \033[0m"
cd $ROBOT_DATA_PATH
echo -e "\033[34m ==> git add --all \033[0m"
git add --all
if [ $? -ne 0 ];then
	echo -e "\033[31m something wrong \033[0m"
	exit 1
fi
echo -e "\033[34m ==> git commit -m 'man update' \033[0m"
git commit -m "man update"
if [ $? -ne 0 ];then
	echo -e "\033[31m something wrong \033[0m"
	exit 1
fi
echo -e "\033[34m ==> git push origin master' \033[0m"
git push origin master
if [ $? -ne 0 ];then
	echo -e "\033[31m something wrong \033[0m"
	exit 1
fi
echo -e "\033[32m ==> all ok \033[0m"
