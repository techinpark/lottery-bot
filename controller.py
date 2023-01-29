import os
import sys
from dotenv import load_dotenv

import auth
import lotto645
import notification

def login(user_id: str, user_pw: str):
    globalAuthCtrl = auth.AuthController()
    globalAuthCtrl.login(user_id, user_pw)

    return globalAuthCtrl

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

def send_message(mode: lotto645.Lotto645Mode, response: dict, webhook_url: str):
    notify = notification.Notification() 

    if mode == lotto645.Lotto645Mode.CHECK:
        notify.send_winning_message(response, webhook_url)
    elif mode == lotto645.Lotto645Mode.BUY: 
        notify.send_buying_message(response, webhook_url)

def check(): 
    load_dotenv() 

    username = os.environ.get('USERNAME')
    password = os.environ.get('PASSWORD')
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL') 
    discord_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')

    authCtrl = login(username, password)
    response = check_winning_lotto645(authCtrl)
    send_message(lotto645.Lotto645Mode.CHECK, response, discord_webhook_url)

def buy(): 
    
    load_dotenv() 

    username = os.environ.get('USERNAME')
    password = os.environ.get('PASSWORD')
    count = int(os.environ.get('COUNT'))
    slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL') 
    discord_webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    mode = "AUTO"

    authCtrl = login(username, password)
    response = buy_lotto645(authCtrl, count, mode) 
    send_message(mode=lotto645.Lotto645Mode.BUY, response=response, webhook_url=discord_webhook_url)

def run():
    if len(sys.argv) < 2:
        print("Usage: python controller.py [buy|check]")
        return

    if sys.argv[1] == "buy":
        buy()
    elif sys.argv[1] == "check":
        check()
  

if __name__ == "__main__":
    run()
