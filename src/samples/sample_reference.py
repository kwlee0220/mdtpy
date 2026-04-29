
import mdtpy

manager = mdtpy.connect("http://localhost:12985/instance-manager")
instance = manager.instances['test']

ref = manager.resolve_reference('test:Data:DataInfo.Equipment.EquipmentParameterValues[0].ParameterValue')
print(ref.ref_string)
print(ref.model_type)
print(ref.id_short)

print(ref.read())
v = ref.read_value()
assert isinstance(v, int)
print(v)
ref.update_value(21)

ref = manager.resolve_reference('param:test:SleepTime')
print(ref.ref_string)
print(ref.model_type)
print(ref.id_short)
print(ref.value_type)
print(ref.read())
v = ref.read_value()
assert isinstance(v, float)
print(v)
ref.update_value(v + 1.1)

ref = manager.resolve_reference('param:inspector:UpperImage')
ref.put_attachment('/home/kwlee/tmp/Innercase05-3.jpg', 'image/jpg')

print(ref.model_type)
print(ref.read())
print(ref.read_value())
x = ref.get_attachment()

ref.delete_attachment()