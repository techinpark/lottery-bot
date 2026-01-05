import datetime
import json

from datetime import timedelta
from enum import Enum

from bs4 import BeautifulSoup as BS

import auth
from HttpClient import HttpClientSingleton

class Lotto645Mode(Enum):
    AUTO = 1
    MANUAL = 2
    BUY = 10 
    CHECK = 20

class Lotto645:

    _REQ_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
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
        assert type(auth_ctrl) == auth.AuthController
        assert type(cnt) == int and 1 <= cnt <= 5
        assert type(mode) == Lotto645Mode

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
        assert type(auth_ctrl) == auth.AuthController
        return auth_ctrl.add_auth_cred_to_headers(self._REQ_HEADERS)

    def _generate_body_for_auto_mode(self, cnt: int, requirements: list) -> dict:
        assert type(cnt) == int and 1 <= cnt <= 5
        
        SLOTS = ["A", "B", "C", "D", "E"]  

        return {
            "round": requirements[3],
            "direct": requirements[0], 
            "nBuyAmount": str(1000 * cnt),
            "param": json.dumps(
                [
                    {"genType": "0", "arrGameChoiceNum": None, "alpabet": slot}
                    for slot in SLOTS[:cnt]
                ]
            ),
            'ROUND_DRAW_DATE' : requirements[1],
            'WAMT_PAY_TLMT_END_DT' : requirements[2],
            "gameCnt": cnt,
            "saleMdaDcd": "10"
        }

    def _generate_body_for_manual(self, cnt: int) -> dict:
        assert type(cnt) == int and 1 <= cnt <= 5
        raise NotImplementedError()

    def _getRequirements(self, headers: dict) -> list:
        org_headers = headers.copy()
        headers["Referer"] = "https://ol.dhlottery.co.kr/olotto/game/game645.do"
        headers["Origin"] = "https://ol.dhlottery.co.kr"
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["Sec-Fetch-Mode"] = "cors"
        headers["Sec-Fetch-Dest"] = "empty"
        headers["X-Requested-With"] ="XMLHttpRequest"

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
        except Exception as e:
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
        assert type(headers) == dict
        assert type(data) == dict

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
        assert type(auth_ctrl) == auth.AuthController

        headers = self._generate_req_headers(auth_ctrl)

        parameters = self._make_search_date()

        data = {
            "nowPage": 1, 
            "searchStartDate": parameters["searchStartDate"],
            "searchEndDate": parameters["searchEndDate"],
            "winGrade": 2,
            "lottoId": "LO40", 
            "sortOrder": "DESC"
        }

        result_data = {
            "data": "no winning data"
        }

        try:
            res = self.http_client.post(
                "https://dhlottery.co.kr/myPage.do?method=lottoBuyList",
                headers=headers,
                data=data
            )

            html = res.text
            soup = BS(html, "html5lib")

            winnings = soup.find("table", class_="tbl_data tbl_data_col").find_all("tbody")[0].find_all("td")

            get_detail_info = winnings[3].find("a").get("href")

            order_no, barcode, issue_no = get_detail_info.split("'")[1::2]
            url = f"https://dhlottery.co.kr/myPage.do?method=lotto645Detail&orderNo={order_no}&barcode={barcode}&issueNo={issue_no}"

            response = self.http_client.get(url)

            soup = BS(response.text, "html5lib")

            lotto_results = []

            for li in soup.select("div.selected li"):
                label = li.find("strong").find_all("span")[0].text.strip()
                status = li.find("strong").find_all("span")[1].text.strip().replace("낙첨","0등")
                nums = li.select("div.nums > span")

                status = " ".join(status.split())

                formatted_nums = []
                for num in nums:
                    ball = num.find("span", class_="ball_645")
                    if ball:
                        formatted_nums.append(f"✨{ball.text.strip()}")
                    else:
                        formatted_nums.append(num.text.strip())

                lotto_results.append({
                    "label": label,
                    "status": status,
                    "result": formatted_nums
                })

            if len(winnings) == 1:
                return result_data

            result_data = {
                "round": winnings[2].text.strip(),
                "money": winnings[6].text.strip(),
                "purchased_date": winnings[0].text.strip(),
                "winning_date": winnings[7].text.strip(),
                "lotto_details": lotto_results
            }
        except:
            pass

        return result_data
    
    def _make_search_date(self) -> dict:
        today = datetime.datetime.today()
        today_str = today.strftime("%Y%m%d")
        weekago = today - timedelta(days=7)
        weekago_str = weekago.strftime("%Y%m%d")
        return {
            "searchStartDate": weekago_str,
            "searchEndDate": today_str
        }

    def _show_result(self, body: dict) -> None:
        assert type(body) == dict

        if body.get("loginYn") != "Y":
            return

        result = body.get("result", {})
        if result.get("resultMsg", "FAILURE").upper() != "SUCCESS":    
            return
