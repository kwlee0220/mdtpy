from __future__ import annotations

from typing import Any

import mdtpy
from mdtpy import ElementValue, ArgumentType
from mdtpy.ref import reference

MDT_MANAGER_URL = "http://localhost:12985/instance-manager"
manager = mdtpy.connect(url=MDT_MANAGER_URL)


def call_add_and_sleep() -> None:
    test = manager.instances['test']
    add_and_sleep = test.operations['AddAndSleep']

    data_ref = reference("param:test:Data")
    inc_amount = 7
    sleep_time = 2.5

    # results = add_and_sleep.invoke(Data=data_ref, IncAmount=inc_amount, SleepTime=sleep_time)
    results = add_and_sleep.invoke(Data=data_ref, SleepTime=sleep_time)

    print("AddAndSleep results:")
    for key, value in results.items():
        print(f"  {key}: {value.to_raw_object()}") 
    data_ref.update_value(results['Output'])


def call_count_records() -> None:
    test = manager.instances['test']
    count_records = test.operations['CountRecords']

    # TimeSeries 데이터는 SubmodelElement를 직접 전달한다.
    timeseries_ref = reference("timeseries:Welder:NozzleProductionLog#last=7")
    timeseries = timeseries_ref.read()

    results = count_records.invoke(TimeSeriesData=timeseries)

    print("CountRecords results:")
    for key, value in results.items():
        print(f"  {key}: {value.to_raw_object()}")

def call_thickness_inspection() -> ElementValue:
    inspector = manager.instances['inspector']
    inspection = inspector.operations['ThicknessInspection']

    import os
    mdt_home:str = os.environ['MDT_HOME']
    image_file_path = f'{mdt_home}/models/innercase/inspector/test_images/Innercase05-1.jpg'
    upper_image = inspector.parameters['UpperImage']
    upper_image.put_attachment(image_file_path)
    upper_image_ref = reference("param:inspector:UpperImage")
    
    results = inspection.invoke(UpperImage=upper_image_ref)

    print("ThicknessInspection results:")
    for key, value in results.items():
        print(f"  {key}: {value.to_raw_object()}") 
    return results['Defect']


def call_update_defect_list(defect:ArgumentType) -> None:
    inspector = manager.instances['inspector']
    update = inspector.operations['UpdateDefectList']

    defect_list_ref = reference("param:inspector:DefectList")
    results = update.invoke(DefectList=defect_list_ref, Defect=defect,
                            UpdatedDefectList=defect_list_ref)

    print("UpdateDefectList results:")
    for key, value in results.items():
        print(f"  {key}: {value.to_raw_object()}")


def call_process_simulation() -> None:
    inspector = manager.instances['inspector']
    simulation = inspector.operations['ProcessSimulation']

    defect_list_ref = reference("param:inspector:DefectList")
    cycle_time_ref = reference("param:inspector:CycleTime")
    avg_ct_ref = reference("param:inspector:CycleTime")
    results = simulation.invoke(DefectList=defect_list_ref, AverageCycleTime=avg_ct_ref)

    print("ProcessSimulation results:")
    for key, value in results.items():
        print(f"  {key}: {value.to_raw_object()}")


def call_total_quantity_prediction() -> None:
    welder = manager.instances['Welder']
    prediction = welder.operations['TotalQuantityPrediction']

    results = prediction.invoke(NozzleProduction=reference("param:Welder:NozzleProduction"),
                                TotalQuantityPrediction=reference("param:Welder:TotalQuantityPrediction"))
    print("TotalQuantityPrediction results:")
    for key, value in results.items():
        print(f"  {key}: {value.to_raw_object()}")

def main():
    call_add_and_sleep()
    call_count_records()

    defect = call_thickness_inspection()
    call_update_defect_list(defect)
    call_process_simulation()

    call_total_quantity_prediction()

if __name__ == "__main__":
    main()