"""
天翼云盘 API，封装了对天翼云的各种操作，解除了上传格式、大小限制
"""

import os
import re
import json

import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

from cloud189.api.utils import *
from cloud189.api.types import *
from cloud189.api.models import *

__all__ = ['Cloud189']


class Cloud189(object):
    FAILED = -1
    SUCCESS = 0
    ID_ERROR = 1
    PASSWORD_ERROR = 2
    LACK_PASSWORD = 3
    ZIP_ERROR = 4
    MKDIR_ERROR = 5
    URL_INVALID = 6
    FILE_CANCELLED = 7
    PATH_ERROR = 8
    NETWORK_ERROR = 9
    CAPTCHA_ERROR = 10

    def __init__(self):
        self._session = requests.Session()
        self._captcha_handler = None
        self._timeout = 15  # 每个请求的超时(不包含下载响应体的用时)
        self._host_url = 'https://cloud.189.cn'
        self._auth_url = 'https://open.e.189.cn/api/logbox/oauth2/'
        self._cookies = None
        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:74.0) Gecko/20100101 Firefox/76.0',
            'Referer': 'https://open.e.189.cn/',
        }
        disable_warnings(InsecureRequestWarning)  # 全局禁用 SSL 警告

    def _get(self, url, **kwargs):
        try:
            kwargs.setdefault('timeout', self._timeout)
            kwargs.setdefault('headers', self._headers)
            return self._session.get(url, verify=False, **kwargs)
        except requests.Timeout:
            logger.warning("Encountered timeout error while requesting network!")
            raise TimeoutError
        except (requests.RequestException, Exception) as e:
            logger.error(f"Unexpected error: {e=}")

    def _post(self, url, data, **kwargs):
        try:
            kwargs.setdefault('timeout', self._timeout)
            kwargs.setdefault('headers', self._headers)
            return self._session.post(url, data, verify=False, **kwargs)
        except requests.Timeout:
            logger.warning("Encountered timeout error while requesting network!")
            raise TimeoutError
        except (requests.RequestException, Exception) as e:
            logger.error(f"Unexpected error: {e=}")

    def get_cookie(self):
        return self._session.cookies.get_dict()

    def login_by_cookie(self, cookies: dict):
        try:
            for k, v in cookies.items():
                self._session.cookies.set(k, v, domain=".cloud.189.cn")

            r = self._get(self._host_url + "/v2/getUserLevelInfo.action")
            if "InvalidSessionKey" not in r.text:
                return Cloud189.SUCCESS
        except: pass
        return Cloud189.FAILED

    def login(self, username, password):
        captchaToken, returnUrl, paramId = self.redirect()
        validateCode = self.needcaptcha(captchaToken, username)
        url = self._auth_url + "loginSubmit.do"
        data = {
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
        r = self._post(url, data=data)
        msg = r.json()["msg"]
        if msg == "登录成功":
            self._get(r.json()["toUrl"])
            return Cloud189.SUCCESS
        print(msg)
        return Cloud189.FAILED

    def redirect(self):
        r = self._get(self._host_url + "/udb/udb_login.jsp?pageId=1&redirectURL=/main.action")
        captchaToken = re.findall(r"captchaToken' value='(.+?)'", r.text)[0]
        lt = re.findall(r'lt = "(.+?)"', r.text)[0]
        returnUrl = re.findall(r"returnUrl = '(.+?)'", r.text)[0]
        paramId = re.findall(r'paramId = "(.+?)"', r.text)[0]
        self._session.headers.update({"lt": lt})
        return captchaToken, returnUrl, paramId

    def needcaptcha(self, captchaToken, username):
        r = self._post(
            url= self._auth_url + "needcaptcha.do",
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
            r = self._get(
                url= self._auth_url + "picCaptcha.do",
                params={"token": captchaToken}
            )
            with open("./captcha.png", "wb") as f:
                f.write(r.content)
                f.close()  
            return input("验证码下载完成，打开 ./captcha.png 查看: ")

    def share_file(self, fid):
        expireTime_dict = {
            "1": "1",
            "2": "7",
            "3": "2099"
        }
        expireTime = input("请选择分享有效期：1、1天，2、7天，3、永久：")
        withAccessCode = input("请选择分享形式：1、私密分享，2、公开分享：")
        if withAccessCode == "1":
            url = self._host_url + "/v2/privateLinkShare.action"
            params = {
                "fileId": fid,
                "expireTime": expireTime_dict[expireTime],
                "withAccessCode": withAccessCode
            }
        else:
            url = self._host_url + "/v2/createOutLinkShare.action"
            params = {
                "fileId": fid,
                "expireTime": expireTime_dict[expireTime]
            }
        resp = self._get(url=url, params=params).json()
        share_url = resp['shortShareUrl']
        pwd = resp['accessCode'] if 'accessCode' in resp else ''
        return share_url, pwd

    def get_file_list(self, fid) -> (FolderList, FolderList):
        file_list = FolderList()
        path_list = FolderList()
        url = self._host_url + "/v2/listFiles.action"
        params = {
            "fileId": fid, # 根目录
            "inGroupSpace": "false",
            "orderBy": "1",
            "order": "ASC",
            "pageNum": "1",
            "pageSize": "60"
        }
        resp = self._get(url, params=params).json()
        if 'data' not in resp:
            print(resp)
        for info in resp["data"]:
            fname = info['fileName']
            fid = info['fileId']
            pid = info['parentId']
            time = info['createTime']
            size = info['fileSize'] if 'fileSize' in info else ''
            ftype = info['fileType']
            durl = info['downloadUrl'] if 'downloadUrl' in info else ''
            isFolder = info['isFolder']
            isStarred = info['isStarred']
            file_list.append(FolderInfo(fname, fid, pid, time, size, ftype, durl, isFolder, isStarred))
        for path in resp["path"]:
            path_list.append(PathInfo(path['fileName'], path['fileId'], path['isCoShare']))

        return file_list, path_list

    def upload(self, fid, filePath):
        self._session.headers["Referer"] = self._host_url
        def get_upload_url():
            r = self._get(self._host_url + "/v2/getUserUploadUrl.action")
            return "https:" + r.json()["uploadUrl"]

        def get_session_key():
            r = self._get(
                url=self._host_url + "/main.action",
                headers={"Host": "cloud.189.cn"}
            )
            sessionKey = re.findall(r"sessionKey = '(.+?)'", r.text)[0]
            return sessionKey

        def upload_file():
            filename = os.path.basename(filePath)
            filesize = os.path.getsize(filePath)
            print(f"正在上传: {filename} 大小: {filesize}")
            upload_url = get_upload_url()
            multipart_data = MultipartEncoder(
                fields={
                    "parentId": fid,
                    "fname": filename,
                    "sessionKey": get_session_key(),
                    "albumId": "undefined",
                    "opertype": "1",
                    'file': (filename, open(filePath, 'rb'), 'application/octet-stream')
                }
            )
            headers = {"Content-Type": multipart_data.content_type}
            r = self._post(url=upload_url, data=multipart_data, headers=headers).json()
            print(f"上传完毕！文件ID：{r['id']} 上传时间: {r['createDate']}")
        upload_file()

    def get_file_info_by_id(self, fid):
        infos = {}
        r = self._get(self._host_url + f"/v2/getFileInfo.action?fileId={fid}").json()
        # print(r)
        infos["fname"] =  r["fileName"]
        infos["fid"] = fid
        infos["size"] = r['fileSize']
        infos["srcParentId"] = "-11" # 根目录
        infos["isfolder"] = True if r["isFolder"] else False
        infos["durl"] = "https:"+r["downloadUrl"]
        return infos

    def download_by_id(self, fid, save_path='./downloads'):
        infos = self.get_file_info_by_id(fid)
        if infos:
            if not os.path.isdir(save_path):
                os.mkdir(save_path)
            r = self._get(infos['durl'], stream=True)
            save_path = save_path + os.sep + infos['fname']
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024**2):
                    f.write(chunk)
                f.close()
            print(f"{infos['fname']} 下载完成!")

    def delete_by_id(self, fid):
        infos = self.get_file_info_by_id(fid)

        taskInfo = {"fileId": infos["fid"],
                    "srcParentId": "-11", # 根目录
                    "fileName": infos["fname"],
                    "isFolder": 1 if infos["isfolder"] else 0 }

        url = self._host_url + "/createBatchTask.action"
        post_data = { "type": "DELETE", "taskInfos": json.dumps([taskInfo,])}

        r = self._post(url, data=post_data)
        if r.text:
            print("删除成功！")

    def mkdir(self, parent_id, fname):
        '''新建文件夹'''
        url = self._host_url + '/v2/createFolder.action'
        html = self._get(url, params={'parentId': parent_id, 'fileName': fname})
        if not html:
            return Cloud189.FAILED
        fid = html.json()['fileId']
        return fid
