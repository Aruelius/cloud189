from cloud189.cli.utils import *
from cloud189.cli import config


class Recovery:
    """回收站命令行模式"""

    def __init__(self, disk: Cloud189):
        self._prompt = 'Recovery > '
        self._reader_mode = config.reader_mode
        self._disk = disk

        print("回收站数据加载中...")
        self._file_list = disk.get_rec_file_list()

    def ls(self):
        if self._reader_mode:  # 适宜屏幕阅读器的显示方式
            for file in self._file_list:
                print(f"{file.name}  大小:{get_file_size_str(file.size)}  删除时间:{file.optime}  路径:{file.path}")
            print("")
        else:  # 普通用户的显示方式
            for file in self._file_list:
                print("#{0:<18}{1:<21} {3:>9} {4}\t{2}".format(file.id, file.optime, file.name, get_file_size_str(file.size), file.path))

    def clean(self):
        """清空回收站"""
        if len(self._file_list) == 0:
            print("当前回收站为空！")
        else:
            choice = input('确认清空回收站?(y) ')
            if choice.lower() == 'y':
                if self._disk.rec_empty(self._file_list[0]) == Cloud189.SUCCESS:
                    self._file_list.clear()
                    info('回收站清空成功!')
                else:
                    error('回收站清空失败!')

    def rm(self, name):
        """彻底删除文件(夹)"""
        if file := self._file_list.find_by_name(name):  # 删除文件
            if self._disk.rec_delete(file) == Cloud189.SUCCESS:
                self._file_list.pop_by_id(file.id)
            else:
                error(f'彻底删除文件失败: {name}')
        else:
            error(f'文件不存在: {name}')

    def rec(self, name):
        """恢复文件"""
        if file := self._file_list.find_by_name(name):
            if self._disk.rec_restore(file) == Cloud189.SUCCESS:
                info(f"文件恢复成功: {name}")
                self._file_list.pop_by_id(file.id)
            else:
                error(f'彻底删除文件失败: {name}')
        else:
            error('(#`O′) 没有这个文件啊喂')

    def run(self):
        """在回收站模式下运行"""
        choice_list = self._file_list.all_name
        cmd_list = ['clean', 'cd', 'rec', 'rm']
        set_completer(choice_list, cmd_list=cmd_list)

        while True:
            try:
                args = input(self._prompt).split()
                if len(args) == 0:
                    continue
            except KeyboardInterrupt:
                info('已退出回收站模式')
                break

            cmd, arg = args[0], ' '.join(args[1:])

            if cmd == 'ls':
                self.ls()
            elif cmd == 'clean':
                self.clean()
            elif cmd == 'rec':
                self.rec(arg)
            elif cmd == 'rm':
                self.rm(arg)
            elif cmd == 'cd' and arg == '..':
                print('')
                info('已退出回收站模式')
                break
            else:
                info('使用 cd .. 或 Crtl + C 退出回收站')
