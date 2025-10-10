import requests
from bs4 import BeautifulSoup
import json

HEADER = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-encoding': 'gzip, deflate, br, zstd',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
}

def getCookie(username: str, password: str):
    url = "https://ca.muc.edu.cn/zfca/login?service=https://so.muc.edu.cn/ai_service/auth-center/account/mucCasLogin"
    def getExecution():
        pageResponse = requests.get(url)
        soup = BeautifulSoup(pageResponse.text, 'html.parser')
        inputTag = soup.find('input', {'name': 'execution'})
        executionValue = inputTag.get('value')
        return executionValue

    cookie = {
        '_7da9a': 'http://10.0.1.13:8080'
    }
    payload = {
        'username': username,
        'password': password,
        'submit': '登录',
        'type': 'username_password',
        'execution': getExecution(),
        '_eventId': 'submit'
    }
    loginResponse = requests.post(url, headers=HEADER, cookies=cookie, data=payload, allow_redirects=False)
    return loginResponse.headers

def getAuthorization(ticketLocation: str):
    url = "https://so.muc.edu.cn/ai_service/auth-center/account/mucCasLogin?clientid=aih5_100040;MUCShow;state;"
    def getSession(ticketLocation):
        response = requests.get(ticketLocation, headers=HEADER, allow_redirects=False)
        return response.headers
    
    getSessionString = getSession(ticketLocation)
    setCookieString = getSessionString.get('Set-Cookie')
    sessionCookie = setCookieString.split(';')[0]
    cookie = {
        sessionCookie.split('=')[0]: sessionCookie.split("=")[1]
    }
    response = requests.get(url, headers=HEADER, cookies=cookie, allow_redirects=False)
    return response.headers

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
