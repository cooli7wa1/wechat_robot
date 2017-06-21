#!/bin/bash -
# ps -aux | grep -E "chrome|wechat" | awk -F ' ' '{system("kill -9 "$2"")}'
echo -e "\033[34m ==> begin to clean process \033[0m"
killall python
echo -e "\033[34m ==> python clear \033[0m"
killall chromedriver
echo -e "\033[34m ==> chromdriver clear \033[0m"
killall /opt/google/chrome/chrome
echo -e "\033[34m ==> chrome clear \033[0m"
echo -e "\033[32m ==> clear finish \033[0m"
