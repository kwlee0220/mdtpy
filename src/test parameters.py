import mdtpy

manager = mdtpy.connect(url="http://localhost:12985/instance-manager")
welder = manager.instances['Welder']
parameters = welder.parameters

status = parameters['Status']
print(status.ref_string)
print(status.id)
print(status.model_type)
print(status.id_short)
print(status.value_type)
print(status.read())
v = status.read_value()
print(v)
status.update_value('Running' if v == 'IDLE' else 'IDLE')
print(status.read_value())

production = parameters['NozzleProduction']
print(production.ref_string)
print(production.id)
print(production.model_type)
print(production.id_short)
print(production.value_type)
print(production.read())

v = production.read_value()
v['QuantityProduced'] = v['QuantityProduced'] + 10   # type: ignore
production.update_value(v)