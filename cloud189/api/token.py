"""
模拟客户端登录，获取 token，用于秒传检查
"""

import re
import requests

from cloud189.api.utils import rsa_encode, calculate_md5_sign, API, get_time, UA, logger
from cloud189.api import Cloud189


def get_token_pre_params():
    """登录前参数准备"""
    url = 'https://cloud.189.cn/unifyLoginForPC.action'
    params = {
        'appId': 8025431004,
        'clientType': 10020,
        'returnURL': 'https://m.cloud.189.cn/zhuanti/2020/loginErrorPc/index.html',
        'timeStamp': get_time(stamp=True)
    }
    resp = requests.get(url, params=params)
    if not resp:
        return Cloud189.NETWORK_ERROR, None

    param_id = re.search(r'paramId = "(\S+)"', resp.text, re.M)
    req_id = re.search(r'reqId = "(\S+)"', resp.text, re.M)
    return_url = re.search(r"returnUrl = '(\S+)'", resp.text, re.M)
    captcha_token = re.search(r"captchaToken' value='(\S+)'", resp.text, re.M)
    j_rsakey = re.search(r'j_rsaKey" value="(\S+)"', resp.text, re.M)
    lt = re.search(r'lt = "(\S+)"', resp.text, re.M)

    param_id = param_id.group(1) if param_id else ''
    req_id = req_id.group(1) if req_id else ''
    return_url = return_url.group(1) if return_url else ''
    captcha_token = captcha_token.group(1) if captcha_token else ''
    j_rsakey = j_rsakey.group(1) if j_rsakey else ''
    lt = lt.group(1) if lt else ''

    return Cloud189.SUCCESS, (param_id, req_id, return_url, captcha_token, j_rsakey, lt)


def get_token(username, password):
    """获取token"""
    code, result = get_token_pre_params()
    if code != Cloud189.SUCCESS:
        return code, None

    param_id, req_id, return_url, captcha_token, j_rsakey, lt = result

    username = rsa_encode(j_rsakey, username)
    password = rsa_encode(j_rsakey, password)
    url = "https://open.e.189.cn/api/logbox/oauth2/loginSubmit.do"
    headers = {
        "User-Agent": UA,
        "Referer": "https://open.e.189.cn/api/logbox/oauth2/unifyAccountLogin.do",
        "Cookie": f"LT={lt}",
        "X-Requested-With": "XMLHttpRequest",
        "REQID": req_id,
        "lt": lt
    }
    data = {
        "appKey": "8025431004",
        "accountType": "02",
        "userName": f"{{RSA}}{username}",
        "password": f"{{RSA}}{password}",
        "validateCode": "",
        "captchaToken": captcha_token,
        "returnUrl": return_url,
        "mailSuffix": "@189.cn",
        "dynamicCheck": "FALSE",
        "clientType": 10020,
        "cb_SaveName": 1,
        "isOauth2": 'false',
        "state": "",
        "paramId": param_id
    }
    resp = requests.post(url, data=data, headers=headers, timeout=10)
    if not resp:
        return Cloud189.NETWORK_ERROR, None
    resp = resp.json()
    if 'toUrl' in resp:
        redirect_url = resp['toUrl']
    else:
        redirect_url = ''
    logger.debug(f"Token: {resp=}")
    url = API + '/getSessionForPC.action'
    headers = {
        "User-Agent": UA,
        "Accept": "application/json;charset=UTF-8"
    }
    params = {
        'clientType': 'TELEMAC',
        'version': '1.0.0',
        'channelId': 'web_cloud.189.cn',
        'redirectURL': redirect_url
    }
    resp = requests.get(url, params=params, headers=headers, timeout=10)
    if not resp:
        return Cloud189.NETWORK_ERROR, None

    sessionKey = resp.json()['sessionKey']
    sessionSecret = resp.json()['sessionSecret']
    accessToken = resp.json()['accessToken']  # 需要再验证一次？

    url = API + '/open/oauth2/getAccessTokenBySsKey.action'
    timestamp = get_time(stamp=True)
    params = f'AppKey=601102120&Timestamp={timestamp}&sessionKey={sessionKey}'
    headers = {
        "AppKey": '601102120',
        'Signature': calculate_md5_sign(params),
        "Sign-Type": "1",
        "Accept": "application/json",
        'Timestamp': timestamp,
    }
    resp = requests.get(url, params={'sessionKey': sessionKey}, headers=headers, timeout=10)
    if not resp:
        return Cloud189.NETWORK_ERROR
    accessToken = resp.json()['accessToken']

    return Cloud189.SUCCESS, (sessionKey, sessionSecret, accessToken)
