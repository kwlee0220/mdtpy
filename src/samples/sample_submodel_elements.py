import mdtpy

manager = mdtpy.connect("http://localhost:12985/instance-manager")
instance = manager.instances['inspector']

svc = instance.submodel_services["Data"]

sm = svc.read()
print(sm)

sme = svc.submodel_elements["DataInfo.Equipment.EquipmentParameters[0].ParameterID"]
print(str(sme.id_short), sme.value)