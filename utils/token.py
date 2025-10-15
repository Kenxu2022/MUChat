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
    def __init__(self):
        self._lock = Lock()
        self._refreshing = False
        self.token, self.createTime = self._acquireAccessToken()

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
        return accessToken, int(time())

    def _refreshToken(self):
        """Refresh token synchronously and update state under lock."""
        try:
            newToken, newTime = self._acquireAccessToken()
            with self._lock:
                self.token = newToken
                self.createTime = newTime
            logger.info("Token refreshed in background")
        except Exception as e:
            logger.exception("Background token refresh failed: {}", e)

    def _refreshTokenAsync(self):
        """Start a daemon thread to refresh token if not already refreshing."""
        with self._lock:
            if self._refreshing:
                return
            self._refreshing = True

        def _runner():
            try:
                self._refreshToken()
            finally:
                with self._lock:
                    self._refreshing = False

        Thread(target=_runner, daemon=True).start()

    def getAccessToken(self):
        # check token status every 6 hour
        if int(time()) - self.createTime <= 21600:
            logger.info("Token valid")
            return self.token
        # first check if token is valid after 6 hour
        elif checkToken(self.token):
            logger.info("Refreshing token in background...")
            self._refreshTokenAsync()
            return self.token
        else:
            logger.info("Token expired, refreshing...")
            self.token, self.createTime = self._acquireAccessToken()
            return self.token