import mdtpy
from mdtpy.descriptor import MDTInstanceStatus
from mdtpy import InvalidResourceStateError

manager = mdtpy.connect("http://localhost:12985/instance-manager")

for inst in manager.instances:
  print(f"Instance: {inst.id}")
  print(f"  Status: {inst.status}")
  print(f"  AAS_ID: {inst.aas_id}")
  print(f"  ServiceUrl: {inst.base_endpoint}")

for inst in manager.instances:
  try:
    inst.start()
    print(f"Started instance {inst.id}")
  except InvalidResourceStateError as e:
    assert (inst.status == MDTInstanceStatus.RUNNING
            or inst.status == MDTInstanceStatus.FAILED)
    print(f"Instance {inst.id} is already running.")