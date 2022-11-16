from binance.client import Client
import keys
import pandas as pd
import time

client = Client(keys.api_key, keys.api_secret)


def top_coin():
    all_tickers = pd.DataFrame(client.get_ticker())
    usdt = all_tickers[all_tickers.symbol.str.contains('USDT')]
    work = usdt[~(usdt.symbol.str.contains('UP')) & ~(usdt.symbol.str.contains('DOWN'))]
    top_coin = work[work.priceChangePercent == work.priceChangePercent.max()]
    top_coin = top_coin.symbol.values[0]
    print(top_coin)
    return top_coin

def last_data(symbol, interval, lookback):
    frame = pd.DataFrame(client.get_historical_klines(symbol, interval, lookback + 'min ago UTC'))
    frame = frame.iloc[:, :6]
    frame.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
    frame = frame.set_index('Time')
    frame.index = pd.to_datetime(frame.index, unit='ms')
    frame = frame.astype(float)
    return frame

def check_minQty(asset, qty):
    """Проверка на минимамальный необходимый объём покупки."""
    info = client.get_symbol_info(asset)
    minQty = float(info['filters'][2]['minQty'])

    if qty > minQty:
        print('minQty - OK')
        return True
    else:
        print('minQty - FAIL')
        print(f'qty = {qty}, minQty = {minQty}')
        return False

def check_stepSize(asset, qty):
    """Проверка на корректный шаг покупки. И его исправление, если он не корректный."""
    info = client.get_symbol_info(asset)
    stepSize = float(info['filters'][2]['stepSize'])

    if qty > stepSize and qty % stepSize == 0:
        print('steSize - OK')
        return True
    else:
        print('stepSize - FAIL')
        print(f'qty = {qty}, stepSize = {stepSize}. residue = {qty % stepSize}')
        return False

def check_minNotional(asset, buy_amt):
    info = client.get_symbol_info(asset)
    minNotional = float(info['filters'][3]['minNotional'])

    if buy_amt >= minNotional:
        print('min_Notional - OK')
        return True
    else:
        print('min_Notional - FAIL')
        print(f'result = {buy_amt} < {minNotional}')
        checked = False

def check_order_possibility(buy_amt, asset, qty, df):
    """Проверка монеты на соответствие основным ограничениям для создания ордера"""
    checked = True
    print(asset)
    print(df.iloc[-1])

    if not check_stepSize(asset, qty):
        tick_sized_qty = tick_sized(asset, qty)
        print(f'Corrected qty = {tick_sized_qty}\nstepSize - OK')
        checked = check_minQty(asset, qty) and check_minNotional(asset, buy_amt)
        return checked, tick_sized_qty
    else:
        checked = check_minQty(asset, qty) and check_minNotional(asset, buy_amt)
        return checked, qty

def tick_sized(asset, qty):
    tick_size = client.get_symbol_info(asset)
    minQty = float(tick_size['filters'][2]['minQty'])
    if qty < 1 and minQty < 1:
        return round(qty, len(str(round(1 / minQty)))-1)
    elif qty > 1 and minQty >= 1:
        stepSize = float(tick_size['filters'][2]['stepSize'])
        return round(qty - qty % stepSize)
    else:
        print(f'{qty} {minQty}')
        return round(qty, int(int(qty * (1 / minQty)) / (1 / minQty)))

def strategy(buy_amt, SL=0.985, Target=1.02, open_position=False):
    """Основная часть программы.
    1. Ищет топовую по росту за день монету относительно USDT. - top_coin()
    2. Смотрим, чтобы за последние 120 минут на минутном графике она так же росла. - last_data()
    3. Если это так - покупаем на количество = qty USDT эту монету.
    4. Устанавливаем стоп-лосс на -1,5% от покупки, а лимит на продажу на +2%"""
    try:
        asset = top_coin()
        df = last_data(asset, '1m', '120')

    except:
        time.sleep(61)
        asset = top_coin()
        df = last_data(asset, '1m', '120')

    qty = round(buy_amt*0.999/df.Close.iloc[-1], 2)
    print(((df.Close.pct_change() + 1).cumprod()).iloc[-1])
    print('Searching possible orders...')
    checked, qty_to_work = check_order_possibility(buy_amt, asset, qty, df)

    if ((df.Close.pct_change() + 1).cumprod()).iloc[-1] > 1 & checked is True:
        order = client.create_order(symbol=asset, side='BUY', type='MARKET', quantity=qty_to_work)
        print(order)
        buyprice = float(order['fills'][0]['price'])
        open_position = True

        while open_position:
            try:
                df = last_data(asset, '1m', '1')

            except:
                print('Restart after 1 min')
                time.sleep(61)
                df = last_data(asset, '1m', '1')

            print(f'Price ' + str(df.Close[-1]))
            print(f'Target ' + str(buyprice * Target))
            print(f'Stop ' + str(buyprice * SL))

            if df.Close[-1] < buyprice * SL or df.Close[-1] >= buyprice * Target:
                order = client.create_order(symbol=asset, side='SELL', type='MARKET', quantity=qty_to_work)
                print(f"Продали за: {order['fills'][0]['price']} + комиссия {order['fills'][0]['commission']}")
                plus = buyprice-float(order['fills'][0]['price'])*float(order['fills'][0]['price'])
                print(f"Итого в + на {plus} USDT")
                break
    else:
        print('Orders not found...')
        time.sleep(2)


while True:
    strategy(20)
"""
i=0
while i < 1:
    print(check_stepSize('PEOPLEUSDT', 837.38))
    tick_sized_qty = tick_sized('PEOPLEUSDT', 837.38)
    print(f'Corrected qty = {tick_sized_qty}\nstepSize - OK')
    i = 1"""