import json
import time
from uuid import uuid4
from configparser import ConfigParser
from starlette.responses import StreamingResponse
from fastapi import FastAPI
import uvicorn
from threading import Lock

from utils.token import TokenManager
from db import DatabaseManager
from network.chat import getAnswerData
from utils.models import UsageChunk, Usage, ChatCompletionRequest, ChatCompletionChunk, ChatMessage, Choices

conf = ConfigParser()
conf.read('config.ini')
listenIP = conf['API']['ListenIP']
listenPort = int(conf['API']['Port'])
context = conf['API']['Context']
tokenCount = int(conf['API']['TokenCount'])
app = FastAPI(title="MUChat API")
tokenManager = TokenManager(tokenCount)
lock = Lock()
previousContent = {}

START_THINKING_STRING = {"id": "", "object": "", "created": 0, "model": "", "choices": [{"delta": {"role": "assistant", "content": "<think>\n"}, "index": 0, "finish_reason": None}]}
END_THINKING_STRING = {"id": "", "object": "", "created": 0, "model": "", "choices": [{"delta": {"role": "assistant", "content": "\n</think>\n"}, "index": 0, "finish_reason": None}]}

def updateContext(id, response, contextType):
    if contextType == "internal":
        with lock:
            previousContent[response] = id
    elif contextType == "external":
        with DatabaseManager() as dbManager:
            dbManager.updateDbContext(id, response)

def getChatId(content, contextType):
    if contextType == "internal":
    # remove previous chat content
        with lock:
            return previousContent.pop(content, None)
    elif contextType == "external":
        with DatabaseManager() as dbManager:
            id = dbManager.getDbChatId(content)
        return id
    
def parseLine(line: dict, uuid: str, createTime: str, model: str, adjustReasoningContent: bool = False):
    line['id'] = uuid
    line['object'] = "chat.completion.chunk"
    line['created'] = createTime
    line['model'] = model
    if adjustReasoningContent:
        line['choices'][0]['delta']['content'] = line['choices'][0]['delta'].pop("reasoning_content")
    return line

def adjustContent(question: str, injectChatId: str, contextType: str, reasoning: bool):
    reasoningStart = False
    contentStart = False
    uuid = str(uuid4())
    timeStamp = int(time.time())
    model = "deepseek-r1-minda" if reasoning else "deepseek-v3-minda"
    chatId, rawData = getAnswerData(tokenManager.getAccessToken(), question, reasoning, injectChatId)
    for line in rawData:
        if line == "[DONE]":
            responseStats = json.loads(next(rawData))
            if contextType in ("internal", "external"):
                previousResponse = responseStats[4]['historyPreview'][-1]['value'].strip()
                updateContext(chatId, previousResponse, contextType)
            usageChunk = UsageChunk(
                id = uuid,
                created = timeStamp,
                model = model,
                usage = Usage(
                    prompt_tokens = responseStats[4]['inputTokens'],
                    completion_tokens = responseStats[4]['outputTokens'],
                    total_tokens = responseStats[4]['tokens'],
                    streaming_time = responseStats[4]['runningTime']
                )
            )
            yield f"data: {usageChunk.model_dump_json()}\n\n"
            break
        line = json.loads(line)
        if line.get("id") is None:
            continue
        if reasoning:
            if line['choices'][0]['delta'].get("reasoning_content") is not None:
                if not reasoningStart:
                    startThinking = parseLine(START_THINKING_STRING, uuid, timeStamp, model)
                    yield f"data: {json.dumps(startThinking)}\n\n" # need TWO newline characters
                    reasoningStart = True
                line = parseLine(line, uuid, timeStamp, model, True)
                yield f"data: {json.dumps(line)}\n\n"
            elif line['choices'][0]['delta'].get('content') == "":
                    continue
            else:
                if not contentStart:
                    endThinking = parseLine(END_THINKING_STRING, uuid, timeStamp, model)
                    yield f"data: {json.dumps(endThinking)}\n\n"
                    contentStart = True
                line = parseLine(line, uuid, timeStamp, model)
                yield f"data: {json.dumps(line)}\n\n"
        else:
            line = parseLine(line, uuid, timeStamp, model)
            yield f"data: {json.dumps(line)}\n\n"   

def adjustNonStreamContent(question: str, reasoning: bool):
    uuid = str(uuid4())
    timeStamp = int(time.time())
    model = "deepseek-r1-minda" if reasoning else "deepseek-v3-minda"
    _, rawData = getAnswerData(tokenManager.getAccessToken(), question, reasoning)
    for line in rawData:
        if line == "[DONE]":
            responseStats = json.loads(next(rawData))
            chatCompletion = ChatCompletionChunk(
                id = uuid,
                created = timeStamp,
                model = model,
                choices = [Choices(
                    message = ChatMessage(
                        role = "assistant",
                        content = responseStats[4]['historyPreview'][-1]['value'].strip()
                    )
                )],
                usage=Usage(
                    prompt_tokens=responseStats[4]['inputTokens'],
                    completion_tokens=responseStats[4]['outputTokens'],
                    total_tokens=responseStats[4]['tokens'],
                    streaming_time=responseStats[4]['runningTime']
                )
            )

            return chatCompletion

@app.post("/v1/chat/completions")
def chatCompletion(request: ChatCompletionRequest):
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