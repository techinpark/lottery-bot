import requests

class HttpClient:
    def __init__(self):
        self.session = requests.Session()

    def __del__(self):
        self.session.close()

    def post(self, url: str, headers: dict = None, data: dict = None) -> requests.Response:
        session_headers = self.session.headers.copy()
        if headers:
            session_headers.update(headers)
        res = self.session.post(url, headers=session_headers, data=data, timeout=10, allow_redirects=True)
        res.raise_for_status()
        return res

    def get(self, url: str, headers: dict = None, params: dict = None) -> requests.Response:
        session_headers = self.session.headers.copy()
        if headers:
            session_headers.update(headers)
        res = self.session.get(url, headers=session_headers, params=params, timeout=10)
        res.raise_for_status()
        return res

class HttpClientSingleton:
    _instance = None

    @staticmethod
    def get_instance():
        if HttpClientSingleton._instance is None:
            HttpClientSingleton._instance = HttpClient()
        return HttpClientSingleton._instance