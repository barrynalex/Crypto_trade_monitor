#!/bin/bash
# Initialize Kafka topics
# 進容器
docker exec -it broker bash

# 在容器內 (用內部 listener broker:29092)
kafka-topics --bootstrap-server broker:29092 --create --topic trades.raw --partitions 1 --replication-factor 1
kafka-topics --bootstrap-server broker:29092 --create --topic signals.alerts --partitions 1 --replication-factor 1

# 檢查
kafka-topics --bootstrap-server broker:29092 --list
exit