import os
import sys
import logging
from platform import system as platform

import readline
import requests

from cloud189.api.utils import ROOT_DIR
from cloud189.api import Cloud189
from cloud189.cli import version

__all__ = ['error', 'info', 'clear_screen', 'get_file_size_str', 'parsing_up_params',
           'check_update', 'handle_name', 'handle_args', 'captcha_handler',
           'set_completer', 'print_help', 'check_update']

GIT_REPO = "Aruelius/cloud189"
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
M_platform = platform()
OS_NAME = os.name
_ERR = False  # 用于标识是否遇到错误


def error(msg):
    global _ERR
    print(f"\033[1;31mError : {msg}\033[0m")
    _ERR = True


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
    if 0 < filesize < 1 << 20:
        return f"{round(filesize/1024, 2)}KB"
    elif 1 << 20 < filesize < 1 << 30:
        return f"{round(filesize/(1 << 20), 2)}MB"
    elif 1 << 30 < filesize < 1 << 40:
        return f"{round(filesize/(1 << 30), 2)}GB"
    elif 1 << 40 < filesize < 1 << 50:
        return f"{round(filesize/(1 << 40), 2)}TB"
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
    elif code == Cloud189.NETWORK_ERROR:
        return '网络连接异常'
    elif code == Cloud189.CAPTCHA_ERROR:
        return '验证码错误'
    elif code == Cloud189.UP_COMMIT_ERROR:
        return '上传文件 commit 错误'
    elif code == Cloud189.UP_CREATE_ERROR:
        return '创建上传任务出错'
    elif code == Cloud189.UP_EXHAUSTED_ERROR:
        return '今日上传量已用完'
    elif code == Cloud189.UP_ILLEGAL_ERROR:
        return '文件非法'
    else:
        return '未知错误'


def get_upload_status(msg, percent):
    """文件上传状态"""
    if msg == 'quick_up':
        return "  \033[1;34m秒传!\033[0m "
    elif msg == 'check':
        return "\033[1;34m秒传检查\033[0m"
    elif msg == 'error':
        return "\033[1;31m秒传失败\033[0m"
    elif msg == 'exist':
        return "\033[1;31m远端存在\033[0m"
    elif msg == 'illegal':
        return "\033[1;31m非法文件\033[0m"
    elif msg == 'exhausted':
        return "\033[1;31m流量耗尽\033[0m"
    else:
        return percent


def set_console_style():
    """设置命令行窗口样式"""
    if os.name != 'nt':
        return None
    os.system('mode 120, 40')
    os.system(f'title 天翼云盘-cli {version}')


def captcha_handler(img_data):
    """处理下载时出现的验证码"""
    img_path = ROOT_DIR + os.sep + 'captcha.png'
    with open(img_path, 'wb') as f:
        f.write(img_data)
    if M_platform == 'Darwin':
        os.system(f'open {img_path}')
    elif M_platform == 'Linux':
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


def parsing_up_params(arg: str, follow, force, mkdir) -> (bool, bool, bool, bool):
    """解析文件上传参数
    :param str arg: 解析参数
    :param bool follow: 实时任务
    :param bool force: 强制上传
    :param bool mkdir: 不创建父文件夹
    :return: follow, force, mkdir, match(标识是否需要删除 arg)
    """
    match = False
    if len(arg) > 1:
        if arg.startswith('--'):
            if arg == '--follow':  # 实时任务
                follow = True
                match = True
            elif arg == '--force':  # 强制上传
                force = True
                match = True
            elif arg == '--nodir':  # 不创建父文件夹
                mkdir = False
                match = True
        elif arg.startswith('-'):
            for i in arg[1:]:
                if i == 'f':  # 实时任务
                    follow = True
                    match = True
                elif i == 'F':  # 强制上传
                    force = True
                    match = True
                elif i == 'n':  # 不创建父文件夹
                    mkdir = False
                    match = True
    return follow, force, mkdir, match


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
    if _ERR:  # 有错误就不清屏不打印 logo
        return None
    else:
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
    help_text = f""" cloud189-cli | 天翼云盘客户端 for {M_platform} | v{version}
    • 支持文件秒传，文件夹保持相对路径上传
    • 获取文件分享链接，批量上传下载，断点续传等功能

    命令帮助 :
    help        显示本信息
    update      检查更新
    *rmode      屏幕阅读器模式
    refresh/r   强制刷新文件列表
    login       使用账号密码登录网盘/添加用户
    clogin      使用 Cookie 登录网盘/添加用户
    *logout     删除当前用户 Cookie/删除指定用户
    su          列出、切换账户
    jobs/j      查看后台任务列表
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
    clear/c     清空屏幕
    upload/u    上传文件(夹)
    down/d      下载文件、提取分享链接直链 # TODO: 下载文件夹
    setpath     设置文件下载路径
    who/quota   查看当前账户信息
    sign        签到+抽奖
    bye/exit/b  退出本程序

    * 表示目前版本无法使用。
    更详细的介绍请参考本项目的 Github 主页:
    https://github.com/{GIT_REPO}   
    如有 Bug 反馈或建议请在 GitHub 提 Issue
    感谢您的使用 (●'◡'●)
    """
    print(help_text)


def check_update():
    """检查更新"""
    print("正在检测更新...")
    api = f"https://api.github.com/repos/{GIT_REPO}/releases/latest"
    tag_name = None
    try:
        resp = requests.get(api, timeout=3).json()
        tag_name, msg = resp['tag_name'], resp['body']
    except (requests.RequestException, AttributeError, KeyError) as err:
        error(f"检查更新时发生异常，可能是 GitHub 间歇性无法访问！\n{err=}")
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
