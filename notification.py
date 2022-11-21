import requests

                    
class Notification: 

    def send_buying_message(self, body: dict, webhook_url: str) -> None:
        assert type(webhook_url) == str

        result = body.get("result", {})
        if result.get("resultMsg", "FAILURE").upper() != "SUCCESS":  
            return

        message = f"{result['buyRound']}회 로또 구매 완료 :moneybag:\n\n ```{result['arrGameChoiceNum']}```"
        self._send_slack_webhook(webhook_url, message)

    def send_winning_message(self, winning: dict, webhook_url: str) -> None: 
        assert type(winning) == dict
        assert type(webhook_url) == str

        message = f"*{winning['round']}회* - *{winning['money']}* 당첨 되었습니다 :tada:"
        self._send_slack_webhook(webhook_url, message)

    def _send_slack_webhook(self, webhook_url: str, message: str) -> None:        
        payload = { "text": message }
        requests.post(webhook_url, json=payload)