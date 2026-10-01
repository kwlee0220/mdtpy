from __future__ import annotations

import datetime

from basyx.aas import model

from ..submodel import SubmodelService
from ..ref import ElementReference
from ..value import ElementValue, update_element_with_raw_value, get_value, RawElementValueType
from ..aas_misc import OperationVariable
from ..exceptions import OperationError


# 오퍼레이터 호출에 사용되는 인자의 타입을 정의한다.
ArgumentType = ElementValue | RawElementValueType | ElementReference | model.SubmodelElement


class AASOperationService:
    """AAS ``Operation`` SubmodelElement 하나의 동기 호출을 담당하는 서비스.

    Submodel 내 특정 경로(``operation_path``)의 ``model.Operation`` 을 감싸,
    그 입력(``input_variable``)·입출력(``in_output_variable``)·출력(``output_variable``)
    변수를 :class:`~mdtpy.aas_misc.OperationVariable` 목록으로 보관한다.
    :meth:`invoke` 로 keyword 인자를 넘겨 연산을 동기 호출하고 출력 값을 돌려받는다.

    Attributes:
        in_op_variables (list[OperationVariable]): 입력 변수 목록.
        inout_op_variables (list[OperationVariable]): 입출력 변수 목록.
        out_op_variables (list[OperationVariable]): 출력 변수 목록.
    """
    def __init__(self, submodel_svc:SubmodelService, operation_path:str) -> None:
        """지정한 경로의 SubmodelElement 를 ``Operation`` 으로 검증하고 서비스를 초기화한다.

        Args:
            submodel_svc (SubmodelService): 대상 Operation 이 속한 Submodel 서비스.
            operation_path (str): Submodel 내에서 Operation 을 가리키는 id_short 경로.
        Raises:
            ValueError: ``operation_path`` 가 가리키는 SubmodelElement 가
                ``model.Operation`` 이 아닌 경우.
        """
        self.__submodel_svc = submodel_svc
        self.__operation_path = operation_path

        # Submodel 내에서 지정한 경로의 SubmodelElement 를 조회하고
        # ``model.Operation`` 인지 확인한다.
        op = submodel_svc.submodel_elements[operation_path]
        if not isinstance(op, model.Operation):
            raise ValueError(f"not an Operation: path={operation_path}, type={type(op).__name__}")

        self.in_op_variables = [ OperationVariable(value=var) for var in op.input_variable ]
        self.inout_op_variables = [ OperationVariable(value=var) for var in op.in_output_variable ]
        self.out_op_variables = [ OperationVariable(value=var) for var in op.output_variable ]

    def invoke(self, **kwargs: ArgumentType) -> dict[str, ElementValue]:
        """연산을 동기 호출하고 출력 값을 돌려준다.

        전달된 keyword 인자로 입력·입출력 변수를 갱신한 뒤 연산을 호출한다.
        각 인자 값의 형태에 따라 다음과 같이 반영된다.

        * :class:`~mdtpy.ref.ElementReference`: 참조가 가리키는 값을 읽어 반영.
        * :class:`~mdtpy.value.ElementValue`: 값을 그대로 반영.
        * ``model.SubmodelElement``: 변수의 ``id_short`` 를 보존한 채 요소 자체를 대체.
        * 그 외 raw 값(:data:`~mdtpy.value.RawElementValueType`): 원시 값으로 반영.

        Args:
            **kwargs (ArgumentType): 연산 인자 식별자(``id_short``)를 키로, 전달할 인자
                값을 값으로 하는 keyword 인자.
        Returns:
            dict[str, ElementValue]: 출력·입출력 인자 식별자를 키로 하는 결과 값 목록.
        Raises:
            OperationError: 연산 호출이 실패한 경우.
        """
        # 인자로 전달된 값을 OperationVariable의 값으로 업데이트한다.
        for opv in self.in_op_variables + self.inout_op_variables:
            var_id = str(opv.value.id_short)
            if var_id in kwargs:
                arg = kwargs[var_id]
                match arg:
                    case ElementReference():
                        arg.read_value().apply_to(opv.value)
                    case ElementValue():
                        arg.apply_to(opv.value)
                    case model.SubmodelElement():
                        # OperationVariable의 idshort가 연산 변수의 식별자로 사용되기 때문에
                        # SubmodelElement의 idshort를 덮어쓰지 않도록 보존한다.
                        arg_name = opv.value.id_short
                        opv.value = arg
                        opv.value.id_short = arg_name
                    case _:
                        update_element_with_raw_value(opv.value, arg)

        result = self.__submodel_svc.invoke_operation_sync(self.__operation_path,
                                                          self.in_op_variables,
                                                          self.inout_op_variables,
                                                          timeout=datetime.timedelta(days=7))
        if result.success:
            output_values:dict[str, ElementValue] = {}
            if result.output_op_variables is not None:
                for op_var in result.output_op_variables:
                    output_values[str(op_var.value.id_short)] = get_value(op_var.value)
            if result.inoutput_op_variables is not None:
                for op_var in result.inoutput_op_variables:
                    output_values[str(op_var.value.id_short)] = get_value(op_var.value)
            return output_values
        else:
            if result.messages:
                raise OperationError(f'Operation {self.__operation_path} failed: {result.messages}')
            else:
                raise OperationError(f'Operation {self.__operation_path} failed')
