from configparser import ConfigParser
from urllib.parse import urlparse, parse_qs
from loguru import logger
from time import time
from threading import Thread, Lock

from network.login import getCookie, getAuthorization, checkToken

conf = ConfigParser()
conf.read("config.ini")
username = conf['Login']['Username']
password = conf['Login']['Password']

class TokenManager:
    def __init__(self, tokenCount = 1):
        self._lock = Lock()
        self.tokenCount = tokenCount
        self._refreshing = [False] * tokenCount
        self.tokenList = []
        self._rr_index = 0
        self._startMultiThread()

    def _acquireAccessToken(self):
        while True:
            loginHeader = getCookie(username, password)
            ticketLocation = loginHeader.get('Location')
            setCookie = loginHeader.get('Set-Cookie')
            if setCookie is not None and "CASTGC" in setCookie:
                break
            else:
                logger.warning("Get cookie failed, retrying...")
        logger.info("Get cookie success")

        authorizationString = getAuthorization(ticketLocation)
        locationString = authorizationString.get('Location')
        accessToken = parse_qs(urlparse(locationString).fragment).get('/accessLogin?access_token')[0]
        logger.info("Token generated")
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


    def _refreshToken(self, position):
        """Refresh token synchronously and update state under lock."""
        try:
            with self._lock:
                self.tokenList[position] = self._acquireAccessToken()

            logger.info("Token refreshed in background")
        except Exception as e:
            logger.exception("Background token refresh failed: {}", e)

    def _refreshTokenAsync(self, currentIndex):
        """Start a daemon thread to refresh token if not already refreshing."""
        with self._lock:
            if self._refreshing[currentIndex]:
                return
            self._refreshing[currentIndex] = True

        def _runner(currentIndex):
            try:
                self._refreshToken(currentIndex)
            finally:
                with self._lock:
                    self._refreshing[currentIndex] = False

        Thread(target=_runner, args = (currentIndex,), daemon=True).start()

    def getAccessToken(self):
        # round-robin
        with self._lock:
            token = self.tokenList[self._rr_index]["token"]
            createTime = self.tokenList[self._rr_index]["createTime"]
            currentIndex = self._rr_index
            self._rr_index = (self._rr_index + 1) % len(self.tokenList)
        # check token status every 6 hour
        if int(time()) - createTime <= 21600:
            logger.info(f"Token {currentIndex} valid")
            return token
        # first check if token is valid after 6 hour
        elif checkToken(token):
            logger.info(f"Refreshing token {currentIndex} in background...")
            self._refreshTokenAsync(currentIndex)
            return token
        else:
            logger.info(f"Token {currentIndex} expired, refreshing...")
            data = self._acquireAccessToken()
            self.tokenList[currentIndex] = data
            return data["token"]