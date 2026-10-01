"""`PythonScriptOperator` 사용 예제.

Airflow 없이 `LocalDagContext`로 task 하나를 실행한다.

`collect_samples`: 시계열 Submodel에서 지정된 시각부터 `count`개의 전류 샘플을 읽어,
다음 조회 시작 시각(`next_time`) / 샘플 문자열(`samples`) / 완전한 배치 여부(`sampled`)를
출력한다. `next_time`은 `param:Welder:NextTime`에 기록되므로, 다시 실행하면 이전에 읽은
지점부터 이어서 읽는다.

script 작성 시 주의할 점 두 가지:

1. script의 전역에는 `inputs`(입력 이름 → `ElementValue`)와 builtins만 주어진다. 그 외에
   필요한 모듈·클래스는 script 안에서 직접 import해야 한다.
2. 출력은 script가 정의한 **변수**로 전달된다. `outputs` 같은 dict에 담는 것이 아니라,
   operator의 `outputs`에 선언한 이름과 같은 이름의 변수에 값을 대입하면 된다.
   `ElementValue`를 대입하면 그대로 쓰이고, 원시 값을 대입하면 `mdt_value()`로 변환된다.

`inputs[...]` 값은 raw 값이 아니라 `ElementValue`이므로, `to_raw_object()`로 원시 Python
값을 꺼내서 사용한다.
"""

from __future__ import annotations

from mdtpy.airflow import LocalDagContext, reference, task_output, literal, sink
from mdtpy.airflow import PythonScriptOperator

MDT_MANAGER_URL = "http://localhost:12985/instance-manager"


# --------------------------------------------------------------------------- #
# 전류 샘플 수집
# --------------------------------------------------------------------------- #
COLLECT_SAMPLES = """
from typing import cast
from datetime import datetime, timedelta
import json

from basyx.aas.model.datatypes import DateTime

import mdtpy
from mdtpy import PropertyValue, TimeSeriesService, mdt_value, utils

mdt_url = cast(str, inputs['mdt_url'].to_raw_object())
print(f'mdt_url={mdt_url}', flush=True)

timeseries_ref = cast(str, inputs['timeseries_ref'].to_raw_object())
print(f'timeseries_ref={timeseries_ref}', flush=True)

start_time = inputs['start_time'].to_raw_object()
if start_time is None:
    start_time = datetime.min
print(f'start_time={start_time}', flush=True)

count = cast(int, inputs['count'].to_raw_object())
print(f'count={count}', flush=True)

manager = mdtpy.connect(mdt_url)

instance_id, submodel_id_short = timeseries_ref.split(':')
print(f'instance={instance_id}, submodel={submodel_id_short}', flush=True)

inst = manager.instances[instance_id]
timeseries_sm = cast(TimeSeriesService, inst.submodel_services[submodel_id_short])
records, _ = timeseries_sm.read_records_since(since=start_time, count=count)

last_time = None
ampere_list = []
for rec in records.values():
    last_time, ampere = rec['Time'].value, rec['Ampere'].value
    ampere_list.append(ampere)
print(f'last_time={last_time}, ampere_list={ampere_list}', flush=True)
ampere_list_str = f'[{json.dumps(ampere_list)}]'

ok = len(records) >= count
if ok:
    if last_time is None:
        raise ValueError('No records were collected while ok was true.')
    # 조회 범위가 시작 시각을 포함하므로 마지막 레코드를 다시 읽지 않도록 1밀리초를 더한다.
    next_ts = last_time + timedelta(milliseconds=1)
else:
    # 배치를 채우지 못했으므로 다음 실행이 같은 지점에서 다시 시도한다.
    next_ts = start_time
print(f'next_time={next_ts}', flush=True)

# 출력은 operator의 outputs에 선언한 이름과 같은 이름의 변수에 대입한다.
outputs['next_time'] = PropertyValue(utils.datetime_to_iso8601(next_ts), DateTime)
outputs['samples'] = mdt_value(ampere_list_str)
outputs['sampled'] = mdt_value(ok)
"""

ctx = LocalDagContext("collect_samples", MDT_MANAGER_URL)
PythonScriptOperator(
    COLLECT_SAMPLES,
    inputs = {
        'mdt_url': literal(MDT_MANAGER_URL),
        'timeseries_ref': literal("Welder:WelderAmpereLog"),
        'start_time': reference("param:Welder:NextTime"),
        'count': literal(30),
    },
    outputs = {
        'next_time': sink("param:Welder:NextTime"),     # 기록하고 후속 task에 전달
    }
).run(ctx)
print(ctx)
print(ctx.get_task_output("collect_samples", "next_time"))
