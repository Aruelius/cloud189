"""
API 处理后返回的数据类型
"""

from collections import namedtuple

FolderInfo = namedtuple('FolderInfo', ['name', 'id', 'pid', 'time', 'size', 'type', 'durl', 'isFolder', 'isStarred'], defaults=('',) * 9)
PathInfo = namedtuple('PathInfo', ['name', 'id', 'isCoShare'])

UpCode = namedtuple('UpCode', ['code', 'id'], defaults=(0, ''))
MkCode = namedtuple('MkCode', ['code', 'id'], defaults=(0, ''))
ShareCode = namedtuple('ShareCode', ['code', 'url', 'pwd', 'et'], defaults=(0, '', '', ''))
