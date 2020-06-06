Kafka configuration
===================

`Apache Kafka <https://kafka.apache.org/>`__ is a distributed streaming
platform. It is useful for building real-time streaming data pipelines
to get data between the systems or applications. Another useful feature
is real-time streaming applications that can transform streams of data
or react on a stream of data.

GNU/Linux
---------

Arch Linux
~~~~~~~~~~

.. code:: ipython3

    $ yay -S kafka
    $ sudo pip install kafka-python 

Ubuntu
~~~~~~

A very useful guide (and recomended) can be readed in
`tecadmin.net <https://tecadmin.net/install-apache-kafka-ubuntu/>`__,
just follow it until step 3.

**TL;DR**

.. code:: ipython3

    $ sudo apt update
    $ sudo apt install default-jdk
    
    $ wget http://www-us.apache.org/dist/kafka/2.4.0/kafka_2.13-2.4.0.tgz
        
    $ tar xzf kafka_2.13-2.4.0.tgz
    $ mv kafka_2.13-2.4.0 /usr/local/kafka
    
    $ echo """[Unit]
    Description=Apache Zookeeper server
    Documentation=http://zookeeper.apache.org
    Requires=network.target remote-fs.target
    After=network.target remote-fs.target
    
    [Service]
    Type=simple
    ExecStart=/usr/local/kafka/bin/zookeeper-server-start.sh /usr/local/kafka/config/zookeeper.properties
    ExecStop=/usr/local/kafka/bin/zookeeper-server-stop.sh
    Restart=on-abnormal
    
    [Install]
    WantedBy=multi-user.target""" >> /etc/systemd/system/zookeeper.service
    
    $ echo """[Unit]
    Description=Apache Kafka Server
    Documentation=http://kafka.apache.org/documentation.html
    Requires=zookeeper.service
    
    [Service]
    Type=simple
    Environment="JAVA_HOME=/usr/lib/jvm/java-1.11.0-openjdk-amd64"
    ExecStart=/usr/local/kafka/bin/kafka-server-start.sh /usr/local/kafka/config/server.properties
    ExecStop=/usr/local/kafka/bin/kafka-server-stop.sh
    
    [Install]
    WantedBy=multi-user.target
    """ >> /etc/systemd/system/kafka.service
    
    $ systemctl daemon-reload

Daemon
~~~~~~

Start daemon, on ``Ubuntu`` must be ``zookeeper.service`` instead of
``zookeeper@kafka.service``.

.. code:: ipython3

    systemctl enable kafka.service zookeeper@kafka.service
    systemctl start kafka.service zookeeper@kafka.service

Create topic, on ``Ubuntu`` the complete path moust be specified:
``/usr/local/kafka/bin/kafka-topics.sh``

.. code:: ipython3

    kafka-topics.sh --zookeeper localhost:2181 --delete --topic binary
    kafka-topics.sh --zookeeper localhost:2181 --delete --topic beeg
    kafka-topics.sh --zookeeper localhost:2181 --delete --topic marker
    
    kafka-topics.sh --create --zookeeper localhost:2181 --replication-factor 1 --partitions 1 --topic binary
    kafka-topics.sh --create --zookeeper localhost:2181 --replication-factor 1 --partitions 1 --topic eeg
    kafka-topics.sh --create --zookeeper localhost:2181 --replication-factor 1 --partitions 1 --topic marker

Change retention

.. code:: ipython3

    kafka-configs.sh --zookeeper localhost:2181  --entity-type topics --entity-name binary --alter --add-config retention.ms=1000
    kafka-configs.sh --zookeeper localhost:2181  --entity-type topics --entity-name eeg --alter --add-config retention.ms=1000
    kafka-configs.sh --zookeeper localhost:2181  --entity-type topics --entity-name marker --alter --add-config retention.ms=1000

Windows
-------

Who cares
