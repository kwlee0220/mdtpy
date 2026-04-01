import mdtpy

# 파일을 읽어 문자열로 변환
with open('/home/kwlee/tmp/output.json', 'r') as f:
  json_str = f.read()
  obj = mdtpy.basyx.serde.from_json(json_str)
  print(obj)