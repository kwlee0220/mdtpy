
import mdtpy
from mdtpy import PropertyValue, ElementCollectionValue, FileValue, mdt_value
from mdtpy.ref import reference

manager = mdtpy.connect("http://localhost:12985/instance-manager")
instance = manager.instances['test']

# Default ElementReference
ref = reference('test:Data:DataInfo.Equipment.EquipmentParameterValues[0].ParameterValue')
print(f"type={type(ref)}, ref_string={ref.ref_string}, model_type={ref.model_type}")
print(f"element={ref.read()}")
smev = ref.read_value()
print(f"value={smev}")
assert isinstance(smev, PropertyValue)
print(smev.value)
v = mdt_value(int(smev.to_raw_object()) + 21)
ref.update_value(v)

# Parameter Reference
ref = reference('param:Welder:NozzleProduction')
print(f"type={type(ref)}, ref_string={ref.ref_string}, model_type={ref.model_type}")
print(f"element={ref.read()}")
v = ref.read_value()
print(f"value={v}")
assert isinstance(v, ElementCollectionValue)

# 'File' type reference
ref = reference('param:inspector:UpperImage')
print(f"type={type(ref)}, ref_string={ref.ref_string}, model_type={ref.model_type}")
ref.put_attachment('/home/kwlee/tmp/Innercase05-2.jpg', 'image/jpg')
print(ref.model_type)
print(ref.read())
print(ref.read_value())
x = ref.get_attachment()
ref.delete_attachment()

# Operation Argument Reference
ref = reference('oparg:inspector:ThicknessInspection:in:UpperImage')
print(f"type={type(ref)}, ref_string={ref.ref_string}, model_type={ref.model_type}")
print(f"element={ref.read()}")
smev = ref.read_value()
print(f"value={smev}")
assert isinstance(smev, FileValue)