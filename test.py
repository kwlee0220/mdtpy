from __future__ import annotations

import os
from pathlib import Path

from mdtpy import connect
from mdtpy.model.mdt import *
from mdtpy.client.http_service_client import *


mdt = connect()
print(mdt.instances)

for inst in mdt.instances:
  print(inst)

print('------------------------------------------')
for inst in mdt.instances.find("instance.status = 'RUNNING' and submodel.semanticId like '%AI%'"):
  print(inst)
  
already_exists = 'test' in mdt.instances
if already_exists:
  if mdt.instances['test'].status == 'RUNNING':
    mdt.instances['test'].stop()
  
  del mdt.instances['test']
  assert 'test' not in mdt.instances

models_home = Path(os.environ['MDT_HOME']) / 'models'
test = mdt.instances.add('test', 19000, f'{models_home}/test')
mdt.instances['test'].start()

if not already_exists:
  mdt.instances['test'].stop()
  mdt.instances.remove('test')

inspector = mdt.instances['inspector']
if inspector.status != 'RUNNING':
  inspector.start()
for sm in inspector.submodels:
  print(sm.id)

innercase = mdt.instances['innercase']
if innercase.status != 'RUNNING':
  innercase.start()
info_model:InformationModelServiceClient = innercase.submodels['InformationModel']
print(info_model.twinComposition)

data:DataService = inspector.submodels['Data']
for param in data.parameters:
  print(param)

inspection:AIService = inspector.submodels['UpdateDefectList']
for input in inspection.inputs:
  print(input)
for output in inspection.outputs:
  print(output)

# test = mdt.instances['test']
# print(test)

# data = mdt.submodels

# print(test.id)

# mdt_manager.instances.remove(test.id)