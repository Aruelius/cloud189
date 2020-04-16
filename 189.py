import base64
import hashlib
import json
import os
import re
import sys
import time

import requests
import rsa

session = requests.session()
session.headers.update({
    'Referer': 'https://open.e.189.cn/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36'
})

RSA_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDY7mpaUysvgQkbp0iIn2ezoUyh
i1zPFn0HCXloLFWT7uoNkqtrphpQ/63LEcPz1VYzmDuDIf3iGxQKzeoHTiVMSmW6
FlhDeqVOG094hFJvZeK4OzA6HVwzwnEW5vIZ7d+u61RV1bsFxmB68+8JXs3ycGcE
4anY+YzZJcyOcEGKVQIDAQAB
-----END PUBLIC KEY-----
"""

def encrypt(password: str) -> str:
    return base64.b64encode(
        rsa.encrypt(
            (password).encode('utf-8'),
            rsa.PublicKey.load_pkcs1_openssl_pem(RSA_KEY.encode())
        )
    ).decode()

b64map = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
BI_RM = list("0123456789abcdefghijklmnopqrstuvwxyz")

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
    # print(d)
    return d

def redirect():
    r = session.get("https://cloud.189.cn/udb/udb_login.jsp?pageId=1&redirectURL=/main.action")
    captchaToken = re.findall(r"captchaToken' value='(.+?)'", r.text)[0]
    lt = re.findall(r'lt = "(.+?)"', r.text)[0]
    returnUrl = re.findall(r"returnUrl = '(.+?)'", r.text)[0]
    paramId = re.findall(r'paramId = "(.+?)"', r.text)[0]
    session.headers.update({"lt": lt})
    return captchaToken, returnUrl, paramId

def md5(s):
    hl = hashlib.md5()
    hl.update(s.encode(encoding='utf-8'))
    return hl.hexdigest()

def needcaptcha(captchaToken):
    r = session.post(
        url="https://open.e.189.cn/api/logbox/oauth2/needcaptcha.do",
        data={
            "accountType": "01",
            "userName": "{RSA}" + b64tohex(encrypt(username)),
            "appKey": "cloud"
        }
    )
    if r.text == "0":
        print("DONT NEED CAPTCHA")
        return ""
    else:
        print("NEED CAPTCHA")
        r = session.get(
            url="https://open.e.189.cn/api/logbox/oauth2/picCaptcha.do",
            params={"token": captchaToken}
        )
        with open("./captcha.png", "wb") as f:
            f.write(r.content)
            f.close()  
        return input("验证码下载完成，打开 ./captcha.png 查看: ")

def save_cookie(username: str):
    with open(f"./.{username}", mode="w") as f:
        json.dump(session.cookies.get_dict(), f, indent=2)
        f.close()

def load_cookie(username: str):
    cookie_file = f"./.{username}"
    if os.path.exists(cookie_file):
        with open(cookie_file, mode="r") as f:
            cookie_dict = json.loads(f.read())
            f.close()
        [session.cookies.set(k, v, domain=".cloud.189.cn") for k, v in cookie_dict.items()]
        r = session.get("https://cloud.189.cn/v2/getUserLevelInfo.action")
        if "InvalidSessionKey" not in r.text: return True
    return False

def login():
    if load_cookie(username):
        return
    captchaToken, returnUrl, paramId = redirect()
    validateCode = needcaptcha(captchaToken)
    r = session.post(
        url="https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do",
            data={
            "appKey": "cloud",
            "accountType": '01',
            "userName": "{RSA}" + b64tohex(encrypt(username)),
            "password": "{RSA}" + b64tohex(encrypt(password)),
            "validateCode": validateCode,
            "captchaToken": captchaToken,
            "returnUrl": returnUrl,
            "mailSuffix": "@189.cn",
            "paramId": paramId
        }
    )
    msg = r.json()["msg"]
    if "登录成功" == msg:
        session.get(r.json()["toUrl"])
        save_cookie(username)
    else:
        print(msg)
        os._exit(0)

def get_file_size_str(filesize: int) -> str:
    if 0 < filesize < 1024**2:
        return f"{round(filesize/1024, 2)}KB"
    elif 1024**2 < filesize < 1024**3:
        return f"{round(filesize/1024**2, 2)}MB"
    elif 1024**3 < filesize < 1024**4:
        return f"{round(filesize/1024**3, 2)}GB"
    elif 1024**4 < filesize < 1024**5:
        return f"{round(filesize/1024**4, 2)}TB"
    else: return f"{filesize}Bytes"

def share_file(fileId):
    expireTime_dict = {
        "1": "1",
        "2": "7",
        "3": "2099"
    }
    expireTime = input("请选择分享有效期：1、1天，2、7天，3、永久：")
    withAccessCode = input("请选择分享形式：1、私密分享，2、公开分享：")
    if withAccessCode == "1":
        url = "https://cloud.189.cn/v2/privateLinkShare.action"
        params = {
            "fileId": fileId,
            "expireTime": expireTime_dict[expireTime],
            "withAccessCode": withAccessCode
        }
    else:
        url = "https://cloud.189.cn/v2/createOutLinkShare.action"
        params = {
            "fileId": fileId,
            "expireTime": expireTime_dict[expireTime]
        }
    r = session.get(url=url, params=params).json()
    msg = f"链接：{r['shortShareUrl']} "
    msg += "" if not r.get("accessCode") else f"访问码：{r['accessCode']}"
    print(msg)

def get_files():
    r = session.get(
        url="https://cloud.189.cn/v2/listFiles.action",
        params={
            "fileId": "-11", # 根目录
            "inGroupSpace": "false",
            "orderBy": "1",
            "order": "ASC",
            "pageNum": "1",
            "pageSize": "60"
        }
    ).json()
    for file in r["data"]:
        folder_or_file = "文件夹: " if file["isFolder"] else f"大小: {get_file_size_str(file['fileSize'])} 文件名: "
        filename = file["fileName"]
        print(f"{folder_or_file}{filename} {'' if file['isFolder'] else '文件ID: ' + file['fileId']}")

def upload(filePath):
    session.headers["Referer"] = "https://cloud.189.cn"
    def get_upload_url():
        r = session.post("https://cloud.189.cn/v2/getUserUploadUrl.action")
        return "https:" + r.json()["uploadUrl"]
    
    def get_session_key():
        r = session.get(
            url="https://cloud.189.cn/main.action",
            headers={"Host": "cloud.189.cn"}
        )
        sessionKey = re.findall(r"sessionKey = '(.+?)'", r.text)[0]
        return sessionKey

    def upload_file():
        filename = os.path.basename(filePath)
        filesize = os.path.getsize(filePath)
        print(f"正在上传: {filename} 大小: {get_file_size_str(filesize)}")
        upload_url = get_upload_url()
        r = session.post(
            url=upload_url,
            data={
                "sessionKey": get_session_key(),
                "parentId": "-11", # 上传文件夹 根目录
                "albumId": "undefined",
                "opertype": "1",
                "fname": filename,
            },
            files={
                "Filedata": open(filePath, "rb").read()
            }
        ).json()
        print(f"上传完毕！文件ID：{r['id']} 上传时间: {r['createDate']}")
    upload_file()

def task(task_type, fileid):
    taskInfos = []
    def get_file_info(download=False):
        r = session.get(f"https://cloud.189.cn/v2/getFileInfo.action?fileId={fileid}").json()
        filename = r["fileName"]
        if download:
            print(f"开始下载: {filename} 大小: {get_file_size_str(r['fileSize'])}")
            return "https:"+r["downloadUrl"], filename
        taskInfo = {}
        taskInfo["fileId"] = fileid
        taskInfo["srcParentId"] = "-11" # 根目录
        taskInfo["fileName"] = filename
        taskInfo["isFolder"] = 1 if r["isFolder"] else 0
        taskInfos.append(taskInfo)
    
    def create_batch_task(action):
        r = session.post(
            url="https://cloud.189.cn/createBatchTask.action",
            data={
                "type": action,
                "taskInfos": json.dumps(taskInfos)
            }
        )
        if r.text:
            print("删除成功！")

    def download(url, filename, filepath="./"):
        print(f"下载链接：{url}")
        if input("需要继续下载吗？ 1、继续下载，2、取消下载") == "1":
            r = session.get(url, stream=True)
            with open(filepath+filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024**2):
                    f.write(chunk)
                f.close()
            print(f"{filename} 下载完成!")

    if task_type == "delete":
        get_file_info()
        create_batch_task("DELETE")
    elif task_type == "download":
        url, filename = get_file_info(True)
        download(url, filename)

if __name__ == "__main__":
    username = ""
    password = ""
    login()
    try:
        if sys.argv[1] == "upload":
            upload(sys.argv[2])
        elif sys.argv[1] in ["delete", "download"]:
            task(sys.argv[1], int(sys.argv[2]))
        elif sys.argv[1] == "list":
            get_files()
        elif sys.argv[1] == "share":
            share_file(int(sys.argv[2]))
    except IndexError:
        print("请输入正确的参数:\n \
            upload [filename]: 上传文件\n \
            download [file id]: 下载文件\n \
            list: 列出根目录文件及文件夹\n \
            share: 分享文件\n \
            delete [file id]: 删除文件")
    except ValueError:
        print("文件ID输入错误")