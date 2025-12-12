from loguru import logger
from time import time
from threading import Thread, Lock, Event
import jwt

from network.login import getToken

class TokenManager:
    def __init__(self, tokenCount = 1):
        self._lock = Lock()
        self.tokenCount = tokenCount
        self._refreshing = [False] * tokenCount
        self._refreshed_evt = [Event() for _ in range(tokenCount)]
        for e in self._refreshed_evt:
            e.set()
        self.tokenList = []
        self._rr_index = 0
        self._startMultiThread()

    def _acquireAccessToken(self):
        accessToken = getToken()
        return {
                "token": accessToken,
                "createTime": int(time())
            }
    
    def _tokenThread(self):
        token = self._acquireAccessToken()
        with self._lock:
            self.tokenList.append(token)

    def _startMultiThread(self):
        threads = []
        for _ in range(self.tokenCount):
            t = Thread(target = self._tokenThread)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    def _refreshToken(self, currentIndex: int, sync: bool):
        def do_refresh():
            try:
                new_data = self._acquireAccessToken()
                with self._lock:
                    self.tokenList[currentIndex] = new_data
            finally:
                with self._lock:
                    self._refreshing[currentIndex] = False
                    self._refreshed_evt[currentIndex].set()

        with self._lock:
            if not self._refreshing[currentIndex]:
                self._refreshing[currentIndex] = True
                self._refreshed_evt[currentIndex].clear()
                leader = True
            else:
                leader = False
                evt = self._refreshed_evt[currentIndex]

        if not leader:
            # wait until finished under sync mode, otherwise just return
            if sync:
                evt.wait()
            return
        else: # only let leading request actually do refresh procedure
            if sync:
                do_refresh()
            else:
                Thread(target=do_refresh, daemon=True).start()

    def getAccessToken(self):
        # round-robin
        with self._lock:
            currentIndex = self._rr_index
            token = self.tokenList[currentIndex]['token']
            # createTime = self.tokenList[currentIndex]['createTime']
            self._rr_index = (self._rr_index + 1) % len(self.tokenList)
        # verify exp in jwt token 
        tokenStatus = jwt.decode(token, options = {"verify_signature": False, "verify_exp": False})
        expireTime = tokenStatus['exp'] - int(time())
        if expireTime >= 3600:
            logger.info(f"Token {currentIndex} valid, {expireTime}s from expiring.")
            return token
        elif expireTime > 0:
            logger.info(f"Token {currentIndex} will expire in 1 hour, refreshing in background...")
            self._refreshToken(currentIndex, False)
            return token
        else:
            logger.info(f"Token {currentIndex} expired, refreshing...")
            self._refreshToken(currentIndex, True)
            with self._lock:
                return self.tokenList[currentIndex]["token"]