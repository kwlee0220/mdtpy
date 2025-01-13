from __future__ import annotations

import sys
from typing import Optional
import subprocess

from mdt.types import *
from mdt.types import Parameter, Input, Output, ElementReference


MDT_OPERATION_SERVER_ENDPOINT = "http://localhost:12987"
LOG_LEVEL:Optional[str] = None
CLIENT_CONFIG_PATH:Optional[str] = None

def list_instances(filter:Optional[str]=None) -> list[str]:
    filter_opt = f" --filter {filter}" if filter else ""
    loglevel_str = f" --loglevel {LOG_LEVEL}" if LOG_LEVEL else ""
    client_conf_opt = f" --client_conf {CLIENT_CONFIG_PATH}" if CLIENT_CONFIG_PATH else ""
    cmd:str = f"mdt list instances {filter_opt}{loglevel_str}{client_conf_opt}"
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        raise MDTCliError(result.stderr)
    return result.stdout.decode('utf-8').splitlines()


def add_instance(id:str, model_path:str, conf_path:str,
                 jar_path:Optional[str]=None,
                 port:Optional[int]=None,
                 logger:Optional[str]=None,
                 endpoint:Optional[str]=None):
    jar_path_str = f" --jar {jar_path}" if jar_path else ""
    port_str = f" --port {port}" if port else ""
    logger_str = f" --logger {logger}" if logger else ""
    ep_str = f" --endpoint {endpoint}" if endpoint else ""
    cmd:str = f"mdt add {id} -m {model_path} -c {conf_path}{jar_path_str}{port_str} " \
              f"{logger_str}{ep_str}"
    result = subprocess.run(cmd, shell=True, capture_output=True, check=True, encoding='utf-8')
    if result.returncode != 0:
        raise MDTCliError(result.stderr)


def remove_instance(id:str, endpoint:Optional[str]=None):
    ep_str = f" --endpoint {endpoint}" if endpoint else ""
    cmd:str = f"mdt remove {id}{ep_str}"
    result = subprocess.run(cmd, shell=True, capture_output=True, check=True, encoding='utf-8')
    if result.returncode != 0:
        raise MDTCliError(result.stderr)
    
    
def start_instance(id:str, all:bool=False, recursive:bool=False, nowait:bool=False, thread_count:int=1,
                   poll_interval:str="1s", timeout:Optional[str]=None):
    all_opt = f" --all" if all else ""
    recursive_opt = f" --recursive" if recursive else ""
    thread_count_opt = f" --nthreads {thread_count}" if all else ""
    nowait_opt = f" --nowait" if nowait else ""
    poll_interval_pot = f" --poll {poll_interval}"
    timeout_opt = f" --timeout {timeout}" if all else ""
    loglevel_str = f" --loglevel {LOG_LEVEL}" if LOG_LEVEL else ""
    client_conf_opt = f" --client_conf {CLIENT_CONFIG_PATH}" if CLIENT_CONFIG_PATH else ""
    cmd:str = f"mdt start {id} {all_opt}{recursive_opt}{thread_count_opt}{nowait_opt}" \
                f"{poll_interval_pot}{timeout_opt}{loglevel_str}{client_conf_opt}"
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        raise MDTCliError(result.stderr)
    
    
def stop_instance(id:str, all:bool=False, recursive:bool=False, nowait:bool=False):
    all_opt = f" --all" if all else ""
    recursive_opt = f" --recursive" if recursive else ""
    nowait_opt = f" --nowait" if nowait else ""
    loglevel_str = f" --loglevel {LOG_LEVEL}" if LOG_LEVEL else ""
    client_conf_opt = f" --client_conf {CLIENT_CONFIG_PATH}" if CLIENT_CONFIG_PATH else ""
    cmd:str = f"mdt stop {id} {all_opt}{recursive_opt}{nowait_opt}{loglevel_str}{client_conf_opt}"
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        raise MDTCliError(result.stderr)
    
    
def get_element(ref:Parameter|Input|Output|ElementReference, output:str='value'):
    cmd:str = f"mdt get element {ref} -o {output}"
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        raise MDTCliError(result.stderr)
    return result.stdout.decode('utf-8')


