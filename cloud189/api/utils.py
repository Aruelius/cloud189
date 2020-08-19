"""
API 处理网页数据、数据切片时使用的工具
"""

import os
import logging
import hmac
import hashlib
from datetime import datetime
from base64 import b64encode
import rsa

__all__ = ['logger', 'encrypt', 'b64tohex', 'calculate_hmac_sign',
           'API', 'UA', 'SUFFIX_PARAM', 'get_time', 'get_file_md5',
           'get_file_name', 'get_relative_folder', 'get_upload_chunks',
           'get_chunk_size']

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(ROOT_DIR))

# 调试日志设置
logger = logging.getLogger('cloud189')
log_file = ROOT_DIR + os.sep + 'debug-cloud189.log'
fmt_str = "%(asctime)s [%(filename)s:%(lineno)d] %(funcName)s %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG,
                    filename=log_file,
                    filemode="a",
                    format=fmt_str,
                    datefmt="%Y-%m-%d %H:%M:%S")

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

API = 'https://api.cloud.189.cn'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) ????/1.0.0 ' \
     'Chrome/69.0.3497.128 Electron/4.2.12 Safari/537.36 '
# UA = 'Mozilla/5.0'
SUFFIX_PARAM = 'clientType=TELEMAC&version=1.0.0&channelId=web_cloud.189.cn'

RSA_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDY7mpaUysvgQkbp0iIn2ezoUyh
i1zPFn0HCXloLFWT7uoNkqtrphpQ/63LEcPz1VYzmDuDIf3iGxQKzeoHTiVMSmW6
FlhDeqVOG094hFJvZeK4OzA6HVwzwnEW5vIZ7d+u61RV1bsFxmB68+8JXs3ycGcE
4anY+YzZJcyOcEGKVQIDAQAB
-----END PUBLIC KEY-----
"""
b64map = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
BI_RM = list("0123456789abcdefghijklmnopqrstuvwxyz")


def encrypt(password: str) -> str:
    return b64encode(
        rsa.encrypt(
            (password).encode('utf-8'),
            rsa.PublicKey.load_pkcs1_openssl_pem(RSA_KEY.encode())
        )
    ).decode()


def int2char(a):
    return BI_RM[a]


def b64tohex(a):
    d = ""
    e = 0
    for i in range(len(a)):
        if list(a)[i] != "=":
            v = b64map.index(list(a)[i])
            if 0 == e:
                e = 1
                d += int2char(v >> 2)
                c = 3 & v
            elif 1 == e:
                e = 2
                d += int2char(c << 2 | v >> 4)
                c = 15 & v
            elif 2 == e:
                e = 3
                d += int2char(c)
                d += int2char(v >> 2)
                c = 3 & v
            else:
                e = 0
                d += int2char(c << 2 | v >> 4)
                d += int2char(15 & v)
    if e == 1:
        d += int2char(c << 2)
    return d


def md5(s):
    hl = hashlib.md5()
    hl.update(s.encode(encoding='utf-8'))
    return hl.hexdigest()


def calculate_md5_sign(params):
    return hashlib.md5('&'.join(sorted(params.split('&'))).encode('utf-8')).hexdigest()


def rsa_encode(j_rsakey, string):
    rsa_key = f"-----BEGIN PUBLIC KEY-----\n{j_rsakey}\n-----END PUBLIC KEY-----"
    pubkey = rsa.PublicKey.load_pkcs1_openssl_pem(rsa_key.encode())
    result = b64tohex((b64encode(rsa.encrypt(f'{string}'.encode(), pubkey))).decode())
    return result


def calculate_hmac_sign(secret_key, session_key, operate, url, date):
    request_uri = url.split("?")[0].replace(f"{API}", "")
    plain = f'SessionKey={session_key}&Operate={operate}&RequestURI={request_uri}&Date={date}'
    return hmac.new(secret_key.encode(), plain.encode(), hashlib.sha1).hexdigest().upper()


def get_time(stamp=False):
    '''获取当前时间戳'''
    if stamp:
        return str(int(datetime.utcnow().timestamp() * 1000))
    else:
        return datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')


def get_file_md5(file_path, check=True):
    if check:
        _md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(64 * 1024)
                if not data:
                    break
                _md5.update(data)
            hash_md5 = _md5.hexdigest()
        return hash_md5.upper()
    else:
        return 'random_md5_value'  # TODO: 这里需要返回一个值


def get_file_name(file_path):
    '''文件路径获取文件名'''
    return file_path.strip('/').strip('\\').rsplit('\\', 1)[-1].rsplit('/', 1)[-1]


def get_relative_folder(full_path, work_path, is_file=True):
    '''文件路径获取文件夹'''
    work_name = get_file_name(work_path)
    # 有可能 work_name 在父文件夹中有出现，
    # 因此 反转路径 以替换最后一个文件(夹)名，最后再倒回来 (〒︿〒)
    work_hone = work_path[::-1].strip('/').strip('\\').replace(work_name[::-1], '', 1)[::-1]
    relative_path = full_path.strip('/').strip('\\').replace(work_hone, '')
    file_name = relative_path.rsplit('\\', 1)[-1].rsplit('/', 1)[-1] if is_file else ''
    logger.debug(f"{work_name=},{work_hone=},{relative_path=},{file_name=}")
    return relative_path.replace(file_name, '').strip('/').strip('\\')


def get_upload_chunks(file, chunk_size=8096):
    """文件上传 块生成器"""
    while True:
        data = file.read(chunk_size)
        if not data: break
        yield data


def get_chunk_size(total_size: int) -> int:
    """根据文件大小返回 块大小"""
    if total_size >= 1 << 30:  # 1 GB
        return  10 << 20  # 10 MB
    elif total_size >= 100 << 20:  # 100 MB
        return 4 << 20  # 4 MB
    elif total_size == -1:
        return 100 << 10  # 100 KB
    else:
        return 1 << 20  # 1 MB
