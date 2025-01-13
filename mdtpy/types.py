from __future__ import annotations

from typing import Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# class MDTCliError(Exception):
#     def __init__(self, msg):
#         self.message = msg.decode('utf-8') if isinstance(msg, bytes) else str(msg)
        
#     def __repr__(self):
#         return f"MDTCliError({self.message})"
    
# @dataclass(frozen=True, eq=True, unsafe_hash=True, slots=True)
# class Submodel:
#     instance_id: str
#     idshort: str

#     def parameters(self, param_spec:str|int):
#         pass


# @dataclass(frozen=True, eq=True, unsafe_hash=True, slots=True)
# class Parameter:
#     instance_id: str
#     id: str|int
    
#     @property
#     def to_ref(self) -> str:
#         return f"param:{self.instance_id}/{self.id}"
    
#     def __repr__(self) -> str:
#         return self.to_ref


# @dataclass(frozen=True, eq=True, unsafe_hash=True, slots=True)
# class Input:
#     instance_id: str
#     submodel: str
#     id: str|int
    
#     @property
#     def to_ref(self) -> str:
#         return f"arg:{self.instance_id}/{self.submodel}/in/{self.id}"
    
#     def __repr__(self) -> str:
#         return self.to_ref


# @dataclass(frozen=True, eq=True, unsafe_hash=True, slots=True)
# class Output:
#     instance_id: str
#     submodel: str
#     id: str|int
    
#     @property
#     def to_ref(self) -> str:
#         return f"arg:{self.instance_id}/{self.submodel}/out/{self.id}"
    
#     def __repr__(self) -> str:
#         return self.to_ref


@dataclass(frozen=True, eq=True, unsafe_hash=True, slots=True)
class ElementReference:
    instance_id: str
    submodel: str
    path: str
    
    @property
    def to_ref(self) -> str:
        return f"{self.instance_id}/{self.submodel}/{self.path}"
    
    def __repr__(self) -> str:
        return self.to_ref
    

@dataclass(frozen=True, eq=True, unsafe_hash=True, slots=True)
class File:
    file_path: str
    path: Optional[str] = field(default=None)
