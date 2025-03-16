from fastapi import FastAPI
import requests
import json
from queue import Queue
from login import getAccessToken

from uuid import uuid4
import time

from typing import List, Optional
from pydantic import BaseModel
from starlette.responses import StreamingResponse
import uvicorn

q = Queue()
app = FastAPI(title="MUChat API")


URL = "http://so.muc.edu.cn/ai_service/search-server//needle/chat/completions/stream"
chatId = ""
previousContent = {}
startThinkingString = {"id": "", "object": "", "created": 0, "model": "", "choices": [{"delta": {"role": "assistant", "content": "<think>\n"}, "index": 0, "finish_reason": None}]}
endThinkingString = {"id": "", "object": "", "created": 0, "model": "", "choices": [{"delta": {"role": "assistant", "content": "\n</think>\n"}, "index": 0, "finish_reason": None}]}


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "minda-sk1-deepseek-r1"
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.1
    stream: Optional[bool] = False

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

def processLine(line, uuid, createTime):
    line['id'] = uuid
    line['object'] = "chat.completion.chunk"
    line['created'] = createTime
    line['model'] = "deepseek-r1-minda"
    return line

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
    response = requests.post(URL, headers=header, cookies=cookie, json=payload, verify=False, stream=True)
    global chatId
    chatId = response.headers['Chat-Question-Id'].split("_")[0]
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

def adjustContent(question, injectChatId):
    reasoningCount = 0
    contentCount = 0
    uuid = str(uuid4())
    timeStamp = int(time.time())
    rawData = getAnswerData(header, cookie, question, injectChatId)
    for line in rawData:
        if line == "[DONE]":
            responseStats = json.loads(next(rawData))
            promptTokens = responseStats[2]['inputTokens']
            completionTokens = responseStats[2]['outputTokens']
            totalTokens = responseStats[2]['tokens']
            streamingTime = responseStats[2]['runningTime']
            # previousRequest = responseStats[2]['historyPreview'][-2]['value']
            previousResponse = responseStats[2]['historyPreview'][-1]['value'].strip()
            # print(previousResponse.md5().hexdigest())
            previousContent[previousResponse] = chatId
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

@app.post("/v1/chat/completions")
async def chatCompletion(request: ChatCompletionRequest):
    injectChatId = ""
    question = request.messages[-1].content
    if len(request.messages) > 1:
        previousChatContent = request.messages[-2].content.strip()
        if previousContent.get(previousChatContent) is not None:
            # remove previous chat content(pop will return its value)
            injectChatId = previousContent.pop(previousChatContent)
            # print(injectChatId)
    return StreamingResponse(adjustContent(question, injectChatId), media_type="application/x-ndjson")

if __name__ == "__main__":
    uvicorn.run(app, host='0.0.0.0', port=8000)