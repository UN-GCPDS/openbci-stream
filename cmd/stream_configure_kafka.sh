#!/usr/bin/bash

function secure_file {
    if test -f $1.orig; then
        rm $1
        cp $1.orig $1
    else
        cp $1 $1.orig
    fi
}

FILE=/etc/kafka/server.properties
secure_file $FILE
echo "
advertised.listeners=PLAINTEXT://192.168.1.1:9092
listener.security.protocol.map=PLAINTEXT:PLAINTEXT,SSL:SSL,SASL_PLAINTEXT:SASL_PLAINTEXT,SASL_SSL:SASL_SSL
" >> $FILE


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

