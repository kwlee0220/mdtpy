from typing import Any

import mdtpy

# MDT Platform에 접속한다.
manager = mdtpy.connect("http://localhost:12985/instance-manager")

# 'test' 트윈에 접속한다.
test = manager.instances['test']
if not test.is_running():
  test.start()
  assert test.is_running()

# 'AddAndSleep' AI Submodel을 획득한다.
op = test.operations['AddAndSleep']

# 'AddAndSleep' AI Submodel을 호출한다.
result = op.invoke(IncAmount=20)
print(result)
op.output_arguments['Output'].update_value(result['Output'])

# 'AddAndSleep' AI Submodel의 입력 인자를 업데이트한다.
op.input_arguments['Data'].update_value(result['Output'])