# Flink anomaly detection job
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment, EnvironmentSettings
from pyflink.table.expressions import col, lit
from pyflink.table.window import Tumble
from pyflink.table.types import DataTypes
import json

def main():
    # ---- 1) Flink env setup ----
    env_settings = EnvironmentSettings.in_streaming_mode()
    env = StreamExecutionEnvironment.get_execution_environment()
    
    # Set parallelism (adjust as needed)
    env.set_parallelism(1)
    
    # Kafka connector and JSON format JARs are installed in /opt/flink/lib
    # No need to add them here since they're already on the classpath
    # If needed, you can uncomment and update the URLs below:
    # kafka_connector_jar = "https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.3.0-1.20/flink-sql-connector-kafka-3.3.0-1.20.jar"
    # json_format_jar = "https://repo1.maven.org/maven2/org/apache/flink/flink-json/1.20.0/flink-json-1.20.0.jar"
    # env.add_jars(kafka_connector_jar, json_format_jar)
    
    t_env = StreamTableEnvironment.create(env, environment_settings=env_settings)

    # ---- 2) Kafka source table ----
    t_env.execute_sql("""
    CREATE TABLE trades_raw (
        ts BIGINT,
        ingest_ts BIGINT,
        exchange STRING,
        symbol STRING,
        trade_id STRING,
        side STRING,
        price STRING,
        qty STRING,
        rowtime AS TO_TIMESTAMP_LTZ(ts, 3),
        WATERMARK FOR rowtime AS rowtime - INTERVAL '5' SECOND
    ) WITH (
        'connector' = 'kafka',
        'topic' = 'trades.raw',
        'properties.bootstrap.servers' = 'broker:29092',
        'properties.group.id' = 'flink-trades',
        'scan.startup.mode' = 'latest-offset',
        'format' = 'json',
        'json.ignore-parse-errors' = 'true'
    )
    """)

    # ---- 3) Kafka sink table (alerts) ----
    t_env.execute_sql("""
    CREATE TABLE alerts (
        ts BIGINT,
        symbol STRING,
        exchange STRING,
        signal STRING,
        volume STRING,
        avg_price STRING
    ) WITH (
        'connector' = 'kafka',
        'topic' = 'signals.alerts',
        'properties.bootstrap.servers' = 'broker:29092',
        'format' = 'json',
        'json.timestamp-format.standard' = 'ISO-8601'
    )
    """)

    # ---- 4) Build realtime window logic using SQL ----
    # Create a view with window aggregation
    t_env.execute_sql("""
    CREATE TEMPORARY VIEW windowed_trades AS
    SELECT 
        TUMBLE_END(rowtime, INTERVAL '10' SECOND) as window_end,
        symbol,
        exchange,
        SUM(CAST(qty AS DOUBLE)) as volume,
        AVG(CAST(price AS DOUBLE)) as avg_price
    FROM trades_raw
    GROUP BY TUMBLE(rowtime, INTERVAL '10' SECOND), symbol, exchange
    """)
    
    # Select from the view with proper timestamp conversion
    t_env.execute_sql("""
    INSERT INTO alerts
    SELECT 
        CAST(UNIX_TIMESTAMP(CAST(window_end AS STRING)) * 1000 AS BIGINT) as ts,
        symbol,
        exchange,
        'volume_spike' as signal,
        CAST(volume AS STRING) as volume,
        CAST(avg_price AS STRING) as avg_price
    FROM windowed_trades
    WHERE volume > 1.0
    """).wait()


if __name__ == "__main__":
    main()
