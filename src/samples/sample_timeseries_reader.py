"""시계열 Submodel의 레코드를 지정된 시각부터 고정 크기 배치로 반복 조회하는 예제.

Java 예제 `mdt.sample.SampleTimeSeriesBatchReader`에 대응한다.

시작 시각 `T`부터 `N`개씩 레코드를 읽어 처리하는 것을 반복하며, 읽어온 레코드가 `N`개보다
적으면 **해당 배치를 처리하지 않고 버린 뒤** 프로그램을 종료한다. 즉 완전한 배치만 처리하고,
아직 `N`개가 쌓이지 않은 구간은 다음 실행으로 미룬다.

조회에 사용한 시작 시각은 `CURSOR_FILE`에 저장되므로, 프로그램을 다시 실행하면 이전에
중단된 지점부터 이어서 읽는다.

사용법: python sample_timeseries_reader.py [<start-timestamp>] <batch-size>

  python sample_timeseries_reader.py 2023-05-24T19:11:07Z 5   시작 시각을 지정하여 조회
  python sample_timeseries_reader.py 5                        저장된 시작 시각부터 이어서 조회
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, cast

import mdtpy
from mdtpy import AASOperationService, TimeSeriesService

MDT_MANAGER_URL = "http://localhost:12985/instance-manager"

#: 조회 대상 MDTInstance id.
INSTANCE_ID = 'Welder'
#: 조회 대상 시계열 Submodel의 idShort.
SUBMODEL_IDSHORT = 'WelderAmpereLog'
#: 배치마다 호출할 Operation Submodel의 idShort와 그 Submodel 내 Operation 경로.
OPERATION_IDSHORT = 'ProductionEstimation'
OPERATION_PATH = 'Operation'
#: 다음 조회에 사용할 시작 시각을 보관하는 파일.
CURSOR_FILE = Path('timeseries-cursor.txt')
#: 시계열 레코드의 시각 필드 이름.
TIME_FIELD = 'Time'
#: 시계열 레코드의 전류 필드 이름.
AMPERE_FIELD = 'Ampere'

Record = dict[str, Any]


def main() -> None:
    start_ts, batch_size = parse_args()

    manager = mdtpy.connect(url=MDT_MANAGER_URL)
    welder = manager.instances[INSTANCE_ID]

    # 전력 시계열 Submodel 서비스 가져오기
    ts_svc = cast(TimeSeriesService, welder.submodel_services[SUBMODEL_IDSHORT])
    op_svc = AASOperationService(welder.submodel_services[OPERATION_IDSHORT], OPERATION_PATH)

    batch_count, cursor = process_batches(ts_svc, op_svc, start_ts, batch_size)

    print(f"종료: 처리한 배치={batch_count}개, 다음 시작 시각={cursor} ({CURSOR_FILE.absolute()})")


def parse_args() -> tuple[datetime, int]:
    """명령행 인자를 해석하여 (시작 시각, 배치 크기)를 반환한다.

    인자는 `[<start-timestamp>] <batch-size>` 형태이다. 시작 시각이 생략되면 `CURSOR_FILE`에
    저장된 시작 시각을 사용한다.

    :return: (첫 배치의 시작 시각, 한 배치의 레코드 개수)
    """
    args = sys.argv[1:]
    if len(args) == 2:
        # 시작 시각이 주어진 경우는 해당 시각부터 조회한다.
        start_ts = parse_timestamp(args[0])
        batch_size = int(args[1])
    elif len(args) == 1:
        # 시작 시각이 없는 경우는 마지막으로 사용된 시작 시각부터 이어서 조회한다.
        batch_size = int(args[0])
        loaded = load_cursor()
        if loaded is None:
            print(f"저장된 시작 시각이 없습니다. 최초 실행에서는 시작 시각을 지정하십시오: "
                  f"file={CURSOR_FILE.absolute()}", file=sys.stderr)
            sys.exit(1)
        start_ts = loaded
    else:
        print(f"사용법: {Path(sys.argv[0]).name} [<start-timestamp>] <batch-size>", file=sys.stderr)
        sys.exit(1)
    if batch_size <= 0:
        print(f"batch-size는 1 이상이어야 합니다: {batch_size}", file=sys.stderr)
        sys.exit(1)

    return start_ts, batch_size


def process_batches(ts_svc: TimeSeriesService, op_svc: AASOperationService,
                    start_ts: datetime, batch_size: int) -> tuple[int, datetime]:
    """`start_ts`부터 `batch_size`개씩 레코드를 읽어 배치 단위로 처리한다.

    완전한 배치만 처리하며, 레코드가 `batch_size`개보다 적게 읽히면 그 배치를 버리고 반복을
    끝낸다. 매 배치를 조회하기 전에 시작 시각을 파일에 저장하므로, 중간에 중단되어도 다음
    실행이 같은 지점에서 재개한다.

    :param ts_svc: 조회 대상 시계열 Submodel의 서비스.
    :param op_svc: 배치마다 호출할 Operation의 서비스.
    :param start_ts: 첫 배치의 시작 시각(포함).
    :param batch_size: 한 배치의 레코드 개수.
    :return: (처리한 배치 개수, 다음 실행이 사용할 시작 시각)
    """
    cursor = start_ts
    batch_count = 0
    count = 0.0
    while True:
        # 조회에 사용할 시작 시각을 먼저 저장한다.
        # (배치가 중단되더라도 다음 실행이 같은 지점에서 재개할 수 있도록 한다)
        save_cursor(cursor)

        records = read_records(ts_svc, cursor, batch_size)
        if len(records) < batch_size:
            # 배치를 채울 만큼 레코드가 쌓이지 않았으므로 이 레코드 집합은 버리고 종료한다.
            print(f"불완전한 배치를 취소합니다: records={len(records)} < {batch_size}, start={cursor}")
            break

        batch_count += 1
        samples = samples_expr(records)

        outputs = op_svc.invoke(Samples=samples)
        score = cast(float, outputs['AnomalyScore'].to_raw_object())
        cluster = cast(str, outputs['Cluster'].to_raw_object())

        count += float(cluster)

        print(f"AnomalyScore={score:f}, Cluster={cluster}, Count={count:.1f}")

        # 마지막으로 읽은 레코드 다음 시각으로 커서를 옮긴다.
        cursor = next_cursor(records[-1])

    return batch_count, cursor


def read_records(ts_svc: TimeSeriesService, since: datetime, count: int) -> list[Record]:
    """`since` 시각(포함)부터 최대 `count`개의 레코드를 시각 오름차순으로 조회한다.

    :param ts_svc: 대상 시계열 Submodel의 서비스.
    :param since: 조회 시작 시각(포함).
    :param count: 읽어올 최대 레코드 개수.
    :return: 조회된 레코드 목록. 각 레코드는 필드 이름 → 값 사전이다.
    """
    records, _metadata = ts_svc.read_records_since(since=since, count=count)
    # 레코드는 `rec00`, `rec01`, ... 을 키로 갖는 사전으로 돌아온다. 키 이름에 의존하지 않도록
    # 시각 필드를 기준으로 정렬한다.
    return sorted(records.to_raw_object().values(), key=record_timestamp)  # type: ignore[arg-type]


def record_timestamp(record: Record) -> datetime:
    """레코드에서 시각 필드(`TIME_FIELD`)의 값을 읽어 반환한다.

    시각 필드가 projection에서 제외된 경우는 첫번째 필드를 시각으로 간주한다.
    """
    if TIME_FIELD in record:
        return record[TIME_FIELD]
    return next(iter(record.values()))


def record_ampere(record: Record) -> float:
    """레코드에서 전류 필드(`AMPERE_FIELD`)의 값을 읽어 반환한다.

    전류 필드가 projection에서 제외된 경우는 두번째 필드를 전류로 간주한다.
    """
    if AMPERE_FIELD in record:
        return float(record[AMPERE_FIELD])
    return float(list(record.values())[1])


def next_cursor(last_record: Record) -> datetime:
    """주어진 레코드 다음 배치의 시작 시각을 계산한다.

    조회 범위가 시작 시각을 포함하므로 마지막 레코드의 시각을 그대로 사용하면 같은 레코드를
    다시 읽게 된다. 조회 질의의 시각 리터럴이 밀리초 단위로 표현되기 때문에 1밀리초를 더해
    다음 시각을 만든다. (따라서 마지막 레코드와 **같은 밀리초**에 기록된 레코드는 건너뛴다)
    """
    return record_timestamp(last_record) + timedelta(milliseconds=1)


def samples_expr(records: list[Record]) -> str:
    """레코드 목록의 전류 값을 Operation 입력 문자열 `[[v1,v2,...]]`로 만든다."""
    values = ','.join(str(record_ampere(record)) for record in records)
    return f"[[{values}]]"


def parse_timestamp(text: str) -> datetime:
    """ISO 8601 시각 문자열을 `datetime`으로 파싱한다.

    Python 3.10의 `datetime.fromisoformat`은 `Z` 접미사를 받지 않기 때문에 `+00:00`으로
    바꿔준다. 시간대가 없는(naive) 문자열은 그대로 두는데, 시계열 레코드의 시각 필드도
    naive로 오기 때문에 커서 왕복이 어긋나지 않게 하려면 변환하지 않아야 한다.
    """
    normalized = text[:-1] + '+00:00' if text.endswith('Z') else text
    return datetime.fromisoformat(normalized)


def load_cursor() -> Optional[datetime]:
    """마지막으로 사용된 시작 시각을 파일에서 읽어 반환한다.

    :return: 저장된 시작 시각. 저장된 값이 없으면 `None`.
    """
    if not CURSOR_FILE.exists():
        return None

    cursor_str = CURSOR_FILE.read_text(encoding='utf-8').strip()
    return parse_timestamp(cursor_str) if cursor_str else None


def save_cursor(cursor: datetime) -> None:
    """조회에 사용할 시작 시각을 파일에 저장한다."""
    CURSOR_FILE.write_text(cursor.isoformat(), encoding='utf-8')


if __name__ == "__main__":
    main()
