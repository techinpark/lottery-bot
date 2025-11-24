import os
import auth
import traceback
import time
from typing import List, Optional
from selenium.webdriver.remote.webelement import WebElement

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import requests
import json
import random

class Recharge:
    def __init__(self, *, wait_timeout_seconds: Optional[int] = None, headless: Optional[bool] = None):
        """
        초기 설정을 구성합니다.

        - wait_timeout_seconds: WebDriverWait 타임아웃을 설정합니다. 미지정 시 환경변수 WAIT_TIMEOUT_SECONDS(기본 10)를 사용합니다.
        - headless: 헤드리스 모드 여부. 미지정 시 환경변수 HEADLESS(기본 true)를 사용합니다.
        """
        self._wait_timeout_seconds = (
            int(wait_timeout_seconds)
            if wait_timeout_seconds is not None
            else int(os.environ.get("WAIT_TIMEOUT_SECONDS", "10") or 10)
        )
        if headless is None:
            headless_env = os.environ.get("HEADLESS", "true").lower()
            self._headless = headless_env not in ("0", "false", "no")
        else:
            self._headless = bool(headless)

    def _create_driver(self) -> webdriver.Chrome:
        """Chrome WebDriver를 생성하고 공통 옵션을 적용합니다."""
        chrome_options = Options()
        if self._headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        return webdriver.Chrome(options=chrome_options)

    def _extract_jsession_from_auth(self, auth_ctrl: auth.AuthController) -> str:
        """AuthController에서 발급받은 JSESSIONID를 헤더에서 추출합니다."""
        headers_with_cookie = auth_ctrl.add_auth_cred_to_headers({})
        cookie_header = headers_with_cookie.get("Cookie", "")
        jsession_id = ""
        if "JSESSIONID=" in cookie_header:
            jsession_id = cookie_header.split("JSESSIONID=", 1)[1]
        return jsession_id.strip()

    def _inject_cookies(self, driver: webdriver.Chrome, jsession_id: str) -> None:
        """동일 도메인으로 진입 후 JSESSIONID 및 선택 쿠키(WMONID, userId)를 주입합니다."""
        driver.get("https://dhlottery.co.kr/")
        driver.add_cookie({
            "name": "JSESSIONID",
            "value": jsession_id,
            "domain": "dhlottery.co.kr",
            "path": "/",
        })

        # 선택적 쿠키: 환경 변수로 주어졌을 때만 주입
        wmonid = os.environ.get("WMONID", "").strip()
        if wmonid:
            driver.add_cookie({
                "name": "WMONID",
                "value": wmonid,
                "domain": "dhlottery.co.kr",
                "path": "/",
            })
        user_id_cookie = os.environ.get("USERID_COOKIE_VALUE", "").strip()
        if user_id_cookie:
            driver.add_cookie({
                "name": "userId",
                "value": user_id_cookie,
                "domain": "dhlottery.co.kr",
                "path": "/",
            })

    def _select_amount(self, wait: WebDriverWait, amount: int) -> None:
        """
        허용된 금액 중 유효한 값을 선택 요소에 반영합니다.

        허용 범위를 벗어나면 기본값 10000원을 선택합니다.
        """
        allowed_values = {"5000", "10000", "20000", "30000", "50000", "100000", "150000"}
        desired_value = str(amount)
        if desired_value not in allowed_values:
            desired_value = "10000"
        select_el = wait.until(EC.presence_of_element_located((By.ID, "EcAmt")))
        Select(select_el).select_by_value(desired_value)

    def _click_payment_button(self, wait: WebDriverWait) -> None:
        """결제 버튼을 클릭합니다. CSS 우선, 실패 시 XPATH 폴백을 사용합니다."""
        try:
            btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btn2 > button")))
            btn.click()
        except TimeoutException:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='btn2']/button")))
            btn.click()

    def _switch_to_ecaccount_popup(self, driver: webdriver.Chrome) -> None:
        """URL에 ecAccount.do가 포함된 팝업으로 전환합니다. 없으면 현재 창 유지."""
        target_substr = "dhlottery.co.kr/ecAccount.do"
        start_ts = time.time()
        target_handle = None
        while time.time() - start_ts < 10:
            handles = driver.window_handles
            if not handles:
                time.sleep(0.2)
                continue
            for h in handles:
                try:
                    driver.switch_to.window(h)
                    current_url = driver.current_url or ""
                    if target_substr in current_url:
                        target_handle = h
                        break
                except Exception:
                    continue
            if target_handle:
                break
            time.sleep(0.2)

        if target_handle:
            driver.switch_to.window(target_handle)
            print(f"[Recharge] Switched to target popup: {driver.current_url}")
        else:
            print("[Recharge] Target popup (ecAccount.do) not found; staying in current window")

    def _infer_keypad_layout_via_openrouter(self, layout_img_src: str) -> Optional[List[int]]:
        """
        키패드 프롬프트 이미지를 기반으로 0~9의 배열 순서를 OpenRouter로부터 추론합니다.

        실패(네트워크/HTTP/파싱/스키마) 시 None을 반환합니다.
        """
        print(f"[Recharge] Inferring keypad layout via OpenRouter: {layout_img_src}")
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        # 하드코딩된 모델 목록 (필요 시 이 배열만 수정하세요)
        models: List[str] = [
            "x-ai/grok-4.1-fast",
            "x-ai/grok-4.1-fast:free",
            "google/gemma-3-27b-it:free",
            "google/gemini-2.0-flash-exp:free",
            # "nvidia/nemotron-nano-12b-v2-vl:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
            "mistralai/mistral-small-3.2-24b-instruct:free",
            # "qwen/qwen2.5-vl-32b-instruct:free",
            "google/gemma-3-4b-it:free",
            "google/gemma-3-12b-it:free",
        ]

        if not api_key:
            print("[Recharge] OPENROUTER_API_KEY not set; skipping keypad layout inference")
            return None

        timeout_seconds = int(os.environ.get("OPENROUTER_TIMEOUT", "15") or 15)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        # 모델 목록을 무작위로 섞은 뒤 순차 시도
        models_to_try = list(models)
        random.shuffle(models_to_try)

        for model_name in models_to_try:
            print(f"[Recharge] Trying OpenRouter model: {model_name}")
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "You are an expert at image-based data extraction. \
Analyze the given image, which contains a blue keypad with numbers and buttons labeled in Korean. \
The image always shows two identical keypads side by side, each containing digits (0-9) randomly placed in a 3x4 grid. \
The bottom row includes Korean text “전체삭제” (which means \"clear all\") and a backspace icon — ignore these elements completely. \
Your task: \
1. Focus only on the left keypad. \
2. Identify and extract only the 10 digits (0-9) visible inside the left keypad area. \
3. Read the digits in the left keypad in row-major order (left to right, top to bottom). \
4. Return the result as a numeric array containing exactly 10 numbers. \
Example output: { \"keypad_layout\": [6, 7, 8, 3, 9, 5, 4, 1, 0, 2] } \
Output only the numeric array, nothing else — no explanations or text."},
                            {"type": "image_url", "image_url": {"url": layout_img_src}},
                        ],
                    }
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "keypad",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "keypad_layout": {
                                    "type": "array",
                                    "description": "A layout of a keypad with a length of 10 with one number from 0 to 9.",
                                    "items": {"type": "number", "description": "keypad number"},
                                }
                            },
                            "required": ["keypad_layout"],
                            "additionalProperties": False,
                        },
                    },
                },
            }

            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=timeout_seconds,
                )
            except Exception as e:
                print(f"[Recharge] OpenRouter request failed (model={model_name}): {e}")
                continue

            if not getattr(response, "status_code", 0) or response.status_code >= 400:
                status_code = getattr(response, "status_code", "?")
                reason = getattr(response, "reason", "")
                body_text = ""
                try:
                    body_text = response.text or ""
                except Exception:
                    body_text = ""
                err_message = ""
                try:
                    j = response.json()
                    if isinstance(j, dict):
                        if "error" in j:
                            err_val = j["error"]
                            if isinstance(err_val, dict):
                                err_message = str(err_val.get("message") or err_val.get("error") or "")
                            else:
                                err_message = str(err_val)
                        elif "message" in j:
                            err_message = str(j.get("message") or "")
                except Exception:
                    pass
                print(f"[Recharge] OpenRouter HTTP error (model={model_name}): status={status_code} reason={reason} message={err_message} body={body_text[:500]}")
                continue

            try:
                json_data = response.json()
                print("[Recharge] OpenRouter response (formatted):")
                print(json.dumps(json_data, ensure_ascii=False, indent=2))

                content_text = json_data["choices"][0]["message"]["content"]
                content_json = json.loads(content_text)
                # keypad_layout_data = content_json["keypad_layout"] or content_json
                keypad_layout_data = content_json if isinstance(content_json, list) else content_json["keypad_layout"]
            except Exception as e:
                print(f"[Recharge] OpenRouter response parsing failed (model={model_name}): {e}")
                continue

            # 아래 정규화/검증 로직은 성공 시에만 반환하며, 실패 시 다음 모델로 시도합니다.
            if len(keypad_layout_data) == 20:
                keypad_layout: List[int] = []
                seen = set()
                for x in keypad_layout_data:
                    if x not in seen:
                        keypad_layout.append(x)
                        seen.add(x)
            elif len(keypad_layout_data) == 9:
                keypad_layout = list(keypad_layout_data)
                missing = None
                for num in range(10):
                    if num not in keypad_layout_data:
                        missing = num
                        break
                if missing is not None:
                    keypad_layout.append(missing)
            elif len(keypad_layout_data) == 18:
                keypad_layout = []
                seen = set()
                for x in keypad_layout_data:
                    if x not in seen:
                        keypad_layout.append(x)
                        seen.add(x)
                missing = None
                for num in range(10):
                    if num not in keypad_layout_data:
                        missing = num
                        break
                if missing is not None:
                    keypad_layout.append(missing)
            elif len(keypad_layout_data) == 10:
                keypad_layout = list(keypad_layout_data)
            else:
                print(f"[Recharge] Keypad layout data length is not 9, 10, 18 or 20: {len(keypad_layout_data)} (model={model_name})")
                continue

            if len(keypad_layout) != 10:
                continue
            if any(type(x) != int for x in keypad_layout):
                continue
            if set(keypad_layout) != set(range(10)):
                continue
            return keypad_layout

        print("[Recharge] All models failed to produce a valid keypad layout")
        return None

    def _find_keypad_element(self, wait: WebDriverWait) -> WebElement:
        """키패드 루트 요소를 탐색합니다. 우선 id, 실패 시 일반 클래스 선택자로 재시도."""
        try:
            return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#nppfs-keypad-ecpassword")))
        except Exception:
            return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.nppfs-keypad")))

    def _extract_layout_image_src(self, keypad: WebElement) -> str:
        """키패드 내 레이아웃 가이드 이미지의 src URL을 추출합니다."""
        key_layout_img = keypad.find_element(By.CSS_SELECTOR, "img.kpd-image-button")
        return key_layout_img.get_attribute("src") or ""

    def _parse_coords(self, el: WebElement) -> tuple:
        """키 이미지의 data-coords(y/x)를 파싱해 정렬 키로 사용합니다. 실패 시 큰 값 반환."""
        try:
            c = (el.get_attribute("data-coords") or "0,0,0,0").split(",")
            x1, y1 = int(c[0]), int(c[1])
            return (y1, x1)
        except Exception:
            return (9999, 9999)

    def _get_sorted_key_images(self, keypad: WebElement) -> List[WebElement]:
        """키패드의 키 이미지 목록을 좌표 기준으로 정렬하여 반환합니다."""
        key_imgs = keypad.find_elements(By.CSS_SELECTOR, "img.kpd-data[data-action^='data:'][data-coords]")
        print(f"[Recharge] Found {len(key_imgs)} key images")
        return sorted(key_imgs, key=self._parse_coords)

    def _click_password_sequence(self, wait: WebDriverWait, key_imgs_sorted: List[WebElement], keypad_layout: List[int], account_password: str) -> None:
        """키패드 레이아웃과 계좌 비밀번호를 이용해 숫자 키를 순서대로 클릭합니다."""
        for num in list(account_password):
            # keypad_layout에서 password의 숫자 index 찾기
            index = keypad_layout.index(int(num))
            # 찾은 index로 key_imgs_sorted에서 해당 요소 찾기
            el = key_imgs_sorted[index]
            coords = el.get_attribute("data-coords") or "?"
            action = el.get_attribute("data-action") or "?"
            try:
                wait.until(EC.element_to_be_clickable(el))
                el.click()
            except Exception as _e:
                print(f"[Recharge] Keypad click failed index={num} coords={coords} action={action}: {_e}")
                traceback.print_exc()
            time.sleep(1)

    def recharge(self, jsession_id: str, amount: int) -> dict:
        """
        예치금 충전 시도를 수행합니다.

        매개변수:
          - jsession_id: 로그인 이후 확보한 JSESSIONID 값
          - amount: 충전 금액 (예: 10000)

        반환:
          - {"status": "success", "amount": amount} 성공 시도
          - {"status": "error", "error": "..."} 에러 발생 시
        """
        assert type(amount) == int and amount > 0

        account_password = os.environ.get("ACCOUNT_PASSWORD", "")

        if not account_password:
            print("[Recharge] Missing environment: ACCOUNT_PASSWORD")
            return {
                "status": "error",
                "error": "Missing ACCOUNT_PASSWORD in environment",
            }

        driver = None
        try:
            try:
                driver = self._create_driver()
            except Exception as e:
                print(f"[Recharge] Failed to initialize ChromeDriver: {e}")
                traceback.print_exc()
                return {"status": "error", "error": f"driver_init: {e}"}

            wait = WebDriverWait(driver, self._wait_timeout_seconds)
            
            # 쿠키 주입 (하드코드 제거, 환경 변수 기반)
            try:
                self._inject_cookies(driver, jsession_id)
            except Exception as e:
                print(f"[Recharge] Failed to add cookie: {e}")
                traceback.print_exc()
                return {"status": "error", "error": f"add_cookie: {e}"}
            
            # 충전 페이지로 이동
            driver.get("https://dhlottery.co.kr/payment.do?method=payment")

            # 충전 금액 선택 (외부 입력값, 기본 10000원)
            try:
                self._select_amount(wait, amount)
            except Exception as e:
                print(f"[Recharge] Failed to select amount: {e}")
                traceback.print_exc()

            # 충전 팝업 열기
            # 결제 버튼 클릭: CSS 우선, 실패 시 XPath 폴백
            self._click_payment_button(wait)

            # # 새 창(팝업)으로 전환: 특정 URL(https://dhlottery.co.kr/ecAccount.do)로만 전환
            try:
                self._switch_to_ecaccount_popup(driver)
            except TimeoutException:
                print("[Recharge] Popup window not detected; continuing in current window")
                pass

            # 직접 클릭: 키패드 찾기 → 레이아웃 이미지 추출 → 키패드 배열 추론 → 키 이미지 정렬 → 비밀번호 클릭
            try:
                keypad = self._find_keypad_element(wait)
                layout_img_src = self._extract_layout_image_src(keypad)
                keypad_layout = self._infer_keypad_layout_via_openrouter(layout_img_src)
                if keypad_layout is None:
                    print("[Recharge] Skipping keypad clicking due to missing or invalid keypad layout")
                    return {"status": "error", "error": "missing or invalid keypad layout"}
                key_imgs_sorted = self._get_sorted_key_images(keypad)
                self._click_password_sequence(wait, key_imgs_sorted, keypad_layout, account_password)
            except Exception as e:
                print(f"[Recharge] Keypad clicking failed: {e}")
                traceback.print_exc()

            # 알럿 텍스트 가져오기
            alert_text = None
            alert = wait.until(EC.alert_is_present())
            alert_text = alert.text
            try:
                alert.accept()
            except Exception:
                pass
            
            if alert_text is None:
                return {"status": "error", "error": "no alert detected"}
            
            # 출금계좌의 잔액이 부족합니다.\n(케이뱅크 고객센터 1522-1000)
            # 간편충전 비밀번호를\n정확하게 입력해 주세요.\n(1회 입력 실패)
            # 예치금 충전이 완료되었습니다.
            if "예치금 충전이 완료되었습니다." in alert_text:
                return {"status": "success", "amount": amount}
            else:
                return {"status": "error", "error": alert_text}
        except Exception as e:
            print(f"[Recharge] Exception during recharge flow: {e}")
            traceback.print_exc()
            return {"status": "error", "error": str(e)}
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    print(f"[Recharge] Failed to quit driver: {e}")
                    traceback.print_exc()