from typing import Generator, Iterator, cast

import mdtpy
from mdtpy import ElementCollectionValue, TimeSeriesService

manager = mdtpy.connect(url="http://localhost:12985/instance-manager")

welder = manager.instances['Welder']
# time_series = welder.timeseries

# print(len(time_series))
# ts = time_series['WelderAmpereLog'].timeseries()
# print(ts.metadata)

# print(ts.segments.keys())
# seg = ts.segments['Tail']
# print(seg.name)
# print(seg.record_count)

# # print(len(seg.records))
# # for record in seg.records:
# #   print(record.fields)

# df = seg.records_as_pandas()
# print(df)

ts_sm_svc = welder.submodel_services['WelderAmpereLog']
ts_sm_svc = cast(TimeSeriesService, ts_sm_svc)
records, metadata = ts_sm_svc.read_records_since(since="2023-06-01T00:00:00Z", count=10)
print(records)


def read_records_by_range(submodel_svc, ts_range: str) -> tuple[ElementCollectionValue, ElementCollectionValue]:
    from mdtpy import AASOperationService

    read_records_by_range = AASOperationService(submodel_svc, "ReadRecordsByRange")
    outputs = read_records_by_range.invoke(Range=ts_range)
    return outputs['Records'], outputs['RecordMetadata']  # type: ignore
  
