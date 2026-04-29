from typing import Any

import mdtpy

# MDT Platform에 접속한다.
manager = mdtpy.connect("http://localhost:12985/instance-manager")

test = manager.instances['test']
add_and_sleep = test.operations['AddAndSleep']

data = test.parameters['Data']
inc_amount = 7
sleep_time = add_and_sleep.input_arguments['SleepTime']

result = add_and_sleep.invoke(Data=data, IncAmount=inc_amount, SleepTime=sleep_time, Output=data)
add_and_sleep.output_arguments.update_value(result)