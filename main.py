import time
import logging
from datetime import datetime
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trading_bot.log"),
        logging.StreamHandler()
    ]
)

# Configuration Parameters for Gold (XAUUSD)
SYMBOL = "XAUUSD"  # Agar aap ke broker mein symbol 'GOLD' hai toh yahan 'GOLD' likh dein
TIMEFRAME = mt5.TIMEFRAME_M15
LOT_SIZE = 0.01    # Gold par shuru mein chhota lot size (0.01) behter hota hai risk control ke liye
MAGIC_NUMBER = 123456
EMA_SHORT = 9
EMA_LONG = 21

# Gold ke liye 30 Pips Stop Loss aur 100 Pips Take Profit
SL_PIPS = 30
TP_PIPS = 100


def initialize_mt5():
    """Initializes and connects to the MetaTrader 5 terminal."""
    if not mt5.initialize():
        logging.error(f"MT5 initialization failed, error code: {mt5.last_error()}")
        return False
    
    if not mt5.symbol_select(SYMBOL, True):
        logging.error(f"Failed to select symbol {SYMBOL}, error code: {mt5.last_error()}")
        mt5.shutdown()
        return False
        
    logging.info(f"Successfully connected to MetaTrader 5. Trading symbol: {SYMBOL}")
    return True


def get_market_data(symbol, timeframe, count=100):
    """Fetches recent price rates and converts them into a Pandas DataFrame."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        logging.warning("Failed to fetch rates from MetaTrader 5")
        return None
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df


def calculate_indicators(df):
    """Calculates Exponential Moving Averages for strategy evaluation."""
    df['ema_short'] = df['close'].ewm(span=EMA_SHORT, adjust=False).mean()
    df['ema_long'] = df['close'].ewm(span=EMA_LONG, adjust=False).mean()
    return df


def check_open_positions():
    """Checks if there are already active positions for this bot."""
    positions = mt5.positions_get(symbol=SYMBOL)
    if positions is None:
        return 0
    
    bot_positions = [pos for pos in positions if pos.magic == MAGIC_NUMBER]
    return len(bot_positions)


def execute_trade(action, price, sl, tp):
    """Executes a market order (BUY or SELL) with Stop Loss and Take Profit for Gold."""
    deviation = 50  # Gold mein volatility zyada hoti hai is liye deviation thori barha di hai
    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT_SIZE,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": deviation,
        "magic": MAGIC_NUMBER,
        "comment": "Gold Bot 30SL 100TP",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Order failed, retcode={result.retcode}, error={mt5.last_error()}")
    else:
        logging.info(f"Successfully executed Gold {action}! Ticket: {result.order}, Price: {price}, SL: {sl}, TP: {tp}")


def run_strategy():
    """Core logic loop evaluating market trends for Gold with 30 Pips SL and 100 Pips TP."""
    logging.info("Evaluating Gold market conditions...")
    
    df = get_market_data(SYMBOL, TIMEFRAME, count=100)
    if df is None or len(df) < EMA_LONG:
        return

    df = calculate_indicators(df)
    
    prev_short = df['ema_short'].iloc[-2]
    prev_long = df['ema_long'].iloc[-2]
    curr_short = df['ema_short'].iloc[-1]
    curr_long = df['ema_long'].iloc[-1]

    if check_open_positions() > 0:
        logging.info("Position already active. Waiting for exit criteria or next signal.")
        return

    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        logging.warning("Failed to fetch current tick data")
        return

    symbol_info = mt5.symbol_info(SYMBOL)
    if symbol_info is None:
        return
        
    point = symbol_info.point
    digits = symbol_info.digits
    
    # Gold pip calculation multiplier
    pip_multiplier = 10 if digits in [3, 5] else 1
    
    sl_distance = SL_PIPS * pip_multiplier * point
    tp_distance = TP_PIPS * pip_multiplier * point

    # Bullish Crossover: BUY Signal for Gold
    if prev_short <= prev_long and curr_short > curr_long:
        logging.info("Bullish EMA crossover detected on Gold!")
        ask_price = tick.ask
        sl = ask_price - sl_distance
        tp = ask_price + tp_distance
        execute_trade("BUY", ask_price, sl, tp)

    # Bearish Crossover: SELL Signal for Gold
    elif prev_short >= prev_long and curr_short < curr_long:
        logging.info("Bearish EMA crossover detected on Gold!")
        bid_price = tick.bid
        sl = bid_price + sl_distance
        tp = bid_price - tp_distance
        execute_trade("SELL", bid_price, sl, tp)


def main():
    """Main execution entry point."""
    if not initialize_mt5():
        return

    try:
        while True:
            run_strategy()
            time.sleep(60)
    except KeyboardInterrupt:
        logging.info("Bot execution manually stopped by user.")
    finally:
        mt5.shutdown()
        logging.info("MT5 connection closed safely.")


if __name__ == "__main__":
    main()
