#!/usr/bin/bash

function secure_file {
    if test -f $1.orig; then
        rm $1
        cp $1.orig $1
    else
        cp $1 $1.orig
    fi
}

echo "Starting daemons"
systemctl enable kafka.service zookeeper@kafka.service
systemctl start kafka.service zookeeper@kafka.service

#echo "Removing previous partitions"
#kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic binary
#kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic eeg
#kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic marker
#kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic annotation
#kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic command
#kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic feedback

echo "Creating partitions"
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic binary
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic binary0
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic binary1
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic binary2
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic binary3
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic eeg
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic aux
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic eeg0
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic eeg1
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic eeg2
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic eeg3
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic marker
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic annotation
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic command
kafka-topics.sh --create --bootstrap-server localhost:9092 --replication-factor 1 --partitions 1 --topic feedback

echo "Setting retention"
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name binary --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name binary0 --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name binary1 --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name binary2 --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name binary3 --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name aux --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name eeg --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name eeg0 --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name eeg1 --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name eeg2 --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name eeg3 --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name marker --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name annotation --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name command --alter --add-config retention.ms=1000
kafka-configs.sh --bootstrap-server localhost:9092 --entity-type topics --entity-name feedback --alter --add-config retention.ms=1000

FILE=/etc/kafka/server.properties
secure_file $FILE
echo "
advertised.listeners=PLAINTEXT://192.168.1.1:9092
listener.security.protocol.map=PLAINTEXT:PLAINTEXT,SSL:SSL,SASL_PLAINTEXT:SASL_PLAINTEXT,SASL_SSL:SASL_SSL
" >> $FILE

FILE=/usr/lib/systemd/system/kafka.service
secure_file $FILE
rm $FILE
echo "
[Unit]
Description=Kafka publish-subscribe messaging system
Requires=zookeeper@kafka.service
After=network.target zookeeper@kafka.service
StartLimitIntervalSec=500
StartLimitBurst=5

[Service]
User=kafka
Group=kafka
SyslogIdentifier=kafka
ExecStart=/usr/bin/java \
  -Xmx1G -Xms1G -server \
  -XX:+UseG1GC \
  -XX:+DisableExplicitGC \
  -Djava.awt.headless=true \
  -verbose:gc \
  -Dcom.sun.management.jmxremote \
  -Dcom.sun.management.jmxremote.authenticate=false \
  -Dcom.sun.management.jmxremote.ssl=false \
  -Dkafka.logs.dir=/var/log/kafka \
  -Dlog4j.configuration=file:/etc/kafka/log4j.properties \
  -cp /usr/share/java/kafka/* \
  kafka.Kafka \
  /etc/kafka/server.properties
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target

" >> $FILE
systemctl daemon-reload
systemctl restart kafka.service zookeeper@kafka.service
