from mdtpy import connect
from mdtpy.model import MDTFile

# MDT 프레임워크 서버에 연결
mdt = connect()

# 'inspector' MDTInstance 가져오기
inspector = mdt.instances['inspector']

# 1. UpperImage 파라미터에 이미지 파일 설정
inspector.parameters['UpperImage'] = MDTFile('c:/mdt/models/innercase/test_images/Innercase01-1.jpg')

# 2. ThicknessInspection 연산 실행
thickness_op = inspector.operations['ThicknessInspection']
thickness_result = thickness_op(
    server="http://localhost:12987",
    in_UpperImage=inspector.parameters('UpperImage')
)

# 3. UpdateDefectList 연산 실행
update_defect_op = inspector.operations['UpdateDefectList']
update_defect_op(
    server="http://localhost:12987",
    in_Defect=thickness_op.outputs('Defect'),
    in_DefectList=inspector.parameters('DefectList'),
    out_DefectList=inspector.parameters('DefectList')
)

# 4. ProcessSimulation 연산 실행
process_sim_op = inspector.operations['ProcessSimulation']
process_sim_op(
    server="http://localhost:12987",
    in_DefectList=inspector.parameters('DefectList'),
    out_AverageCycleTime=inspector.parameters('CycleTime')
)
