from threading import Thread
from time import sleep, monotonic

from cloud189.cli.downloader import TaskType
from cloud189.cli.utils import info, error, get_file_size_str, OS_NAME, get_upload_status
from cloud189.cli.reprint import output  # 修改了 magic_char

__all__ = ['global_task_mgr']

output_list = output()
total_tasks = 0


class TimeoutExpired(Exception):
    pass


def input_with_timeout(timeout, timer=monotonic):
    if OS_NAME == 'posix':  # *nix
        import select
        import sys

        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if ready:
            try:
                return sys.stdin.readline().rstrip('\n')
            except OSError:
                return None
        raise TimeoutExpired

    else:  # windos
        import msvcrt

        endtime = timer() + timeout
        result = []
        while timer() < endtime:
            if msvcrt.kbhit():
                result.append(msvcrt.getwche())
                if result[-1] == '\n' or result[-1] == '\r':
                    return ''.join(result[:-1])
            sleep(0.05)  # 这个值太大会导致丢失按键信息
        raise TimeoutExpired


class TaskManager(object):
    """下载/上传任务管理器"""

    def __init__(self):
        self._tasks = []

    def __len__(self):
        return len(self._tasks)

    def is_empty(self):
        """任务列表是否为空"""
        return len(self._tasks) == 0

    def has_alive_task(self):
        """是否有任务在后台运行"""
        for task in self._tasks:
            if task.is_alive():
                return True
        return False

    def add_task(self, task):
        """提交一个上传/下载任务"""
        for t in self._tasks:
            if task.get_cmd_info() == t.get_cmd_info():  # 操作指令相同,认为是相同的任务
                old_pid = t.get_task_id()
                if t.is_alive():  # 下载任务正在运行
                    info(f"任务正在后台运行: PID {old_pid}")
                    return None
                else:  # 下载任务为 Finished 或 Error 状态
                    choice = input(f"任务已完成, PID {old_pid}, 重新下载吗?(y) ")
                    if choice.lower() == 'y':
                        task.set_task_id(old_pid)
                        self._tasks[old_pid] = task
                        task.start()
                return None
        # 没有发现重复的任务
        task.set_task_id(len(self._tasks))
        self._tasks.append(task)
        task.start()

    @staticmethod
    def _size_to_msg(now_size, total_size, msg, pid, task) -> str:
        """任务详情可视化"""
        if total_size == -1:  # zip 打包下载
            percent = get_file_size_str(now_size)
        else:
            percent = "{:7.1f}%".format(now_size / total_size * 100)
        has_error = len(task.get_err_msg()) != 0
        if task.is_alive():  # 任务执行中
            if now_size >= total_size:  # 有可能 thread 关闭不及时
                status = '\033[1;34mFinished\033[0m'
            else:
                status = '\033[1;32mRunning \033[0m'
        elif not task.is_alive() and has_error:  # 任务执行完成, 但是有错误信息
            status = '\033[1;31mError   \033[0m'
        else:  # 任务正常执行完成
            percent = "{:7.1f}%".format(100)  # 可能更新不及时
            status = '\033[1;34mFinished\033[0m'
        if task.get_task_type() == TaskType.DOWNLOAD:
            d_arg, f_name = task.get_cmd_info()
            d_arg = f_name if isinstance(d_arg, int) else d_arg  # 显示 id 对应的文件名
            result = f"[{pid}] Status: {status} | Process: {percent} | Download: {d_arg}"
        else:
            up_path, folder_name = task.get_cmd_info()
            done_files, total_files = task.get_count()
            count = f" ({done_files}/{total_files})" if total_files > 0 else ""
            proc = get_upload_status(msg, percent)
            result = f"[{pid}] Status: {status} | Process:{proc} | Upload: {up_path}{count} -> {folder_name}"

        return result

    @staticmethod
    def _show_task(pid, task, follow=False):
        TaskManager.running = True  # 相当于每次执行 jobs -f 都初始化
        # total_tasks 用于标记还没完成的任务数量
        global output_list, total_tasks

        def stop_show_task():
            """停止显示任务状态"""
            stop_signal = None
            while TaskManager.running or total_tasks > 0:
                try:
                    stop_signal = input_with_timeout(3)
                except TimeoutExpired:
                    pass
                else:
                    if stop_signal:
                        TaskManager.running = False
                        break

        if follow: Thread(target=stop_show_task).start()
        now_size, total_size, msg = task.get_process()
        done_files, total_files = task.get_count()
        while  total_size == -1 or now_size < total_size or done_files < total_files:
            if not TaskManager.running:
                break  # 用户中断
            result = TaskManager._size_to_msg(now_size, total_size, msg, pid, task)
            if follow:
                output_list[pid] = result
                sleep(1)
                now_size, total_size, msg = task.get_process()
                done_files, total_files = task.get_count()
                if now_size >= total_size and done_files >= total_files:
                    total_tasks -= 1
                    break
            else:
                break  # 非实时显示模式，直接结束
            if msg and done_files >= total_files:
                break  # 文件秒传、出错 没有大小
        if follow:
            if now_size >= total_size:
                output_list[pid] = TaskManager._size_to_msg(now_size, total_size, msg, pid, task)
                while True:
                    if not task.is_alive():
                        output_list.append(f"[{pid}] finished")
                        for err_msg in task.get_err_msg():
                            output_list.append(f"[{pid}] Error Messages: {err_msg}")
                        break
                    sleep(1)
            if TaskManager.running:
                if total_tasks < 1:  # 只有还有一个没有完成, 就不能改 TaskManager.running
                    TaskManager.running = False  # 辅助控制 stop_show_task 线程的结束 🤣
        else:
            print(TaskManager._size_to_msg(now_size, total_size, msg, pid, task))

    def _show_task_bar(self, pid=None, follow=False):
        """多行更新状态栏"""
        global output_list, total_tasks
        with output(output_type="list", initial_len=len(self._tasks), interval=0) as output_list:
            pool = []
            total_tasks = len(self)
            for _pid, task in enumerate(self._tasks):
                if pid is not None and _pid != pid:  # 如果指定了 pid 就只更新 pid 这个 task
                    continue
                t = Thread(target=self._show_task, args=(_pid, task, follow))
                t.start()
                pool.append(t)
            [t.join() for t in pool]

    def show_tasks(self, follow=False):
        """显示所有任务"""
        if self.is_empty():
            print(f"没有任务在后台运行哦")
        else:
            if not follow:
                print('-' * 100)
            if follow:
                self._show_task_bar(follow=follow)
            else:
                for pid, task in enumerate(self._tasks):
                    self._show_task(pid, task)
            if not follow:
                print('-' * 100)

    def show_detail(self, pid=-1, follow=False):
        """显示指定任务详情"""
        if 0 <= pid < len(self._tasks):
            task = self._tasks[pid]
            self._show_task_bar(pid, follow)
            print("Error Messages:")
            for msg in task.get_err_msg():
                print(msg)
        else:
            error(f"进程号不存在: PID {pid}")


# 全局任务管理器对象
global_task_mgr = TaskManager()
