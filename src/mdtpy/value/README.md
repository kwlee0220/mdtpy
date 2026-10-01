# mdtpy.value — SubmodelElement 값 모델 패키지

SubmodelElement 의 **값**을 표현하는 `ElementValue` 클래스 계층과, 값을 여러 외부
표현(원시 Python 값 / JSON / basyx SME)과 상호 변환하는 기능을 제공한다.
`ref.read_value()`, `parameters[...]`, 연산 인자 등 mdtpy 의 모든 값 읽기/쓰기가
이 패키지의 타입을 주고받는다.

## 값 클래스 한눈에 보기

| SME 종류 | 값 클래스 | 성격 |
|---|---|---|
| Property | `PropertyValue` | 스칼라 (`.value`, `.value_type`) |
| SubmodelElementCollection | `ElementCollectionValue` | 읽기 전용 `Mapping[str, Optional[ElementValue]]` |
| SubmodelElementList | `ElementListValue` | 읽기 전용 `Sequence[ElementValue]` (멤버 None 불가) |
| File | `FileValue` | `.content_type` + 파일명 `.value` |
| Range | `RangeValue` | `.min` / `.max` |
| MultiLanguageProperty | `MLPropertyValue` | `Mapping[str, str]` (언어 → 텍스트) |

## 활용 가이드 (이 패키지를 쓰는 코드 작성 시)

### 1. 값 읽기 — `read_value()` 는 원시 값이 아니라 `ElementValue` 를 반환한다

```python
v = instance.parameters['Status'].read_value()   # -> PropertyValue
print(v.value)             # 스칼라는 .value 로
raw = v.to_raw_object()    # 어떤 타입이든 원시 Python 표현으로 (재귀 변환)
```

컨테이너 값은 Mapping/Sequence 인터페이스로 바로 순회할 수 있다:

```python
coll = ref.read_value()                  # -> ElementCollectionValue
for key, member in coll.items():         # member: Optional[ElementValue]
    ...
qty = coll['QuantityProduced'].value     # 중첩 멤버 접근
```

### 2. 값 쓰기 — `update_value()` 는 `ElementValue`, 원시 값은 `update_with_raw_value()`

```python
import mdtpy

# 스칼라: mdt_value() 로 감싼다 (str/bool/int/float/timedelta 지원)
ref.update_value(mdtpy.mdt_value('Running'))

# 원시 값을 그대로 쓰려면
ref.update_with_raw_value('Running')

# 부분 갱신: 컨테이너 값 객체는 읽기 전용이므로,
# 원시 dict 를 만들어 update_with_raw_value 로 쓴다
raw = ref.read_value().to_raw_object()
raw['QuantityProduced'] += 10
ref.update_with_raw_value(raw)
```

### 3. 값 객체 직접 생성

```python
from basyx.aas import model
from mdtpy.value import PropertyValue, FileValue, MLPropertyValue, mdt_value

mdt_value(42)                                    # 타입 자동 판별 (bool 이 int 보다 우선)
PropertyValue(42, model.datatypes.Int)           # value_type 명시 (필수 인자)
FileValue.from_file_path('/path/img.jpg')        # MIME 타입 자동 추론
MLPropertyValue({'en': 'Welder', 'ko': '용접기'})
```

### 4. basyx SME 와의 상호 변환

```python
from mdtpy.value import get_value, update_element_with_raw_value

ev = get_value(sme)                        # SME -> ElementValue
ev.apply_to(other_sme)                     # ElementValue -> SME (타입 불일치 시 ValueError)
update_element_with_raw_value(sme, 42)     # 원시 값 -> SME (proto 기반 분배)
```

### 5. JSON 직렬화 — 용도에 맞는 쌍을 골라 쓴다

| 형식 | 직렬화 | 역직렬화 | 특징 |
|---|---|---|---|
| **`@type` polymorphic** (권장) | `to_json_node()` / `to_json_string()` | `parse_json_node()` / `parse_json_string()` | 자기 서술적(proto 불필요), 서버 `$value`·RPC 와 wire 호환 |
| bare wire (`@type` 없음) | `to_raw_json_node()` | `from_raw_json_node(value, proto)` | proto `ElementValue` 필요, 스칼라를 XSD 문자열화 |
| 원시 Python 객체 | `to_raw_object()` | `from_raw_object(value, proto)` | proto SME 필요, XSD 디코딩 없음 |

```python
from mdtpy.value import parse_json_string

json_str = ev.to_json_string()      # '{"@type": "mdt:value:integer", "value": 42}'
ev2 = parse_json_string(json_str)   # 왕복 보장
```

## 주의사항 (흔한 실수)

- **동등성은 값만 비교한다**: `PropertyValue(3, Int) == PropertyValue(3, Long)` 는
  `True` 다 (`value_type` 무시). Mapping/Sequence 계열은 평범한 dict/list 와도
  비교된다 (`MLPropertyValue({'en':'x'}) == {'en':'x'}` → `True`).
- **`None` 의 의미**:
  - `PropertyValue(None).apply_to(sme)` → SME 의 값을 **지운다**.
  - `update_element_with_raw_value(sme, None)` → Property 는 지우고, 그 외 타입은
    `ValueError`.
  - `from_raw_object` / `from_raw_json_node` 에 `None` 입력은 Property 계열 proto
    에서만 허용된다.
- **File 필드명이 표현마다 다르다**: 원시 Python 표현은 `content_type`(snake_case),
  JSON 두 형식은 `contentType`(camelCase).
- **MLP 표현도 형식마다 다르다**: 원시/bare-wire 는 평탄 `{lang: text}` dict,
  `@type` 형식은 `[{"lang": ..., "text": ...}]` 리스트.
- **컨테이너 값은 읽기 전용**: `coll['x'] = ...` 불가. 부분 갱신은 §2 의 원시 dict
  패턴을 쓴다.
- `MLPropertyValue` 는 생성 시 전달한 dict 를 **복사하지 않고 보관**하므로, 생성 후
  원본 dict 를 재사용/수정하지 않는 것이 안전하다.

## 패키지 구성

| 파일 | 내용 |
|---|---|
| `element_value.py` | `ElementValue` ABC + 6개 서브클래스, `mdt_value()`, `FileValue.from_file_path()` |
| `factory.py` | 역직렬화/생성 진입점: `get_value`, `from_raw_object`, `from_raw_json_node`, `parse_json_node`, `parse_json_string` |
| `codec.py` | `@type` 상수, XSD ↔ 타입 식별자 매핑, 스칼라 인코딩/디코딩 (내부용) |
| `types.py` | 타입 별칭 (`RawElementValueType`, `ElementJsonValueType`, `FileJsonValue` 등) |
| `__init__.py` | `update_element_with_raw_value()` + 공개 API 재수출 |

모든 공개 심볼은 `mdtpy.value.*` 와 `mdtpy.*` 최상위에서 접근할 수 있다.
상세 예제는 저장소 루트의 [`doc/programming_guide.md`](../../../doc/programming_guide.md) 참조.
