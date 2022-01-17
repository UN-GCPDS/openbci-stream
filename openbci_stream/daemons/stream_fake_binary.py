import pickle
from datetime import datetime

# import rawutil
import numpy as np
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

def aux_(values): return list(struct.pack(
    '>hhh', *(np.array(values) * (16 / 0.002)).astype(int).tolist()))

def eeg_(values): return [rawutil.pack('>u', v // 24)
                          for v in values.tolist()]


def t0(): return ((time.time() * 10) // 1)


# ----------------------------------------------------------------------
def main():
    """"""
    ti = t0()
    while True:

        if t0() >= ti + 1:
            aux_value = np.random.random(3)
            aux = aux_(aux_value / aux_value.sum())
            eeg = eeg_(np.random.randint(100, size=8))

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
