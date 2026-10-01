from __future__ import annotations

from datetime import datetime
import os

import mdtpy
from mdtpy import MDTInstance
from mdtpy.airflow import LocalDagContext, reference, task_output, sink
from mdtpy.airflow import OperationSubmodelOperator, SetElementOperator
from mdtpy.airflow.dag_task_argument import literal
from mdtpy.airflow.operator import AASOperationOperator, RestfulAsyncRpcOperator

import logging
logger = logging.getLogger(__name__)

MDT_MANAGER_URL = "http://localhost:12985/instance-manager"
manager = mdtpy.connect(url=MDT_MANAGER_URL)

def start_if_not_running(inst_id) -> MDTInstance:
    instance = manager.instances[inst_id]
    if not instance.is_running():
        logger.info(f"Starting MDT instance '{inst_id}'...")
        instance.start()
        assert instance.is_running()
    return instance

test = start_if_not_running('test')
Welder = start_if_not_running('Welder')
inspector = start_if_not_running('inspector')
start_if_not_running('heater')
start_if_not_running('former')
start_if_not_running('trimmer')
start_if_not_running('innercase')

mdt_home:str = os.environ['MDT_HOME']
image_file_path = f'{mdt_home}/models/innercase/inspector/test_images/Innercase05-1.jpg'
upper_image = inspector.parameters['UpperImage']
upper_image.put_attachment(image_file_path)

inspection = AASOperationOperator(
    instance = "inspector",
    submodel = "ThicknessInspection",
    path = "Operation",
    inputs = {
        "UpperImage": reference("param:inspector:UpperImage")
    }
).run(LocalDagContext("inspect_image", MDT_MANAGER_URL))

update_defect_list = RestfulAsyncRpcOperator(
    base_url = "http://localhost:12987",
    op_endpoint = "/api/v1/operations/UpdateDefectList",
    inputs = {
        'Defect': task_output("inspect_image", "Defect"),
        'DefectList': reference("param:inspector:DefectList"),
    },
    outputs = {
        'UpdatedDefectList': sink("param:inspector:DefectList")
    }
).run(LocalDagContext("update_defect_list", MDT_MANAGER_URL))

simulation = OperationSubmodelOperator(
    instance = "inspector",
    submodel = "ProcessSimulation",
    inputs = {
        'DefectList': task_output("update_defect_list", "UpdatedDefectList")
    },
    outputs = {
        'AverageCycleTime': sink("param:inspector:CycleTime")
    }
).run(LocalDagContext("process_simulation", MDT_MANAGER_URL))

dag_context = LocalDagContext("count_records", MDT_MANAGER_URL)
count_records = RestfulAsyncRpcOperator(
    base_url = "http://localhost:12987",
    op_endpoint = "/api/v1/operations/CountRecords",
    inputs = {
        'TimeSeriesData': reference("timeseries:Welder:NozzleProductionLog#last=50s|Time,QuantityProduced"),
    }
).run(dag_context)
count_records = OperationSubmodelOperator(
    instance = "test",
    submodel = "CountRecords",
    inputs = {
        'TimeSeriesData': reference("timeseries:Welder:NozzleProductionLog#last=50s|Time,QuantityProduced"),
    }
).run(dag_context)
print(dag_context)

dag_context = LocalDagContext("get_heater_cycle_time", MDT_MANAGER_URL)
SetElementOperator(
    inputs = {'source': reference("param:heater:CycleTime")}
).run(dag_context)
print(dag_context)

dag_context = LocalDagContext("get_trimmer_cycle_time", MDT_MANAGER_URL)
SetElementOperator(
    inputs = {'source': reference("param:trimmer:CycleTime")}
).run(dag_context)

dag_context = LocalDagContext("get_former_cycle_time", MDT_MANAGER_URL)
SetElementOperator(
    inputs = {'source': reference("param:former:CycleTime")}
).run(dag_context)

dag_context = LocalDagContext("innercase_optimization", MDT_MANAGER_URL)
optimization = OperationSubmodelOperator(
    instance = "innercase",
    submodel = "ProcessOptimization",
    inputs = {
        'HTCycleTime': task_output("get_heater_cycle_time", "target"),
        'PTCycleTime': task_output("get_trimmer_cycle_time", "target"),
        'VFCycleTime': task_output("get_former_cycle_time", "target"),
        'QICycleTime': task_output("process_simulation", "AverageCycleTime")
    },
    outputs = {
        'TotalThroughput': sink("param:innercase:CycleTime")
    }
).run(dag_context)

inspection = AASOperationOperator(
    instance = "test",
    submodel = "AddAndSleep",
    path = "Operation",
    inputs = {
        "Data": task_output("get_heater_cycle_time", "target"),
        "IncAmount": task_output("count_records", "Count"),
        "SleepTime": literal(3.5)
    },
    outputs = {
        "Output": sink("param:test:Data")
    }
).run(LocalDagContext("add_and_sleep", MDT_MANAGER_URL))
