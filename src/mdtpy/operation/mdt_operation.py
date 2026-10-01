from __future__ import annotations

from ..submodel import SubmodelService
from ..descriptor import MDTOperationDescriptor, MDTSubmodelDescriptor
from ..ref import ElementReference, reference
from ..value import ElementValue
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

        Args:
            **kwargs (ArgumentType): 연산 인자 식별자(``id``)를 키로, 전달할 인자 값을
                값으로 하는 keyword 인자.
        Returns:
            dict[str, ElementValue]: 출력·입출력 인자 식별자를 키로 하는 결과 값 목록.
        Raises:
            OperationError: 연산 호출이 실패한 경우.
        """
        # 함수 인자로 전달된 값을 input argument에 반영시킨다.
        input_args_dict: dict[str, ArgumentType] = {}
        for arg_desc in self.input_arg_descs:
            input_args_dict[arg_desc.id] = kwargs.get(arg_desc.id, reference(arg_desc.reference))

        # 연산을 호출한다.
        result = self.op.invoke(**input_args_dict)

        # 결과 값 중에서 ElementReference 형태로 출력 인자로 제공된 경우에는
        # 해당 ElementReference 객체의 값을 갱신한다
        for arg_id, argv in result.items():
            if (argspec := kwargs.get(arg_id)) is not None:
                # 인자를 통해 출력 값을 저장할 ElementReference가 전달된 경우에는
                # 해당 ElementReference의 값을 갱신한다.
                if isinstance(argspec, ElementReference):
                    argspec.update_value(argv)
            elif (def_out_arg := self.output_arg_desc_dict.get(arg_id)) is not None:
                # 인자에 저장될 위치가 지정되지 않은 경우에는 연산 서브모델에
                # 등록된 출력 인자에 해당하는 ElementReference의 값을 갱신한다.
                reference(def_out_arg.reference).update_value(argv)

        return result
