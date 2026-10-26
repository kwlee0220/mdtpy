"""`PythonScriptOperator` 사용 예제.

Airflow 없이 `LocalDagContext`로 task 하나를 실행한다.

`collect_samples`: 시계열 Submodel에서 지정된 시각부터 `count`개의 전류 샘플을 읽어,
다음 조회 시작 시각(`next_time`) / 샘플 문자열(`samples`) / 완전한 배치 여부(`sampled`)를
출력한다. `next_time`은 `param:Welder:NextTime`에 기록되므로, 다시 실행하면 이전에 읽은
지점부터 이어서 읽는다. `samples`와 `sampled`는 저장 위치를 지정하지 않았으므로 기록 없이
후속 task에만 전달된다.

실제 파이프라인에 옮길 때의 주의: 이 예제는 수집 task에서 바로 커서(`next_time`)를 기록하므로,
후속 task가 샘플 처리에 실패하면 그 배치는 다시 읽히지 않는다. 모든 배치를 처리해야 한다면
커서 기록을 샘플을 소비하는 task가 성공한 뒤로 옮긴다.

script 작성 시 주의할 점 두 가지:

1. script의 전역에는 `inputs`(입력 이름 → `ElementValue`), 빈 dict `outputs`, builtins만
   주어진다. 그 외에 필요한 모듈·클래스는 script 안에서 직접 import해야 한다.
2. 출력은 `outputs` dict에 넣는다. 같은 이름의 변수에 대입하는 것만으로는 출력되지 않는다.
   `outputs` dict에 넣은 값은 모두 task 출력이 되고, operator의 `outputs` 인자는 그중 어떤 값을
   어디에 기록할지만 정한다. `ElementValue`를 넣으면 그대로 쓰이고, 원시 값을 넣으면
   `mdt_value()`로 변환된다.

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
    # 조회 범위가 시작 시각을 포함하므로(서버: ts >= since) 마지막 레코드를 다시 읽지 않도록
    # 1밀리초를 더한다. 서버는 since를 밀리초 단위로 잘라 비교하므로 이보다 촘촘한 커서는 쓸 수 없다.
    # 따라서 타임스탬프가 밀리초 단위로 유일하다고 가정한다(예: 고정 주기 샘플링). 같은 시각의
    # 레코드가 여러 개이면 배치 경계에서 일부가 누락될 수 있다.
    next_ts = last_time + timedelta(milliseconds=1)
else:
    # 배치를 채우지 못했으므로 다음 실행이 같은 지점에서 다시 시도한다.
    next_ts = start_time
print(f'next_time={next_ts}', flush=True)

# outputs dict에 넣은 값은 모두 후속 task에 전달된다.
# 그중 operator의 outputs 인자에 저장 위치를 지정한 'next_time'만 기록된다.
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
        # 'samples'/'sampled'는 선언하지 않아도 후속 task에 전달된다.
    }
).run(ctx)
print(ctx)
for name in ('next_time', 'samples', 'sampled'):
    print(f'{name}: {ctx.get_task_output("collect_samples", name)}')
