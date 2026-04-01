from typing import Generator, Iterator

import mdtpy

manager = mdtpy.connect(url="http://localhost:12985/instance-manager")

welder = manager.instances['Welder']
time_series = welder.timeseries

print(len(time_series))
ts = time_series['WelderAmpereLog'].timeseries()
print(ts.metadata)

print(ts.segments.keys())
seg = ts.segments['Tail']
print(seg.name)
print(seg.record_count)

# print(len(seg.records))
# for record in seg.records:
#   print(record.fields)

df = seg.records_as_pandas()
print(df)
  
