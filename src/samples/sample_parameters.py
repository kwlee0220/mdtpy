from typing import Any

import json

import mdtpy

manager = mdtpy.connect(url="http://localhost:12985/instance-manager")

# welder = manager.instances['Welder']
# parameters = welder.parameters

# status = parameters['Status']
# print(status.ref_string)
# print(status.id)
# print(status.model_type)
# print(status.id_short)
# print(status.value_type)
# print(status.read())
# v = status.read_value()
# print(v)
# status.update_value('Running' if v == 'IDLE' else 'IDLE')
# print(status.read_value())

# production = parameters['NozzleProduction']
# print(production.ref_string)
# print(production.id)
# print(production.model_type)
# print(production.id_short)
# print(production.value_type)
# print(production.read())

# v = production.read_value()
# v['QuantityProduced'] = v['QuantityProduced'] + 10   # type: ignore
# production.update_value(v)


# def param_to_dict(param: mdtpy.MDTParameter) -> dict[str,Any]:
#     value = param.read_value()
#     return { 'id': param.id, 'name': param.name, 'valueType': param.descriptor.value_type,'value': value }

# test = manager.instances['test']
# test_dict = test.descriptor.to_dict()
# params_dict = { param.id: param_to_dict(param) for param in test.parameters.values() }
# test_dict["parameters"] = params_dict
# print(json.dumps(test_dict))


process = manager.instances['HeatProcess']
wip_lot_list = process.parameters['WIPLotList'].read_value()
print(mdtpy.json_dumps(wip_lot_list))