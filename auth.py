import copy
import requests
import json
import base64
import binascii
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from HttpClient import HttpClientSingleton

class AuthController:
    _REQ_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "Upgrade-Insecure-Requests": "1",
        "Origin": "https://dhlottery.co.kr",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Referer": "https://dhlottery.co.kr/",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Accept-Language": "ko,en-US;q=0.9,en;q=0.8,ko-KR;q=0.7",
    }

    _AUTH_CRED = ""

    def __init__(self):
        self.http_client = HttpClientSingleton.get_instance()

    def login(self, user_id: str, password: str):
        assert type(user_id) == str
        assert type(password) == str

        self.http_client.get("https://dhlottery.co.kr/")
        self.http_client.get("https://dhlottery.co.kr/user.do?method=login")

        modulus, exponent = self._get_rsa_key()

        enc_user_id = self._rsa_encrypt(user_id, modulus, exponent)
        enc_password = self._rsa_encrypt(password, modulus, exponent)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://dhlottery.co.kr",
            "Referer": "https://dhlottery.co.kr/user.do?method=login"
        }
        headers.update(self._REQ_HEADERS)
        
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Origin"] = "https://dhlottery.co.kr"
        headers["Referer"] = "https://dhlottery.co.kr/user.do?method=login"
        
        data = {
            "userId": enc_user_id,
            "userPswdEncn": enc_password, 
            "inpUserId": user_id
        }

        self._try_login(headers, data)
        
    def add_auth_cred_to_headers(self, headers: dict) -> str:
        assert type(headers) == dict

        copied_headers = copy.deepcopy(headers)
        return copied_headers

    def _get_default_auth_cred(self):
        res = self.http_client.get(
            "https://dhlottery.co.kr/common.do?method=main"
        )
        return self._get_j_session_id_from_response(res)

    def _get_rsa_key(self):
        headers = copy.deepcopy(self._REQ_HEADERS)
        headers.update({
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://dhlottery.co.kr/user.do?method=login"
        })
        headers.pop("Upgrade-Insecure-Requests", None)

        res = self.http_client.get(
            "https://dhlottery.co.kr/login/selectRsaModulus.do",
            headers=headers
        )
        
        try:
            data = res.json()
        except:
             raise ValueError(f"Failed to parse JSON. St: {res.status_code}")
        
        if "data" in data and "rsaModulus" in data["data"]:
            modulus = data["data"]["rsaModulus"]
            exponent = data["data"]["publicExponent"]
            return modulus, exponent
        
        if "rsaModulus" in data:
            return data["rsaModulus"], data["publicExponent"]
            
        raise KeyError("rsaModulus not found")

    def _rsa_encrypt(self, text, modulus, exponent):
        key_spec = RSA.construct((int(modulus, 16), int(exponent, 16)))
        cipher = PKCS1_v1_5.new(key_spec)
        ciphertext = cipher.encrypt(text.encode('utf-8'))
        return binascii.hexlify(ciphertext).decode('utf-8')

    def _get_j_session_id_from_response(self, res: requests.Response):
        assert type(res) == requests.Response

        for cookie in res.cookies:
            if cookie.name == "JSESSIONID":
                return cookie.value
        
        if self.http_client.session.cookies.get("JSESSIONID"):
             return self.http_client.session.cookies.get("JSESSIONID")
             
        if self.http_client.session.cookies.get("DHJSESSIONID"):
             return self.http_client.session.cookies.get("DHJSESSIONID")

        if self._AUTH_CRED: 
            return self._AUTH_CRED
        
        if self.http_client.session.cookies.get("WMONID"):
            return self.http_client.session.cookies.get("WMONID")

        return ""

    def _generate_req_headers(self, j_session_id: str):
        return copy.deepcopy(self._REQ_HEADERS)

    def _try_login(self, headers: dict, data: dict):
        assert type(headers) == dict
        assert type(data) == dict
        

        res = self.http_client.post(
            "https://dhlottery.co.kr/login/securityLoginCheck.do",
            headers=headers,
            data=data,
        )
        
        new_jsessionid = self._get_j_session_id_from_response(res)
        if new_jsessionid:
             self._update_auth_cred(new_jsessionid)

        return res

    def _update_auth_cred(self, j_session_id: str) -> None:
        assert type(j_session_id) == str
        self._AUTH_CRED = j_session_id
