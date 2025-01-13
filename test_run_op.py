from __future__ import annotations

import os

from mdtpy import connect
from mdtpy.model import MDTFile

MDT_OPERATION_SERVER = 'http://localhost:12987'

test_images = ['Innercase01-1.jpg', 'Innercase01-2.jpg', 'Innercase01-3.jpg', 'Innercase01-4.jpg', 'Innercase01-5.jpg',
              'Innercase05-1.jpg', 'Innercase05-2.jpg','Innercase05-3.jpg','Innercase05-4.jpg', 'Innercase05-5.jpg',
              'Innercase07-1.jpg', 'Innercase07-2.jpg', 'Innercase07-3.jpg', 'Innercase07-4.jpg', 'Innercase07-5.jpg',
              'Innercase12-1.jpg', 'Innercase12-2.jpg', 'Innercase12-3.jpg', 'Innercase12-4.jpg', 'Innercase12-5.jpg',
              'Innercase13-1.jpg', 'Innercase13-2.jpg', 'Innercase13-3.jpg', 'Innercase13-4.jpg', 'Innercase13-5.jpg']

mdt = connect()
inspector = mdt.instances['inspector']
inspection = inspector.operations['ThicknessInspection']
update = inspector.operations['UpdateDefectList']
simulate = inspector.operations['ProcessSimulation']

def inspect(image_file: MDTFile):
    # 표면 검사용 이미지 등록
    print(f"Inspecting {image_file}...")
    inspector.parameters['UpperImage'] = image_file
    
    inspection(server=MDT_OPERATION_SERVER, in_UpperImage=inspector.parameters('UpperImage'))
    update(server=MDT_OPERATION_SERVER, in_DefectList=inspector.parameters('DefectList'), in_Defect=inspection.outputs('Defect'),
                                        out_DefectList=inspector.parameters('DefectList'))
    simulate(server=MDT_OPERATION_SERVER, in_DefectList=inspector.parameters('DefectList'),
                                        out_AverageCycleTime=inspector.parameters('CycleTime'))

def main():
    mdt_home:str = os.environ['MDT_HOME']
    dir:str = mdt_home + '/models/innercase/inspector/ThicknessInspection/test_images/'
    for image_file_name in test_images:
        image_file = MDTFile(dir + image_file_name)
        inspect(image_file)

if __name__ == '__main__':
    main()