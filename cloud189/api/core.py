"""
天翼云盘 API，封装了对天翼云的各种操作
"""

import os
import re
import json
from time import sleep

from xml.etree import ElementTree
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
    MKDIR_ERROR = 5
    URL_INVALID = 6
    FILE_CANCELLED = 7
    PATH_ERROR = 8
    NETWORK_ERROR = 9
    CAPTCHA_ERROR = 10
    UP_COMMIT_ERROR = 4  # 上传文件 commit 错误
    UP_CREATE_ERROR = 11  # 创建上传任务出错
    UP_UNKNOWN_ERROR = 12  # 创建上传任务未知错误
    UP_EXHAUSTED_ERROR = 13  # 上传量用完
    UP_ILLEGAL_ERROR = 14  # 文件非法

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
            logger.warning(
                "Encountered timeout error while requesting network!")
            raise TimeoutError
        except (requests.RequestException, Exception) as e:
            logger.error(f"Unexpected error: {e=}")

    def _post(self, url, data, **kwargs):
        try:
            kwargs.setdefault('timeout', self._timeout)
            kwargs.setdefault('headers', self._headers)
            return self._session.post(url, data, verify=False, **kwargs)
        except requests.Timeout:
            logger.warning(
                "Encountered timeout error while requesting network!")
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
        r = self._get(self._host_url
                      + "/udb/udb_login.jsp?pageId=1&redirectURL=/main.action")
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
                img_data = self._get(
                    pic_url, params={"token": captchaToken}).content
                captcha = self._captcha_handler(img_data)  # 用户手动识别验证码
            else:
                logger.error("No verification code processing function!")
        return captcha

    def login_by_cookie(self, config):
        """使用 cookie 登录"""
        cookies = config if isinstance(config, dict) else config.cookie
        try:
            for k, v in cookies.items():
                self._session.cookies.set(k, v, domain=".cloud.189.cn")
            resp = self._get(self._host_url + "/v2/getUserLevelInfo.action")
            if "InvalidSessionKey" not in resp.text:
                try:
                    self.set_session(config.key, config.secret, config.token)
                except:
                    pass
                return Cloud189.SUCCESS
        except:
            pass
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

    def _get_more_page(self, resp: dict, r_path=False) -> (list, bool):
        """处理可能需要翻页的请求信息"""
        if resp['pageNum'] * resp['pageSize'] >= resp['recordCount']:
            done = True  # 没有了
        else:
            done = False
        if r_path:
            return [resp['data'], resp['path']], done
        else:
            return resp['data'], done

    def get_rec_file_list(self) -> FileList:
        """获取回收站文件夹列表"""
        results = FileList()
        page = 1
        data = []
        url = self._host_url + '/v2/listRecycleBin.action'

        while True:
            resp = self._get(url, params={'pageNum': page, 'pageSize': 60})
            if not resp:
                logger.error("Rec file list: network error!")
                return None
            resp = resp.json()
            familyId = resp['familyId']
            data_, done = self._get_more_page(resp)
            data.extend(data_)
            if done:
                break
            page += 1
            sleep(0.5)  # 大量请求可能会被限制

        for item in data:
            name = item['fileName']
            id_ = item['fileId']
            pid = item['parentId']
            ctime = item['createTime']
            optime = item['lastOpTime']
            size = item['fileSize']
            ftype = item['fileType']
            durl = item['downloadUrl']
            isFolder = item['isFolder']
            isFamily = item['isFamilyFile']
            path = item['pathStr']
            results.append(RecInfo(name=name, id=id_, pid=pid, ctime=ctime, optime=optime, size=size,
                                   ftype=ftype, isFolder=isFolder, durl=durl, isFamily=isFamily, path=path,
                                   fid=familyId))
        return results

    def _batch_task(self, file_info, action: str, target_id: str = '') -> int:
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
        post_data = {"type": action, "taskInfos": json.dumps([task_info, ])}
        if target_id:
            post_data.update({"targetFolderId": target_id})
        resp = self._post(create_url, data=post_data)
        task_id = resp.text.strip('"').strip('\'')
        logger.debug(
            f"Text: {resp.text=}, {task_id=}, {action=}, {target_id=}")
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
                logger.debug(
                    f"BatchTask[_check]: {post_data=},{task_id=},{resp=}")
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
        resp = self._get(
            url, params={'familyId': file_info.fid, 'fileIdList': file_info.id})
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
            logger.error(f"Share file: {fid=}network error!")
            return ShareCode(Cloud189.FAILED)
        resp = resp.json()
        share_url = resp['shortShareUrl']
        pwd = resp['accessCode'] if 'accessCode' in resp else ''
        return ShareCode(Cloud189.SUCCESS, share_url, pwd, expireTime)

    def get_file_list(self, fid) -> (FileList, PathList):
        """获取文件列表"""
        file_list = FileList()
        path_list = PathList()
        page = 1
        data_path = []
        data = []
        path = []
        url = self._host_url + "/v2/listFiles.action"
        while True:
            params = {
                "fileId": str(fid),
                "inGroupSpace": "false",
                "orderBy": "1",
                "order": "ASC",
                "pageNum": page,
                "pageSize": 60
            }
            resp = self._get(url, params=params)
            if not resp:
                logger.error(f"File list: {fid=}network error!")
                return file_list, path_list
            try:
                resp = resp.json()
            except json.JSONDecodeError:
                # 如果 fid 文件夹被删掉，resp 是 200 但是无法使用 json 方法
                logger.error(f"File list: {fid=} not exit")
                return file_list, path_list
            if 'errorCode' in resp:
                logger.error(f"Get file: {resp}")
                return file_list, path_list
            data_, done = self._get_more_page(resp, r_path=True)
            data_path.append(data_)
            if done:
                break
            page += 1
            sleep(0.5)  # 大量请求可能会被限制
        for data_ in data_path:
            data.extend(data_[0])
            if not path:
                path = data_[1]  # 不同 page 路径因该是一样的
        for item in data:
            name = item['fileName']
            id_ = int(item['fileId'])
            pid = int(item['parentId'])
            ctime = item['createTime']
            optime = item['lastOpTime']
            size = item['fileSize'] if 'fileSize' in item else ''
            ftype = item['fileType']
            durl = item['downloadUrl'] if 'downloadUrl' in item else ''
            isFolder = item['isFolder']
            isStarred = item['isStarred']
            file_list.append(FileInfo(name=name, id=id_, pid=pid, ctime=ctime, optime=optime, size=size,
                                      ftype=ftype, durl=durl, isFolder=isFolder, isStarred=isStarred))
        for item in path:
            path_list.append(PathInfo(name=item['fileName'], id=int(item['fileId']),
                                      isCoShare=item['isCoShare']))

        return file_list, path_list

    def _create_upload_file(self, up_info: UpInfo) -> (int, tuple):
        """创建上传任务，包含秒传检查，返回状态码、创建信息"""
        infos = tuple()
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
                "parentFolderId": up_info.fid,
                "baseFileId": "",
                "fileName": up_info.name,
                "size": up_info.size,
                "md5": get_file_md5(up_info.path, up_info.check),
                "lastWrite": "",
                "localPath": up_info.path,
                "opertype": 1,
                "flag": 1,
                "resumePolicy": 1,
                "isLog": 0
            }
            resp = requests.post(url, headers=headers, data=post_data, verify=False, timeout=10)
            if resp:
                resp = resp.json()
                if resp['res_message'] == "UserDayFlowOverLimited":
                    _msg = f"{up_info.path=}, The daily transmission of the current login account has been exhausted!"
                    code = Cloud189.UP_EXHAUSTED_ERROR
                elif resp.get('res_code') == 'InfoSecurityErrorCode':
                    _msg = f"{up_info.path=} Illegal file!"
                    code = Cloud189.UP_ILLEGAL_ERROR
                elif resp.get('uploadFileId'):
                    upload_file_id = resp['uploadFileId']
                    file_upload_url = resp['fileUploadUrl']
                    file_commit_url = resp['fileCommitUrl']
                    file_data_exists = resp['fileDataExists']
                    node = file_upload_url.split('//')[1].split('.')[0]
                    _msg = f"successfully created upload task, {node=}"
                    infos = (upload_file_id, file_upload_url, file_commit_url, file_data_exists)
                    code = Cloud189.SUCCESS
                else:
                    _msg = f"unknown response {resp=}. Please contact the developer!"
                    code = Cloud189.UP_UNKNOWN_ERROR
                logger.debug(f'Upload by client [create]: {_msg}')
            else:
                code = Cloud189.NETWORK_ERROR
        except Exception as e:
            code = Cloud189.UP_CREATE_ERROR
            logger.error(f'Upload by client [create]: an error occurred! {e=}')
        return code, infos

    def _upload_file_data(self, file_upload_url, upload_file_id, up_info: UpInfo):
        """客户端接口上传文件数据"""
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
            "Edrive-UploadFileRange": f"0-{up_info.size}",
            "ResumePolicy": "1"
        }

        self._upload_finished_flag = False  # 上传完成的标志

        def _call_back(it, chunk_size):
            for chunk_now, item in enumerate(it):
                yield item
                if up_info.callback:
                    now_size = chunk_now * chunk_size
                    if not self._upload_finished_flag:
                        up_info.callback(up_info.path, up_info.size, now_size)
                    if now_size == up_info.size:
                        self._upload_finished_flag = True
            if up_info.callback:  # 保证迭代完后，两者大小一样
                up_info.callback(up_info.path, up_info.size, up_info.size)

        chunk_size = get_chunk_size(up_info.size)
        with open(up_info.path, 'rb') as f:
            chunks = get_upload_chunks(f, chunk_size)
            post_data = _call_back(chunks, chunk_size)

            resp = requests.put(url, data=post_data, headers=headers, verify=False, timeout=None)
            if resp.text != "":
                node = ElementTree.XML(resp.text)
                if node.text == "error":
                    if node.findtext('code') != 'UploadFileCompeletedError':
                        logger.error(
                            f"Upload by client [data]: an error occurred while uploading data {node.findtext('code')},{node.findtext('message')}")
                        return Cloud189.FAILED
            else:
                logger.debug(f"Upload by client [data]: upload {up_info.path} success!")
                return Cloud189.SUCCESS

    def _upload_client_commit(self, file_commit_url, upload_file_id):
        """客户端接口上传确认"""
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
            resp = requests.post(url, data=post_data, headers=headers, verify=False, timeout=10)
            node = ElementTree.XML(resp.text)
            if node.text != 'error':
                fid = node.findtext('id')
                fname = node.findtext('name')
                time = node.findtext('createDate')
                logger.debug(f"Upload by client [commit]: at[{time}] upload [{fname}], {fid=} success!")
            else:
                logger.error(f'Upload by client [commit]: unknown error {resp.text=}')
        except Exception as e:
            logger.error(f'Upload by client [commit]: an error occurred! {e=}')
        return fid

    def _upload_file_by_client(self, up_info: UpInfo) -> UpCode:
        """使用客户端接口上传单文件，支持秒传功能
        :param up_info: UpInfo
        :return:        UpCode
        """
        if up_info.callback and up_info.check:
            up_info.callback(up_info.path, 1, 0, 'check')
        quick_up = False
        fid = ''
        code, infos = self._create_upload_file(up_info)
        if code == Cloud189.SUCCESS:
            upload_file_id, file_upload_url, file_commit_url, file_data_exists = infos
            if file_data_exists == 1:  # 数据存在，进入秒传流程
                logger.debug(f"Upload by client: [{up_info.path}] enter the quick_up process...")
                fid = self._upload_client_commit(file_commit_url, upload_file_id)
                if fid:
                    call_back_msg = 'quick_up'
                    quick_up = True
                else:
                    call_back_msg = 'error'
                    code = Cloud189.UP_COMMIT_ERROR
            else:  # 上传文件数据
                logger.debug(f"Upload by client: [{up_info.path}] enter the normal upload process...")
                code = self._upload_file_data(file_upload_url, upload_file_id, up_info)
                if code == Cloud189.SUCCESS:
                    call_back_msg = None
                    fid = self._upload_client_commit(file_commit_url, upload_file_id)
                else:
                    call_back_msg = 'error'
                    logger.debug(f"Upload by client: [{up_info.path}] normal upload failed!")
        elif code == Cloud189.UP_ILLEGAL_ERROR:
            call_back_msg = 'illegal'
        elif code == Cloud189.UP_EXHAUSTED_ERROR:
            call_back_msg = 'exhausted'
        else:
            call_back_msg = 'error'

        if up_info.callback and call_back_msg:
            up_info.callback(up_info.path, 1, 1, call_back_msg)
        return UpCode(code=code, id=fid, quick_up=quick_up, path=up_info.path)

    def _upload_file_by_web(self, up_info: UpInfo) -> UpCode:
        """使用网页接口上传单文件，不支持秒传
        :param up_info: UpInfo
        :return:         UpCode
        """
        headers = {'Referer': self._host_url}
        url = self._host_url + "/v2/getUserUploadUrl.action"
        resp = self._get(url, headers=headers)
        if not resp:
            logger.error(f"Upload by web: [{up_info.path}] network error(1)!")
            if up_info.callback:
                up_info.callback(up_info.path, 1, 1, 'error')
            return UpCode(code=Cloud189.NETWORK_ERROR, path=up_info.path)
        resp = resp.json()
        if 'uploadUrl' in resp:
            upload_url = "https:" + resp['uploadUrl']
        else:
            logger.error(f"Upload by web: [{up_info.path}] failed to obtain upload node!")
            upload_url = ''

        self._session.headers["Referer"] = self._host_url  # 放到 headers？

        headers.update({"Host": "cloud.189.cn"})
        url = self._host_url + "/main.action"
        resp = self._get(url, headers=headers)
        if not resp:
            logger.error(f"Upload by web: [{up_info.path}] network error(2)!")
            if up_info.callback:
                up_info.callback(up_info.path, 1, 1, 'error')
            return UpCode(code=Cloud189.NETWORK_ERROR, path=up_info.path)
        sessionKey = re.findall(r"sessionKey = '(.+?)'", resp.text)[0]

        def _call_back(read_monitor):
            if up_info.callback:
                if not self._upload_finished_flag:
                    up_info.callback(up_info.path, read_monitor.len, read_monitor.bytes_read)
                if read_monitor.len == read_monitor.bytes_read:
                    self._upload_finished_flag = True

        with open(up_info.path, 'rb') as file_:
            post_data = MultipartEncoder({
                "parentId": up_info.fid,
                "fname": up_info.name,
                "sessionKey": sessionKey,
                "albumId": "undefined",
                "opertype": "1",
                "upload_file": (up_info.name, file_, 'application/octet-stream')
            })
            headers = {"Content-Type": post_data.content_type}
            self._upload_finished_flag = False  # 上传完成的标志

            monitor = MultipartEncoderMonitor(post_data, _call_back)
            result = self._post(upload_url, data=monitor, headers=headers, timeout=None)
            fid = ''
            if result:
                result = result.json()
                if 'id' in result:
                    call_back_msg = ''
                    fid = result['id']
                    code = Cloud189.SUCCESS
                else:
                    call_back_msg = 'error'
                    code = Cloud189.FAILED
                    logger.error(f"Upload by web: [{up_info.path}] failed, {result=}")
            else:  # 网络异常
                call_back_msg = 'error'
                code = Cloud189.NETWORK_ERROR
                logger.error(f"Upload by web: [{up_info.path}] network error(3)!")
            if up_info.callback:
                up_info.callback(up_info.path, 1, 1, call_back_msg)
            return UpCode(code=code, id=fid, path=up_info.path)


    def _check_up_file_exist(self, up_info: UpInfo) -> UpInfo:
        """检查文件是否已经存在"""
        if not up_info.force:
            files_info, _ = self.get_file_list(up_info.fid)
            for file_info in files_info:
                if up_info.name == file_info.name and up_info.size == file_info.size:
                    logger.debug(f"Check file exist: {up_info.path} already exist! {file_info.id}")
                    up_info = up_info._replace(id=file_info.id, exist=True)
                    break
        return up_info

    def upload_file(self, file_path, folder_id=-11, force=False, callback=None) -> UpCode:
        """单个文件上传接口
        :param str file_path: 待上传文件路径
        :param int folder_id: 上传目录 id
        :param bool force: 强制上传已经存在的文件(文件名、大小一致的文件)
        :param func callback: 上传进度回调
        :return: UpCode
        """
        if not os.path.isfile(file_path):
            logger.error(f"Upload file: [{file_path}] is not a file!")
            return UpCode(code=Cloud189.PATH_ERROR, path=file_path)

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)  # Byte
        up_info = self._check_up_file_exist(UpInfo(name=file_name, path=file_path, size=file_size,
                                                   fid=str(folder_id), force=force, callback=callback))
        if not force and up_info.exist:
            logger.debug(f"Abandon upload because the file is already exist: {file_path=}")
            if up_info.callback:
                up_info.callback(up_info.path, 1, 1, 'exist')
            return UpCode(code=Cloud189.SUCCESS, id=up_info.id, path=file_path)
        elif self._sessionKey and self._sessionSecret and self._accessToken:
            logger.debug(f"Use the client interface to upload files: {file_path=}, {folder_id=}")
            return self._upload_file_by_client(up_info)
        else:
            logger.debug(f"Use the web interface to upload files: {file_path=}, {folder_id=}")
            return self._upload_file_by_web(up_info)

    def upload_dir(self, folder_path, parrent_fid=-11, force=False, mkdir=True, callback=None,
                   failed_callback=None, up_handler= None):
        """文件夹上传接口
        :param str file_path: 待上传文件路径
        :param int folder_id: 上传目录 id
        :param bool force: 强制上传已经存在的文件(文件名、大小一致的文件)
        :param bool mkdir: 是否在 parrent_fid 创建父文件夹
        :param func callback: 上传进度回调
        :param func failed_callback: 错误回调
        :param func up_handler: 上传文件数回调
        :return: UpCode list  or  Cloud189 error code(mkdir error)
        """
        if not os.path.isdir(folder_path):
            logger.error(f"Upload dir: [{folder_path}] is not a file")
            return UpCode(Cloud189.PATH_ERROR)

        dir_dict = {}
        logger.debug(f'Upload dir: start parsing {folder_path=} structure...')
        upload_files = []
        folder_name = get_file_name(folder_path)
        if mkdir:
            result = self.mkdir(parrent_fid, folder_name)
            if result.code != Cloud189.SUCCESS:
                return result  # MkCode

            dir_dict[folder_name] = result.id
        else:
            dir_dict[folder_name] = parrent_fid

        for home, dirs, files in os.walk(folder_path):
            for _file in files:
                f_path = home + os.sep + _file
                f_rfolder = get_relative_folder(f_path, folder_path)
                logger.debug(f"Upload dir: {f_rfolder=}, {f_path=}, {folder_path=}")
                if f_rfolder not in dir_dict:
                    dir_dict[f_rfolder] = ''
                upload_files.append((f_path, dir_dict[f_rfolder]))
            for _dir in dirs:
                p_rfolder = get_relative_folder(
                    home, folder_path, is_file=False)
                logger.debug(f"Upload dir: {p_rfolder=}, {home=}, {folder_path=}")
                dir_rname = p_rfolder + os.sep + _dir  # 文件夹相对路径

                result = self.mkdir(dir_dict[p_rfolder], _dir)
                if result.code != Cloud189.SUCCESS:
                    logger.error(
                        f"Upload dir: create a folder in the upload sub folder{dir_rname=} failed! {folder_name=}, {dir_dict[p_rfolder]=}")
                    return result  # MkCode
                logger.debug(
                    f"Upload dir: folder successfully created {folder_name=}, {dir_dict[p_rfolder]=}, {dir_rname=}, {result.id}")
                dir_dict[dir_rname] = result.id
        up_codes = []
        total_files = len(upload_files)
        for index, upload_file in enumerate(upload_files, start=1):
            if up_handler:
                up_handler(index, total_files)
            logger.debug(f"Upload dir: file [{upload_file[0]}] enter upload process...")
            up_code = self.upload_file(upload_file[0], upload_file[1], force=force, callback=callback)
            if failed_callback and up_code.code != Cloud189.SUCCESS:
                failed_callback(up_code.code, up_code.path)
                logger.debug(f"Up Dir Code: {up_code.code=}, {up_code.path=}")
            up_codes.append(up_code)
            logger.debug(f"Dir: {index=}, {total_files=}")
        return up_codes

    def get_file_info_by_id(self, fid) -> (int, FileInfo):
        '''获取文件(夹) 详细信息'''
        url = self._host_url + "/v2/getFileInfo.action"
        resp = self._get(url, params={'fileId': fid})
        if resp:
            resp = resp.json()
        else:
            return Cloud189.NETWORK_ERROR, FileInfo()
        # createAccount     # createTime
        # fileId            # fileIdDigest
        # fileName          # fileSize
        # fileType          # isFolder
        # lastOpTime        # parentId
        # subFileCount
        name = resp['fileName']
        id_ = int(resp['fileId'])
        pid = int(resp['parentId'])
        ctime = resp['createTime']
        optime = resp['lastOpTime']
        size = resp['fileSize']
        ftype = resp['fileType']
        isFolder = resp['isFolder']
        account = resp['createAccount']
        durl = resp['downloadUrl'] if 'downloadUrl' in resp else ''
        count = resp['subFileCount'] if 'subFileCount' in resp else ''
        return Cloud189.SUCCESS, FileInfo(name=name, id=id_, pid=pid, ctime=ctime, optime=optime,
                                          size=size, ftype=ftype, isFolder=isFolder, account=account,
                                          durl=durl, count=count)

    def _down_one_link(self, durl, save_path, callback=None) -> int:
        """下载器"""
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        os.environ['LANG'] = 'enUS.UTF-8'
        resp = self._get(durl, stream=True, timeout=None)
        if not resp:
            logger.error("Download link: network error!")
            return Cloud189.FAILED

        content_d = resp.headers['content-disposition'].encode('latin-1').decode('utf-8')
        file_name = re.search(r'filename="(.+)"', content_d)
        file_name = file_name.group(1) if file_name else ''
        if not file_name:
            logger.error("Download link: cannot get file name!")
            return Cloud189.FAILED

        file_path = save_path + os.sep + file_name
        total_size = resp.headers.get('content-length')
        if total_size:
            total_size = int(total_size)
        else:  # no content length in headers
            total_size = -1

        now_size = 0
        if os.path.exists(file_path) and total_size != -1:
            now_size = os.path.getsize(file_path)  # 本地已经下载的文件大小
            if now_size >= total_size:  # 已经下载完成
                if callback is not None:
                    callback(file_name, total_size, now_size, 'exist')
                logger.debug(f"Download link: the file already exists in the local {file_name=} {durl=}")
                return Cloud189.SUCCESS
            else:  # 断点续传
                headers = {**self._headers, 'Range': 'bytes=%d-' % now_size}
                resp = self._get(durl, stream=True, headers=headers, timeout=None)
                if not resp:
                    return Cloud189.FAILED

        logger.debug(f'Download link: {file_path=}, {now_size=}, {total_size=}')
        chunk_size = get_chunk_size(total_size)
        with open(file_path, "ab") as f:
            for chunk in resp.iter_content(chunk_size):
                if chunk:
                    f.write(chunk)
                    f.flush()
                    now_size += len(chunk)
                    if callback:
                        callback(file_name, total_size, now_size)
        if total_size == -1 and callback:
            callback(file_name, now_size, now_size)
        logger.debug(f"Download link: finished {total_size=}, {now_size=}")
        return Cloud189.SUCCESS

    def down_file_by_id(self, fid, save_path='./Download', callback=None) -> int:
        """通过 fid 下载单个文件"""
        code, infos = self.get_file_info_by_id(fid)
        if code != Cloud189.SUCCESS:
            logger.error(f"Down by id: 获取文件{fid=}详情失败！")
            return code
        durl = 'https:' + infos.durl
        return self._down_one_link(durl, save_path, callback)

    def down_dirzip_by_id(self, fid, save_path='./Download', callback=None) -> int:
        """打包下载文件夹"""
        url = self._host_url + '/downloadMultiFiles.action'
        params = {
            'fileIdS': fid,
            'downloadType': 1,
            'recursive': 1
        }
        resp = self._get(url, params=params, allow_redirects=False)
        if resp.status_code == requests.codes['found']:  # 302
            durl = resp.headers.get("Location")
        else:
            logger.debug(f"Down folder failed: {resp.status_code}")
            return Cloud189.FAILED

        return self._down_one_link(durl, save_path, callback)

    def delete_by_id(self, fid):
        '''删除文件(夹)'''
        code, infos = self.get_file_info_by_id(fid)
        if code != Cloud189.SUCCESS:
            logger.error(f"Delete by id: get file's {fid=} details failed!")
            return code

        return self._batch_task(infos, 'DELETE')

    def move_file(self, info, target_id):
        '''移动文件(夹)'''
        return self._batch_task(info, 'MOVE', str(target_id))

    def cpoy_file(self, tasks, fid):
        '''复制文件(夹)'''
        code, infos = self.get_file_info_by_id(fid)
        if code != Cloud189.SUCCESS:
            logger.error(f"Copy by id: get file's {fid=} details failed!")
            return code

        return self._batch_task(infos, 'COPY')

    def mkdir(self, parent_id, fname):
        '''新建文件夹, 如果存在该文件夹，会返回存在的文件夹 id'''
        url = self._host_url + '/v2/createFolder.action'
        result = self._get(
            url, params={'parentId': str(parent_id), 'fileName': fname})
        if not result:
            logger.error("Mkdir: network error!")
            return MkCode(Cloud189.NETWORK_ERROR)
        result = result.json()
        if 'fileId' in result:
            return MkCode(Cloud189.SUCCESS, result['fileId'])
        else:
            logger.error(f"Mkdir: unknown error {result=}")
            return MkCode(Cloud189.MKDIR_ERROR)

    def rename(self, fid, fname):
        ''''重命名文件(夹)'''
        url = self._host_url + '/v2/renameFile.action'
        resp = self._get(url, params={'fileId': str(fid), 'fileName': fname})
        if not resp:
            logger.error("Rename: network error!")
            return Cloud189.NETWORK_ERROR
        resp = resp.json()
        if 'success' in resp:
            return Cloud189.SUCCESS
        logger.error(f"Rename:  unknown error {resp=}, {fid=}, {fname=}")
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
            params = {'pageNum': 1, 'pageSize': 500}  # 应该没有大于 500 个文件夹的吧？
            resp = self._post(url, params=params, data=post_data)
            if not resp:
                return
            for folder in resp.json():
                name = folder['name']
                id_ = int(folder['id'])
                pid = int(folder['pId']) if 'pId' in folder else ''
                isParent = folder['isParent']  # str
                tree.append(FolderTree(name=name, id=id_, pid=pid,
                                       isParent=isParent), repeat=False)
                logger.debug(
                    f"Sub Folder: {name=}, {id_=}, {pid=}, {isParent=}")
                if deep < max_deep:
                    _get_sub_folder(id_, deep + 1)

        _get_sub_folder(fid, deep)
        logger.debug(f"Sub Folder Tree len: {len(tree)}")
        return tree

    def list_shared_url(self, stype: int, page: int = 1) -> FileList:
        """列出自己的分享文件、转存的文件链接
        :param stype:  1 发出的分享，2 收到的分享
        :param page:   页面，60 条记录一页
        :return:        FileList 类
        """
        get_url = self._host_url + "/v2/listShares.action"
        data = []
        while True:
            params = {"shareType": stype, "pageNum": page, "pageSize": 60}
            resp = self._get(get_url, params=params)
            if not resp:
                logger.error("List shared: network error!")
                return None
            resp = resp.json()
            data_, done = self._get_more_page(resp)
            data.extend(data_)
            if done:
                break
            page += 1
            sleep(0.5)  # 大量请求可能会被限制
        results = FileList()
        for item in data:
            name = item['fileName']
            id_ = item['fileId']
            ctime = item['shareTime']
            size = item['fileSize']
            ftype = item['fileType']
            isFolder = item['isFolder']
            pwd = item['accessCode']
            copyC = item['accessCount']['copyCount']
            downC = item['accessCount']['downloadCount']
            prevC = item['accessCount']['previewCount']
            url = item['accessURL']
            durl = item['downloadUrl']
            path = item['filePath']
            need_pwd = item['needAccessCode']
            s_type = item['shareType']
            s_mode = item['shareMode']
            r_stat = item['reviewStatus']

            results.append(ShareInfo(name=name, id=id_, ctime=ctime, size=size, ftype=ftype,
                                     isFolder=isFolder, pwd=pwd, copyC=copyC, downC=downC, prevC=prevC,
                                     url=url, durl=durl, path=path, need_pwd=need_pwd, s_type=s_type,
                                     s_mode=s_mode, r_stat=r_stat))

        return results

    def get_share_folder_info(self, share_id, verify_code, pwd='undefined'):
        """获取分享的文件夹信息"""
        result = []
        page = 1
        info_url = self._host_url + '/v2/listShareDir.action'
        while True:
            params = {
                'shareId': share_id,
                'verifyCode': verify_code,
                'accessCode': pwd or 'undefined',
                'orderBy': 1,
                'order': 'ASC',
                'pageNum': page,
                'pageSize': 60
            }
            resp = requests.get(info_url, params=params, headers=self._headers, verify=False)
            if not resp:
                return None
            resp = resp.json()
            if 'errorVO' in resp:
                print("是文件夹，并且需要密码或者密码错误！")
                logger.debug("Access password is required!")
                return None
            for item in resp['data']:
                durl = 'https:' + item['downloadUrl'] if 'downloadUrl' in item else ''
                print('#', item['fileId'], '文件名', item['fileName'], item['fileSize'], durl)
            if resp['recordCount'] <= resp['pageSize'] * resp['pageNum']:
                break

            page += 1
        print(f"共 {resp['recordCount']} 条记录")
        return result

    def get_share_file_info(self, share_id, pwd=''):
        """获取分享的文件信息"""
        verify_url = self._host_url + "/shareFileVerifyPass.action"
        params = {
            'fileVO.id': share_id,
            'accessCode': pwd
        }
        resp = requests.get(verify_url, params=params, verify=False)
        if not resp:
            return None
        resp = resp.json()
        if not resp:
            print("是文件，并且需要密码或者密码错误！")
            return None
        f_id = resp['fileId']
        f_name = resp['fileName']
        f_size = resp['fileSize']
        f_type = resp['fileType']
        durl = resp['longDownloadUrl']

        print(f_id, f_name, f_size, f_type, durl)

    def get_file_info_by_url(self, share_url, pwd=''):
        """通过分享链接获取信息"""

        first_page = requests.get(share_url, headers=self._headers, verify=False)
        if not first_page:
            logger.error("File info: network error!")
            return None
        first_page = first_page.text
        # 抱歉，您访问的页面地址有误，或者该页面不存在
        if '您访问的页面地址有误' in first_page:
            logger.debug(f"The sharing link has been cancelled {share_url}")
            return None
        if 'window.fileName' in first_page:  # 文件
            share_id = re.search(r'class="shareId" value="(\w+?)"', first_page).group(1)
            # 没有密码，则直接暴露 durl
            durl = re.search(r'class="downloadUrl" value="(\w+?)"', first_page)
            if durl:
                durl = durl.group(1)
                print('直链：', durl)
                return None
            is_file = True
        else:  # 文件夹
            share_id = re.search(r"_shareId = '(\w+?)';", first_page).group(1)
            verify_code = re.search(r"_verifyCode = '(\w+?)';", first_page).group(1)
            is_file = False

        if is_file:
            return self.get_share_file_info(share_id, pwd)
        else:
            return self.get_share_folder_info(share_id, verify_code, pwd)

    def user_sign(self):
        """签到 + 抽奖"""
        sign_url = API + '//mkt/userSign.action'
        headers = {
            'SessionKey': self._sessionKey
        }
        resp = requests.get(sign_url, headers=headers, verify=False)
        if not resp:
            logger.error("Sign: network error!")
        if resp.status_code != requests.codes.ok:
            print(f"签到失败 {resp=}, {headers=}")
        else:
            msg = re.search(r'获得.+?空间', resp.text)
            msg = msg.group() if msg else ""
            print(f"签到成功！{msg}。每天签到可领取更多福利哟，记得常来！")

        url = 'https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action'
        params = {
            'taskId': 'TASK_SIGNIN',
            'activityId': 'ACT_SIGNIN'
        }
        for i in range(1, 3):
            resp = self._get(url, params=params)
            if not resp:
                logger.error("Sign: network error!")
            resp = resp.json()
            if 'errorCode' in resp:
                print(f"今日抽奖({i})次数已用完： {resp['errorCode']}")
            else:
                print(f"今日抽奖({i})次：{resp['prizeName']}")
            params.update({'taskId': 'TASK_SIGNIN_PHOTOS'})

    def get_user_infos(self):
        """获取登录用户信息"""
        url = self._host_url + "/v2/getLoginedInfos.action"
        resp = self._get(url)
        if not resp:
            logger.error("Get user info: network error!")
            return None
        resp = resp.json()
        id_ = resp['userId']
        account = resp['userAccount']
        nickname = resp['nickname'] if 'nickname' in resp else ''
        used = resp['usedSize']
        quota = resp['quota']
        vip = resp['superVip'] if 'superVip' in resp else ''
        endTime = resp['superEndTime'] if 'superEndTime' in resp else ''
        beginTime = resp['superBeginTime'] if 'superBeginTime' in resp else ''
        domain = resp['domainName'] if 'domainName' in resp else ''
        return UserInfo(id=id_, account=account, nickname=nickname, used=used, quota=quota,
                        vip=vip, endTime=endTime, beginTime=beginTime, domain=domain)
