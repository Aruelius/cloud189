from time import sleep
from threading import Thread

from cloud189.cli.downloader import TaskType
from cloud189.cli.utils import info, error, get_file_size_str
from cloud189.cli.reprint import output  # 修改了 magic_char

__all__ = ['global_task_mgr']


def input_with_timeout(timeout=1.5):
    """带超时的 input"""
    input_with_timeput_ans = None
    def foo():
        global input_with_timeput_ans
        input_with_timeput_ans = input()

    thd = Thread(target=foo)
    thd.daemon = True
    thd.start()
    sleep(timeout)
    return input_with_timeput_ans


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
    def _size_to_msg(now_size, total_size, msg, pid, task) -> (str, bool):
        if total_size == -1:
            percent = get_file_size_str(now_size)
        else:
            percent = "{:7.1f}%".format(now_size / total_size * 100)
        has_error = len(task.get_err_msg()) != 0
        finish = False  # 秒传退出外层循环
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
            if msg == 'quick_up':
                finish = True
                proc = "  \033[1;34m秒传!\033[0m "
            elif msg == 'check':
                proc = "\033[1;34m秒传检查\033[0m"
            elif msg == 'error':
                finish = True
                proc = "\033[1;31m秒传失败\033[0m"
            elif msg == 'skip':
                finish = True
                proc = "\033[1;31m远端存在\033[0m"
            else:
                proc = percent
            result = f"[{pid}] Status: {status} | Process:{proc} | Upload: {up_path}{count} -> {folder_name}"

        return result, finish

    @staticmethod
    def _show_task(pid, task, follow=False):
        TaskManager.running = True  # 相当于每次执行 jobs -f 都初始化
        global output_list, total_tasks

        def stop_show_task():
            """停止显示任务状态"""
            while TaskManager.running or total_tasks > 0:
                stop_signal = input_with_timeout()
                if stop_signal:
                    TaskManager.running = False
                sleep(1)
        if follow: Thread(target=stop_show_task).start()
        now_size, total_size, msg = task.get_process()
        done_files, total_files = task.get_count()
        while total_tasks > 1 or total_size == -1 or now_size < total_size or done_files < total_files:
            if not TaskManager.running:
                break
            result, finished = TaskManager._size_to_msg(now_size, total_size, msg, pid, task)
            if follow:
                output_list[pid] = result
                sleep(1)
                now_size, total_size, msg = task.get_process()
                done_files, total_files = task.get_count()
                if now_size >= total_size:
                    total_tasks -= 1
                    break
            else:
                break
            if finished:  # 文件秒传没有大小
                break
        if now_size >= total_size:
            result, _ = TaskManager._size_to_msg(now_size, total_size, msg, pid, task)
            output_list[pid] = result
            if follow:
                output_list.append(f"[{pid}] finished")

        if follow and TaskManager.running:
            if total_tasks < 1:
                TaskManager.running = False
        elif not TaskManager.running:
            pass
        else:
            print(result)

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
