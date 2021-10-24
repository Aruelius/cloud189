import os
from time import sleep
from getpass import getpass
from random import choice
from sys import exit as exit_cmd
from webbrowser import open_new_tab

from cloud189.api import Cloud189
from cloud189.api.models import FileList, PathList
from cloud189.api.token import get_token
from cloud189.api.utils import logger

from cloud189.cli import config
from cloud189.cli.downloader import Downloader, Uploader
from cloud189.cli.manager import global_task_mgr
from cloud189.cli.recovery import Recovery
from cloud189.cli.utils import *


class Commander:
    """网盘命令行"""

    def __init__(self):
        self._prompt = '> '
        self._disk = Cloud189()
        self._task_mgr = global_task_mgr
        self._dir_list = ''
        self._file_list = FileList()
        self._path_list = PathList()
        self._parent_id = -11
        self._parent_name = ''
        self._work_name = ''
        self._work_id = -11
        self._last_work_id = -11
        self._reader_mode = False
        self._reader_mode = config.reader_mode
        self._default_dir_pwd = ''
        self._disk.set_captcha_handler(captcha_handler)

    @staticmethod
    def clear():
        clear_screen()

    @staticmethod
    def help():
        print_help()

    @staticmethod
    def update():
        check_update()

    def bye(self):
        if self._task_mgr.has_alive_task():
            info("有任务在后台运行, 退出请直接关闭窗口")
        else:
            config.work_id = self._work_id
            exit_cmd(0)

    def rmode(self):
        """适用于屏幕阅读器用户的显示方式"""
        # TODO
        choice = input("以适宜屏幕阅读器的方式显示(y): ")
        if choice and choice.lower() == 'y':
            config.reader_mode = True
            self._reader_mode = True
            info("已启用 Reader Mode")
        else:
            config.reader_mode = False
            self._reader_mode = False
            info("已关闭 Reader Mode")

    def cdrec(self):
        """进入回收站模式"""
        rec = Recovery(self._disk)
        rec.run()
        self.refresh()

    def refresh(self, dir_id=None, auto=False):
        """刷新当前文件夹和路径信息"""
        dir_id = self._work_id if dir_id is None else dir_id

        if dir_id == -11:
            self._file_list, self._path_list = self._disk.get_root_file_list()
        else:
            self._file_list, self._path_list = self._disk.get_file_list(dir_id)
        if not self._file_list and not self._path_list:
            if auto:
                error(f"文件夹 id={dir_id} 无效(被删除), 将切换到根目录！")
                return self.refresh(-11)
            else:
                error(f"文件夹 id 无效 {dir_id=}, {self._work_id=}")
                return None
        self._prompt = '/'.join(self._path_list.all_name) + ' > '
        self._last_work_id = self._work_id
        self._work_name = self._path_list[-1].name
        self._work_id = self._path_list[-1].id
        if dir_id != -11:  # 如果存在上级路径
            self._parent_name = self._path_list[-2].name
            self._parent_id = self._path_list[-2].id

    def login(self, args):
        """登录网盘"""
        if args:
            if '--auto' in args:
                if config.cookie and self._disk.login_by_cookie(config) == Cloud189.SUCCESS:
                    self.refresh(config.work_id, auto=True)
                    return None
        username = input('输入用户名:')
        password = getpass('输入密码:')
        if not username or not password:
            error('没有用户名或密码 :(')
            return None
        code = self._disk.login(username, password)
        if code == Cloud189.NETWORK_ERROR:
            error("登录失败,网络连接异常")
            return None
        elif code == Cloud189.FAILED:
            error('登录失败,用户名或密码错误 :(')
            os._exit(0)
        # 登录成功保存用户 cookie
        config.username = username
        config.password = password
        config.cookie = self._disk.get_cookie()
        code, token = get_token(username, password)
        if code == Cloud189.SUCCESS:
            config.set_token(*token)
            self._disk.set_session(*token)
        self._work_id = -11
        self.refresh(-11)

    def clogin(self):
        """使用 cookie 登录"""
        if platform() == 'Linux' and not os.environ.get('DISPLAY'):
            info("请使用浏览器打开: https://cloud.189.cn 获取 cookie")
        else:
            open_new_tab('https://cloud.189.cn')
            info("请设置 Cookie 内容:")
        c_login_user = input("COOKIE_LOGIN_USER=")
        if not c_login_user:
            error("请输入正确的 Cookie 信息")
            return None
        cookie = {"COOKIE_LOGIN_USER": str(c_login_user)}
        if self._disk.login_by_cookie(cookie) == Cloud189.SUCCESS:
            user = self._disk.get_user_infos()
            if not user:
                error("发生未知错误！")
                return None
            user_infos = {
                'name': user.account.replace('@189.cn', ''),
                'pwd': '',
                'cookie': cookie,
                'key': '',
                'secret': '',
                'token': '',
                'save_path': './downloads',
                'work_id': -11
            }
            config.set_infos(user_infos)
            self._work_id = config.work_id
            self.refresh()
        else:
            error("登录失败, 请检查 Cookie 是否正确")

    def logout(self, args):
        """注销/删除用户"""
        if args:  # 删除用户
            for name in args:
                result = config.del_user(name)
                if result:
                    info(f"成功删除用户 {name}")
                else:
                    error(f"删除用户 {name} 失败！")
            return None
        clear_screen()
        self._prompt = '> '
        # self._disk.logout()  # TODO(rachpt@126.com): 还没有注销登录的方法
        self._file_list.clear()
        self._path_list = ''
        self._parent_id = -11
        self._work_id = -11
        self._last_work_id = -11
        self._parent_name = ''
        self._work_name = ''
        config.cookie = None

    def su(self, args):
        """列出、切换用户"""
        users = config.get_users_name()
        def list_user():
            for i, user in enumerate(users):
                user_info = config.get_user_info(user)
                methord = "用户名+密码 登录" if user_info[2] else "Cookie 登录"
                print(f"[{i}] 用户名: {user}, {methord}")
        if args:
            if args[0] == '-l':
                list_user()
                return None
            elif args[0] in users:
                select_user = args[0]
            else:
                error(f"用户名 {args[0]} 无效")
                return None
        else:
            list_user()
            select = input("请输入用户序号, [0、1 ... ]: ")
            if select.isnumeric():
                select = int(select)
                if select > len(users):
                    error(f"序号 {select} 无效!")
                    return None
                select_user = users[select]
            else:
                error(f"序号 {select} 无效!")
                return None
        config.work_id = self._work_id  # 保存旧的工作目录
        result = config.change_user(select_user)
        if result and self._disk.login_by_cookie(config) == Cloud189.SUCCESS:
            info(f"成功切换至用户 {config.username}")
            self.refresh(config.work_id)
        else:
            error("切换用户失败!")

    def ls(self, args):
        """列出文件(夹)"""
        fid = old_fid = self._work_id
        flag_full = False
        flag_arg_l = False
        if args:
            if len(args) >= 2:
                if args[0] == '-l':
                    flag_full = True
                    fname = args[-1]
                elif args[-1] == '-l':
                    flag_full = True
                    fname = args[0]
                else:
                    info("暂不支持查看多个文件！")
                    fname = args[0]
            else:
                if args[0] == '-l':
                    flag_full = True
                    flag_arg_l = True
                else:
                    fname = args[0]
            if not flag_arg_l:
                if file := self._file_list.find_by_name(fname):
                    if file.isFolder:
                        fid = file.id
                    else:
                        error(f"{fname} 非文件夹，显示当前目录文件")
                else:
                    error(f"{fname} 不存在，显示当前目录文件")
        if fid != old_fid:
            self._file_list, _ = self._disk.get_file_list(fid)
        if not flag_full:  # 只罗列文件名
            for file in self._file_list:
                if file.isFolder:
                    print(f"\033[1;34m{handle_name(file.name)}\033[0m", end='  ')
                else:
                    print(f"{handle_name(file.name)}", end='  ')
            print()
        else:
            if self._reader_mode:  # 方便屏幕阅读器阅读
                for file in self._file_list:
                    print(
                        f"{handle_name(file.name)}  大小:{get_file_size_str(file.size)}  上传时间:{file.ctime}  ID:{file.id}")
            else:  # 普通用户显示方式
                for file in self._file_list:
                    star = '✦' if file.isStarred else '✧'  # 好像 没什么卵用
                    file_name = f"\033[1;34m{handle_name(file.name)}\033[0m" if file.isFolder else handle_name(file.name)
                    print("# {0:<17}{1:<4}{2:<20}{3:>8}  {4}".format(
                        file.id, star, file.ctime, get_file_size_str(file.size), file_name))
        if fid != old_fid:
            self._file_list, _ = self._disk.get_file_list(old_fid)

    def cd(self, args):
        """切换工作目录"""
        dir_name = args[0]
        if not dir_name:
            info('cd .. 返回上级路径, cd - 返回上次路径, cd / 返回根目录')
        elif dir_name in ["..", "../"]:
            self.refresh(self._parent_id)
        elif dir_name == '/':
            self.refresh(-11)
        elif dir_name == '-':
            self.refresh(self._last_work_id)
        elif dir_name == '.':
            pass
        elif folder := self._file_list.find_by_name(dir_name):
            self.refresh(folder.id)
        else:
            error(f'文件夹不存在: {dir_name}')

    def mkdir(self, args):
        """创建文件夹"""
        if not args:
            info('参数：新建文件夹名')
        refresh_flag = False
        for name in args:
            if self._file_list.find_by_name(name):
                error(f'文件夹已存在: {name}')
                continue
            r = self._disk.mkdir(self._work_id, name)
            if r.code == Cloud189.SUCCESS:
                print(f"{name} ID: ", r.id)
                refresh_flag = True
            else:
                error(f'创建文件夹 {name} 失败!')
                continue
        if refresh_flag:
            self.refresh()

    def rm(self, args):
        """删除文件(夹)"""
        if not args:
            info('参数：删除文件夹(夹)名')
            return None
        for name in args:
            if file := self._file_list.find_by_name(name):
                self._disk.delete_by_id(file.id)
                print(f"删除：{name} 成功！")
            else:
                error(f"无此文件：{name}")
        self.refresh()

    def rename(self, args):
        """重命名文件(夹)"""
        name = args[0].strip(' ')
        if not name:
            info('参数：原文件名 [新文件名]')
        elif file := self._file_list.find_by_name(name):
            new = args[1].strip(' ') if len(args) == 2 else input("请输入新文件名：")
            logger.debug(f"{new=}, {args=}")
            code = self._disk.rename(file.id, new)
            if code == Cloud189.SUCCESS:
                self.refresh()
            elif code == Cloud189.NETWORK_ERROR:
                error('网络错误，请重试！')
            else:
                error('失败，未知错误！')
        else:
            error(f'没有找到文件(夹): {name}')

    def mv(self, args):
        """移动文件或文件夹"""
        name = args[0]
        if not name:
            info('参数：文件(夹)名 [新文件夹名/id]')
        folder_name = ''
        target_id = None
        file_info = self._file_list.find_by_name(name)
        if not file_info:
            error(f"文件(夹)不存在: {name}")
            return None
        if len(args) > 1:
            if args[-1].isnumeric():
                target_id = args[-1]
            else:
                folder_name = args[-1]
        if not target_id:
            info("正在获取所有文件夹信息，请稍后...")
            tree_list = self._disk.get_folder_nodes()
            if not tree_list:
                error("获取文件夹信息出错，请重试.")
                return None
            if folder_name:
                if folder := tree_list.find_by_name(folder_name):
                    target_id = folder.id
                else:
                    error(f"文件夹 {folder_name} 不存在！")
                    return None
            else:
                tree_dict = tree_list.get_path_id()
                choice_list = list(tree_dict.keys())

                def _condition(typed_str, choice_str):
                    path_depth = len(choice_str.split('/'))
                    # 没有输入时, 补全 Cloud189,深度 1
                    if not typed_str and path_depth == 1:
                        return True
                    # Cloud189/ 深度为 2,补全同深度的文件夹 Cloud189/test 、Cloud189/txt
                    # Cloud189/tx 应该补全 Cloud189/txt
                    if path_depth == len(typed_str.split('/')) and choice_str.startswith(typed_str):
                        return True

                set_completer(choice_list, condition=_condition)
                choice = input('请输入路径(TAB键补全) : ')
                if not choice or choice not in choice_list:
                    error(f"目标路径不存在: {choice}")
                    return None
                target_id = tree_dict.get(choice)

        if self._disk.move_file(file_info, target_id) == Cloud189.SUCCESS:
            self._file_list.pop_by_id(file_info.id)
        else:
            error(f"移动文件(夹)到 {choice} 失败")

    def down(self, args):
        """自动选择下载方式"""
        task_flag = False
        follow = False
        for arg in args:
            if arg == '-f':
                follow = True
                args.remove(arg)
        # TODO: 通过分享链接下载
        i = 0
        while i < len(args):
            item = args[i]
            if item.startswith("http"):
                pwd = ''
                if i < len(args) - 1 and (not args[i + 1].startswith("http")):
                    pwd = args[i + 1]
                    i += 1  # 额外加一
                self._disk.get_file_info_by_url(item, pwd)
            elif file := self._file_list.find_by_name(item):
                downloader = Downloader(self._disk)
                f_path = '/'.join(self._path_list.all_name)  # 文件在网盘的父路径
                if file.isFolder:  # 使用 web 接口打包下载文件夹
                    downloader.set_fid(file.id, is_file=False, f_path=f_path, f_name=item)
                    task_flag = True
                    self._task_mgr.add_task(downloader)  # 提交下载任务
                else:  # 下载文件
                    downloader.set_fid(file.id, is_file=True, f_path=f_path, f_name=item)
                    task_flag = True
                    self._task_mgr.add_task(downloader)  # 提交下载任务
            else:
                error(f'文件(夹)不存在: {item}')
            i += 1
        if follow and task_flag:
            self.jobs(['-f', ])
        elif task_flag:
            print("开始下载, 输入 jobs 查看下载进度...")

    def jobs(self, args):
        """显示后台任务列表"""
        follow = False
        for arg in args:
            if arg == '-f':
                print()
                follow = True
                args.remove(arg)
        if not args:
            self._task_mgr.show_tasks(follow)
        for arg in args:
            if arg.isnumeric():
                self._task_mgr.show_detail(int(arg), follow)
            else:
                self._task_mgr.show_tasks(follow)

    def upload(self, args):
        """上传文件(夹)"""
        if not args:
            info('参数：文件路径')
        task_flag = False
        follow = False
        force = False
        mkdir = True
        for arg in args:
            follow, force, mkdir, match = parsing_up_params(arg, follow, force, mkdir)
            if match:
                args.remove(arg)
        for path in args:
            path = path.strip('\"\' ')  # 去除直接拖文件到窗口产生的引号
            if not os.path.exists(path):
                error(f'该路径不存在哦: {path}')
                continue
            uploader = Uploader(self._disk)
            if os.path.isfile(path):
                uploader.set_upload_path(path, is_file=True, force=force)
            else:
                uploader.set_upload_path(path, is_file=False, force=force, mkdir=mkdir)
            uploader.set_target(self._work_id, self._work_name)
            self._task_mgr.add_task(uploader)
            task_flag = True
        if follow and task_flag:
            self.jobs(['-f', ])
        elif task_flag:
            print("开始上传, 输入 jobs 查看上传进度...")

    def share(self, args):
        """分享文件"""
        name = args[0]
        if not name:
            info('参数：需要分享的文件 [1/2/3] [1/2]')
            return None
        if file := self._file_list.find_by_name(name):
            et = args[1] if len(args) >= 2 else None
            ac = args[2] if len(args) >= 3 else None
            result = self._disk.share_file(file.id, et, ac)
            if result.code == Cloud189.SUCCESS:
                print("-" * 50)
                print(f"{'文件夹名' if file.isFolder else '文件名  '} : {name}")
                print(f"上传时间 : {file.ctime}")
                if not file.isFolder:
                    print(f"文件大小 : {get_file_size_str(file.size)}")
                print(f"分享链接 : {result.url}")
                print(f"提取码   : {result.pwd or '无'}")
                if result.et == '1':
                    time = '1天'
                elif result.et == '2':
                    time = '7天'
                else:
                    time = '永久'
                print(f"有效期   : {time}")
                print("-" * 50)
            else:
                error('获取文件(夹)信息出错！')
        else:
            error(f"文件(夹)不存在: {name}")

    def shared(self, args):
        """显示分享文件"""
        stype = 1  # 默认查看 发出的分享
        if args and args[0] == '2':
            stype = 2  # 收到的分享
        all_file = self._disk.list_shared_url(stype)
        if not all_file:
            info("失败或者没有数据！")
            return None
        for item in all_file:
            f_name = item.name if item.isFolder else f"\033[1;34m{item.name}\033[0m"  # 给你点颜色..
            print("https:{0:<30} 提取码: {1:>4} [转存/下载/浏览: {2}/{3}/{4}] 文件名: {5}".format(
                item.url, item.pwd, item.copyC, item.downC, item.prevC, f_name))

    def sign(self, args):
        """签到 + 抽奖"""
        if '-a' in args or '--all' in args:
            old_user = self.who()
            for user in config.get_users_name():
                self.su([user, ])
                sleep(0.5)
                self._disk.user_sign()
                sleep(0.5)
            self.su([old_user, ])
        else:
            self._disk.user_sign()

    def who(self):
        """打印当前登录账户信息，没有错误则返回用户名"""
        user = self._disk.get_user_infos()
        if not user:
            error("发生未知错误！")
            return None
        quota = ", 总空间: {:.3f} GB".format(user.quota/1073741824)  # GB
        used = ", 已使用: {:.3f} GB".format(user.used/1073741824)  # GB
        nickname = f", 昵称: {user.nickname}"
        print(f"账号: {user.account}, UID: {user.id}{nickname}{quota}{used}")
        # 99 家庭云黄金会员, 199 家庭云铂金会员 (可能不是这个的值)
        if user.vip == 100:
            vip = "黄金会员"
        elif user.vip == 200:
            vip = "铂金会员"
        else:  # 0
            vip = "普通会员"
        start_time = f", 开始时间: {user.beginTime}" if user.beginTime else ''
        end_time = f", 到期时间: {user.endTime}" if user.endTime else ''
        print(f"用户类别: {vip}{start_time}{end_time}")
        if user.domain:
            print(f"个人主页: https://cloud.189.cn/u/{user.domain}")
        return user.account.replace('@189.cn', '')

    def setpath(self):
        """设置下载路径"""
        print(f"当前下载路径 : {config.save_path}")
        path = input('修改为 -> ').strip("\"\' ")
        if os.path.isdir(path):
            config.save_path = path
        else:
            error('路径非法,取消修改')

    def ll(self, args):
        """列出文件(夹)，详细模式"""
        if choice((0, 1, 0)):  # 1/3 概率刷新
            self.refresh()
        self.ls(['-l', *args])

    def quota(self):
        self.who()

    def exit(self):
        self.bye()

    def b(self):
        self.bye()

    def r(self):
        self.refresh()

    def c(self):
        self.clear()

    def j(self, args):
        self.jobs(args)

    def u(self, args):
        self.upload(args)

    def d(self, args):
        self.down(args)

    def run_one(self, cmd, args):
        """运行单任务入口"""
        no_arg_cmd = ['help', 'update', 'who', 'quota']
        cmd_with_arg = ['ls', 'll', 'down', 'mkdir', 'su', 'sign', 'logout',
                        'mv', 'rename', 'rm', 'share', 'upload']

        if cmd in ("upload", "down"):
            if "-f" not in args:
                args.append("-f")

        if cmd in no_arg_cmd:
            getattr(self, cmd)()
        elif cmd in cmd_with_arg:
            getattr(self, cmd)(args)
        else:
            print(f"命令有误，或者不支持单任务运行 {cmd}")

    def run(self):
        """处理交互模式用户命令"""
        no_arg_cmd = ['bye', 'exit', 'cdrec', 'clear', 'clogin', 'help', 'r', 'c', 'b',
                      'refresh', 'rmode', 'setpath', 'update', 'who', 'quota']
        cmd_with_arg = ['ls', 'll', 'cd', 'down', 'jobs', 'shared', 'su', 'login', 'logout',
                        'mkdir', 'mv', 'rename', 'rm', 'share', 'upload', 'sign', 'j', 'u', 'd']

        choice_list = [handle_name(i) for i in self._file_list.all_name]  # 引号包裹空格文件名
        cmd_list = no_arg_cmd + cmd_with_arg
        set_completer(choice_list, cmd_list=cmd_list)

        try:
            args = input(self._prompt).split(' ', 1)
            if len(args) == 0:
                return None
        except KeyboardInterrupt:
            print('')
            info('退出本程序请输入 bye 或 exit')
            return None

        cmd, args = (args[0], []) if len(args) == 1 else (
            args[0], handle_args(args[1]))  # 命令, 参数(可带有空格, 没有参数就设为空)

        if cmd in no_arg_cmd:
            getattr(self, cmd)()
        elif cmd in cmd_with_arg:
            getattr(self, cmd)(args)
