import os
import sys
import logging
from platform import system as platform

import readline
import requests

from cloud189.api import Cloud189
from cloud189.cli import version


GIT_REPO = "Aruelius/cloud189"
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def error(msg):
    print(f"\033[1;31mError : {msg}\033[0m")


def info(msg):
    print(f"\033[1;34mInfo : {msg}\033[0m")


def clear_screen():
    """清空屏幕"""
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


def get_file_size_str(filesize) -> str:
    if not filesize:
        return ''
    filesize = int(filesize)
    if 0 < filesize < 1024**2:
        return f"{round(filesize/1024, 2)}KB"
    elif 1024**2 < filesize < 1024**3:
        return f"{round(filesize/1024**2, 2)}MB"
    elif 1024**3 < filesize < 1024**4:
        return f"{round(filesize/1024**3, 2)}GB"
    elif 1024**4 < filesize < 1024**5:
        return f"{round(filesize/1024**4, 2)}TB"
    else: return f"{filesize}Bytes"


def why_error(code):
    """错误原因"""
    if code == Cloud189.URL_INVALID:
        return '分享链接无效'
    elif code == Cloud189.LACK_PASSWORD:
        return '缺少提取码'
    elif code == Cloud189.PASSWORD_ERROR:
        return '提取码错误'
    elif code == Cloud189.FILE_CANCELLED:
        return '分享链接已失效'
    elif code == Cloud189.ZIP_ERROR:
        return '解压过程异常'
    elif code == Cloud189.NETWORK_ERROR:
        return '网络连接异常'
    elif code == Cloud189.CAPTCHA_ERROR:
        return '验证码错误'
    else:
        return '未知错误'


def set_console_style():
    """设置命令行窗口样式"""
    if os.name != 'nt':
        return None
    os.system('mode 120, 40')
    os.system(f'title 天翼云盘-cli {version}')


def captcha_handler(img_data):
    """处理下载时出现的验证码"""
    img_path = os.path.dirname(sys.argv[0]) + os.sep + 'captcha.png'
    with open(img_path, 'wb') as f:
        f.write(img_data)
    m_platform = platform()
    if m_platform == 'Darwin':
        os.system(f'open {img_path}')
    elif m_platform == 'Linux':
        # 检测是否运行在没有显示屏的 console 上
        if os.environ.get('DISPLAY'):
            os.system(f'xdg-open {img_path}')
        else:
            from fabulous import image as fabimg

            print(fabimg.Image(f'{img_path}'))
    else:
        os.startfile(img_path)  # windows
    ans = input('\n请输入验证码:')
    os.remove(img_path)
    return ans


def text_align(text, length) -> str:
    """中英混合字符串对齐"""
    text_len = len(text)
    for char in text:
        if u'\u4e00' <= char <= u'\u9fff':
            text_len += 1
    space = length - text_len
    return text + ' ' * space


def handle_name(name: str) -> str:
    """使用引号包裹有空格的文件名"""
    if ' ' in name:
        name = "'" + name + "'"
    return name


def handle_args(args: str) -> list:
    '''处理参数列表，返回参数列表'''
    result = []
    arg = ''
    i = 0
    flag_1 = False  # 标记 "
    flag_2 = False  # 标记 '
    while i < len(args):
        if flag_1 and args[i] != '"':
            arg += args[i]
        elif flag_2 and args[i] != '\'':
            arg += args[i]
        elif args[i] not in (' ', '\\', '"', '\''):
            arg += args[i]
        elif args[i] == '\\' and i < len(args) and args[i + 1] in (' ', '"', '\''):
            arg += args[i + 1]
            i += 1  # 额外前进一步
        elif args[i] == ' ':
            if arg:
                result.append(arg)
                arg = ''  # 新的参数
        elif args[i] == '"':
            if flag_2:  # ' some"s thing ' "other params"
                arg += args[i]
            else:
                flag_1 = not flag_1
        elif args[i] == '\'':
            if flag_1:  # " some's thing " 'other params'
                arg += args[i]
            else:
                flag_2 = not flag_2
        i += 1
    if arg:
        result.append(arg)
    return result


