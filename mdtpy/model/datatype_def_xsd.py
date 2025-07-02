from __future__ import annotations

from typing import Any, Optional
from datetime import datetime, timedelta


def from_xsd_to_python(type_xsd:str, value:Optional[str]) -> Any:
    if value is None:
        return None
    
    if type_xsd == 'xs:string':
        return value
    elif type_xsd == 'xs:int':
        return int(value) if value and len(value) > 0 else None
    elif type_xsd == 'xs:float':
        return float(value) if value and len(value) > 0 else None
    elif type_xsd == 'xs:boolean':
        return value == 'true'
    elif type_xsd == 'xs:dateTime':
        if value and value != '':
            from mdtpy.client.utils import iso8601_to_datetime  
            return iso8601_to_datetime(value)
        else:
            return None
    elif type_xsd == 'xs:duration':
        if value and value != '':
            from mdtpy.client.utils import iso8601_to_timedelta
            return iso8601_to_timedelta(value)
        else:
            return None
    else:
        raise ValueError(f"Unsupported DataTypeDefXsd: {type_xsd}")
    

def from_python_to_xsd(type_xsd:str, python_value:Optional[Any]) -> Optional[str]:
    if python_value is None:
        return None
    
    if type_xsd == 'xs:dateTime':
        assert isinstance(python_value, datetime)
        from mdtpy.client.utils import datetime_to_iso8601
        return datetime_to_iso8601(python_value)
    elif type_xsd == 'xs:duration':
        assert isinstance(python_value, timedelta)
        from mdtpy.client.utils import timedelta_to_iso8601
        return timedelta_to_iso8601(python_value) 
    else:
        return str(python_value)