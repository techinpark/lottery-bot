import json
import datetime
import base64
import requests

from enum import Enum
from bs4 import BeautifulSoup as BS
from datetime import timedelta
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA256
from Crypto.Random import get_random_bytes

from HttpClient import HttpClientSingleton

import auth
import common
import re

class Win720:

    keySize = 128
    iterationCount = 1000
    BlockSize = 16
    keyCode = ""

    _pad = lambda self, s: s + (self.BlockSize - len(s) % self.BlockSize) * chr(self.BlockSize - len(s) % self.BlockSize)
    _unpad = lambda self, s : s[:-ord(s[len(s)-1:])]

    _REQ_HEADERS = {
        "User-Agent": auth.USER_AGENT,
        "Connection": "keep-alive",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "Origin": "https://el.dhlottery.co.kr",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Referer": "https://el.dhlottery.co.kr/game/pension720/game.jsp",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "sec-ch-ua-platform": "\"Windows\"",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "ko,ko-KR;q=0.9,en-US;q=0.8,en;q=0.7",
        "X-Requested-With": "XMLHttpRequest"
    }

    def __init__(self):
        self.http_client = HttpClientSingleton.get_instance()

    def buy_Win720(
        self, 
        auth_ctrl: auth.AuthController,
        username: str
    ) -> dict:
        assert isinstance(auth_ctrl, auth.AuthController)

        headers = self._generate_req_headers(auth_ctrl)
        
        requirements = self._getRequirements(headers)

        jsessionid = auth_ctrl.get_current_session_id()
        
        self.keyCode = jsessionid
        win720_round = self._get_round()
        
        makeAutoNum_ret = self._makeAutoNumbers(auth_ctrl, win720_round)
        
        try:
            q_val = json.loads(makeAutoNum_ret)['q']
        except json.JSONDecodeError:
            raise ValueError(f"Failed to parse makeAutoNum response: {makeAutoNum_ret[:100]}...")
        except Exception as e:
            raise e
            
        try:
            decrypted = self._decText(q_val)
        except Exception as e:
            raise e
        
        if "resultMsg" in decrypted and ":" in decrypted:
             decrypted = re.sub(r'("resultMsg":\s*)([^",}]*)([,}])', r'\1"\2"\3', decrypted)

        parsed_ret = decrypted
        try:
           extracted_num = json.loads(parsed_ret).get("selLotNo", "")
        except ValueError:
             raise ValueError(f"Failed to parse decrypted parsed_ret: {repr(parsed_ret)[:500]}... (Key: {self.keyCode[:5]}...{self.keyCode[-5:] if len(self.keyCode)>5 else ''})")

        if not extracted_num:
             return json.loads(parsed_ret)

        orderNo, orderDate = self._doOrderRequest(auth_ctrl, win720_round, extracted_num)
        
        body = json.loads(self._doConnPro(auth_ctrl, win720_round, extracted_num, username, orderNo, orderDate))

        self._show_result(body)
        body['round'] = win720_round
        return body

    def _generate_req_headers(self, auth_ctrl: auth.AuthController) -> dict:
        assert isinstance(auth_ctrl, auth.AuthController)
        return auth_ctrl.add_auth_cred_to_headers(self._REQ_HEADERS)
    
    def _getRequirements(self, headers: dict) -> list:
        org_headers = headers.copy()
        
        headers["Referer"] = "https://el.dhlottery.co.kr/game/pension720/game.jsp"
        headers["Content-Type"] = "application/json" 
        headers["X-Requested-With"] = "XMLHttpRequest"

        try:
             res = self.http_client.post(
                url="https://el.dhlottery.co.kr/olotto/game/egovUserReadySocket.json", 
                headers=headers
            )
             direct = json.loads(res.text)["ready_ip"]
        except:
             pass
        
        return []

    def _get_round(self) -> str:
        try:
            res = self.http_client.get(
                "https://dhlottery.co.kr/common.do?method=main",
                headers=self._REQ_HEADERS
            )
            html = res.text
            soup = BS(html, "html5lib")
            found = soup.find("strong", id="drwNo720")
            if found:
                return str(int(found.text) - 1)
            else:
                raise ValueError("drwNo720 not found")
        except:
             base_date = datetime.datetime(2024, 12, 26)
             base_round = 244
             
             today = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
             
             days_ahead = (3 - today.weekday()) % 7
             next_thursday = today + datetime.timedelta(days=days_ahead)
             
             weeks = (next_thursday - base_date).days // 7
             
             return str(base_round + weeks - 1)

    def _makeAutoNumbers(self, auth_ctrl: auth.AuthController, win720_round: str) -> str:
        payload = "ROUND={}&round={}&LT_EPSD={}&SEL_NO=&BUY_CNT=&AUTO_SEL_SET=SA&SEL_CLASS=&BUY_TYPE=A&ACCS_TYPE=01".format(win720_round, win720_round, win720_round)
        headers = self._generate_req_headers(auth_ctrl)
        
        data = {
            "q": requests.utils.quote(self._encText(payload))
        }

        res = self.http_client.post(
            url="https://el.dhlottery.co.kr/makeAutoNo.do", 
            headers=headers,
            data=data
        )

        return res.text

    def _doOrderRequest(self, auth_ctrl: auth.AuthController, win720_round: str, extracted_num: str) -> str:
        payload = "ROUND={}&round={}&LT_EPSD={}&AUTO_SEL_SET=SA&SEL_CLASS=&SEL_NO={}&BUY_TYPE=M&BUY_CNT=5".format(win720_round, win720_round, win720_round, extracted_num)
        headers = self._generate_req_headers(auth_ctrl)

        data = {
            "q": requests.utils.quote(self._encText(payload))
        }

        res = self.http_client.post(
            url="https://el.dhlottery.co.kr/makeOrderNo.do", 
            headers=headers,
            data=data
        )

        try:
            ret = json.loads(self._decText(json.loads(res.text)['q']))
            return ret['orderNo'], ret['orderDate']
        except ValueError:
             raise ValueError(f"Failed to parse doOrderRequest/decText: {res.text[:100]}...")

    def _doConnPro(self, auth_ctrl: auth.AuthController, win720_round: str, extracted_num: str, username: str, orderNo: str, orderDate: str) -> str:
        payload = "ROUND={}&FLAG=&BUY_KIND=01&BUY_NO={}&BUY_CNT=5&BUY_SET_TYPE=SA%2CSA%2CSA%2CSA%2CSA&BUY_TYPE=A%2CA%2CA%2CA%2CA%2C&CS_TYPE=01&orderNo={}&orderDate={}&TRANSACTION_ID=&WIN_DATE=&USER_ID={}&PAY_TYPE=&resultErrorCode=&resultErrorMsg=&resultOrderNo=&WORKING_FLAG=true&NUM_CHANGE_TYPE=&auto_process=N&set_type=SA&classnum=&selnum=&buytype=M&num1=&num2=&num3=&num4=&num5=&num6=&DSEC=34&CLOSE_DATE=&verifyYN=N&curdeposit=&curpay=5000&DROUND={}&DSEC=0&CLOSE_DATE=&verifyYN=N&lotto720_radio_group=on".format(win720_round,"".join([ "{}{}%2C".format(i,extracted_num) for i in range(1,6)])[:-3],orderNo, orderDate, username, win720_round)
        headers = self._generate_req_headers(auth_ctrl)
        
        data = {
            "q": requests.utils.quote(self._encText(payload))
        }
        
        res = self.http_client.post(
            url="https://el.dhlottery.co.kr/connPro.do", 
            headers=headers,
            data=data
        )

        try:
            ret = self._decText(json.loads(res.text)['q'])
            return ret
        except ValueError:
             raise ValueError(f"Failed to parse doConnPro: {res.text[:100]}...")

    def _encText(self, plainText: str) -> str:
        encSalt = get_random_bytes(32)
        encIV = get_random_bytes(16)
        passPhrase = self.keyCode[:32]
        encKey = PBKDF2(passPhrase, encSalt, self.BlockSize, count=self.iterationCount, hmac_hash_module=SHA256)
        aes = AES.new(encKey, AES.MODE_CBC, encIV)

        plainText = self._pad(plainText).encode('utf-8')

        return "{}{}{}".format(bytes.hex(encSalt), bytes.hex(encIV), base64.b64encode(aes.encrypt(plainText)).decode('utf-8'))

    def _decText(self, encText: str) -> str:

        decSalt = bytes.fromhex(encText[0:64])
        decIv = bytes.fromhex(encText[64:96])
        cryptText = encText[96:]
        passPhrase = self.keyCode[:32]
        decKey = PBKDF2(passPhrase, decSalt, self.BlockSize, count=self.iterationCount, hmac_hash_module=SHA256)

        aes = AES.new(decKey, AES.MODE_CBC, decIv)

        decrypted_bytes = self._unpad(aes.decrypt(base64.b64decode(cryptText)))
        try:
            return decrypted_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return decrypted_bytes.decode('euc-kr')
            except UnicodeDecodeError:
                return f'{{"resultMsg": "Decryption Failed (Raw: {decrypted_bytes.hex()[:20]}...)"}}'




    def check_winning(self, auth_ctrl: auth.AuthController) -> dict:
        assert isinstance(auth_ctrl, auth.AuthController)

        headers = self._generate_req_headers(auth_ctrl)

        parameters = common.get_search_date_range()
        data = {
            "nowPage": 1, 
            "searchStartDate": parameters["searchStartDate"],
            "searchEndDate": parameters["searchEndDate"],
            "winGrade": 1,
            "lottoId": "LP72", 
            "sortOrder": "DESC"
        }

        result_data = {
            "data": "no winning data"
        }

        try:
            api_url = "https://www.dhlottery.co.kr/mypage/selectMyLotteryledger.do"
            params = {
                "srchStrDt": parameters["searchStartDate"],
                "srchEndDt": parameters["searchEndDate"],
                "ltGdsCd": "LP72",
                "pageNum": 1,
                "recordCountPerPage": 10
            }
            
            res = self.http_client.get(api_url, params=params, headers=headers)
            
            if res.status_code == 200:
                try:
                    data = res.json()
                    data = data.get("data", {})
                    
                    if data.get("list"):
                        item = data["list"][0]
                        
                        purchased_date = item.get("eltOrdrDt", "-")
                        round_no = item.get("ltEpsdView", "")
                        money = item.get("ltWnAmt", "-")
                        
                        if "회" in round_no:
                            round_no = round_no.replace("회", "")
                        
                        if money == "0" or money == 0:
                             money = "0 원"
                        else:
                            money = f"{int(money):,} 원" 
                            
                        result_data = {
                            "round": round_no,
                            "money": money,
                            "purchased_date": purchased_date,
                            "winning_date": item.get("epsdRflDt", "-"),
                            "win720_details": []
                        }
                        
                        try:
                            detail_url = "https://www.dhlottery.co.kr/mypage/lottery720select.do"
                            detail_params = {
                                "ntslOrdrNo": item.get("ntslOrdrNo")
                            }
                            
                            res_detail = self.http_client.get(detail_url, params=detail_params, headers=headers)
                            detail_data = res_detail.json()
                            
                            detail_data = detail_data.get("data", detail_data)
                            
                            win720_details = []
                            
                            if "list" in detail_data:
                                for i, d_item in enumerate(detail_data["list"]):
                                    label = common.SLOTS[i] if i < len(common.SLOTS) else "?"
                                    
                                    info_cn = d_item.get("ltGmInfoCn", "")
                                    
                                    rank = d_item.get("wnRnk")
                                    if rank is None:
                                        rank = 0
                                    else:
                                        try:
                                            rank = int(rank)
                                        except:
                                            rank = 0
                                            
                                    status = "0등" if rank == 0 else f"{rank}등"
                                    
                                    if ":" in info_cn:
                                        parts = info_cn.split(":")
                                        group = parts[0]
                                        number_str = parts[1]
                                        
                                        hl_count = 0 
                                        hl_group = False
                                        
                                        if rank == 1:
                                            hl_count = 6
                                            hl_group = True
                                        elif rank == 2:
                                            hl_count = 6
                                        elif rank == 3:
                                            hl_count = 5
                                        elif rank == 4:
                                            hl_count = 4
                                        elif rank == 5:
                                            hl_count = 3
                                        elif rank == 6:
                                            hl_count = 2
                                        elif rank == 7:
                                            hl_count = 1
                                        
                                        formatted_chars = []
                                        digits = list(number_str)
                                        L = len(digits)
                                        
                                        for idx, digit in enumerate(digits):
                                            if idx >= (L - hl_count):
                                                formatted_chars.append(f"[{digit}]")
                                            else:
                                                formatted_chars.append(f" {digit} ")
                                        
                                        formatted_num = " ".join(formatted_chars)
                                        
                                        if hl_group:
                                             label = f"{group}조"
                                        else:
                                             label = f"{group}조"
                                        
                                        result_str = formatted_num
                                    else:
                                        label = "?"
                                        result_str = info_cn
                                    
                                    
                                    win720_details.append({
                                        "label": label,
                                        "result": result_str,
                                        "status": status
                                    })
                                    
                            result_data["win720_details"] = win720_details

                        except Exception as e:
                            print(f"[Error] Win720 detail error: {e}")
                            
                except Exception as e:
                     print(f"[Error] Win720 list process error: {e}")
            
        except Exception as e:
            print(f"[Error] Win720 check error: {e}")

        return result_data
    

    def _show_result(self, body: dict) -> None:
        assert isinstance(body, dict)

        if body.get("loginYn") != "Y":
            return

        result = body.get("result", {})
        if result.get("resultMsg", "FAILURE").upper() != "SUCCESS":    
            return