def set_completer(choice_list, *, cmd_list=None, condition=None):
    """设置自动补全"""
    if condition is None:
        condition = lambda typed, choice: choice.startswith(typed) or choice.startswith("'" + typed)  # 默认筛选条件：选项以键入字符开头

    def completer(typed, rank):
        tab_list = []  # TAB 补全的选项列表
        if cmd_list is not None and not typed:  # 内置命令提示
            return cmd_list[rank]

        for choice in choice_list:
            if condition(typed, choice):
                tab_list.append(choice)
        return tab_list[rank]

    readline.parse_and_bind("tab: complete")
    readline.set_completer(completer)


def print_logo():
    """输出logo"""
    clear_screen()
    logo_str = f"""
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
      Github: https://github.com/{GIT_REPO} (Version: {version})
--------------------------------------------------------------------------
    """
    print(logo_str)


def print_help():
    # clear_screen()
    help_text = f""" cloud189-cli | 天翼云盘客户端 for {sys.platform} | v{version}
    • 支持文件秒传，文件夹保持相对路径上传
    • 获取文件分享链接，批量上传下载，断点续传等功能

    命令帮助 :
    help        显示本信息
    update      检查更新
    *rmode      屏幕阅读器模式
    refresh     强制刷新文件列表
    login       使用账号密码登录网盘
    clogin      使用 Cookie 登录网盘
    *logout     注销当前账号
    jobs        查看后台任务列表
    ls          列出文件(夹)，仅文件名
    ll          列出文件(夹)，详细
    cd          切换工作目录
    cdrec       进入回收站目录
        rm      彻底删除文件
        rec     恢复文件
        clean   清空回收站
        cd ..   退出回收站
    rm          删除网盘文件(夹)
    rename      重命名文件(夹)
    mv          移动文件(夹)
    mkdir       创建新文件夹
    share       显示文件(夹)分享信息
    shared      显示已经分享的文件(夹)信息
    clear       清空屏幕
    upload      上传文件(夹)
    down        下载文件 # TODO: 下载文件夹、url
    setpath     设置文件下载路径
    bye/exit    退出本程序

    * 表示目前版本无法使用。
    更详细的介绍请参考本项目的 Github 主页:
    https://github.com/{GIT_REPO}   
    如有 Bug 反馈或建议请在 GitHub 提 Issue
    感谢您的使用 (●'◡'●)
    """
    print(help_text)


def check_update():
    """检查更新"""
    clear_screen()
    print("正在检测更新...")
    api = f"https://api.github.com/repos/{GIT_REPO}/releases/latest"
    tag_name = None
    try:
        resp = requests.get(api, timeout=3).json()
        tag_name, msg = resp['tag_name'], resp['body']
    except (requests.RequestException, AttributeError, KeyError) as err:
        error(f"检查更新时发生异常\n{err=}")
        input()
        return None
    if tag_name:
        ver = version.split('.')
        ver2 = tag_name.replace('v', '').split('.')
        local_version = int(ver[0]) * 100 + int(ver[1]) * 10 + int(ver[2])
        remote_version = int(ver2[0]) * 100 + int(ver2[1]) * 10 + int(ver2[2])
        if remote_version > local_version:
            print(f"程序可以更新 v{version} -> {tag_name}")
            print(f"\n@更新说明:\n{msg}")
            print("\n@Linux 更新:")
            input(f"git clone --depth=1 https://github.com/{GIT_REPO}.git")
        else:
            print("(*/ω＼*) 暂无新版本发布~")
            print("但项目可能已经更新，建议去项目主页看看")
            print("如有 Bug 或建议,请提 Issue")
            print(f"Github: https://github.com/{GIT_REPO}")
