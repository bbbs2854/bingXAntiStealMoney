import json
import time
import requests
import hmac
from prettytable import PrettyTable
from hashlib import sha256

from config import APIKEY, APIURL, SECRETKEY, PROXY

def get_spot_balances(spot_data):
    data = json.loads(spot_data)
    spot_table = PrettyTable()
    spot_table.field_names = ["Asset", "Free", "Locked", "Total"]

    for balance in data['data']['balances']:
        asset = balance['asset']
        free = float(balance['free'])
        locked = float(balance['locked'])
        total = free + locked

        if total > 0:
            spot_table.add_row([asset, f"{free:.8f}", f"{locked:.8f}", f"{total:.8f}"])

    spot_table.align["Free"] = "c"
    spot_table.align["Locked"] = "c"
    spot_table.align["Total"] = "c"

    spot_table.title = "Spot balances"

    spot_table.header = True
    spot_table.border = True

    print(spot_table)


def get_futures_balances(futures_data):
    data = json.loads(futures_data)

    balance_info = data['data']['balance']

    table = PrettyTable()

    fields_to_display = [
        "asset", "balance", "equity", "unrealizedProfit", "realisedProfit",
        "availableMargin", "usedMargin", "freezedMargin"
    ]

    table.field_names = fields_to_display

    table.add_row([balance_info[field] for field in fields_to_display])

    for field in fields_to_display:
        table.align[field] = "r"
    table.title = "FUTURES"

    print(table)


def get_spot_usdt_balance():
    payload = {}
    path = '/openApi/spot/v1/account/balance'
    method = "GET"
    paramsMap = {
        "timestamp": str(int(time.time() * 1000))
    }
    paramsStr = parseParam(paramsMap)
    try:
        spot_data = send_request(method, path, paramsStr, payload)
        data = json.loads(spot_data)
        usdt_balance = next((balance for balance in data['data']['balances'] if balance['asset'] == 'USDT'), None)

        if usdt_balance:
            return float(usdt_balance['free'])
    except Exception as e:
        print(f"Error: {e}")


def getBalances():
    payload = {}
    path = '/openApi/spot/v1/account/balance'
    method = "GET"
    paramsMap = {
        "timestamp": str(int(time.time() * 1000))
    }
    paramsStr = parseParam(paramsMap)
    try:
        spot_data = send_request(method, path, paramsStr, payload)
        get_spot_balances(spot_data)
        path = '/openApi/swap/v2/user/balance'
        paramsMap = {
            "recvWindow": "10000",
            "timestamp": str(int(time.time() * 1000))
        }
        paramsStr = parseParam(paramsMap)
        futures_data = send_request(method, path, paramsStr, payload)
        get_futures_balances(futures_data)
    except Exception as e:
        print(f"Error: {e}")


def get_sign(api_secret, payload):
    signature = hmac.new(api_secret.encode("utf-8"), payload.encode("utf-8"), digestmod=sha256).hexdigest()
    return signature


def send_request(method, path, urlpa, payload):
    url = "%s%s?%s&signature=%s" % (APIURL, path, urlpa, get_sign(SECRETKEY, urlpa))
    headers = {
        'X-BX-APIKEY': APIKEY,
    }
    proxies = {
        'http': PROXY,
        'https': PROXY
    }
    response = requests.request(method, url, headers=headers, data=payload, proxies=proxies)
    if response.ok:
        return response.text
    else:
        raise Exception(f"Unexpected error: {response.status_code} {response.text}")


def parseParam(paramsMap):
    sortedKeys = sorted(paramsMap)
    paramsStr = "&".join(["%s=%s" % (x, paramsMap[x]) for x in sortedKeys])
    if paramsStr != "":
        return paramsStr + "&timestamp=" + str(int(time.time() * 1000))
    else:
        return paramsStr + "timestamp=" + str(int(time.time() * 1000))


def format_to_three(number):
    number_str = str(number)
    if '.' in number_str:
        integer_part, decimal_part = number_str.split('.')
        truncated_decimal_part = decimal_part[:3]
        return f"{integer_part}.{truncated_decimal_part}"
    else:
        return number_str


def get_usdt_amount_in_futures_balance():
    payload = {}
    method = "GET"
    path = '/openApi/swap/v2/user/balance'
    paramsMap = {
        "recvWindow": "10000",
        "timestamp": str(int(time.time() * 1000))
    }
    paramsStr = parseParam(paramsMap)
    try:
        futures_data = send_request(method, path, paramsStr, payload)
        data = json.loads(futures_data)
        balance_info = data['data']['balance']['balance']
        print(format_to_three(balance_info))
        return format_to_three(balance_info)
    except Exception as e:
        print(f"Error: {e}")
        return 0


def transfer_assets_to_spot():
    payload = {}
    path = '/openApi/api/v3/post/asset/transfer'
    method = "POST"
    paramsMap = {
        "recvWindow": "6000",
        "timestamp": str(int(time.time() * 1000)),
        "asset": "USDT",
        "amount": get_usdt_amount_in_futures_balance(),
        "type": "PFUTURES_FUND",

    }
    paramsStr = parseParam(paramsMap)
    try:
        request = send_request(method, path, paramsStr, payload)
        print(request)
        return request
    except Exception as e:
        print(f"Error: {e}")


def close_all_orders_and_position():
    payload = {}
    path = '/openApi/swap/v2/trade/closeAllPositions'
    method = "POST"
    paramsMap = {
        "timestamp": str(int(time.time() * 1000)),
    }
    paramsStr = parseParam(paramsMap)
    try:
        send_request(method, path, paramsStr, payload)
        print("Positions probably closed. Check all balances and try transfer USDT.")
    except Exception as e:
        print(f"Error: {e}")
    path = '/openApi/swap/v2/trade/allOpenOrders'
    method = "DELETE"
    paramsMap = {
        "timestamp": str(int(time.time() * 1000)),
    }
    paramsStr = parseParam(paramsMap)
    try:
        send_request(method, path, paramsStr, payload)
    except Exception as e:
        print(f"Error: {e}")


def withdraw():
    address = input("Enter BSC address: ")
    amount = get_spot_usdt_balance()
    payload = {}
    path = '/openApi/wallets/v1/capital/withdraw/apply'
    method = "POST"
    paramsMap = {
        "address": address,
        "amount": format_to_three(amount),
        "coin": "USDT",
        "network": "BEP20",
        "timestamp": str(int(time.time() * 1000)),
        "walletType": "1"
    }
    paramsStr = parseParam(paramsMap)
    try:
        response = send_request(method, path, paramsStr, payload)
        print(response)
    except Exception as e:
        print(f"Error: {e}")


def menu():
    while True:
        print("1. Get all balances")
        print("2. Transfer all USDT to spot balance")
        print("3. Close all orders and position")
        print("4. Withdraw all USDT")
        print("9. Exit")

        try:
            user_input = int(input("Enter number: "))
        except:
            print("Wrong input! Try again.")
            continue

        if user_input == 1:
            getBalances()
        elif user_input == 2:
            transfer_assets_to_spot()
        elif user_input == 3:
            close_all_orders_and_position()
        elif user_input == 4:
            withdraw()
        elif user_input == 9:
            exit(0)
        else:
            print("Wrong input! Try again.")


if __name__ == '__main__':
    menu()
