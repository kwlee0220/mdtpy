"""
MQTT로 "test" 트윈의 'Data' 파라미터를 연속 갱신할 때 걸리는 시간을 측정한다.

1. "test" 트윈의 동작 상태를 출력한다.
2. 'Data' 파라미터 값을 0으로 초기화한다.
3. MQTT broker에 접속한다.
4. 시작 시각을 계측한다.
5. 'Data' 파라미터의 토픽에 1부터 1000까지의 JSON 값을 쉬지 않고 publish한다.
6. 'Data' 파라미터 값이 1000이 될 때까지 polling한 뒤, 시작 시각과의 차이(총 소요 시간)와
   그 값을 1000으로 나눈 시간(갱신 1회당 평균 시간)을 출력한다.

실행 중인 MDTInstanceManager와 MQTT broker가 필요하므로 pytest 테스트 함수는 두지 않고
스크립트로 실행한다::

    uv run python tests/test_perf_mqtt.py
"""
from __future__ import annotations

import json
import time

import paho.mqtt.client as mqtt

import mdtpy
from mdtpy.exceptions import RemoteError, ResourceNotFoundError

MANAGER_URL = "http://localhost:12985/instance-manager"
INSTANCE_ID = "test"
PARAMETER_ID = "Data"

MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = f"mdt/{INSTANCE_ID}/parameters/{PARAMETER_ID}"
PUBLISH_COUNT = 10000

POLL_INTERVAL = 0.1        # 초
POLL_TIMEOUT = 120.0        # 초. 이 시간 안에 마지막 값이 반영되지 않으면 실패로 끝낸다.


def main() -> None:
    manager = mdtpy.connect(MANAGER_URL)
    inst = manager.instances[INSTANCE_ID]

    # 파라미터 값은 트윈이 RUNNING일 때만 읽고 쓸 수 있다.
    if not inst.is_running():
        return
    param = inst.parameters[PARAMETER_ID]
    param.update_with_raw_value(0)
    initial = param.read_value().to_raw_object()
    print(f"{PARAMETER_ID} (initial): {initial}")
    print()
    
    # 이전 실행에서 밀린 MQTT 메시지가 아직 처리 중이면 초기화한 값이 덮어써져 측정이 틀어진다.
    if initial != 0:
        print("previous messages are still being applied; run again later")
        return

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_start()
    try:
        started = time.perf_counter()
        print(f"start time: {started:.3f}")
        for i in range(1, PUBLISH_COUNT + 1):
            info = client.publish(MQTT_TOPIC, json.dumps(i), qos=1)
            if i % 1000 == 0:
                print(f"published {i} messages")
            if i != PUBLISH_COUNT and i % 500 == 0:
                time.sleep(4.1) # 4.5s 대기
        published = time.perf_counter()
        print(f"published {PUBLISH_COUNT} messages: {published - started:.3f}s")

        # 갱신이 몰리는 동안 읽기가 서버 오류(RemoteError, ResourceNotFoundError)로 실패할 수 있다.
        # 세어 두고 계속 polling한다.
        read_errors = 0
        value = None
        deadline = started + POLL_TIMEOUT
        while True:
            try:
                value = param.read_value().to_raw_object()
            except (RemoteError, ResourceNotFoundError) as e:
                read_errors += 1
                if read_errors == 1:
                    print(f"read failed (retrying): {e}")
            now = time.perf_counter()
            if value == PUBLISH_COUNT:
                break
            if now >= deadline:
                print(f"timeout: {PARAMETER_ID}={value} after {POLL_TIMEOUT:.0f}s")
                return
            time.sleep(POLL_INTERVAL)
    finally:
        client.loop_stop()
        client.disconnect()

    print()
    now = time.perf_counter()
    elapsed = now - started
    print(f"{PARAMETER_ID}: {value}")
    print(f"finish time: {now:.3f}")
    print(f"elapsed: {elapsed:.3f}s")
    print(f"per update: {elapsed / PUBLISH_COUNT * 1000:.3f}ms")


if __name__ == "__main__":
    main()
