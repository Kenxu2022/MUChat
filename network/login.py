import requests
from bs4 import BeautifulSoup
import json
from gmssl import sm2
import base64
from configparser import ConfigParser
from urllib.parse import urlparse, parse_qs

HEADER = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
}

conf = ConfigParser()
conf.read("config.ini")
USERNAME = conf['Login']['Username']
PASSWORD = conf['Login']['Password']

def getTicket():
    '''
    return location URL and TGT (Ticket Granting Ticket)
    '''
    url = "https://ca.muc.edu.cn/zfca/login?service=https://so.muc.edu.cn/ai_service/auth-center/account/mucCasLogin?clientid=aipc_100050;MUCShow;ZXlKMWNtd2lPaUpvZEhSd2N6b3ZMM052TG0xMVl5NWxaSFV1WTI0dllXbHhZUzhqTDJ4dloybHVJbjA9"

    def getMiscInfo() -> list[str, str, str]: # get flowId and sm2 public key
        response = requests.get(url = url, headers = HEADER)
        cookie = response.cookies.get_dict()
        content = response.text
        # get sessionID
        sessionID = cookie.get('JSESSIONID')
        # get flowID
        soup = BeautifulSoup(content, 'html.parser')
        flowId = soup.find("input", attrs={"name": "flowId"}).get('value')
        # get sm2 public key
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                for line in script.string.splitlines():
                    if line.strip().startswith("var ssoConfig ="):
                        ssoConfig = json.loads(line.strip().split("var ssoConfig =")[1].strip()[:-1])
                        sm2PublicKey = ssoConfig['sm2']['publicKey']
        return sessionID, flowId, sm2PublicKey

    def getEncryptedPassword(password: str, publicKey: str) -> str: # encrypt password using sm2
        bytePublicKey = base64.b64decode(publicKey)
        hexPublicKey = bytePublicKey[1:].hex() # remove leading 0x04, then convert to hex
        sm2Crypt = sm2.CryptSM2(public_key = hexPublicKey, private_key = None, mode = 1)
        byteEncryptedPassword = sm2Crypt.encrypt(password.encode())
        encryptedPassword = base64.b64encode(byteEncryptedPassword).decode()
        return encryptedPassword

    sessionID, flowId, sm2PublicKey = getMiscInfo()
    encryptedPassword = getEncryptedPassword(PASSWORD, sm2PublicKey)

    payload = {
        'username': USERNAME,
        'password': encryptedPassword,
        'submit': '登录',
        'loginType': 'username_password',
        'flowId': flowId
    }
    response = requests.post(url, headers = HEADER, data = payload, allow_redirects = False)
    location = response.headers.get('Location')
    tgt = response.cookies.get('SSO_TGC')
    return location, tgt

def getSession():
    location, tgt = getTicket()
    cookie = {
        'SSO_TGC': tgt
    }
    response = requests.get(url = location, headers = HEADER, cookies = cookie, allow_redirects = False)
    location = response.headers.get('Location')
    session = response.cookies.get('SESSION')
    return location, session, tgt

def getToken():
    location, session, tgt = getSession()
    cookie = {
        'SSO_TGC': tgt,
        'SESSION': session
    }
    response = requests.get(url = location, headers = HEADER, cookies = cookie, allow_redirects = False)
    location = response.headers.get('Location')
    urlParams = parse_qs(urlparse(location).fragment)
    accessToken = urlParams.get('/accessLogin?access_token')[0]
    return accessToken

def checkToken(token: str):
    header = {
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Authorization': f'Bearer {token}',
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/json',
        'Pragma': 'no-cache',
        'Proxy-Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
    }
    cookie = {
        'Authorization': f'Bearer {token}'
    }
    url = "https://so.muc.edu.cn/ai_service/search-server//agent-reminder-record/query-unread-count"
    response = requests.get(url, headers=header, cookies=cookie)
    data = json.loads(response.text)
    loginStatus = data.get('code')
    if loginStatus == "0000":
        return True
    else:
        return False
