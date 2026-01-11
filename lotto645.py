import datetime
import json
import requests

from datetime import timedelta
from enum import Enum

from bs4 import BeautifulSoup as BS

import auth
import common
import logging
from HttpClient import HttpClientSingleton

logger = logging.getLogger(__name__)

class Lotto645Mode(Enum):
    AUTO = 1
    MANUAL = 2
    BUY = 10 
    CHECK = 20

class Lotto645:

    _REQ_HEADERS = {
        "User-Agent": auth.USER_AGENT,
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
        "Origin": "https://ol.dhlottery.co.kr",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Referer": "https://ol.dhlottery.co.kr/olotto/game/game645.do",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Accept-Language": "ko,en-US;q=0.9,en;q=0.8,ko-KR;q=0.7",
    }

    def __init__(self):
        self.http_client = HttpClientSingleton.get_instance()

    def buy_lotto645(
        self, 
        auth_ctrl: auth.AuthController, 
        cnt: int, 
        mode: Lotto645Mode
    ) -> dict:
        assert isinstance(auth_ctrl, auth.AuthController)
        assert isinstance(cnt, int) and 1 <= cnt <= 5
        assert isinstance(mode, Lotto645Mode)

        headers = self._generate_req_headers(auth_ctrl)
        
        requirements = self._getRequirements(headers)
        
        data = (
            self._generate_body_for_auto_mode(cnt, requirements)
            if mode == Lotto645Mode.AUTO
            else self._generate_body_for_manual(cnt)
        )

        body = self._try_buying(headers, data)

        self._show_result(body)
        return body

    def _generate_req_headers(self, auth_ctrl: auth.AuthController) -> dict:
        assert isinstance(auth_ctrl, auth.AuthController)
        return auth_ctrl.add_auth_cred_to_headers(self._REQ_HEADERS)

    def _generate_body_for_auto_mode(self, cnt: int, requirements: list) -> dict:
        assert isinstance(cnt, int) and 1 <= cnt <= 5

        return {
            "round": requirements[3],
            "direct": requirements[0], 
            "nBuyAmount": str(1000 * cnt),
            "param": json.dumps(
                [
                    {"genType": "0", "arrGameChoiceNum": None, "alpabet": slot}
                    for slot in common.SLOTS[:cnt]
                ]
            ),
            'ROUND_DRAW_DATE' : requirements[1],
            'WAMT_PAY_TLMT_END_DT' : requirements[2],
            "gameCnt": cnt,
            "saleMdaDcd": "10"
        }

    def _generate_body_for_manual(self, cnt: int) -> dict:
        assert isinstance(cnt, int) and 1 <= cnt <= 5
        raise NotImplementedError()

    def _getRequirements(self, headers: dict) -> list:
        headers["Referer"] = "https://ol.dhlottery.co.kr/olotto/game/game645.do"
        headers["Origin"] = "https://ol.dhlottery.co.kr"
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["Sec-Fetch-Mode"] = "cors"
        headers["Sec-Fetch-Dest"] = "empty"

        res = self.http_client.post(
            url="https://ol.dhlottery.co.kr/olotto/game/egovUserReadySocket.json", 
            headers=headers
        )
        
        direct = json.loads(res.text)["ready_ip"]
        
        html_headers = self._REQ_HEADERS.copy()
        html_headers.pop("Origin", None)
        html_headers.pop("Content-Type", None)
        html_headers["Referer"] = "https://dhlottery.co.kr/common.do?method=main"
        
        if headers.get("Cookie"):
            html_headers["Cookie"] = headers.get("Cookie")
            
        res = self.http_client.get(
            url="https://ol.dhlottery.co.kr/olotto/game/game645.do", 
            headers=html_headers
        )
        html = res.text
        soup = BS(html, "html5lib")
        
        try:
            draw_date_el = soup.find("input", id="ROUND_DRAW_DATE")
            tlmt_date_el = soup.find("input", id="WAMT_PAY_TLMT_END_DT")
            
            if draw_date_el and tlmt_date_el:
                draw_date = draw_date_el.get('value')
                tlmt_date = tlmt_date_el.get('value')
            else:
                raise ValueError("Date inputs not found")
        except (ValueError, AttributeError, TypeError) as e:
            logger.error(f"[Error] Date extraction failed: {e}")
            today = datetime.datetime.today()
            days_ahead = (5 - today.weekday()) % 7
            next_saturday = today + datetime.timedelta(days=days_ahead)
            draw_date = next_saturday.strftime("%Y-%m-%d")
            
            limit_date = next_saturday + datetime.timedelta(days=366)
            tlmt_date = limit_date.strftime("%Y-%m-%d")

        
        cur_round_input = soup.find("input", id="curRound")
        if cur_round_input:
            current_round = cur_round_input.get('value')
        else:
            current_round = self._get_round()

        return [direct, draw_date, tlmt_date, current_round]

    def _get_round(self) -> str:
        try:
            res = self.http_client.get(
                "https://dhlottery.co.kr/common.do?method=main",
                headers=self._REQ_HEADERS
            )
            html = res.text
            soup = BS(html, "html5lib")
            found = soup.find("strong", id="lottoDrwNo")
            if found:
                last_drawn_round = int(found.text)
                return str(last_drawn_round + 1)
            else:
                 raise ValueError("lottoDrwNo not found")
        except Exception as e:
            base_date = datetime.datetime(2024, 12, 28)
            base_round = 1152
            
            today = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
            
            days_ahead = (5 - today.weekday()) % 7
            next_saturday = today + datetime.timedelta(days=days_ahead)
            
            weeks = (next_saturday - base_date).days // 7
            return str(base_round + weeks)




        
    def _try_buying(self, headers: dict, data: dict) -> dict:
        assert isinstance(headers, dict)
        assert isinstance(data, dict)

        headers["Content-Type"]  = "application/x-www-form-urlencoded; charset=UTF-8"

        res = self.http_client.post(
            "https://ol.dhlottery.co.kr/olotto/game/execBuy.do",
            headers=headers,
            data=data,
        )
        if res.encoding == 'ISO-8859-1':
             res.encoding = 'euc-kr'
        
        try:
             return json.loads(res.text)
        except UnicodeDecodeError:
             res.encoding = 'euc-kr' 
             return json.loads(res.text)

    def check_winning(self, auth_ctrl: auth.AuthController) -> dict:
        assert isinstance(auth_ctrl, auth.AuthController)

        headers = self._REQ_HEADERS.copy()
        headers["Referer"] = "https://www.dhlottery.co.kr/mypage/mylotteryledger"
        headers.pop("Content-Type", None)
        headers.pop("Origin", None)

        parameters = common.get_search_date_range()

        try:
            self.http_client.get("https://www.dhlottery.co.kr/common.do?method=main", headers=headers)
        except requests.RequestException as e:
            print(f"[Warning] Warm-up request failed: {e}")

        result_data = {
            "data": "no winning data"
        }

        try:
            api_url = "https://www.dhlottery.co.kr/mypage/selectMyLotteryledger.do"
            params = {
                "srchStrDt": parameters["searchStartDate"],
                "srchEndDt": parameters["searchEndDate"],
                "ltGdsCd": "LO40",
                "pageNum": 1,
                "recordCountPerPage": 10
            }

            res = self.http_client.get(api_url, params=params, headers=headers)
            
            if res.status_code != 200:
                print(f"DEBUG: API Status {res.status_code}")
                pass
            
            try:
                data = res.json()
                data = data.get("data", {})
                if "list" not in data:
                    print("DEBUG_DATA_LIST_MISSING_IN_DATA")
            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                logger.error(f"[Error] API JSON Parse Failed: {e}")
                data = {}

            if not data.get("list"):
                 return {"data": "no winning data (empty list or API fail)"}

            for item in data["list"]:
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
                    "lotto_details": [] 
                }
                
                detail_url = "https://www.dhlottery.co.kr/mypage/lotto645TicketDetail.do"
                detail_params = {
                    "ltGdsCd": item.get("ltGdsCd"),
                    "ltEpsd": item.get("ltEpsd"),
                    "barcd": item.get("gmInfo"),
                    "ntslOrdrNo": item.get("ntslOrdrNo"),
                    "srchStrDt": params["srchStrDt"],
                    "srchEndDt": params["srchEndDt"]
                }
                
                try:
                    res_detail = self.http_client.get(detail_url, params=detail_params, headers=headers)
                    detail_data = res_detail.json()
                    detail_data = detail_data.get("data", detail_data)
                    
                    ticket = detail_data.get("ticket", {})
                    if not ticket and "data" in detail_data:
                         ticket = detail_data["data"].get("ticket", {})
                         
                    game_dtl = ticket.get("game_dtl", [])
                    win_num = ticket.get("win_num", [])
                    
                    lotto_details = []
                    
                    for i, game in enumerate(game_dtl):
                        label = common.SLOTS[i] if i < len(common.SLOTS) else "?"
                        
                        rank = game.get("rank", "0")
                        status = "낙첨" if rank == "0" else f"{rank}등"
                        
                        nums = game.get("num", [])
                        formatted_nums = []
                        for num in nums:
                            if num in win_num:
                                formatted_nums.append(f"✨{num}")
                            else:
                                formatted_nums.append(str(num))
                        
                        lotto_details.append({
                            "label": label,
                            "status": status,
                            "result": formatted_nums
                        })
                    
                    result_data["lotto_details"] = lotto_details

                except (requests.RequestException, json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                    logger.error(f"[Error] Detail parse error (url={detail_url}, params={detail_params}): {e}")
                
                break
 
                            
        except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
            logger.error(f"[Error] Lotto check error: {e}")
        except Exception as e:
            logger.error(f"[Error] Unexpected Lotto check error: {e}")
            raise

        return result_data
    

    def _show_result(self, body: dict) -> None:
        assert isinstance(body, dict)

        if body.get("loginYn") != "Y":
            return

        result = body.get("result", {})
        if result.get("resultMsg", "FAILURE").upper() != "SUCCESS":    
            return
