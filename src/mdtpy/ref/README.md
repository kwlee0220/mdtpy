# mdtpy.ref — 요소 참조(Element Reference) 패키지

MDT 인스턴스 내부의 SubmodelElement 하나를 **참조 표현식 문자열**(`ref_string`)로
가리키고, 그 요소와 값을 읽고/쓰는 연산을 제공하는 패키지다. 참조 객체는 요소
자체를 보관하지 않으며, **생성 시점에는 어떤 HTTP 요청도 발생하지 않는다** —
원격 자원은 최초 접근 시 지연 해석되어 캐싱된다.

## 빠른 시작

```python
import mdtpy
from mdtpy.ref import reference

manager = mdtpy.connect("http://localhost:12985/instance-manager")

# 참조 생성 (HTTP 없음 — connect 이전에 만들어도 된다)
ref = reference("test/Data/DataInfo.Equipment.EquipmentID")

# 값 읽기/쓰기 — 전역 mdt_manager 를 통해 서버 측에서 해석된다
v = ref.read_value()                     # -> ElementValue
print(v.value)                            # 원시 값은 .value 로 접근
ref.update_value(mdtpy.mdt_value("KR3"))  # ElementValue 로 갱신
ref.update_with_raw_value("KR3")          # 원시 값으로 직접 갱신

# 요소(SubmodelElement) 단위 읽기/쓰기
sme = ref.read()
ref.write(sme)

# File 요소 첨부 파일 (대상 인스턴스가 실행 중이어야 한다)
ref.put_attachment("/path/to/image.jpg")
data = ref.get_attachment()
```

## 구성

| 파일 | 내용 |
|---|---|
| `reference.py` | `ElementReference` 추상 베이스(ABC). 요소/값 읽기·쓰기, 첨부 파일, 참조 serde 의 추상 인터페이스 정의 |
| `base_reference.py` | 구현체: `BaseElementReference`(단일 요소 참조) |
| `__init__.py` | `reference()` 팩토리, 서버 위임 참조 serde(`parse_reference_json_node` / `parse_reference_json_string`) |

## `BaseElementReference` — 연산별 HTTP 경로

연산에 따라 **서로 다른 두 HTTP 계층**을 사용한다:

| 경로 | 연산 | 요구 조건 |
|---|---|---|
| **매니저 경유** (전역 `mdt_manager` 의 참조 API) | `read` / `write` / `read_value` / `update_value` / `update_with_raw_value` / `to_json_node` / `to_json_string` | `mdtpy.connect()` 호출 완료 |
| **FA³ST 직접** (지연 해석된 `service_url`) | `add` / `remove` / `pathes()` / 첨부 파일 4종 | 대상 MDTInstance 가 **실행 중** |

- 대상 인스턴스가 실행 중이 아니면 `service_url` 이 `None` 일 수 있고, 이때
  `add` / `remove` 는 `RuntimeError` 를 발생시킨다.
- `mdtpy.connect()` 를 호출하지 않은 채 원격 연산에 접근하면 `RuntimeError`
  (`mdt_manager is not initialized`)가 발생한다.

### 지연 해석·캐싱되는 속성

| 속성 | 의미 | 캐싱 |
|---|---|---|
| `prototype` | 참조 대상 SubmodelElement (최초 `read()` 결과) | O |
| `service_url` | FA³ST 접근 URL | O (최초 해석 후) |
| `mdt_manager` | 전역 MDTInstanceManager | O |
| `semantic_id` / `model_type` / `value_type` | `prototype` 에서 유도 | (prototype 캐시 공유) |

최초 해석 이후에는 갱신되지 않으므로, 인스턴스를 재시작한 뒤에는 참조를 새로
만드는 것이 안전하다.

## 참조 묶음

여러 참조를 묶는 별도 클래스는 없다(이전의 `ElementReferenceDict`, 그 뒤의
`ArgumentList` 모두 제거됨). 연산 인자 묶음은 `operation/mdt_operation.py` 의
`build_argument_dict()` 가 만든 순수 `dict[str, Argument]` 로 노출되며, 개별
`Argument` 는 `BaseElementReference` 이므로 그 자체로 값 연산을 제공한다.

```python
op = instance.operations['Inspect']
value = op.input_arguments['UpperImage'].read_value()   # 개별 인자 값 읽기
op.output_arguments['Defect'].update_value(result['Defect'])  # 개별 인자 값 갱신
```

## 참조 serde

참조의 `@type` polymorphic JSON 변환은 **서버(매니저) 측에서** 수행된다:

```python
from mdtpy.ref import parse_reference_json_node

jnode = ref.to_json_node()                # ref_string -> JSON (매니저 질의, 캐싱)
ref2 = parse_reference_json_node(jnode)   # JSON -> ElementReference (매니저 질의)
```

두 방향 모두 연결된 전역 `mdt_manager` 가 필요하다.

## 관련 클래스

- `mdtpy.parameter.MDTParameter` — `BaseElementReference` 상속 (파라미터 참조)
- `mdtpy.operation.Argument` — 연산 인자 참조 (`build_argument_dict` 가 `dict` 로 묶음)
- `mdtpy.timeseries` — 세그먼트/메타데이터 접근에 `BaseElementReference` 사용

상세 사용 예제는 저장소 루트의 [`doc/programming_guide.md`](../../../doc/programming_guide.md) 참조.
