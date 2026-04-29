from __future__ import annotations

from datetime import datetime
import os

import mdtpy

test_images = ['Innercase01-1.jpg', 'Innercase01-2.jpg', 'Innercase01-3.jpg', 'Innercase01-4.jpg', 'Innercase01-5.jpg',
              'Innercase05-1.jpg', 'Innercase05-2.jpg','Innercase05-3.jpg','Innercase05-4.jpg', 'Innercase05-5.jpg',
              'Innercase07-1.jpg', 'Innercase07-2.jpg', 'Innercase07-3.jpg', 'Innercase07-4.jpg', 'Innercase07-5.jpg',
              'Innercase12-1.jpg', 'Innercase12-2.jpg', 'Innercase12-3.jpg', 'Innercase12-4.jpg', 'Innercase12-5.jpg',
              'Innercase13-1.jpg', 'Innercase13-2.jpg', 'Innercase13-3.jpg', 'Innercase13-4.jpg', 'Innercase13-5.jpg']

manager = mdtpy.connect(url="http://localhost:12985/instance-manager")
inspector = manager.instances['inspector']

inspection = inspector.operations['ThicknessInspection']
update = inspector.operations['UpdateDefectList']
simulate = inspector.operations['ProcessSimulation']

upper_image = inspector.parameters['UpperImage']
defect_list = inspector.parameters['DefectList']
cycle_time = inspector.parameters['CycleTime']
defect = inspection.output_arguments['Defect']


def inspect(image_file_path: str):
  # 표면 검사용 이미지 등록
  print(f"Inspecting {image_file_path}...")
  upper_image.put_attachment(image_file_path)
  
  started = datetime.now()
  inspection.invoke(UpperImage=upper_image, Defect=defect)
  update.invoke(DefectList=defect_list, Defect=defect, UpdatedDefectList=defect_list)
  simulate.invoke(DefectList=defect_list, AverageCycleTime=cycle_time)
  elapsed = datetime.now() - started
  print(f"Elapsed time: {elapsed.total_seconds():.3f} seconds")


def main():
    mdt_home:str = os.environ['MDT_HOME']
    dir:str = mdt_home + '/models/innercase/inspector/test_images/'
    for file_name in test_images:
        image_file_path = f'/home/kwlee/mdt/models/innercase/inspector/test_images/{file_name}'
        inspect(image_file_path)

if __name__ == '__main__':
    main()