"""
容器类，用于储存文件、文件夹，支持 list 的操作，同时支持许多方法方便操作元素
元素类型为 namedtuple，至少拥有 name id 两个属性才能放入容器
"""

__all__ = ['FileList', 'PathList', 'TreeList']

from cloud189.api.utils import logger

class ItemList:
    """具有 name, id 属性对象的列表"""

    def __init__(self):
        self._items = []

    def __len__(self):
        return len(self._items)

    def __getitem__(self, index):
        return self._items[index]

    def __iter__(self):
        return iter(self._items)

    def __repr__(self):
        return f"<List {', '.join(it.__str__() for it in self)}>"

    def __lt__(self, other):
        """用于路径 List 之间排序"""
        return '/'.join(i.name for i in self) < '/'.join(i.name for i in other)

    @property
    def name_id(self):
        """所有 item 的 name-id 列表，兼容旧版"""
        return {it.name: it.id for it in self}

    @property
    def all_name(self):
        """所有 item 的 name 列表"""
        return [it.name for it in self]

    def append(self, item, repeat=True):
        """在末尾插入元素"""
        if (not repeat) and self.find_by_id(item.id):
            logger.debug(f"List: 不插入元素 {item.name}")
            return
        self._items.append(item)
        logger.debug(f"List: 插入元素  {item.name}")

    def index(self, item):
        """获取索引"""
        return self._items.index(item)

    def insert(self, pos, item):
        """指定位置插入元素"""
        self._items.insert(pos, item)

    def clear(self):
        """清空元素"""
        self._items.clear()

    def filter(self, condition) -> list:
        """筛选出满足条件的 item
        condition(item) -> True
        """
        return [it for it in self if condition(it)]

    def find_by_name(self, name: str):
        """使用文件名搜索(仅返回首个匹配项)"""
        for item in self:
            if name == item.name:
                return item
        return None

    def find_by_id(self, fid: int):
        """使用 id 搜索(精确)"""
        for item in self:
            if fid == item.id:
                return item
        return None

    def pop_by_id(self, fid):
        for item in self:
            if item.id == fid:
                self._items.remove(item)
                return item
        return None

    def update_by_id(self, fid, **kwargs):
        """通过 id 搜索元素并更新"""
        item = self.find_by_id(fid)
        pos = self.index(item)
        data = item._asdict()
        data.update(kwargs)
        self._items[pos] = item.__class__(**data)

    def get_absolute_path(self, fid) -> str:
        res = ''
        if item := self.find_by_id(fid):
            if item.pid:
                res = self.get_absolute_path(item.pid) + item.name
            else:
                res = item.name + '/' + res
        return res

    def get_path_id(self) -> dict:
        """获取文件路径-id"""
        result = {}
        for item in self._items:
            _id = item.id
            full_path = self.get_absolute_path(_id)
            result[full_path] = _id
        return result


class FileList(ItemList):
    """文件列表类"""
    pass


class PathList(ItemList):
    """路径列表类"""
    pass


class TreeList(ItemList):
    """文件夹结构类"""
    pass
