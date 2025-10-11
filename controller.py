import os
import sys
from dotenv import load_dotenv

import auth
import lotto645
import win720
import notification
from recharge import Recharge
import time


def buy_lotto645(authCtrl: auth.AuthController, cnt: int, mode: str):
    lotto = lotto645.Lotto645()
    _mode = lotto645.Lotto645Mode[mode.upper()]
    response = lotto.buy_lotto645(authCtrl, cnt, _mode)
    response['balance'] = lotto.get_balance(auth_ctrl=authCtrl)
    return response

def check_winning_lotto645(authCtrl: auth.AuthController) -> dict:
    lotto = lotto645.Lotto645()
    item = lotto.check_winning(authCtrl)
    return item

def buy_win720(authCtrl: auth.AuthController, username: str):
    pension = win720.Win720()
    response = pension.buy_Win720(authCtrl, username)
    response['balance'] = pension.get_balance(auth_ctrl=authCtrl)
    return response

def check_winning_win720(authCtrl: auth.AuthController) -> dict:
    pension = win720.Win720()
    item = pension.check_winning(authCtrl)
    return item

def send_message(mode: int, lottery_type: int, response: dict, webhook_url: str):
    notify = notification.Notification()

    if mode == 0:
        if lottery_type == 0:
            notify.send_lotto_winning_message(response, webhook_url)
        else:
            notify.send_win720_winning_message(response, webhook_url)
    elif mode == 1: 
        if lottery_type == 0:
            notify.send_lotto_buying_message(response, webhook_url)
        else:
            notify.send_win720_buying_message(response, webhook_url)

def check():
    load_dotenv()

    username = os.environ.get('USERNAME')
    password = os.environ.get('PASSWORD')
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL') 
    discord_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')

    globalAuthCtrl = auth.AuthController()
    globalAuthCtrl.login(username, password)
    
    response = check_winning_lotto645(globalAuthCtrl)
    if slack_webhook_url != '':
        send_message(0, 0, response=response, webhook_url=slack_webhook_url)
    if discord_webhook_url != '':
        send_message(0, 0, response=response, webhook_url=discord_webhook_url)

    time.sleep(10)
    
    response = check_winning_win720(globalAuthCtrl)
    if slack_webhook_url != '':
        send_message(0, 1, response=response, webhook_url=slack_webhook_url)
    if discord_webhook_url != '':
        send_message(0, 1, response=response, webhook_url=discord_webhook_url)

def buy(): 
    load_dotenv() 

    username = os.environ.get('USERNAME')
    password = os.environ.get('PASSWORD')
    count = int(os.environ.get('COUNT'))
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL') 
    discord_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    mode = "AUTO"

    globalAuthCtrl = auth.AuthController()
    globalAuthCtrl.login(username, password)

    response = buy_lotto645(globalAuthCtrl, count, mode) 
    if slack_webhook_url != '':
        send_message(1, 0, response=response, webhook_url=slack_webhook_url)
    if discord_webhook_url != '':
        send_message(1, 0, response=response, webhook_url=discord_webhook_url)

    time.sleep(10)
    
    response = buy_win720(globalAuthCtrl, username)
    if slack_webhook_url != '':
        send_message(1, 1, response=response, webhook_url=slack_webhook_url)
    if discord_webhook_url != '':
        send_message(1, 1, response=response, webhook_url=discord_webhook_url)

def recharge():
    load_dotenv()
    username = os.environ.get('USERNAME')
    password = os.environ.get('PASSWORD')
    amount = int(os.environ.get('AMOUNT', '0'))

    globalAuthCtrl = auth.AuthController()
    globalAuthCtrl.login(username, password)
    headers_with_cookie = globalAuthCtrl.add_auth_cred_to_headers({})
    cookie_header = headers_with_cookie.get("Cookie", "")
    jsession_id = ""
    if "JSESSIONID=" in cookie_header:
        jsession_id = cookie_header.split("JSESSIONID=", 1)[1].strip()

    r = Recharge()
    response = r.recharge(jsession_id, amount)
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL') 
    if slack_webhook_url != '':
        notify = notification.Notification()
        notify.send_recharge_message(response, slack_webhook_url)

def run():
    if len(sys.argv) < 2:
        print("Usage: python controller.py [buy|check]")
        return

    if sys.argv[1] == "buy":
        buy()
    elif sys.argv[1] == "check":
        check()
    elif sys.argv[1] == "recharge":
        recharge()

if __name__ == "__main__":
    run()
