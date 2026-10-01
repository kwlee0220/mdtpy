from typing import Any

import json

import mdtpy
from mdtpy import reference


def param_to_dict(param: mdtpy.MDTParameter) -> dict[str,Any]:
    return { 'id': param.id, 'name': param.name, 'valueType': param.value_type }

def op_to_dict(op_svc: mdtpy.OperationSubmodelService) -> dict[str,Any]:
    op_desc = op_svc.operation_descriptor
    op_type = op_desc.operation_type

    in_args_dict = dict[str,Any]()
    for arg_desc in op_desc.input_arguments:
        arg = reference(arg_desc.reference)
        in_args_dict[arg_desc.id] = arg.read_value().to_raw_object()

    out_args_dict = dict[str,Any]()
    for arg_desc in op_desc.output_arguments:
        arg = reference(arg_desc.reference)
        out_args_dict[arg_desc.id] = arg.read_value().to_raw_object()

    return { 'id': op_svc.id_short, 'type': op_type,
             'input_arguments': in_args_dict, 'output_arguments': out_args_dict }


def _instance_to_dict(inst: mdtpy.MDTInstance) -> dict[str,Any]:
    result_dict = inst.descriptor.to_dict()

    param_list = [param_to_dict(param) for param in inst.parameters.values()]
    result_dict['parameters'] = param_list

    op_list = [op_to_dict(op) for op in inst.operations.values()]
    result_dict['operations'] = op_list

    return result_dict


manager = mdtpy.connect("http://localhost:12985/instance-manager")

inspector = manager.instances['inspector']
result_dict = _instance_to_dict(inspector)
print(json.dumps(result_dict, indent=2))