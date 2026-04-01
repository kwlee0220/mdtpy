from __future__ import annotations

from datetime import datetime
import os

import mdtpy
from mdtpy.airflow import LocalDagContext, reference, task_output
from mdtpy.airflow import AASOperationTaskInvocation, SetElementInvocation


MDT_MANAGER_URL = "http://localhost:12985/instance-manager"
manager = mdtpy.connect(url=MDT_MANAGER_URL)

inspector = manager.instances['inspector']
if not inspector.is_running():
  inspector.start()
  assert inspector.is_running()

mdt_home:str = os.environ['MDT_HOME']
image_file_path = f'{mdt_home}/models/innercase/inspector/test_images/Innercase05-1.jpg'
upper_image = inspector.parameters['UpperImage']
upper_image.put_attachment(image_file_path)

dag_context = LocalDagContext("inspect_image", MDT_MANAGER_URL)
inspection = AASOperationTaskInvocation(
  instance = "inspector",
  submodel = "ThicknessInspection",
  argument_specs = {
    'inputs': {
      "UpperImage": reference("param:inspector:UpperImage")
    }
  }
).run(dag_context)
print(dag_context)

dag_context = LocalDagContext("update_defect_list", MDT_MANAGER_URL)
update_defect_list = AASOperationTaskInvocation(
  instance = "inspector",
  submodel = "UpdateDefectList",
  argument_specs = {
    'inputs': {
      'Defect': task_output("inspect_image", "Defect"),
      'DefectList': reference("param:inspector:DefectList"),
    },
    'outputs': {
      'UpdatedDefectList': reference("param:inspector:DefectList")
    }
  }
).run(dag_context)
print(dag_context)

dag_context = LocalDagContext("process_simulation", MDT_MANAGER_URL)
simulation = AASOperationTaskInvocation(
  instance = "inspector",
  submodel = "ProcessSimulation",
  argument_specs = {
    'inputs': {
      'DefectList': task_output("update_defect_list", "UpdatedDefectList")
    },
    'outputs': {
      'AverageCycleTime': reference("param:inspector:CycleTime")
    }
  }
).run(dag_context)
print(dag_context)

dag_context = LocalDagContext("get_heater_cycle_time", MDT_MANAGER_URL)
SetElementInvocation(
  argument_specs = {
    'inputs': {
      "source": reference("param:heater:CycleTime")
    }
  }
  ).run(dag_context)
print(dag_context)

dag_context = LocalDagContext("get_trimmer_cycle_time", MDT_MANAGER_URL)
SetElementInvocation(
  argument_specs = {
    'inputs': {
      "source": reference("param:trimmer:CycleTime")
    }
  }
  ).run(dag_context)
print(dag_context)

dag_context = LocalDagContext("get_former_cycle_time", MDT_MANAGER_URL)
SetElementInvocation(
  argument_specs = {
    'inputs': {
      "source": reference("param:former:CycleTime")
    }
  }
  ).run(dag_context)
print(dag_context)

dag_context = LocalDagContext("innercase_optimization", MDT_MANAGER_URL)
optimization = AASOperationTaskInvocation(
  instance = "innercase",
  submodel = "ProcessOptimization",
  argument_specs = {
    'inputs': {
      'HTCycleTime': task_output("get_heater_cycle_time", "target"),
      'PTCycleTime': task_output("get_trimmer_cycle_time", "target"),
      'VFCycleTime': task_output("get_former_cycle_time", "target"),
      'QICycleTime': task_output("process_simulation", "AverageCycleTime")
    },
    'outputs': {
      'TotalThroughput': reference("param:innercase:CycleTime")
    }
  }
).run(dag_context)
print(dag_context)