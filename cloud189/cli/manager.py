import time
import threading

from cloud189.cli.downloader import TaskType
from cloud189.cli.utils import info, error
from cloud189.cli.reprint import output  # 修改了 magic_char

__all__ = ['global_task_mgr']


class TaskManager(object):
    """下载/上传任务管理器"""

    def __init__(self):
        self._tasks = []

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
    def _size_to_msg(now_size, total_size, msg, pid, task) -> (str, bool):
        percent = now_size / total_size * 100
        has_error = len(task.get_err_msg()) != 0
        finish = False  # 秒传退出外层循环
        if task.is_alive():  # 任务执行中
            status = '\033[1;32mRunning \033[0m'
        elif not task.is_alive() and has_error:  # 任务执行完成, 但是有错误信息
            status = '\033[1;31mError   \033[0m'
        else:  # 任务正常执行完成
            percent = 100  # 可能更新不及时
            status = '\033[1;34mFinished\033[0m'
        if task.get_task_type() == TaskType.DOWNLOAD:
            d_arg, f_name = task.get_cmd_info()
            d_arg = f_name if type(d_arg) == int else d_arg  # 显示 id 对应的文件名
            result = f"[{pid}] Status: {status} | Process: {percent:5.1f}% | Download: {d_arg}"
        else:
            up_path, folder_name = task.get_cmd_info()
            count = task.get_count()
            if msg == 'quick_up':
                finish = True
                proc = "  \033[1;34m秒传!\033[0m "
            elif msg == 'check':
                proc = "\033[1;34m秒传检查\033[0m"
            elif msg == 'error':
                finish = True
                proc = "\033[1;31m秒传失败\033[0m"
            else:
                proc = f"{percent:7.1f}%"
            result = f"[{pid}] Status: {status} | Process:{proc} | Upload: {up_path}{count} -> {folder_name}"

        return result, finish

    @staticmethod
    def _show_task(pid, task, follow=False):
        TaskManager.running = True  # 相当于每次执行 jobs -f 都初始化

        def stop_show_task():
            """
            停止显示任务状态
            问题：由于线程执行的是阻塞操作，不知道自己被结束了，
                  它还在等待一个 input，所以在任务状态 Finnish 之后需要回车。
            """
            while TaskManager.running:
                stop_signal = input()
                if stop_signal:
                    TaskManager.running = False
                time.sleep(1)
        if follow: threading.Thread(target=stop_show_task).start()
        global output_list
        now_size, total_size, msg = task.get_process()
        while now_size < total_size:
            if not TaskManager.running:
                break
            result, finished = TaskManager._size_to_msg(now_size, total_size, msg, pid, task)
            if follow:
                output_list[pid] = result
                time.sleep(1)
                now_size, total_size, msg = task.get_process()
            else:
                break
            if finished:  # 文件秒传没有大小
                break
        if now_size >= total_size:
            result, _ = TaskManager._size_to_msg(now_size, total_size, msg, pid, task)
            if follow and TaskManager.running:
                output_list[pid] = result
        if follow and TaskManager.running:
            output_list.append(f"[{pid}] finished")
            TaskManager.running = False
        elif not TaskManager.running:
            pass
        else:
            print(result)

    def _show_task_bar(self, pid=None, follow=False):
        """多行更新状态栏"""
        global output_list
        with output(output_type="list", initial_len=len(self._tasks), interval=0) as output_list:
            pool = []
            for _pid, task in enumerate(self._tasks):
                if pid is not None and _pid != pid:  # 如果指定了 pid 就只更新 pid 这个 task
                    continue
                t = threading.Thread(target=self._show_task, args=(_pid, task, follow))
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
