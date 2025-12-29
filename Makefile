SHELL := /bin/bash

# 1. 告訴 Makefile 去讀取 .env 檔案 (如果檔案存在的話)
# -include 代表如果檔案不存在也不要報錯 (防止剛 clone 下來還沒產生 .env 時報錯)
-include .env

# 2. 將讀到的變數匯出給 Shell 使用
export

PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PYTHON ?= python3
DOCKER_COMPOSE ?= docker-compose
FLINK_JOB ?= anomaly_detector.py
FLINK_ENTRY := /opt/flink/usrlib/$(FLINK_JOB)
BINANCE_SYMBOLS ?= BTCUSDT,ETHUSDT,BNBUSDT
KAFKA_BOOTSTRAP_SERVERS ?= ${EC2_PUBLIC_IP}:9092
FLINK_CONTAINER ?= jobmanager

.PHONY: help start stop restart logs init-topics start-producer submit-flink flink-shell

help:
	@echo "Crypto Trade Monitor automation"
	@echo "make start            # Start Kafka + Flink stack"
	@echo "make stop             # Stop all Docker services"
	@echo "make restart          # Restart Docker services"
	@echo "make logs             # Tail docker-compose logs"
	@echo "make init-topics      # Create Kafka topics inside broker"
	@echo "make start-producer   # Launch Binance websocket producer"
	@echo "make submit-flink     # Submit Flink Python job via jobmanager"
	@echo "make flink-shell      # Open shell inside jobmanager container"

start:
	$(DOCKER_COMPOSE) up -d

stop:
	$(DOCKER_COMPOSE) down

restart: stop start

logs:
	$(DOCKER_COMPOSE) logs -f

init-topics:
	bash $(PROJECT_ROOT)/scripts/init_topics.sh

start-producer:
	BINANCE_SYMBOLS=$(BINANCE_SYMBOLS) \
	KAFKA_BOOTSTRAP_SERVERS=$(KAFKA_BOOTSTRAP_SERVERS) \
	$(PYTHON) -m ingestion.producer_binance \
		--symbols $(BINANCE_SYMBOLS) \
		--kafka-bootstrap $(KAFKA_BOOTSTRAP_SERVERS)

submit-flink:
	docker exec $(FLINK_CONTAINER) flink run -py $(FLINK_ENTRY) -d

flink-shell:
	docker exec -it $(FLINK_CONTAINER) /bin/bash

