from __future__ import annotations

from ..submodel import SubmodelService
from ..descriptor import MDTOperationDescriptor, MDTSubmodelDescriptor
from ..ref import ElementReference, reference
from ..value import ElementValue
from ..exceptions import OutputWriteError
from .aas_operation import AASOperationService, ArgumentType


class OperationSubmodelService(SubmodelService):
    """MDT ``Operation`` Submodel 하나를 감싸 연산 호출을 담당하는 서비스.

    연산 등록정보(:class:`~mdtpy.descriptor.MDTOperationDescriptor`)에 기술된
    입력·출력 인자 정의를 바탕으로, 호출 시 지정되지 않은 입력 인자는 등록정보의
    기본 참조(:class:`~mdtpy.ref.ElementReference`)로 채우고, 출력 인자로 참조가
    주어지면 결과 값을 그 참조 위치에 반영한다. 실제 동기 호출은 내부
    :class:`~mdtpy.operation.AASOperationService` 에 위임한다.

    Attributes:
        input_arg_descs: 입력 인자 등록정보 목록.
        output_arg_desc_dict (dict): 출력 인자 식별자를 키로 하는 등록정보 사전.
        op (AASOperationService): 실제 연산 호출을 수행하는 서비스.
    """
    def __init__(self, instance_id:str, sm_desc:MDTSubmodelDescriptor,
                 op_desc:MDTOperationDescriptor) -> None:
        """연산 등록정보로부터 서비스를 초기화한다.

        Args:
            instance_id (str): 연산 Submodel 이 속한 MDT 인스턴스 식별자.
            sm_desc (MDTSubmodelDescriptor): 연산 Submodel 의 등록정보.
            op_desc (MDTOperationDescriptor): 연산의 입력·출력 인자 등록정보.
        """
        super().__init__(instance_id, sm_desc)
        self.__op_desc = op_desc
        self.input_arg_descs = op_desc.input_arguments
        self.output_arg_desc_dict = { desc.id:desc for desc in op_desc.output_arguments }
        self.op = AASOperationService(self, 'Operation')

    @property
    def operation_descriptor(self) -> MDTOperationDescriptor:
        """
        연산의 등록정보를 반환한다.

        Returns:
          MDTOperationDescriptor: 연산의 등록정보.
        """
        return self.__op_desc

    def invoke(self, **kwargs: ArgumentType) -> dict[str, ElementValue]:
        """연산을 호출하고 출력 값을 돌려준다.

        지정하지 않은 입력 인자는 등록정보의 기본 참조로 채워진다. 출력 인자에
        :class:`~mdtpy.ref.ElementReference` 를 전달하면 결과 값이 그 참조 위치에
        갱신되고, 참조를 전달하지 않은 출력 인자는 등록정보에 정의된 참조에 갱신된다.
        입력이기도 한 출력 인자(입출력 인자)에 참조가 아닌 값을 주면, 그 값은 입력으로만
        쓰이고 결과는 등록정보에 정의된 참조에 갱신된다.

        출력 전용 인자에는 결과를 저장할 위치만 지정할 수 있으므로 ``ElementReference`` 만
        받는다. 다른 값을 주면 연산을 호출하지 않고 ``ValueError`` 를 낸다.

        Args:
            **kwargs (ArgumentType): 연산 인자 식별자(``id``)를 키로, 전달할 인자 값을
                값으로 하는 keyword 인자.
        Returns:
            dict[str, ElementValue]: 출력·입출력 인자 식별자를 키로 하는 결과 값 목록.
        Raises:
            ValueError: 출력 전용 인자에 ``ElementReference`` 가 아닌 값을 준 경우.
            OperationError: 연산 호출이 실패한 경우.
            OutputWriteError: 연산은 성공했으나 출력 값을 저장하지 못한 경우. 나머지 출력은 저장을
                시도하며, 예외에 결과 전체(``outputs``)와 실패한 출력(``failures``)을 담는다.
        """
        input_ids = { arg_desc.id for arg_desc in self.input_arg_descs }
        for arg_id, argspec in kwargs.items():
            if (arg_id in self.output_arg_desc_dict and arg_id not in input_ids
                    and not isinstance(argspec, ElementReference)):
                raise ValueError(f"output argument '{arg_id}' accepts only an ElementReference "
                                 f"(the location to store the result): {argspec!r}")

        # 함수 인자로 전달된 값을 input argument에 반영시킨다.
        input_args_dict: dict[str, ArgumentType] = {}
        for arg_desc in self.input_arg_descs:
            input_args_dict[arg_desc.id] = kwargs.get(arg_desc.id, reference(arg_desc.reference))

        # 연산을 호출한다.
        result = self.op.invoke(**input_args_dict)

        # 결과 값마다 저장 위치를 정해 갱신한다. 여기부터는 연산이 이미 성공했으므로, 저장 실패를
        # 연산 실패와 구분할 수 있도록 OutputWriteError 로 모아 알린다. 한 출력의 실패가 나머지 출력의
        # 저장을 막지 않게 끝까지 시도한다.
        failures: dict[str, Exception] = {}
        for arg_id, argv in result.items():
            try:
                if isinstance(argspec := kwargs.get(arg_id), ElementReference):
                    # 인자를 통해 출력 값을 저장할 ElementReference가 전달된 경우에는
                    # 해당 ElementReference의 값을 갱신한다.
                    argspec.update_value(argv)
                elif (def_out_arg := self.output_arg_desc_dict.get(arg_id)) is not None:
                    # 인자에 저장될 위치가 지정되지 않은 경우에는 연산 서브모델에
                    # 등록된 출력 인자에 해당하는 ElementReference의 값을 갱신한다.
                    reference(def_out_arg.reference).update_value(argv)
            except Exception as e:
                failures[arg_id] = e
        if failures:
            raise OutputWriteError(result, failures)

        return result
