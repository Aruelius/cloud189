<h3 align="center">- cloud189-cli -</h3>

### 一：准备
1. Python 版本 >= 3.6
2. 安装依赖
```sh
pip install -r requirements.txt
```
3. 配置
运行 ``python cloud189-cli.py``, 输入用户名与密码  

账号为自己的天翼云盘手机号，密码不会有回显。

也可以 自接两次回车后，输入 `clogin` 按提示输入 `cookie` 登录。

### 二：使用
0. 不加参数者进入交互模式
```sh
python cloud189-cli.py  #  提示符为 >

> bye# 退出
```
1. 查看**根目录**的文件  
```sh
python cloud189-cli.py ls
```  
2. 上传文件至**根目录**  
```sh
python cloud189-cli.py upload '文件路径'
```  
3. 下载**根目录**的文件  
```sh
python cloud189-cli.py down  文件ID # 文件ID 第一步看
```  
4. 分享**根目录**的文件  
```sh
python cloud189-cli.py share 文件ID # 文件ID 第一步看
```  
5. 删除**根目录**的文件  
```sh
python cloud189-cli.py delete 文件ID # 文件ID 第一步看
```

### 三：免责
您使用本工具做的任何事情都雨我无瓜。
