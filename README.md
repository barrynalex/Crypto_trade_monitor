# Crypto Trade Monitor

A self-contained sandbox for ingesting live (or simulated) crypto trades, persisting them to Kafka, and detecting anomalies with a PyFlink streaming job. The stack bundles a single-node Kafka broker and a custom Flink JobManager/TaskManager pair so you can iterate on streaming pipelines locally.

## Architecture
- **Ingestion producers** (`ingestion/producer_binance.py`, `ingestion/producer_mock.py`) publish normalized trade events to the `trades.raw` Kafka topic.
- **Kafka broker** (Confluent image) stores raw trades and emits alert messages.
- **PyFlink anomaly detector** (`flink-jobs/anomaly_detector.py`) consumes `trades.raw`, computes 10s tumbling window aggregates, and writes `signals.alerts` when volume thresholds are exceeded.
- **Docker images** (`docker-compose.yml`, `Dockerfile.jobmanager`) orchestrate Kafka + Flink with the necessary connectors pre-installed.

```
Binance WS / Mock Producer → Kafka topic `trades.raw` → PyFlink job → Kafka topic `signals.alerts`
```

## Repository layout
- `docker-compose.yml` – brings up Kafka + custom Flink cluster.
- `Dockerfile.jobmanager` – installs PyFlink and connector JARs for the JobManager image.
- `flink-jobs/` – Python streaming jobs (default: `anomaly_detector.py`).
- `ingestion/` – trade producers (real Binance WebSocket + mock generator).
- `scripts/init_topics.sh` – helper for creating Kafka topics inside the broker.
- `Makefile` – common workflows (`start`, `stop`, `init-topics`, `start-producer`, `submit-flink`, etc.).

## Prerequisites
- Docker Engine 24+ with the Compose plugin.
- Python 3.10+ on the host for running producers directly.
- GNU Make (invoked via the provided `Makefile`).
- Python deps: `pip install -r requirements.txt` (installs `confluent-kafka` and `websocket-client`).

## Quick start
1. **Start the stack**
   ```bash
   make start
   ```
   This builds the custom Flink image and launches the Kafka broker plus Flink JobManager/TaskManager containers. The Flink UI becomes available at `http://localhost:8081`.

2. **Create Kafka topics**  
   The helper script opens a shell inside the broker and walks you through topic creation:
   ```bash
   make init-topics
   # inside the broker container:
   kafka-topics --bootstrap-server broker:29092 --create --topic trades.raw --partitions 1 --replication-factor 1
   kafka-topics --bootstrap-server broker:29092 --create --topic signals.alerts --partitions 1 --replication-factor 1
   kafka-topics --bootstrap-server broker:29092 --list
   exit
   ```

3. **Run a producer**
   - Real Binance feed (set env vars as needed):
     ```bash
     BINANCE_SYMBOLS=BTCUSDT,ETHUSDT make start-producer
     ```
   - Mock generator (no external network needed):
     ```bash
     python -m ingestion.producer_mock
     ```
   Producers default to `localhost:9092` but honor `KAFKA_BOOTSTRAP_SERVERS`.

4. **Submit the PyFlink job**
   ```bash
   make submit-flink
   ```
   This runs `flink run -py /opt/flink/usrlib/anomaly_detector.py` inside the JobManager container and starts pushing alerts to `signals.alerts` whenever a 10-second window exceeds the configured volume threshold.

5. **Inspect logs / alerts**
   ```bash
   make logs                      # tail all Docker services
   docker exec -it broker kafka-console-consumer \
     --bootstrap-server broker:29092 \
     --topic signals.alerts \
     --from-beginning
   ```

6. **Shutdown**
   ```bash
   make stop
   ```

## Configuration
- `BINANCE_SYMBOLS` – comma-separated trading pairs (defaults to BTCUSDT, ETHUSDT, BNBUSDT).
- `KAFKA_BOOTSTRAP_SERVERS` – producer bootstrap servers (`localhost:9092` outside Docker, `broker:29092` inside).
- `KAFKA_TRADES_TOPIC` / `KAFKA_ALERTS_TOPIC` – override default topic names if needed.
- `BINANCE_STREAM_URL` – point to a custom WebSocket endpoint.
- `KAFKA_USERNAME`, `KAFKA_PASSWORD`, `KAFKA_SECURITY_PROTOCOL`, `KAFKA_SASL_MECHANISM` – enable SASL auth for managed Kafka clusters.

Define long-lived secrets via environment variables or a local `.env` file that you do **not** commit (e.g., add `/ENV` to `.gitignore` if you keep virtualenvs here).

## Development tips
- Place additional PyFlink jobs inside `flink-jobs/` and change `FLINK_JOB=<file>` when running `make submit-flink`.
- Use `make flink-shell` to drop into `/opt/flink/usrlib` inside the JobManager for debugging or manual `flink` CLI commands.
- Persist Kafka state under `kafka-data/`; delete the directory if you want a clean broker ledger between experiments.
- When iterating on producers, keep `producer_mock.py` handy to avoid Binance rate limits during offline development.

## Troubleshooting
- **Flink UI not reachable** – ensure the JobManager container is healthy (`docker ps`) and port `8081` is free.
- **Producers cannot reach Kafka** – inside containers use `broker:29092`; from the host use `localhost:9092`. Confirm the broker healthcheck passes in Compose logs.
- **Missing topics** – rerun the topic creation commands inside the broker or delete/recreate via `kafka-topics`.
- **Permission errors with Kafka libs** – rebuild the JobManager image (`docker-compose build jobmanager`) to refresh connector downloads.

Happy streaming!

