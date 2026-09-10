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

# Configuration Parameters
SYMBOL = "EURUSD"
TIMEFRAME = mt5.TIMEFRAME_M15
LOT_SIZE = 0.1
MAGIC_NUMBER = 123456
EMA_SHORT = 9
EMA_LONG = 21
SL_POINTS = 300  # Stop Loss in points
TP_POINTS = 600  # Take Profit in points


def initialize_mt5():
    """Initializes and connects to the MetaTrader 5 terminal."""
    if not mt5.initialize():
        logging.error(f"MT5 initialization failed, error code: {mt5.last_error()}")
        return False
    
    # Ensure the symbol is available and selected in Market Watch
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
    """Executes a market order (BUY or SELL) with pre-defined risk parameters."""
    deviation = 20
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
        "comment": "World Class MT5 Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logging.error(f"Order failed, retcode={result.retcode}, error={mt5.last_error()}")
    else:
        logging.info(f"Successfully executed {action}! Ticket: {result.order}, Price: {price}")


def run_strategy():
    """Core logic loop evaluating market trends and executing trades."""
    logging.info("Evaluating market conditions...")
    
    df = get_market_data(SYMBOL, TIMEFRAME, count=100)
    if df is None or len(df) < EMA_LONG:
        return

    df = calculate_indicators(df)
    
    # Get the latest completed candle values (-2) and active candle (-1)
    prev_short = df['ema_short'].iloc[-2]
    prev_long = df['ema_long'].iloc[-2]
    curr_short = df['ema_short'].iloc[-1]
    curr_long = df['ema_long'].iloc[-1]

    # Prevent over-trading by checking current open positions
    if check_open_positions() > 0:
        logging.info("Position already active. Waiting for exit criteria or next signal.")
        return

    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        logging.warning("Failed to fetch current tick data")
        return

    # Bullish Crossover: Short EMA crosses above Long EMA
    if prev_short <= prev_long and curr_short > curr_long:
        logging.info("Bullish EMA crossover detected!")
        ask_price = tick.ask
        point = mt5.symbol_info(SYMBOL).point
        sl = ask_price - (SL_POINTS * point)
        tp = ask_price + (TP_POINTS * point)
        execute_trade("BUY", ask_price, sl, tp)

    # Bearish Crossover: Short EMA crosses below Long EMA
    elif prev_short >= prev_long and curr_short < curr_long:
        logging.info("Bearish EMA crossover detected!")
        bid_price = tick.bid
        point = mt5.symbol_info(SYMBOL).point
        sl = bid_price + (SL_POINTS * point)
        tp = bid_price - (TP_POINTS * point)
        execute_trade("SELL", bid_price, sl, tp)


def main():
    """Main execution entry point."""
    if not initialize_mt5():
        return

    try:
        while True:
            run_strategy()
            # Sleep for 60 seconds before checking the market again
            time.sleep(60)
    except KeyboardInterrupt:
        logging.info("Bot execution manually stopped by user.")
    finally:
        mt5.shutdown()
        logging.info("MT5 connection closed safely.")


if __name__ == "__main__":
    main()
