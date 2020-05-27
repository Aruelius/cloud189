"""
天翼云盘 API，封装了对天翼云的各种操作，解除了上传格式、大小限制
"""

import os
import re
import json
import traceback
from time import sleep

import requests
from xml.etree import ElementTree
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
        self._sessionKey = ""
        self._sessionSecret = ""
        self._accessToken = ""
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

    def set_session(self, key, secret, token):
        self._sessionKey = key
        self._sessionSecret = secret
        self._accessToken = token

    def set_captcha_handler(self, captcha_handler):
        """设置下载验证码处理函数
        :param captcha_handler (img_data) -> str 参数为图片二进制数据,需返回验证码字符
        """
        self._captcha_handler = captcha_handler

    def get_cookie(self):
        return self._session.cookies.get_dict()

    def _redirect(self):
        r = self._get(self._host_url + "/udb/udb_login.jsp?pageId=1&redirectURL=/main.action")
        captchaToken = re.findall(r"captchaToken' value='(.+?)'", r.text)[0]
        lt = re.findall(r'lt = "(.+?)"', r.text)[0]
        returnUrl = re.findall(r"returnUrl = '(.+?)'", r.text)[0]
        paramId = re.findall(r'paramId = "(.+?)"', r.text)[0]
        self._session.headers.update({"lt": lt})
        return captchaToken, returnUrl, paramId

    def _needcaptcha(self, captchaToken, username):
        """登录验证码处理函数"""
        url = self._auth_url + "needcaptcha.do"
        post_data = {
            "accountType": "01",
            "userName": "{RSA}" + b64tohex(encrypt(username)),
            "appKey": "cloud"
        }
        r = self._post(url, data=post_data)
        captcha = ""
        if r.text != "0":  # 需要验证码
            if self._captcha_handler:
                pic_url = self._auth_url + "picCaptcha.do"
                img_data = self._get(pic_url, params={"token": captchaToken}).content
                captcha = self._captcha_handler(img_data)  # 用户手动识别验证码
            else:
                logger.error("没有验证码处理函数！")
        return captcha

    def login_by_cookie(self, config):
        """使用 cookie 登录"""
        cookies = config.cookie
        try:
            for k, v in cookies.items():
                self._session.cookies.set(k, v, domain=".cloud.189.cn")
            resp = self._get(self._host_url + "/v2/getUserLevelInfo.action")
            if "InvalidSessionKey" not in resp.text:
                try: self.set_session(config.key, config.secret, config.token)
                except: pass
                return Cloud189.SUCCESS
        except: pass
        return Cloud189.FAILED

    def login(self, username, password):
        """使用 用户名+密码 登录"""
        captchaToken, returnUrl, paramId = self._redirect()
        validateCode = self._needcaptcha(captchaToken, username)
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

    def get_rec_file_list(self) -> FileList:
        """获取回收站文件夹列表"""
        global all_file_lists
        all_file_lists = FileList()
        page = 1
        url = self._host_url + '/v2/listRecycleBin.action'
        def _get_one_page(page: int=1) -> bool:
            """返回 True 表示还有文件需要获取"""
            global all_file_lists
            resp = self._get(url, params={'pageNum': page, 'pageSize': 60})
            if not resp:
                return all_file_lists
            resp = resp.json()
            familyId = resp['familyId']
            for item in resp['data']:
                name = item['fileName']
                fid = item['fileId']
                pid = item['parentId']
                ctime = item['createTime']
                optime = item['lastOpTime']
                size = item['fileSize']
                ftype = item['fileType']
                durl = item['downloadUrl']
                isFolder = item['isFolder']
                isFamily = item['isFamilyFile']
                path = item['pathStr']
                all_file_lists.append(RecInfo(name, fid, pid, ctime, optime, size, ftype, durl, isFolder, isFamily, path, familyId))
            logger.debug(f"RecycleBin{page=}: {resp['recordCount']=}, {resp['pageNum']=}, {resp['pageSize']=}")
            return resp['recordCount'] > resp['pageNum'] * resp['pageSize']
        while _get_one_page(page):  # TODO(rachpt): 大于 60 条记录需要验证是否正确
            page += 1
            if not _get_one_page(page):
                break
        return all_file_lists

    def _batch_task(self, file_info, action: str, target_id: str='') -> int:
        """公共批处理请求
        :param file_info: FolderInfo、RecInfo、RecInfo
        :param action:    RESTORE、DELETE、MOVE、COPY
        :param target_id: 移动文件的目标文件夹 id
        :return:          Cloud189 状态码
        """
        task_info = {
            "fileId": str(file_info.id),                # str
            "srcParentId": str(file_info.pid),          # str
            "fileName": file_info.name,                 # str
            "isFolder": 1 if file_info.isFolder else 0  # int
        }

        create_url = self._host_url + "/createBatchTask.action"
        post_data = {"type": action, "taskInfos": json.dumps([task_info,])}
        if target_id:
            post_data.update({"targetFolderId": target_id})
        resp = self._post(create_url, data=post_data)
        task_id = resp.text.strip('"').strip('\'')
        logger.debug(f"Text: {resp.text=}, {task_id=}, {action=}, {target_id=}")
        if not task_id:
            logger.debug(f"Batch_task: {resp.status_code=}")
            return Cloud189.FAILED

        def _check_task(task_id):
            check_url = self._host_url + '/checkBatchTask.action'
            post_data = {"type": action, "taskId": task_id}
            resp = self._post(check_url, data=post_data)
            if not resp:
                logger.debug("BatchTask[_check] Error!")
            resp = resp.json()
            if 'taskStatus' in resp:
                return resp['taskStatus']
            else:
                logger.debug(f"BatchTask[_check]{post_data=},{task_id=},{resp=}")
                return 5  # 防止无限循环

        task_status = 0
        while task_status != 4:
            sleep(0.5)
            task_status = _check_task(task_id)
        return Cloud189.SUCCESS

    def rec_restore(self, file_info):
        """还原文件"""
        return self._batch_task(file_info, 'RESTORE')

    def rec_delete(self, file_info):
        """回收站删除文件"""
        url = self._host_url + '/v2/deleteFile.action'
        resp = self._get(url, params={'familyId': file_info.fid, 'fileIdList': file_info.id})
        if resp and resp.json()['success']:
            return Cloud189.SUCCESS
        else:
            return Cloud189.FAILED

    def rec_empty(self, file_info):
        """清空回收站"""
        url = self._host_url + '/v2/emptyRecycleBin.action'
        resp = self._get(url, params={'familyId': file_info.fid})
        if resp and resp.json()['success']:
            return Cloud189.SUCCESS
        else:
            return Cloud189.FAILED

    def share_file(self, fid, et=None, ac=None):
        '''分享文件'''
        expireTime_dict = {"1": "1", "2": "7", "3": "2099"}
        if et and et in ('1', '2', '3'):
            expireTime = et
        else:
            expireTime = input("请选择分享有效期：1、1天，2、7天，3、永久：")
        if ac and ac in ('1', '2'):
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
        return ShareCode(Cloud189.SUCCESS, share_url, pwd, expireTime)

    def get_file_list(self, fid) -> (FileList, PathList):
        """获取文件列表"""
        file_list = FileList()
        path_list = PathList()
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
            name = info['fileName']
            _id = int(info['fileId'])
            pid = int(info['parentId'])
            ctime = info['createTime']
            optime = info['lastOpTime']
            size = info['fileSize'] if 'fileSize' in info else ''
            ftype = info['fileType']
            durl = info['downloadUrl'] if 'downloadUrl' in info else ''
            isFolder = info['isFolder']
            isStarred = info['isStarred']
            file_list.append(FileInfo(name=name, id=_id, pid=pid, ctime=ctime, optime=optime, size=size,
                                      ftype=ftype, durl=durl, isFolder=isFolder, isStarred=isStarred))
        for info in resp["path"]:
            path_list.append(PathInfo(info['fileName'], int(info['fileId']), info['isCoShare']))

        return file_list, path_list

    def _create_upload_file(self, filepath, folder_id=-11):
        # for _ in range(MAX_ATTEMPT_NUMBER):
        code = infos = None
        try:
            url = API + "/createUploadFile.action?{SUFFIX_PARAM}"
            date = get_time()
            headers = {
                "SessionKey": self._sessionKey,
                "Sign-Type": "1",
                "User-Agent": UA,
                "Date": date,
                "Signature": calculate_hmac_sign(self._sessionSecret, self._sessionKey, 'POST', url, date),
                "Accept": "application/json;charset=UTF-8",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            post_data = {
                "parentFolderId": folder_id,
                "baseFileId": "",
                "fileName": get_file_name(filepath),
                "size": os.path.getsize(filepath),
                "md5": get_file_md5(filepath),
                "lastWrite": "",
                "localPath": filepath,
                "opertype": 1,
                "flag": 1,
                "resumePolicy": 1,
                "isLog": 0
            }
            resp = requests.post(url, headers=headers, data=post_data, timeout=10)
            if resp.json()['res_message'] == "UserDayFlowOverLimited":
                logger.error("当前登录账号每日传输流量已用尽")
                code = Cloud189.FAILED
            elif resp.json().get('uploadFileId'):
                upload_file_id = resp.json()['uploadFileId']
                file_upload_url = resp.json()['fileUploadUrl']
                file_commit_url = resp.json()['fileCommitUrl']
                file_data_exists = resp.json()['fileDataExists']
                logger.debug(f"创建上传任务成功,上传节点为 {file_upload_url.split('//')[1].split('.')[0]}")
                code = Cloud189.SUCCESS
                infos = (upload_file_id, file_upload_url, file_commit_url, file_data_exists)
            else:
                logger.error(f'未知回显{resp.text=},{resp.json()}, 请联系开发者')
                code = Cloud189.FAILED
        except Exception:
            code = Cloud189.FAILED
            traceback.print_exc()
        return code, infos

    def _upload_file_data(self, file_upload_url, upload_file_id, filepath, callback=None):
        url = f"{file_upload_url}?{SUFFIX_PARAM}"
        date = get_time()
        headers = {
            "SessionKey": self._sessionKey,
            "Edrive-UploadFileId": str(upload_file_id),
            "User-Agent": UA,
            "Date": date,
            "Signature": calculate_hmac_sign(self._sessionSecret, self._sessionKey, 'PUT', url, date),
            "Accept": "application/json;charset=UTF-8",
            "Content-Type": "application/octet-stream",
            "Edrive-UploadFileRange": f"0-{os.path.getsize(filepath)}",
            "ResumePolicy": "1"
        }

        self._upload_finished_flag = False  # 上传完成的标志
        def _call_back(it, total_size):
            for now_size, item in enumerate(it):
                yield item
                if callback is not None:
                    if not self._upload_finished_flag:
                        callback(filepath, total_size, now_size)
                    if now_size == total_size:
                        self._upload_finished_flag = True
                    logger.debug(f"Upload: {total_size=}, {now_size=}")
            if callback is not None:  # 保证迭代完后，两者大小一样
                callback(filepath, total_size, total_size)

        with open(filepath, 'rb') as f:
            total_size = os.path.getsize(filepath)  # Byte
            _counts = (total_size // 4096)  # KB
            chunks = get_chunks(f, 4096)
            data = _call_back(chunks, _counts)

            resp = requests.put(url, data=data, headers=headers)
            if resp.text != "":
                node = ElementTree.XML(resp.text)
                if node.text == "error":
                    if node.findtext('code') != 'UploadFileCompeletedError':
                        logger.error(f"上传文件数据时发生错误{node.findtext('code')},{node.findtext('message')}")
                        return Cloud189.FAILED
            else:
                logger.debug(f"上传文件{filepath}成功!")
                return Cloud189.SUCCESS

    def _upload_client_commit(self, file_commit_url, upload_file_id):
        '''客户端上传确认'''
        # for _ in range(MAX_ATTEMPT_NUMBER):
        fid = ''
        try:
            url = f"{file_commit_url}?{SUFFIX_PARAM}"
            date = get_time()  # 时间戳
            headers = {
                "SessionKey": self._sessionKey,
                "User-Agent": UA,
                "Date": date,
                "Signature": calculate_hmac_sign(self._sessionSecret, self._sessionKey, 'POST', url, date),
                "Accept": "application/json;charset=UTF-8",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            post_data = {
                "uploadFileId": upload_file_id,
                "opertype": 1,
                "isLog": 0,
                "ResumePolicy": 1
            }
            resp = requests.post(url, data=post_data, headers=headers, timeout=10)
            node = ElementTree.XML(resp.text)
            if node.text != 'error':
                fid = node.findtext('id')
                logger.debug(f"于[{node.findtext('createDate')}]上传[{node.findtext('name')}]({node.findtext('id')})成功")
            else:
                logger.error(f'{resp.text=}')
        except Exception:
            traceback.print_exc()
        return fid

    def upload_file_by_client(self, file_path, folder_id=-11, callback=None):
        '''使用客户端接口上传单文件，支持秒传功能'''
        if not os.path.isfile(file_path):
            return UpCode(Cloud189.PATH_ERROR)
        logger.debug(f"文件[{file_path}]进入上传流程")
        code, infos = self._create_upload_file(file_path, folder_id)
        if code == Cloud189.SUCCESS:
            upload_file_id, file_upload_url, file_commit_url, file_data_exists = infos
            if file_data_exists == 1:  # 数据存在，进入秒传流程
                fid = self._upload_client_commit(file_commit_url, upload_file_id)
                if not fid:
                    code = Cloud189.FAILED
                quick_up = True
            else:  # 上传文件数据
                code = self._upload_file_data(file_upload_url, upload_file_id, file_path, callback)
                if code != Cloud189.SUCCESS:
                    return UpCode(code)
                fid = self._upload_client_commit(file_commit_url, upload_file_id)
                quick_up = False
            return UpCode(code, fid, quick_up)
        else:
            return UpCode(code)

    def upload_file_by_web(self, file_path, folder_id=-11, callback=None):
        '''使用网页接口上传单文件，不支持秒传'''
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

        self._session.headers["Referer"] = self._host_url  # 放到 headers？

        headers.update({"Host": "cloud.189.cn"})
        url = self._host_url + "/main.action"
        resp = self._get(url, headers=headers)
        if not resp:
            return UpCode(Cloud189.NETWORK_ERROR)
        sessionKey = re.findall(r"sessionKey = '(.+?)'", resp.text)[0]

        file = open(file_path, 'rb')
        post_data = {
            "parentId": str(folder_id),
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

    def upload_file(self, file_path, folder_id=-11, callback=None):
        if self._sessionKey and self._sessionSecret and self._accessToken:
            return self.upload_file_by_client(file_path, folder_id, callback)
        else:
            return self.upload_file_by_web(file_path, folder_id, callback)

    def upload_dir(self, folder_path, parrent_fid=-11, callback=None):
        '''上传文件夹'''
        if not os.path.isdir(folder_path):
            return UpCode(Cloud189.PATH_ERROR)

        dir_dict = {}
        logger.debug(f'[{folder_path}]是文件夹，开始解析目录结构')
        upload_files = []
        folder_name = get_file_name(folder_path)
        result = self.mkdir(parrent_fid, folder_name)
        if result.code != Cloud189.SUCCESS:
            return result.code

        dir_dict[folder_name] = result.id
        for home, dirs, files in os.walk(folder_path):
            for _file in files:
                f_path = home + os.sep + _file
                f_rfolder = get_relative_folder(f_path, folder_path)
                logger.debug(f"{f_rfolder=}")
                if f_rfolder not in dir_dict:
                    dir_dict[f_rfolder] = '' 
                upload_files.append((f_path, dir_dict[f_rfolder]))
            for _dir in dirs:
                p_rfolder = get_relative_folder(home, folder_path, is_file=False)
                logger.debug(f"{p_rfolder=}, {home=}, {folder_path=}")
                dir_rname = p_rfolder + os.sep + _dir  # 文件夹相对路径

                result = self.mkdir(dir_dict[p_rfolder], _dir)
                if result.code != Cloud189.SUCCESS:
                    logger.error(f"上传文件夹中创建文件夹{dir_rname=} 失败！{folder_name=}, {dir_dict[p_rfolder]=}")
                    return Cloud189.FAILED
                logger.debug(f"成功上传文件夹{folder_name=}, {dir_dict[p_rfolder]=}, {dir_rname=}, {result.id}")
                dir_dict[dir_rname] = result.id
        results = []
        for upload_file in upload_files:
            logger.debug(f"文件[{upload_file[0]}]进入上传流程")
            res = self.upload_file(upload_file[0], upload_file[1], callback)
            results.append(UpCode(res.code, res.id, res.quick_up, upload_file))
        return results

    def get_file_info_by_id(self, fid) -> FileInfo:
        '''获取文件(夹) 详细信息'''
        url = self._host_url + "/v2/getFileInfo.action"
        resp = self._get(url, params={'fileId': fid})
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
        name = resp['fileName']
        _id = resp['fileId']
        pid = resp['parentId']
        ctime = resp['createTime']
        optime = resp['lastOpTime']
        size = resp['fileSize']
        ftype = resp['fileType']
        isFolder = resp['isFolder']
        account = resp['createAccount']
        durl = resp['downloadUrl'] if 'downloadUrl' in resp else ''
        count = resp['subFileCount'] if 'subFileCount' in resp else ''
        return FileInfo(name=name, id=_id, pid=pid, ctime=ctime, optime=optime, size=size,
                        ftype=ftype, isFolder=isFolder, account=account, durl=durl, count=count)

    def down_file_by_id(self, fid, save_path='./Download', callback=None) -> int:
        infos = self.get_file_info_by_id(fid)
        if infos == Cloud189.NETWORK_ERROR:
            return Cloud189.NETWORK_ERROR
        elif infos == Cloud189.FAILED:
            return Cloud189.FAILED

        if not os.path.exists(save_path):
            os.makedirs(save_path)
        durl = 'https:' + infos.durl
        resp = self._get(durl, stream=True)
        if not resp:
            return Cloud189.FAILED
        total_size = int(resp.headers['Content-Length'])

        # ---
        file_path = save_path + os.sep + infos.name
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
                        callback(infos.name, total_size, now_size)
        logger.debug(f"{total_size=}, {now_size=}")
        return Cloud189.SUCCESS

    def delete_by_id(self, fid):
        '''删除文件(夹)'''
        infos = self.get_file_info_by_id(fid)
        if infos == Cloud189.NETWORK_ERROR:
            return Cloud189.NETWORK_ERROR
        elif infos == Cloud189.FAILED:
            return Cloud189.FAILED

        return self._batch_task(infos, 'DELETE')

    def move_file(self, info, target_id):
        '''移动文件(夹)'''
        return self._batch_task(info, 'MOVE', str(target_id))

    def cpoy_file(self, tasks, fid):
        '''复制文件(夹)'''
        infos = self.get_file_info_by_id(fid)
        if infos == Cloud189.NETWORK_ERROR:
            return Cloud189.NETWORK_ERROR
        elif infos == Cloud189.FAILED:
            return Cloud189.FAILED

        return self._batch_task(infos, 'COPY')
        '''
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
        '''

    def mkdir(self, parent_id, fname):
        '''新建文件夹'''
        url = self._host_url + '/v2/createFolder.action'
        result = self._get(url, params={'parentId': str(parent_id), 'fileName': fname})
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
        resp = self._get(url, params={'fileId': str(fid), 'fileName': fname})
        if not resp:
            return Cloud189.NETWORK_ERROR
        resp = resp.json()
        if 'success' in resp:
            return Cloud189.SUCCESS
        logger.debug(f"Rename: {resp=}, {fid=}, {fname=}")
        return Cloud189.FAILED

    def get_folder_nodes(self, fid=None, max_deep=5) -> TreeList:
        '''获取子文件夹信息
        :param fid:      需要获取子文件夹的文件夹id，None 表示获取所有文件夹
        :param max_deep: 子文件夹最大递归深度
        :return:         TreeList 类
        '''
        tree = TreeList()
        url = self._host_url + "/getObjectFolderNodes.action"
        post_data = {"orderBy": '1', 'order': 'ASC'}
        deep = 1
        def _get_sub_folder(fid, deep):
            if fid:
                post_data.update({"id": str(fid)})
            params = {'pageNum': 1, 'pageSize': 500}
            resp = self._post(url, params=params, data=post_data)
            if not resp:
                return
            for folder in resp.json():
                name = folder['name']
                _id = int(folder['id'])
                pid = int(folder['pId']) if 'pId' in folder else ''
                isParent = folder['isParent']  # str
                tree.append(FolderTree(name=name, id=_id, pid=pid, isParent=isParent), repeat=False)
                logger.debug(f"Sub Folder: {name=}, {_id=}, {pid=}, {isParent=}")
                if deep < max_deep:
                    _get_sub_folder(_id, deep+1)

        _get_sub_folder(fid, deep)
        logger.debug(f"Sub Folder Tree len: {len(tree)}")
        return tree
