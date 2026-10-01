from typing import Any

import mdtpy
from mdtpy import reference
from mdtpy.rpc.restful import RESTfulAsyncRpcClient

# MDT Platform에 접속한다.
manager = mdtpy.connect("http://localhost:12985/instance-manager")

test = manager.instances['test']
data = test.parameters['Data']

BASE_URL = "http://localhost:12987"
OP_ENDPOINT = "/api/v1/operations/AddAndSleep"
inputs = {
    "Data": data,
    "IncAmount": 3,
    "SleepTime": 2.7
}
rest_client = RESTfulAsyncRpcClient(base_url=BASE_URL, op_endpoint=OP_ENDPOINT, inputs=inputs)
outputs = rest_client.call()
print("outputs=", outputs)
data.update_with_raw_value(outputs['Output'])

OP_ENDPOINT = "/api/v1/operations/ThicknessInspection"
inputs = {
    "UpperImage": reference("param:inspector:UpperImage"),
}
outputs = {
    "Defect": reference("oparg:inspector:ThicknessInspection:out:Defect")
}
rest_client = RESTfulAsyncRpcClient(base_url=BASE_URL, op_endpoint=OP_ENDPOINT,
                                    inputs=inputs, outputs=outputs)
outputs = rest_client.call()
print("outputs=", outputs)
defect = reference("oparg:inspector:ThicknessInspection:out:Defect")
defect.update_value(outputs['Defect'])