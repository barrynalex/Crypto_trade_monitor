"""Binance trade WebSocket producer publishing to Kafka."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import socket
import sys
import threading
import time
from typing import Dict, List, Optional

from confluent_kafka import Producer
from websocket import WebSocketApp  # type: ignore

# ---- Constants ----------------------------------------------------------------

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
BINANCE_BASE_STREAM = "wss://stream.binance.com:9443/stream?streams="
DEFAULT_TOPIC = "trades.raw"
DEFAULT_BOOTSTRAP = "localhost:9092"
EXCHANGE = "binance"

# ---- Helpers ------------------------------------------------------------------


def parse_symbols(raw: str) -> List[str]:
    """Parse comma separated symbols -> upper-case list."""
    symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]
    return symbols or DEFAULT_SYMBOLS


def build_stream_url(symbols: List[str]) -> str:
    """Build combined stream URL for Binance trade stream."""
    streams = "/".join(f"{symbol.lower()}@trade" for symbol in symbols)
    override = os.getenv("BINANCE_STREAM_URL")
    return override or f"{BINANCE_BASE_STREAM}{streams}"


def build_kafka_conf(bootstrap: str, client_id: str) -> Dict[str, str]:
    """Create Kafka producer configuration."""
    conf: Dict[str, str] = {
        "bootstrap.servers": bootstrap,
        "client.id": client_id,
        "queue.buffering.max.messages": "200000",
        "linger.ms": "20",
        "enable.idempotence": "true",
    }

    username = os.getenv("KAFKA_USERNAME")
    password = os.getenv("KAFKA_PASSWORD")
    if username and password:
        conf.update(
            {
                "security.protocol": os.getenv("KAFKA_SECURITY_PROTOCOL", "SASL_SSL"),
                "sasl.mechanism": os.getenv("KAFKA_SASL_MECHANISM", "PLAIN"),
                "sasl.username": username,
                "sasl.password": password,
            }
        )
    return conf


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


# ---- Producer -----------------------------------------------------------------


class BinanceTradeProducer:
    """Manage Binance WebSocket connection and Kafka publishing."""

    def __init__(
        self, symbols: List[str], kafka_conf: Dict[str, str], topic: str
    ) -> None:
        self.symbols = symbols
        self.topic = topic
        self.kafka_producer = Producer(kafka_conf)
        self.ws_app: Optional[WebSocketApp] = None
        self.stop_event = threading.Event()
        self.logger = logging.getLogger("binance.producer")
        self.stream_url = build_stream_url(symbols)
        self._backoff_seconds = 1

    # -- Signal handling --------------------------------------------------------

    def stop(self) -> None:
        """Signal-safe shutdown."""
        if self.stop_event.is_set():
            return
        self.logger.info("Stopping Binance producer ...")
        self.stop_event.set()
        if self.ws_app:
            try:
                self.ws_app.close()
            except Exception:
                pass
        self.kafka_producer.flush(10)

    # -- Kafka callbacks --------------------------------------------------------

    def _delivery_report(self, err, msg) -> None:  # type: ignore[override]
        if err is not None:
            self.logger.error("Kafka delivery failed: %s", err)
            return
        self.logger.debug(
            "Delivered %s to %s [%s] offset %s",
            msg.key(),
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )

    # -- WebSocket lifecycle ----------------------------------------------------

    def _on_open(self, *_args) -> None:
        self.logger.info(
            "Connected to Binance stream (%s) for %s",
            self.stream_url,
            ",".join(self.symbols),
        )
        self._backoff_seconds = 1

    def _on_close(self, *_args) -> None:
        self.logger.warning("Binance stream closed.")

    def _on_error(self, _ws, error) -> None:
        if not self.stop_event.is_set():
            self.logger.error("WebSocket error: %s", error)

    def _on_message(self, _ws, message: str) -> None:
        try:
            payload = json.loads(message)
            trade = payload.get("data") or payload
            if not trade or trade.get("e") != "trade":
                return
            record = self._format_trade(trade)
            self.kafka_producer.produce(
                self.topic,
                key=record["symbol"],
                value=json.dumps(record),
                on_delivery=self._delivery_report,
            )
            self.kafka_producer.poll(0)
        except json.JSONDecodeError:
            self.logger.warning("Invalid JSON payload: %s", message[:200])
        except Exception as exc:
            self.logger.exception("Failed to process trade: %s", exc)

    # -- Trade formatting -------------------------------------------------------

    def _format_trade(self, trade: Dict[str, str]) -> Dict[str, str]:
        ingest_ts = int(time.time() * 1000)
        ts = int(trade.get("T") or trade.get("E") or ingest_ts)
        side = "sell" if trade.get("m") else "buy"
        return {
            "ts": ts,
            "ingest_ts": ingest_ts,
            "exchange": EXCHANGE,
            "symbol": trade.get("s", "").upper(),
            "trade_id": str(trade.get("t", trade.get("a", ingest_ts))),
            "side": side,
            "price": trade.get("p", "0"),
            "qty": trade.get("q", "0"),
        }

    # -- Main loop --------------------------------------------------------------

    def start(self) -> None:
        """Run WebSocket loop with reconnect/backoff."""
        headers = {"User-Agent": "crypto-trade-monitor/1.0"}
        while not self.stop_event.is_set():
            self.ws_app = WebSocketApp(
                self.stream_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                header=[f"{k}: {v}" for k, v in headers.items()],
            )
            self.ws_app.run_forever(ping_interval=20, ping_timeout=10)

            if self.stop_event.is_set():
                break

            self.logger.warning(
                "WebSocket disconnected, retrying in %s seconds",
                self._backoff_seconds,
            )
            time.sleep(self._backoff_seconds)
            self._backoff_seconds = min(self._backoff_seconds * 2, 60)

        self.logger.info("Producer loop exited")


# ---- Entrypoint ---------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Binance WebSocket trade producer"
    )
    parser.add_argument(
        "--symbols",
        default=os.getenv("BINANCE_SYMBOLS", ",".join(DEFAULT_SYMBOLS)),
        help="Comma separated list of Binance symbols (default: %(default)s)",
    )
    parser.add_argument(
        "--kafka-bootstrap",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", DEFAULT_BOOTSTRAP),
        help="Kafka bootstrap servers",
    )
    parser.add_argument(
        "--kafka-topic",
        default=os.getenv("KAFKA_TRADES_TOPIC", DEFAULT_TOPIC),
        help="Kafka topic for raw trades",
    )
    parser.add_argument(
        "--client-id",
        default=os.getenv(
            "BINANCE_PRODUCER_CLIENT_ID",
            f"binance-producer-{socket.gethostname()}",
        ),
        help="Kafka client.id (defaults to hostname)",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Logging level (default: %(default)s)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.log_level)

    symbols = parse_symbols(args.symbols)
    kafka_conf = build_kafka_conf(args.kafka_bootstrap, args.client_id)
    producer = BinanceTradeProducer(symbols, kafka_conf, args.kafka_topic)

    def _graceful_exit(_sig, _frame) -> None:
        producer.stop()

    signal.signal(signal.SIGINT, _graceful_exit)
    signal.signal(signal.SIGTERM, _graceful_exit)

    try:
        producer.start()
    except KeyboardInterrupt:
        producer.stop()
    except Exception as exc:
        logging.exception("Binance producer failed: %s", exc)
        producer.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
