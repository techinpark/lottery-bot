import os
from dotenv import load_dotenv

import auth
import lotto645

def login(user_id: str, user_pw: str):
    globalAuthCtrl = auth.AuthController()
    globalAuthCtrl.login(user_id, user_pw)

    return globalAuthCtrl

def buy_lotto645(authCtrl: auth.AuthController, cnt: int, mode: str):
    lotto = lotto645.Lotto645()
    _mode = lotto645.Lotto645Mode[mode.upper()]
    lotto.buy_lotto645(authCtrl, cnt, _mode)

def run():
    
    load_dotenv() 

    username = os.environ.get('USERNAME')
    password = os.environ.get('PASSWORD')
    count = os.environ.get('COUNT')
    mode = "AUTO"

    authCtrl = login(username, password)
    buy_lotto645(authCtrl, count, mode)


if __name__ == "__main__":
    run()
