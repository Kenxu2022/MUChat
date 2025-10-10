import requests
import json
from queue import Queue
from utils.token import TokenManager
from db import DatabaseManager

from uuid import uuid4
import time

from configparser import ConfigParser

from typing import List, Optional
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from fastapi import FastAPI
import uvicorn

from v3api import adjustV3Content, adjustV3NonStreamContent

conf = ConfigParser()
conf.read('config.ini')
listenIP = conf['API']['ListenIP']
listenPort = int(conf['API']['Port'])
context = conf['API']['Context']
q = Queue()
app = FastAPI(title="MUChat API")
tokenManager = TokenManager()


URL = "https://so.muc.edu.cn/ai_service/search-server/needle/chat/completions/stream"
previousContent = {}
startThinkingString = {"id": "", "object": "", "created": 0, "model": "", "choices": [{"delta": {"role": "assistant", "content": "<think>\n"}, "index": 0, "finish_reason": None}]}
endThinkingString = {"id": "", "object": "", "created": 0, "model": "", "choices": [{"delta": {"role": "assistant", "content": "\n</think>\n"}, "index": 0, "finish_reason": None}]}


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = False


def getHeaderCookie(token: str):
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
    return header, cookie

def checkLoginStatus(token: str):
    url = "https://so.muc.edu.cn/ai_service/search-server//agent-reminder-record/query-unread-count"
    header, cookie = getHeaderCookie(token)
    response = requests.get(url, headers=header, cookies=cookie)
    data = json.loads(response.text)
    loginStatus = data.get('code')
    if loginStatus == "0000":
        return True
    else:
        return False

def processLine(line, uuid, createTime):
    line['id'] = uuid
    line['object'] = "chat.completion.chunk"
    line['created'] = createTime
    line['model'] = "deepseek-r1-minda"
    return line

def updateContext(id, response, contextType):
    if contextType == "internal":
        previousContent[response] = id
    elif contextType == "external":
        with DatabaseManager() as dbManager:
            dbManager.updateDbContext(id, response)

def getChatId(content, contextType):
    if contextType == "internal":
        if previousContent.get(content) is not None:
            # remove previous chat content(pop will return its value)
            id = previousContent.pop(content)
            return id
        else:
            return None
    elif contextType == "external":
        with DatabaseManager() as dbManager:
            id = dbManager.getDbChatId(content)
        return id

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
    chatId = response.headers['Chat-Question-Id'].split("_")[0]
    def generateLines():
        for line in response.iter_lines():
            line = line.decode('utf-8').strip()
            if line.startswith('data:'):
                dataLine = line[5:]
            elif line.startswith('event:'):
                eventType = line.split(":", 1)[1].strip()
            elif line == "":
                yield dataLine
                if eventType == "flowResponses":
                    break
    # return chatId and generater
    return chatId, generateLines()

def adjustContent(question, injectChatId, contextType):
    reasoningCount = 0
    contentCount = 0
    uuid = str(uuid4())
    timeStamp = int(time.time())
    accessToken = tokenManager.getAccessToken()
    header, cookie = getHeaderCookie(accessToken)
    chatId, rawData = getAnswerData(header, cookie, question, injectChatId)
    for line in rawData:
        if line == "[DONE]":
            responseStats = json.loads(next(rawData))
            promptTokens = responseStats[4]['inputTokens']
            completionTokens = responseStats[4]['outputTokens']
            totalTokens = responseStats[4]['tokens']
            streamingTime = responseStats[4]['runningTime']
            # previousRequest = responseStats[4]['historyPreview'][-2]['value']
            if contextType in ("internal", "external"):
                previousResponse = responseStats[4]['historyPreview'][-1]['value'].strip()
                updateContext(chatId, previousResponse, contextType)
            usageChunk = {
                "id": uuid,
                "object": "chat.completion.chunk",
                "created": timeStamp,
                "model": "deepseek-r1-minda",
                "usage": {
                    "prompt_tokens": promptTokens,
                    "completion_tokens": completionTokens,
                    "total_tokens": totalTokens,
                    "streaming_time": streamingTime
                } 
            }
            # print(previousContent)
            yield f"data: {json.dumps(usageChunk)}\n\n"
            break
        line = json.loads(line)
        if line.get("id") is None:
            continue
        if line['choices'][0]['delta'].get("reasoning_content") is not None:
            if reasoningCount == 0:
                startThinking = processLine(startThinkingString, uuid, timeStamp)
                yield f"data: {json.dumps(startThinking)}\n\n" # need TWO newline characters
            line['choices'][0]['delta']['content'] = line['choices'][0]['delta'].pop("reasoning_content")
            line = processLine(line, uuid, timeStamp)
            yield f"data: {json.dumps(line)}\n\n"
            reasoningCount = reasoningCount + 1
        elif line['choices'][0]['delta'].get('content') == "":
                continue
        else:
            if contentCount == 0:
                endThinking = processLine(endThinkingString, uuid, timeStamp)
                yield f"data: {json.dumps(endThinking)}\n\n"
            line = processLine(line, uuid, timeStamp)
            yield f"data: {json.dumps(line)}\n\n"
            contentCount = contentCount + 1

def adjustNonStreamContent(question):
    uuid = str(uuid4())
    timeStamp = int(time.time())
    accessToken = tokenManager.getAccessToken()
    header, cookie = getHeaderCookie(accessToken)
    _, rawData = getAnswerData(header, cookie, question)
    for line in rawData:
        if line == "[DONE]":
            responseStats = json.loads(next(rawData))
            chatContent = responseStats[4]['historyPreview'][-1]['value'].strip()
            promptTokens = responseStats[4]['inputTokens']
            completionTokens = responseStats[4]['outputTokens']
            totalTokens = responseStats[4]['tokens']
            streamingTime = responseStats[4]['runningTime']
            chatCompletion = {
                "id": uuid,
                "object": "chat.completion",
                "created": timeStamp,
                "model": "deepseek-r1-minda",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": chatContent
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": promptTokens,
                    "completion_tokens": completionTokens,
                    "total_tokens": totalTokens,
                    "response_time": streamingTime
                } 
            }
            return chatCompletion

@app.post("/v1/chat/completions")
async def chatCompletion(request: ChatCompletionRequest):
    injectChatId = ""
    question = request.messages[-1].content
    if request.stream:
        if len(request.messages) > 1 and context in ("internal", "external"):
            previousChatContent = request.messages[-2].content.strip()
            injectChatId = getChatId(previousChatContent, context)
        if request.model == "deepseek-r1-minda":
            return StreamingResponse(adjustContent(question, injectChatId, context), media_type="application/x-ndjson")
        else:
            return StreamingResponse(adjustV3Content(question, injectChatId, context), media_type="application/x-ndjson")
    else:
        if request.model == "deepseek-r1-minda":
            return adjustNonStreamContent(question)
        else:
            return adjustV3NonStreamContent(question)

if __name__ == "__main__":
    uvicorn.run(app, host=listenIP, port=listenPort)