module {
    "name": "mdt",
    "description": "jq functions for having MDT framework"
};

def semantic_id_value:
    .semanticId.keys[0].value;

def submodels: .submodels;
def submodel(name): .submodels[] | select(.idShort == name);

def data_submodel:
    .submodels[]
    | select(semantic_id_value == "https://etri.re.kr/mdt/Submodel/Data/1/1")
    ;

def submodel_element(field_name):
    .submodelElements[] | select(.idShort == field_name);
def smc_field(field_name):
    .value[] | select(.idShort == field_name);
def sml_field(field_name; field_value):
    .value[]
    | select(
        .value[] as $node
        | $node.idShort == field_name and $node.value == field_value
    );

def parameter_values:
    submodel_element("DataInfo")
    | smc_field("Equipment")
    | smc_field("EquipmentParameterValues");
def parameters:
    parameter_values | .value[].value;

def parameter(name):
    parameter_values | sml_field("ParameterID"; name);

def add_type_info(accum):
    if .modelType == "Property" then
        accum["type"] = .valueType
    else
        if .modelType == "File  " then
            accum["type"] = "File" | 
            accum["contentType"] = .contentType
        end
    end;

def parameter_info:
    [ .[]
    | select(.idShort == "ParameterValue" or .idShort == "ParameterID") ]
    | sort_by(.idShort)
    | { "id": .[0].value, "type": .[1].valueType, "value": .[1].value };
def parameter_infos:
    [parameter_info];