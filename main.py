import requests
import json
import threading
from queue import Queue

from login import getAccessToken

q = Queue()
URL = "https://so.muc.edu.cn/ai_service/search-server//needle/chat/completions/stream"
chatId = ""
accessToken = getAccessToken()

header = {
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Authorization': f'Bearer {accessToken}',
    'Cache-Control': 'no-cache',
    'Content-Type': 'application/json',
    'Pragma': 'no-cache',
    'Proxy-Connection': 'keep-alive',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    'accept': 'text/event-stream'
}
cookie = {
    'Authorization': f'Bearer {accessToken}'
}


def getAnswerData(header, cookie, question, newChatId = ""):
    payload = {"chatId":newChatId,
           "detail":"true",
           "alias":"deepseek",
           "question":question,
           "chatQuestionId":"",
           "extendParams":{
               "agentCode":"",
               "reasoning":"true",
               "rewriteResult":"{}"
               }
            }
    response = requests.post(URL, headers=header, cookies=cookie, json=payload, stream=True)
    global chatId
    chatId = response.headers['Chat-Question-Id'].split("_")[0]
    for line in response.iter_lines():
        data = {}
        line = line.decode('utf-8').strip()
        if line.startswith('event:'):
            eventType = line.split(":", 1)[1].strip()
        elif line.startswith('data:'):
            eventData = line.split(":", 1)[1].strip()
        elif line == '':
            data["type"] = eventType
            data["content"] = eventData
            q.put(data)
            if eventType == "flowResponses":
                break

def outputContent():
    reasoningCount = 0
    contentCount = 0
    while True:
        dictData = q.get()
        # print(f"==============================Get Data: ==============================\n{dictData}\n============================================================")
        if dictData['type'] == "flowNodeStatus":
            continue
        elif dictData['type'] == "answer":
            allContent = dictData['content']
            if allContent == "[DONE]":
                continue
            content = json.loads(dictData['content'])['choices'][0]['delta']
            # print(content)
            if content.get('content') is None and contentCount == 0:
                if reasoningCount == 0:
                    print("<think>")
                reasoningContent = content['reasoning_content']
                print(reasoningContent, end='', flush=True)
                reasoningCount = reasoningCount + 1
            elif content.get('content') == "":
                continue
            else:
                if contentCount == 0:
                    print("</think>")
                actualContent = content['content']
                if actualContent is None:
                    actualContent = ""
                print(actualContent, end='', flush=True)
                contentCount = contentCount + 1
        elif dictData['type'] == "flowResponses":
            print("\nEnd of Response")
            break
    print(f"Chat ID: {chatId}")

while True:
    question = input("Ask something, type 'quit' to exit: ")
    if question == "quit":
        print("Bye~🥰")
        break
    get = threading.Thread(target=getAnswerData, args=(header, cookie, question, chatId))
    out = threading.Thread(target=outputContent)

    get.start()
    out.start()

    get.join()
    out.join()