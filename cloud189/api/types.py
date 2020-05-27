"""
API 处理后返回的数据类型
"""

from collections import namedtuple


__all__ = ['FileInfo', 'RecInfo', 'PathInfo', 'UpCode', 'MkCode',
           'ShareCode', 'FolderTree', 'ShareInfo']


_base_info = ['name', 'id', 'pid', 'ctime', 'optime', 'size', 'ftype', 'isFolder', 'durl']
_file_info = (*_base_info, 'isStarred', 'account', 'count')
_rec_info = [*_base_info, 'isFamily', 'path', 'fid']
_share_info = ['pwd', 'copyC', 'downC', 'prevC', 'url', 'path',
               'need_pwd', 's_type', 's_mode', 'r_stat', *_base_info]

# 主文件
FileInfo = namedtuple('FileInfo', _file_info, defaults=('',) * len(_file_info))
# 回收站文件
RecInfo = namedtuple('RecInfo', _rec_info, defaults=('',) * len(_rec_info))
# 文件路径
PathInfo = namedtuple('PathInfo', ['name', 'id', 'isCoShare'])

UpCode = namedtuple('UpCode', ['code', 'id', 'quick_up', 'name'], defaults=(0, '', False, ''))
MkCode = namedtuple('MkCode', ['code', 'id'], defaults=(0, ''))
ShareCode = namedtuple('ShareCode', ['code', 'url', 'pwd', 'et'], defaults=(0, '', '', ''))

FolderTree = namedtuple('FolderTree', ['name', 'id', 'pid', 'isParent'], defaults=('',) * 4)

ShareInfo = namedtuple('ShareInfo', _share_info, defaults=('',) * len(_share_info))
