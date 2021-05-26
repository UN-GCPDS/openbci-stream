import pickle
import logging
import rawutil
import struct
import numpy as np
from datetime import datetime
from typing import Dict, Any
import time

from kafka import KafkaProducer

producer = KafkaProducer(bootstrap_servers=['localhost:9092'],
                         compression_type='gzip',
                         value_serializer=pickle.dumps,
                         )

id_ = 0
data = {}
data['context'] = {'daisy': False,
                   'boardmode': 'default',
                   'montage': {i: ch for i, ch in enumerate('Fp1,Fp2,T3,C3,C4,T4,O1,O2'.split(','))},
                   'connection': 'wifi',
                   'gain': [24, 24, 24, 24, 24, 24, 24, 24]
                   }


data['context']['created'] = datetime.now().timestamp()

def aux_(v): return list(struct.pack(
    '>hhh', *(np.array([v / 3] * 3) * (16 / 0.002)).astype(int).tolist()))

def eeg_(v): return list(rawutil.pack('>u', -v // 24)) * 8
def t0(): return ((time.time() * 10) // 1)


# ----------------------------------------------------------------------
def main():
    """"""
    ti = t0()
    while True:

        if t0() >= ti + 1:

            if (time.time() // 1) % 2:
                aux = aux_(1)
                eeg = eeg_(1)
            else:
                aux = aux_(-1)
                eeg = eeg_(-1)

            data['context']['created'] = datetime.now().timestamp()
            data['data'] = [0xa0,  # header
                            id_ % 256,  # ID 0-255
                            *eeg,
                            *aux,
                            0xc0,  # footer
                            ] * 100

            data['data'] = bytes(data['data'])

            producer.send('binary', data)
            print('.')
            ti += 1


if __name__ == '__main__':
    main()
