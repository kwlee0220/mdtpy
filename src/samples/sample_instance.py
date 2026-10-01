from mdtpy.instance import MDTInstance


import mdtpy
import mdtpy.basyx.serde as basyx_serde

# MDT Platform에 접속한다.
manager = mdtpy.connect(url="http://localhost:12985/instance-manager")

# MDT Instance 목록을 출력한다.
for instance in manager.instances:
  print(f'instance: {instance.id}, aas-id={instance.aas_id}, '
        f'status={instance.status}, base-endpoint={instance.base_endpoint}')


# 'test' 인스턴스에 접속한다
test = manager.instances['test']

# MDTInstance의 등록정보를 Json으로 출력시킨다.
desc_dict = test.descriptor.to_dict()
print(f'descriptor: {desc_dict}')

# MDTInstance의 등록정보를 json 형태로 출력시킨다.
print(f'json: {test.descriptor.to_json()}')

# 중지된 상태가 아니라면 중지시킨다.
if test.is_running():
  test.stop()
  assert not test.is_running()

# 주요 등록 정보를 확인한다.
print(f'id: {test.id}')
print(f'status: {test.status}')
assert test.status == mdtpy.MDTInstanceStatus.STOPPED
print(f'base-endpoint: {test.base_endpoint}')
assert test.base_endpoint is None

# 'test' 인스턴스를 시작시킨다.
test.start()

# 주요 등록 정보를 출력한다.
print(f'id: {test.id}')
print(f'aas-id: {test.aas_id}')
print(f'aas-id-short: {test.aas_id_short}')
print(f'global-asset-id: {test.global_asset_id}')
print(f'asset-type: {test.asset_type}')
print(f'asset-kind: {test.asset_kind}')
print(f'status: {test.status}')
assert test.status == mdtpy.MDTInstanceStatus.RUNNING
print(f'base-endpoint: {test.base_endpoint}')
assert test.base_endpoint is not None

aas = test.read_asset_administration_shell()
print(f'aas: {aas}')
print(f'aas (json): {basyx_serde.to_json(aas)}')

found = list[MDTInstance](manager.instances.find("aasId='http://mdt.etri.re.kr/mdt/Test'"))
print(f'found: {found}')

found = list[MDTInstance](manager.instances.find("submodel.id='http://mdt.etri.re.kr/mdt/Test/sm/Data'"))
print(f'found: {found}')

print("----")
condition = f"parameter.id='CycleTime'"
print(f"list of instances with parameter.id='CycleTime'")
for inst in manager.instances.find(condition):
    print(f"Instance {inst.id}")