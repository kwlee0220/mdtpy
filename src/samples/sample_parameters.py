from typing import Any

import json

import mdtpy
from mdtpy.value import PropertyValue, mdt_value

manager = mdtpy.connect(url="http://localhost:12985/instance-manager")

welder = manager.instances['Welder']
parameters = welder.parameters

status = parameters['Status']
print(status.ref_string)
print(status.id)
print(status.model_type)
print(status.value_type)
print(status.read())
v = status.read_value()
print(v)
raw = 'Running' if v.to_raw_object() == 'IDLE' else 'IDLE'
status.update_value(mdt_value(raw))
print(status.read_value())

production = parameters['NozzleProduction']
print(production.ref_string)
print(production.id)
print(production.model_type)
print(production.value_type)
print(production.read())

v = production.read_value().to_raw_object()
v['QuantityProduced'] = v['QuantityProduced'] + 10   # type: ignore
production.update_with_raw_value(v)

test = manager.instances['test']
test_dict = test.descriptor.to_dict()
params_dict = { param.id: param.read_value().to_raw_object() for param in test.parameters.values() }
test_dict["parameters"] = params_dict
print(json.dumps(test_dict))