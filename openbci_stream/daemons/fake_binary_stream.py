import pickle
import logging
from datetime import datetime
from typing import Dict, Any

from kafka import KafkaProducer

producer = KafkaProducer(bootstrap_servers=['localhost:9092'],
                         compression_type='gzip',
                         value_serializer=pickle.dumps,
                         )

id_ = 0
data = {}
data['context'] = {'daisy': False,
                   'boardmode': 'default',
                   'montage': ['Fp1', 'Fp2', 'F3', 'Fz', 'F4', 'C3', 'C4', 'Cz'],
                   'connection': 'wifi',
                   'gain': [24, 24, 24, 24, 24, 24, 24, 24]
                   }


data['context']['created'] = datetime.now().timestamp()

producer.send('binary', data)


aux_high = [10, 106, 10, 106, 10, 106]  # 1/3 G
aux_low = [245, 150, 245, 150, 245, 150]  # -1/3 G

eeg_high = [0, 0, 100, 0, 0, 100, 0, 0, 100, 0, 0, 100,
            0, 0, 100, 0, 0, 100, 0, 0, 100, 0, 0, 100]  # 100 uv
eeg_low = [255, 255, 156, 255, 255, 156, 255, 255, 156, 255, 255, 156,
           255, 255, 156, 255, 255, 156, 255, 255, 156, 255, 255, 156]  # -100 uv


while True:

    now = datetime.now().timestamp()
    data['context']['created'] = now
    data['data'] = [0xa0,  # header
                    id_ % 256,  # ID 0-255



                    0xc0,  # footer
                    ]
