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

# __all__ = ['logger', 'md5', 'encrypt', 'int2char', 'b64tohex', 'rsa_encode', 'calculate_md5_sign', 'API', 'UA, 'get_gmt_time', 'get_time']

# 调试日志设置
logger = logging.getLogger('cloud189')
fmt_str = "%(asctime)s [%(filename)s:%(lineno)d] %(funcName)s %(levelname)s - %(message)s"
logging.basicConfig(level=logging.DEBUG,
                    filename="debug-cloud189.log",
                    filemode="a",
                    format=fmt_str,
                    datefmt="%Y-%m-%d %H:%M:%S")

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


def get_file_md5(file_path):
    _md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        while True:
            data = f.read(64 * 1024)
            if not data:
                break
            _md5.update(data)
        hash_md5 = _md5.hexdigest()
    return hash_md5.upper()


def get_file_size(file_path):
    return str(os.path.getsize(file_path))


def get_file_name(file_path):
    '''文件路径获取文件名'''
    return file_path.strip('/').strip('\\').rsplit('\\', 1)[-1].rsplit('/', 1)[-1]


def get_relative_folder(full_path, work_path, is_file=True):
    '''文件路径获取文件夹'''
    work_name = get_file_name(work_path)
    work_hone = work_path.strip('/').strip('\\').replace(work_name, '')
    relative_path = full_path.strip('/').strip('\\').replace(work_hone, '')
    file_name = relative_path.rsplit('\\', 1)[-1].rsplit('/', 1)[-1] if is_file else ''
    return relative_path.replace(file_name, '').strip('/').strip('\\')


def get_chunks(file, chunk_size=1):
    while True:
        data = file.read(chunk_size)
        if not data: break
        yield data


def get_down_chunk_size_scale(total_size: int) -> int:
    """获取文件下载 块系数"""
    if total_size >= 1024 * 1024 * 1024:  # 1 GB
        return 10
    elif total_size >= 1024 * 1024 * 100:  # 100 MB
        return 4
    else:
        return 1
