from typing import Generator, Iterator

from mdtpy import connect
from mdtpy.model.timeseries import Record

mdt = connect()

welder = mdt.instances['welder']

x = welder.timeseries['WelderAmpereLog']
print(x.metadata)


segment = x.segment("Tail")
print(segment.Name)
print(segment.RecordCount)
print(segment.StartTime)
print(segment.EndTime)

try:
    # Find records with status=3 and collect until status=0
    waveform = []
    for record in segment.records:
        if int(record['State']) == 3:
            waveform = [record]
        elif int(record['State']) == 1 and waveform:
            waveform.append(record)
            break
        elif waveform:
            waveform.append(record)
    
    # Reverse the waveform
    waveform.reverse()
except StopIteration:
    print("No records found")

for rec in waveform:
    print(rec)