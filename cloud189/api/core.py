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

    def share_file(self, fid, et=None, ac=None):
        '''分享文件'''
        expireTime_dict = {"1": "1", "2": "7", "3": "2099"}
        if et and et in (1, 2, 3):
            expireTime = et
        else:
            expireTime = input("请选择分享有效期：1、1天，2、7天，3、永久：")
        if ac and ac in (1, 2):
            withAccessCode = ac
        else:
            withAccessCode = input("请选择分享形式：1、私密分享，2、公开分享：")
        if withAccessCode == "1":
            url = self._host_url + "/v2/privateLinkShare.action"
            params = {
                "fileId": str(fid),
                "expireTime": expireTime_dict[expireTime],
                "withAccessCode": withAccessCode
            }
        else:
            url = self._host_url + "/v2/createOutLinkShare.action"
            params = {
                "fileId": str(fid),
                "expireTime": expireTime_dict[expireTime]
            }
        resp = self._get(url=url, params=params)
        if not resp:
            return ShareCode(Cloud189.FAILED)
        resp = resp.json()
        share_url = resp['shortShareUrl']
        pwd = resp['accessCode'] if 'accessCode' in resp else ''
        return ShareCode(Cloud189.SUCCESS, share_url, pwd)

    def get_file_list(self, fid) -> (FolderList, FolderList):
        file_list = FolderList()
        path_list = FolderList()
        url = self._host_url + "/v2/listFiles.action"
        params = {
            "fileId": str(fid),
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
            fid = int(info['fileId'])
            pid = int(info['parentId'])
            time = info['createTime']
            size = info['fileSize'] if 'fileSize' in info else ''
            ftype = info['fileType']
            durl = info['downloadUrl'] if 'downloadUrl' in info else ''
            isFolder = info['isFolder']
            isStarred = info['isStarred']
            file_list.append(FolderInfo(fname, fid, pid, time, size, ftype, durl, isFolder, isStarred))
        for info in resp["path"]:
            path_list.append(PathInfo(info['fileName'], int(info['fileId']), info['isCoShare']))

        return file_list, path_list

    def upload_file(self, file_path, folder_id=-11, callback=None):
        ''''上传单文件'''
        if not os.path.isfile(file_path):
            return UpCode(Cloud189.PATH_ERROR)

        # 文件已经存在，则认为已经上传了
        filename = os.path.basename(file_path)
        file_list, _ = self.get_file_list(folder_id)
        _item = file_list.find_by_name(filename)
        if _item:
            return UpCode(Cloud189.SUCCESS, _item.id)

        headers = {'Referer': self._host_url}
        url = self._host_url + "/v2/getUserUploadUrl.action"
        resp = self._get(url, headers=headers)
        if not resp:
            return UpCode(Cloud189.NETWORK_ERROR)
        resp = resp.json()
        if 'uploadUrl' in resp:
            upload_url = "https:" + resp['uploadUrl']
        else:
            upload_url = ''

        self._session.headers["Referer"] = self._host_url
        def get_upload_url():
            r = self._get(self._host_url + "/v2/getUserUploadUrl.action")
            return "https:" + r.json()["uploadUrl"]

        headers.update({"Host": "cloud.189.cn"})
        url = self._host_url + "/main.action"
        resp = self._get(url, headers=headers)
        if not resp:
            return UpCode(Cloud189.NETWORK_ERROR)
        sessionKey = re.findall(r"sessionKey = '(.+?)'", resp.text)[0]

        file = open(file_path, 'rb')
        post_data = {
            "parentId": folder_id,
            "fname": filename,
            "sessionKey": sessionKey,
            "albumId": "undefined",
            "opertype": "1",
            "upload_file": (filename, file, 'application/octet-stream')
        }
        post_data = MultipartEncoder(post_data)
        headers = {"Content-Type": post_data.content_type}
        self._upload_finished_flag = False  # 上传完成的标志

        def _call_back(read_monitor):
            if callback is not None:
                if not self._upload_finished_flag:
                    callback(filename, read_monitor.len, read_monitor.bytes_read)
                if read_monitor.len == read_monitor.bytes_read:
                    self._upload_finished_flag = True

        monitor = MultipartEncoderMonitor(post_data, _call_back)
        result = self._post(upload_url, data=monitor, headers=headers, timeout=None)
        if not result:  # 网络异常
            return UpCode(Cloud189.NETWORK_ERROR)
        else:
            result = result.json()
        if 'id' not in result:
            logger.debug(f'Upload failed: {result=}')
            return UpCode(Cloud189.FAILED)  # 上传失败

        return UpCode(Cloud189.SUCCESS, result['id'])  # 返回 id

    def upload_dir(self, file_path, folder_id=-11, callback=None):
        '''上传文件夹'''
        print(11)
        pass

    def get_file_info_by_id(self, fid):
        '''获取文件(夹) 详细信息'''
        resp = self._get(self._host_url + f"/v2/getFileInfo.action?fileId={fid}")
        if resp:
            resp = resp.json()
        else:
            return Cloud189.NETWORK_ERROR
        # createAccount     # createTime
        # fileId            # fileIdDigest
        # fileName          # fileSize
        # fileType          # isFolder
        # lastOpTime        # parentId
        # subFileCount
        if 'fileName' in resp:
            return resp
        else:
            return Cloud189.FAILED

    def down_file_by_id(self, fid, save_path='./Download', callback=None) -> int:
        infos = self.get_file_info_by_id(fid)
        if infos == Cloud189.NETWORK_ERROR:
            return Cloud189.NETWORK_ERROR
        elif infos == Cloud189.FAILED:
            return Cloud189.FAILED

        if not os.path.exists(save_path):
            os.makedirs(save_path)
        durl = 'https:' + infos['downloadUrl']
        resp = self._get(durl, stream=True)
        if not resp:
            return Cloud189.FAILED
        total_size = int(resp.headers['Content-Length'])

        # ---
        file_path = save_path + os.sep + infos['fileName']
        logger.debug(f'Save file to {file_path=}')
        if os.path.exists(file_path):
            now_size = os.path.getsize(file_path)  # 本地已经下载的文件大小
        else:
            now_size = 0
        chunk_size = 4096
        headers = {**self._headers, 'Range': 'bytes=%d-' % now_size}
        resp = self._get(durl, stream=True, headers=headers)

        if not resp:
            return Cloud189.FAILED
        # if resp.status_code == 416:  # 已经下载完成
        #     return Cloud189.SUCCESS

        with open(file_path, "ab") as f:
            for chunk in resp.iter_content(chunk_size):
                if chunk:
                    f.write(chunk)
                    f.flush()
                    now_size += len(chunk)
                    if callback is not None:
                        callback(infos['fileName'], total_size, now_size)
        return Cloud189.SUCCESS

    def delete_by_id(self, fid):
        '''删除文件(夹)'''
        infos = self.get_file_info_by_id(fid)
        if infos == Cloud189.NETWORK_ERROR:
            return Cloud189.NETWORK_ERROR
        elif infos == Cloud189.FAILED:
            return Cloud189.FAILED

        taskInfo = {"fileId": infos["fileId"],
                    "srcParentId": infos["parentId"],
                    "fileName": infos["fileName"],
                    "isFolder": 1 if infos["isFolder"] else 0 }

        url = self._host_url + "/createBatchTask.action"
        post_data = { "type": "DELETE", "taskInfos": json.dumps([taskInfo,])}

        r = self._post(url, data=post_data)
        if r.text:
            return Cloud189.SUCCESS
        else:
            return Cloud189.FAILED

    def move_file(self, tasks, fid):
        '''移动文件(夹)'''
        infos = self.get_file_info_by_id(fid)
        if infos == Cloud189.NETWORK_ERROR:
            return Cloud189.NETWORK_ERROR
        elif infos == Cloud189.FAILED:
            return Cloud189.FAILED

        taskInfo = {"fileId": infos["fileId"],
                    "srcParentId": infos["parentId"],
                    "fileName": infos["fileName"],
                    "isFolder": 1 if infos["isfolder"] else 0 }

        url = self._host_url + "/createBatchTask.action"
        post_data = { "type": "MOVE", "taskInfos": json.dumps([taskInfo,])}

        resp = self._post(url, data=post_data)
        if resp.text:
            post_data = { "type": "MOVE", "taskId": resp.text}
            resp = self._post(url, data=post_data)
            if resp:
                resp = resp.json()
                print(resp['taskStatus'])

        else:
            return Cloud189.NETWORK_ERROR


    def cpoy_file(self, tasks, fid):
        '''复制文件(夹)'''
        infos = self.get_file_info_by_id(fid)
        if infos == Cloud189.NETWORK_ERROR:
            return Cloud189.NETWORK_ERROR
        elif infos == Cloud189.FAILED:
            return Cloud189.FAILED

        taskInfo = {"fileId": infos["fileId"],
                    "srcParentId": infos["parentId"],
                    "fileName": infos["fileName"],
                    "isFolder": 1 if infos["isfolder"] else 0 }

        url = self._host_url + "/createBatchTask.action"
        post_data = { "type": "COPY", "taskInfos": json.dumps([taskInfo,])}

        resp = self._post(url, data=post_data)
        if resp.text:
            post_data = { "type": "COPY", "taskId": resp.text}
            resp = self._post(url, data=post_data)
            if resp:
                resp = resp.json()
                print(resp['taskStatus'])  # 4

        else:
            return Cloud189.NETWORK_ERROR

    def mkdir(self, parent_id, fname):
        '''新建文件夹'''
        url = self._host_url + '/v2/createFolder.action'
        result = self._get(url, params={'parentId': parent_id, 'fileName': fname})
        if not result:
            return MkCode(Cloud189.NETWORK_ERROR)
        result = result.json()
        if 'fileId' in result:
            fid = result['fileId']
            return MkCode(Cloud189.SUCCESS, fid)
        else:
            return MkCode(Cloud189.FAILED)

    def rename(self, fid, fname):
        ''''重命名文件(夹)'''
        url = self._host_url + '/v2/renameFile.action'
        resp = self._get(url, params={'parentId': str(fid), 'fileName': fname})
        if not resp:
            return Cloud189.NETWORK_ERROR
        resp = resp.json()
        if 'success' in resp:
            return Cloud189.SUCCESS
        # print(resp,  str(fid), fname)  # 有点问题
        return Cloud189.FAILED

    def get_folder_nodes(self, fid):
        '''获取子文件夹信息'''
        url = self._host_url + "/getObjectFolderNodes.action"
        post_data = { "id": fid, "orderBy": '1', 'order': 'ASC'}
        params = {'pageNum': 1, 'pageSize': 500}

        resp = self._post(url, params=params, data=post_data)
        # isParent: "true", name: "我的应用", pId: "-11",id: '65432'
        pass