def set_element(ref:Parameter|Input|Output|ElementReference, value:str|File):
    value_spec = None
    if isinstance(value, str):
        value_spec = f" --value {value}"
    elif isinstance(value, File):
        value_spec = f" --file {value.file_path}"
        if value.path:
            value_spec = f"{value_spec} --path {value.path}"
    else:
        raise ValueError(f'Unexpected value: f{value}')

    loglevel_str = f" --loglevel {LOG_LEVEL}" if LOG_LEVEL else ""
    client_conf_opt = f" --client_conf {CLIENT_CONFIG_PATH}" if CLIENT_CONFIG_PATH else ""
    cmd:str = f"mdt set {ref}{value_spec} {loglevel_str}{client_conf_opt}"
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        raise MDTCliError(result.stderr)


def copy(src_ref:Parameter|Input|Output|ElementReference, tar_ref:Parameter|Input|Output|ElementReference):
    loglevel_str = f" --loglevel {LOG_LEVEL}" if LOG_LEVEL else ""
    client_conf_opt = f" --client_conf {CLIENT_CONFIG_PATH}" if CLIENT_CONFIG_PATH else ""
    cmd:str = f"mdt copy {src_ref} {tar_ref}{loglevel_str}{client_conf_opt}"
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        raise MDTCliError(result.stderr)


def run_program(program_path:str):
    loglevel_str = f" --loglevel {LOG_LEVEL}" if LOG_LEVEL else ""
    client_conf_opt = f" --client_conf {CLIENT_CONFIG_PATH}" if CLIENT_CONFIG_PATH else ""
    cmd:str = f"mdt run program {program_path} {loglevel_str}{client_conf_opt}"
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        raise MDTCliError(result.stderr)
    

def replace_in_arg(arg_name:str):
    return arg_name.replace('in_', 'in.')
def replace_out_arg(arg_name:str):
    return arg_name.replace('out_', 'out.')
def run_http(op_id:str, server:str, poll_interval:Optional[str]=None, timeout:Optional[str]=None, **kwargs):
    loglevel_str = f" --loglevel {LOG_LEVEL}" if LOG_LEVEL else ""
    client_conf_opt = f" --client_conf {CLIENT_CONFIG_PATH}" if CLIENT_CONFIG_PATH else ""
    poll_interval_opt = f" --poll {poll_interval}" if poll_interval else ""
    timeout_opt = f" --timeout {timeout}" if timeout else ""
    extra_in_args = ' '.join([f'--{replace_in_arg(key)} {value}' for key, value in kwargs.items() if key.startswith('in_')])
    extra_out_args = ' '.join([f'--{replace_out_arg(key)} {value}' for key, value in kwargs.items() if key.startswith('out_')])
    cmd:str = f"mdt run http --server {server} --id {op_id} {poll_interval_opt}{timeout_opt}" \
                f"{loglevel_str}{client_conf_opt} {extra_in_args} {extra_out_args}"
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        raise MDTCliError(result.stderr)


import os
def main():
    start_instance('heater')
    # set_value('param:Test/0', '15')

    # os.chdir('/home/kwlee/mdt/models/innercase')
    # set_file('param:inspector/UpperIlluminanceImage', file='Innercase07-1.jpg')

    # os.chdir('/home/kwlee/mdt/models/innercase')
    # # run_program('program.json', logger='info')
    # run_http(op_id='test', submodel='Test/Simulation', timeout='5m', logger='info')

if __name__ == '__main__':
    main()

# mdt run http --server http://localhost:12987 --id inspector/UpdateDefectList \
# --in.Defect arg:inspector/ThicknessInspection/out/Defect  --in.DefectList param:inspector/DefectList --out.DefectList param:inspector/DefectList

# mdt run http --server http://localhost:12987 --id inspector/UpdateDefectList
