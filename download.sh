#!/bin/bash

ROBOT_DATA_PATH=''

echo 'enter where are you? (ali,home,work)'
read place
case "$place" in
ali)
	ROBOT_DATA_PATH=/root/robot_data
	;;
home)
	ROBOT_DATA_PATH=/home/cooli7wa/Documents/robot_data
	;;
work)
	ROBOT_DATA_PATH=/home/cooli7wa/Documents/robot_data
	;;
*)
	echo 'place wrong'
	exit 1
	;;
esac

MONGODB_BACKUP_PATH=$ROBOT_DATA_PATH/xiaoyezi/mongodb

echo -e "\033[34m ==> enter robot data fold \033[0m"
cd ROBOT_DATA_PATH 
echo -e "\033[34m ==> git checkout ./ \033[0m"
git checkout ./
echo -e "\033[34m ==> git pull \033[0m"
git pull
if [ $? -ne 0 ];then
	echo -e "\033[31m something wrong \033[0m"
	exit 1
fi
echo -e "\033[34m ==> enter mongodb fold \033[0m"
cd MONGODB_BACKUP_PATH
echo -e "\033[34m ==> mongorestore \033[0m"
mongorestore --drop
if [ $? -ne 0 ];then
	echo -e "\033[31m something wrong \033[0m"
	exit 1
fi
echo -e "\033[32m ==> all ok \033[0m"
