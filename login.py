import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from configparser import ConfigParser

conf = ConfigParser()
conf.read("config.ini")

username = conf['Login']['Username']
password = conf['Login']['Password']
url = "https://ca.muc.edu.cn/zfca/login?service=https://so.muc.edu.cn/ai_service/auth-center/account/mucCasLogin"
header = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-encoding': 'gzip, deflate, br, zstd',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    # 'Content-Type': 'application/x-www-form-urlencoded',
    # 'Origin': 'https://ca.muc.edu.cn',
    # 'Referer': 'https://ca.muc.edu.cn/zfca/login?service=http://so.muc.edu.cn/ai_service/auth-center/account/mucCasLogin?clientid=aih5_100040;MUCShow;state;',
    # 'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
}

def getExecution():
    pageResponse = requests.get(url)
    soup = BeautifulSoup(pageResponse.text, 'html.parser')
    inputTag = soup.find('input', {'name': 'execution'})
    executionValue = inputTag.get('value')
    return executionValue


def login(username, password, execution):
    cookie = {
        '_7da9a': 'http://10.0.1.13:8080'
    }
    payload = {
        'username': username,
        'password': password,
        'submit': '登录',
        'type': 'username_password',
        'execution': execution,
        '_eventId': 'submit'
    }
    loginResponse = requests.post(url, headers=header, cookies=cookie, data=payload, allow_redirects=False)
    return loginResponse.headers

def getSession(locationUrl):
    response = requests.get(locationUrl, headers=header, allow_redirects=False)
    return response.headers

def getAuthorization(sessionCookie):
    url = "https://so.muc.edu.cn/ai_service/auth-center/account/mucCasLogin?clientid=aih5_100040;MUCShow;state;"
    cookie = {
        sessionCookie.split('=')[0]: sessionCookie.split("=")[1]
    }
    # print(cookie)
    response = requests.get(url, headers=header, cookies=cookie, allow_redirects=False)
    return response.headers

def getAccessToken():
    while True:
        execToken = getExecution()
        loginHeader = login(username, password, execToken)
        # print(execToken)
        # print(loginHeader)
        ticketLocation = loginHeader.get('Location')
        setCookie = loginHeader.get('Set-Cookie')
        if setCookie is not None and "CASTGC" in setCookie:
            # print(ticketLocation)
            # print(setCookie)
            break
        else:
            print("Failed, retrying...")

    print("Complete login")

    getSessionString = getSession(ticketLocation)
    # print(getSessionString)
    setCookieString = getSessionString.get('Set-Cookie')
    sessionCookie = setCookieString.split(';')[0]
    # print(sessionCookie)
    authorizationString = getAuthorization(sessionCookie)
    # print(authorizationString)
    locationString = authorizationString.get('Location')
    # print(locationString)
    accessToken = parse_qs(urlparse(locationString).fragment).get('/accessLogin?access_token')[0]
    # print(accessToken)
    return accessToken