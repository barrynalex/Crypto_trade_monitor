import json
import random
import time
from datetime import datetime
from confluent_kafka import Producer

conf = {'bootstrap.servers': 'localhost:9092'}
producer = Producer(conf)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
EXCHANGE = "binance"

def gen_trade():
    symbol = random.choice(SYMBOLS)
    base_price = {"BTCUSDT": 60000, "ETHUSDT": 3200, "BNBUSDT": 400}[symbol]
    price = round(base_price * random.uniform(0.999, 1.001), 2)
    qty = round(random.uniform(0.5, 1.5), 4)
    ts = int(time.time() * 1000)
    return {
        "ts": ts,
        "ingest_ts": ts,
        "exchange": EXCHANGE,
        "symbol": symbol,
        "trade_id": f"{symbol}-{ts}",
        "side": random.choice(["buy", "sell"]),
        "price": str(price),
        "qty": str(qty)
    }

def delivery_report(err, msg):
    if err is not None:
        print(f"❌ Delivery failed: {err}")
    else:
        print(f"✅ Sent to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")

if __name__ == "__main__":
    print("🚀 Starting mock trade producer... Ctrl+C to stop.")
    while True:
        trade = gen_trade()
        producer.produce(
            "trades.raw",
            key=trade["symbol"],
            value=json.dumps(trade),
            callback=delivery_report
        )
        producer.poll(0)     # trigger callback
        time.sleep(0.3)      # ~3 msgs/sec
