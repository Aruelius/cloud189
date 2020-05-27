"""
API 处理后返回的数据类型
"""

from collections import namedtuple


__all__ = ['FileInfo', 'RecInfo',  'PathInfo', 'UpCode', 'MkCode', 'ShareCode', 'FolderTree']

# 主文件
_file_info = ('name', 'id', 'pid', 'ctime', 'optime', 'size', 'ftype', 'isFolder', 'isStarred', 'account', 'durl', 'count')
FileInfo = namedtuple('FileInfo', _file_info, defaults=('',) * len(_file_info))
# 回收站文件
RecInfo = namedtuple('RecInfo', ['name', 'id', 'pid', 'time', 'size', 'type', 'durl', 'isFolder', 'isFamily', 'path', 'fid'], defaults=('',) * 11)
# 文件路径
PathInfo = namedtuple('PathInfo', ['name', 'id', 'isCoShare'])

UpCode = namedtuple('UpCode', ['code', 'id', 'quick_up', 'name'], defaults=(0, '', False, ''))
MkCode = namedtuple('MkCode', ['code', 'id'], defaults=(0, ''))
ShareCode = namedtuple('ShareCode', ['code', 'url', 'pwd', 'et'], defaults=(0, '', '', ''))

FolderTree = namedtuple('FolderTree', ['name', 'id', 'pid', 'isParent'], defaults=('',) * 4)
