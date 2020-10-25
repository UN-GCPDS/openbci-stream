#!/usr/bin/bash

echo "Starting daemons"
systemctl enable kafka.service zookeeper@kafka.service
systemctl start kafka.service zookeeper@kafka.service

echo "Creating partitions"
kafka-topics.sh --create --zookeeper localhost:2181 --replication-factor 1 --partitions 1 --topic binary
kafka-topics.sh --create --zookeeper localhost:2181 --replication-factor 1 --partitions 1 --topic eeg
kafka-topics.sh --create --zookeeper localhost:2181 --replication-factor 1 --partitions 1 --topic marker

echo "Setting retention"
kafka-configs.sh --bootstrap-server localhost:2181  --entity-type topics --entity-name binary --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:2181  --entity-type topics --entity-name eeg --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:2181  --entity-type topics --entity-name marker --alter --add-config retention.ms=1000
