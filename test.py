from mdtpy import connect
import time

# MDT 프레임워크 서버에 연결
mdt = connect()

# 'innercase' 인스턴스 찾기
instance = mdt.instances['innercase']

# 인스턴스 시작
print("Starting innercase instance...")
instance.start()

# 5초 대기
time.sleep(5)

# 인스턴스 중지
print("Stopping innercase instance...")
instance.stop()
