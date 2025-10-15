import json
import time
from uuid import uuid4
from configparser import ConfigParser
from typing import List, Optional
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from fastapi import FastAPI
import uvicorn

from utils.token import TokenManager
from db import DatabaseManager
from network.chat import getAnswerData

conf = ConfigParser()
conf.read('config.ini')
listenIP = conf['API']['ListenIP']
listenPort = int(conf['API']['Port'])
context = conf['API']['Context']
app = FastAPI(title="MUChat API")
tokenManager = TokenManager()
previousContent = {}

START_THINKING_STRING = {"id": "", "object": "", "created": 0, "model": "", "choices": [{"delta": {"role": "assistant", "content": "<think>\n"}, "index": 0, "finish_reason": None}]}
END_THINKING_STRING = {"id": "", "object": "", "created": 0, "model": "", "choices": [{"delta": {"role": "assistant", "content": "\n</think>\n"}, "index": 0, "finish_reason": None}]}

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = False

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
            # remove previous chat content
            id = previousContent.pop(content)
            return id
        else:
            return None
    elif contextType == "external":
        with DatabaseManager() as dbManager:
            id = dbManager.getDbChatId(content)
        return id

def adjustContent(question: str, injectChatId: str, contextType: str, reasoning: bool):
    reasoningCount = 0
    contentCount = 0
    uuid = str(uuid4())
    timeStamp = int(time.time())
    model = "deepseek-r1-minda" if reasoning else "deepseek-v3-minda"
    chatId, rawData = getAnswerData(tokenManager.getAccessToken(), question, reasoning, injectChatId)
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
                "model": model,
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
        if reasoning:
            if line['choices'][0]['delta'].get("reasoning_content") is not None:
                if reasoningCount == 0:
                    startThinking = processLine(START_THINKING_STRING, uuid, timeStamp)
                    yield f"data: {json.dumps(startThinking)}\n\n" # need TWO newline characters
                line['choices'][0]['delta']['content'] = line['choices'][0]['delta'].pop("reasoning_content")
                line = processLine(line, uuid, timeStamp)
                yield f"data: {json.dumps(line)}\n\n"
                reasoningCount = reasoningCount + 1
            elif line['choices'][0]['delta'].get('content') == "":
                    continue
            else:
                if contentCount == 0:
                    endThinking = processLine(END_THINKING_STRING, uuid, timeStamp)
                    yield f"data: {json.dumps(endThinking)}\n\n"
                line = processLine(line, uuid, timeStamp)
                yield f"data: {json.dumps(line)}\n\n"
                contentCount = contentCount + 1
        else:
            line = processLine(line, uuid, timeStamp)
            yield f"data: {json.dumps(line)}\n\n"   

def adjustNonStreamContent(question: str, reasoning: bool):
    uuid = str(uuid4())
    timeStamp = int(time.time())
    model = "deepseek-r1-minda" if reasoning else "deepseek-v3-minda"
    _, rawData = getAnswerData(tokenManager.getAccessToken(), question, reasoning)
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
                "model": model,
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
    reasoning = True if request.model == "deepseek-r1-minda" else False
    if request.stream:
        if len(request.messages) > 1 and context in ("internal", "external"):
            previousChatContent = request.messages[-2].content.strip()
            injectChatId = getChatId(previousChatContent, context)
        return StreamingResponse(adjustContent(question, injectChatId, context, reasoning), media_type="application/x-ndjson")
    else:
        return adjustNonStreamContent(question, reasoning)

if __name__ == "__main__":
    uvicorn.run(app, host=listenIP, port=listenPort)