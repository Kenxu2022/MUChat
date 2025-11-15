import requests

URL = "https://so.muc.edu.cn/ai_service/search-server/needle/chat/completions/stream"

def getAnswerData(accessToken: str, question: str, reasoning: bool, newChatId: str = ""):
    header = {
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Authorization': f'Bearer {accessToken}',
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/json',
        'Pragma': 'no-cache',
        'Proxy-Connection': 'keep-alive',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
    }
    cookie = {
        'Authorization': f'Bearer {accessToken}'
    } 
    payload = {
        'chatId': newChatId,
        'detail': 'true',
        'alias': 'deepseek',
        'question': question,
        'chatQuestionId': '',
        'extendParams': {
            'agentCode': '',
            'reasoning': reasoning,
            'rewriteResult': '{}'
        }
    }

    response = requests.post(URL, headers = header, cookies = cookie, json = payload, stream = True)
    chatId = response.headers['Chat-Question-Id'].split("_")[0]
    def generateLines():
        for line in response.iter_lines():
            line = line.decode('utf-8').strip()
            if line.startswith('data:'):
                dataLine = line[5:]
            elif line.startswith('event:'):
                eventType = line.split(":", 1)[1].strip()
                if eventType == "fastAnswer":
                    yield "Censored by upstream"
                    break
            elif line == "":
                yield dataLine
                if eventType == "flowResponses":
                    break
    # return chatId and generater
    return chatId, generateLines()