from __future__ import annotations
import os

import mdtpy
from mdtpy import ElementValue, ArgumentType
from mdtpy.ref import reference
from mdtpy.operation.aas_operation import AASOperationService


MDT_MANAGER_URL = "http://localhost:12985/instance-manager"
manager = mdtpy.connect(url=MDT_MANAGER_URL)

def call_add_and_sleep() -> None:
    test = manager.instances['test']
    add_and_sleep = test.operations['AddAndSleep']

    data_ref = reference("param:test:Data")
    inc_amount = 7
    sleep_time = 2.5

    op_submodel = manager.instances['test'].operations['AddAndSleep']
    op = AASOperationService(op_submodel, "Operation")
    results = op.invoke(Data=data_ref, IncAmount=inc_amount, SleepTime=sleep_time)

    print("AddAndSleep results:")
    for key, value in results.items():
        print(f"  {key}: {value.to_raw_object()}") 
    data_ref.update_value(results['Output'])

def call_count_records() -> None:
    test = manager.instances['test']

    # TimeSeries 데이터는 SubmodelElement를 직접 전달한다.
    timeseries_ref = reference("timeseries:Welder:NozzleProductionLog#last=7")
    timeseries = timeseries_ref.read()

    op_submodel = manager.instances['test'].operations['CountRecords']
    op = AASOperationService(op_submodel, "Operation")
    results = op.invoke(TimeSeriesData=timeseries)

    print("CountRecords results:")
    for key, value in results.items():
        print(f"  {key}: {value.to_raw_object()}")

def call_thickness_inspection() -> ElementValue:
    inspector = manager.instances['inspector']

    mdt_home:str = os.environ['MDT_HOME']
    image_file_path = f'{mdt_home}/models/innercase/inspector/test_images/Innercase05-1.jpg'
    upper_image = inspector.parameters['UpperImage']
    upper_image.put_attachment(image_file_path)
    upper_image_ref = reference("param:inspector:UpperImage")

    op_submodel = manager.instances['inspector'].operations['ThicknessInspection']
    op = AASOperationService(op_submodel, "Operation")
    results = op.invoke(UpperImage=upper_image_ref)

    print("ThicknessInspection results:")
    for key, value in results.items():
        print(f"  {key}: {value.to_raw_object()}") 
    return results['Defect']

def call_update_defect_list(defect:ArgumentType) -> None:
    inspector = manager.instances['inspector']
    defect_list_ref = reference("param:inspector:DefectList")

    op_submodel = manager.instances['inspector'].operations['UpdateDefectList']
    op = AASOperationService(op_submodel, "Operation")
    results = op.invoke(DefectList=defect_list_ref, Defect=defect)

    print("UpdateDefectList results:")
    for key, value in results.items():
        print(f"  {key}: {value.to_raw_object()}")
    defect_list_ref.update_value(results['UpdatedDefectList'])

def call_process_simulation() -> None:
    inspector = manager.instances['inspector']
    defect_list_ref = reference("param:inspector:DefectList")
    cycle_time_ref = reference("param:inspector:CycleTime")

    op_submodel = manager.instances['inspector'].operations['ProcessSimulation']
    op = AASOperationService(op_submodel, "Operation")
    results = op.invoke(DefectList=defect_list_ref)

    print("ProcessSimulation results:")
    for key, value in results.items():
        print(f"  {key}: {value.to_raw_object()}")
    cycle_time_ref.update_value(results['AverageCycleTime'])

def call_total_quantity_prediction() -> None:
    welder = manager.instances['Welder']
    nozzle_production_ref = reference("param:Welder:NozzleProduction")
    tqp_ref = reference("param:Welder:TotalQuantityPrediction")

    op_submodel = welder.operations['TotalQuantityPrediction']
    op = AASOperationService(op_submodel, "Operation")
    results = op.invoke(NozzleProduction=nozzle_production_ref)

    print("TotalQuantityPrediction results:")
    for key, value in results.items():
        print(f"  {key}: {value.to_raw_object()}")
    tqp_ref.update_value(results['TotalQuantityPrediction'])


def main():
    call_add_and_sleep()
    call_count_records()

    defect = call_thickness_inspection()
    call_update_defect_list(defect)
    call_process_simulation()

    call_total_quantity_prediction()

if __name__ == "__main__":
    main()