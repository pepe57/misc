import json
import timerit

data = {
    'a': [1, 2, 3, 4],
    'b': [1, 2, 3, 4],
    'c': [1, 2, 3, 4],
    'd': [1, 2, 3, 4],
    'e': [1, 2, 3, 4],
    'f': [1, 2, 3, 4],
    'g': [1, 2, 3, 4],
    'h': [1, 2, 3, 4],
}

ti = timerit.Timerit(10000, bestof=10, verbose=2)

for timer in ti.reset('time'):
    with timer:
        with open('foobar1.json', 'w') as fh:
            fh.write(json.dumps(data))

for timer in ti.reset('time'):
    with timer:
        with open('foobar2.json', 'w') as fh:
            json.dump(data, fh)
