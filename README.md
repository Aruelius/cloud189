<h1 align="center">- cloud189-cli -</h3>
<pre align="center">
#    /$$$$$$  /$$                           /$$   /$$    /$$$$$$   /$$$$$$ 
#   /$$__  $$| $$                          | $$ /$$$$   /$$__  $$ /$$__  $$
#  | $$  \__/| $$  /$$$$$$  /$$   /$$  /$$$$$$$|_  $$  | $$  \ $$| $$  \ $$
#  | $$      | $$ /$$__  $$| $$  | $$ /$$__  $$  | $$  |  $$$$$$/|  $$$$$$$
#  | $$      | $$| $$  \ $$| $$  | $$| $$  | $$  | $$   >$$__  $$ \____  $$
#  | $$    $$| $$| $$  | $$| $$  | $$| $$  | $$  | $$  | $$  \ $$ /$$  \ $$
#  |  $$$$$$/| $$|  $$$$$$/|  $$$$$$/|  $$$$$$$ /$$$$$$|  $$$$$$/|  $$$$$$/
#   \______/ |__/ \______/  \______/  \_______/|______/ \______/  \______/ 
#                                                                          
--------------------------------------------------------------------------
</pre>
<p align="center">
<img src="https://img.shields.io/github/v/release/Aruelius/cloud189.svg?logo=iCloud"> <img src="https://img.shields.io/github/last-commit/Aruelius/cloud189.svg">
</p>

# 准备
1. Python 版本 >= 3.8

2. 安装依赖
    ```sh
    pip install -r requirements.txt
    ```
> 注意 `pyreadline` 是专门为 `Windows` 设计的，`*nix` 中 python 标准库中一般默认包含 `readline` 模块，没有请看[这里](#jump)。

3. 配置
运行 ``python main.py``, 输入用户名与密码，  
账号为自己的天翼云盘手机号，密码不会有回显，  
也可以 直接两次回车后，输入 `clogin` 按提示输入 `cookie` 登录。  
所有信息**加密** 保存至 `.config` 文件。

# 功能

|命令                                 |描述                    |
|-------------------------------------|-----------------------|
|help                                 |查看帮助文档             |
|login                                |用户名+密码 登录/添加用户    |
|clogin                               |cookie 登录/添加用户         |
|refresh                              |刷新当前目录            |
|setpath                              |修改下载路径(默认 ./downloads) |
|update                               |检测软件更新            |
|who/quota                            |查看账户信息、空间大小  |
|clear                                |清屏                   |
|cdrec                                |进入回收站              |
|[cdrec]  ls                          |显示回收站目录           |
|[cdrec]  rec + `文件名`               |恢复文件                |
|[cdrec]  clean                       |清空回收站              |
|[cdrec]  cd ..                       |退出回收站              |
|su     + `[-l/用户名]`                |列出用户/切换用户       |
|ls     + `[-l] [文件夹]`              |列出文件与目录           |
|cd     + `文件夹名`                   |切换工作目录             |
|upload + `文件(夹)路径`                |上传文件(夹)            |
|down   + `文件名/分享链接`             |下载文件/提取分享链接下载直链  |
|mkdir  + `文件夹名`                   |创建文件夹               |
|rm     + `文件/文件夹`                 |删除文件(夹)            |
|share  + `文件/文件夹`                 |分享文件(夹)            |
|shared + `[2]`                       |已经分享文件(夹)信息      |
|jobs   + `[-f] [任务id]`              |查看后台上传下载任务      |
|rename + `文件(夹)名 [新名]`           |重命名                  |
|mv     + `文件名`                     |移动文件                |
|bye/exit                             |退出                    |

*还未完成，在做了……

`ll = ls -l` 表示列出详细列表，`ls` 只显示文件(夹)名，都可以接一个一级子文件夹作为参数。  
`down`、`upload`、`rm` 支持多个多个操作文件作为参数，如果文件名中有空格引号，使用 `''`、`""` 包裹文件名，或则在空格引号前使用转义符 `\`。  
`jobs -f`、`upload -f`、`down -f`表示实时查看任务状态，类似于 `Linux` 中的 `tail -f`，按任意键 + 回车 退出。  
使用账号密码登录时，上传文件时会**先**进行文件秒传检测，目前使用 cookie 登录无法秒传。  
下载支持断点续传。  
注意：从 **v0.0.4** 起，`.config` 文件与以前版本不兼容！

# 使用
1. 不加参数则进入交互模式
```sh
# 提示符为 >
python3 main.py
> cd '文件夹'
...
> ls
...
> bye
```

2. 带上命令与参数进入单任务模式
```sh
python3 main.py upload '文件路径'
# 或者
./main.py upload '文件路径'
```  

# <span id="jump">依赖</span>
如果在 Linux 运行出现
~~~shell
import readline
ValueError: _type_ 'v' not supported
~~~
需要安装依赖，然后重新编译 Python  
Ubuntu
~~~shell
sudo apt-get install libreadline-dev
~~~
CentOS
~~~shell
yum install readline-devel
~~~
# License

[GPL-3.0](https://github.com/Aruelius/cloud189/blob/master/LICENSE)

# 致谢

> [LanZouCloud-CMD](https://github.com/zaxtyson/LanZouCloud-CMD)  
> [Dawnnnnnn/Cloud189](https://github.com/Dawnnnnnn/Cloud189)
