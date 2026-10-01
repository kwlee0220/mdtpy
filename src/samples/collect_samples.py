from __future__ import annotations

from typing import cast, Mapping, MutableMapping

import json
from datetime import timedelta, datetime

from basyx.aas.model.datatypes import DateTime

import mdtpy
from mdtpy import ElementValue, TimeSeriesService, utils, mdt_value, PropertyValue


def collect_sample(inputs:Mapping[str,ElementValue],
                   outputs:MutableMapping[str,ElementValue]) -> None:
    mdt_url = cast(str, inputs['mdt_url'].to_raw_object())
    print(f'mdt_url={mdt_url}', flush=True)

    timeseries_ref = cast(str, inputs['timeseries_ref'].to_raw_object())
    print(f'timeseries_ref={timeseries_ref}', flush=True)

    start_time = cast(datetime, inputs['start_time'].to_raw_object())
    if start_time == None:
        start_time = datetime.min
    print(f'start_time={start_time}', flush=True)
    count = cast(int, inputs['count'].to_raw_object())
    print(f'count={count}', flush=True)

    manager = mdtpy.connect(mdt_url)

    timeseries_ref_parts = timeseries_ref.split(':')
    print(f'instance={timeseries_ref_parts[0]}, submodel={timeseries_ref_parts[1]}', flush=True)

    inst = manager.instances[timeseries_ref_parts[0]]
    timeseries_sm = cast(TimeSeriesService, inst.submodel_services[timeseries_ref_parts[1]])
    records, _ = timeseries_sm.read_records_since(since=start_time, count=count)

    last_time: datetime | None = None
    ampere_list: list[float] = []
    for rec in records.values():
        last_time, ampere = rec['Time'].value, rec['Ampere'].value      # type: ignore
        ampere_list.append(ampere)
    print(f'last_time={last_time}, ampere_list={ampere_list}', flush=True)
    ampere_list_str = json.dumps(ampere_list)
    ampere_list_str = f'[{ampere_list_str}]'

    ok = len(records) >= count
    if ok:
        if last_time is None:
            raise ValueError('No records were collected while ok was true.')
        next_time = last_time + timedelta(milliseconds=1)
    else:
        next_time = start_time
    next_time = utils.datetime_to_iso8601(next_time)
    print(f'next_time={next_time}', flush=True)

    outputs['next_time'] = PropertyValue(next_time, DateTime)
    outputs['samples'] = mdt_value(ampere_list_str)
    outputs['sampled'] = mdt_value(ok)


def main():
    inputs = {
        'mdt_url': mdt_value("http://localhost:12985/instance-manager"),
        'timeseries_ref': mdt_value("Welder:WelderAmpereLog"),
        'start_time': PropertyValue(None, DateTime),
        'count': mdt_value(5),
        'sampled': mdt_value('sampled.txt'),
        'samples': mdt_value('samples.txt'),
        'next_time': mdt_value('next_time.txt'),
    }
    outputs = dict()
    collect_sample(inputs, outputs)
    print(outputs)

if __name__ == '__main__':
    main()