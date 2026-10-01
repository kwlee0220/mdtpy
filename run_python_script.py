from __future__ import annotations

from typing import Any, Optional

import signal
import argparse
import json
import sys

from mdtpy import MDTInstanceManager
from mdtpy.operation import ArgumentType, parse_argument_json_node, to_argument_json_node


def signal_handler(sig, frame):
  print(f"Task interrupted (signal={sig}).")
  sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
    

def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """커맨드라인 인자를 파싱한다.

    사용 예:
        python run_python_script.py --mdt localhost:12985 --file <file-path1> \
                                    --inputs <file-path2> --outputs <file-path3>
    """
    parser = argparse.ArgumentParser(description="Operation script template")
    parser.add_argument("--mdt", required=False, help="MDTPlatform endpoint URL")
    parser.add_argument("--file", required=True, help="target file path to process")
    parser.add_argument("--inputs", required=True, help="input arguments JSON file path")
    parser.add_argument("--outputs", required=True, help="output arguments JSON file path")
    return parser.parse_args(argv)


def load_inputs(inputs_path: str) -> dict[str, ArgumentType]:
    """입력 인자 JSON 파일을 읽어 dict 로 반환한다."""
    with open(inputs_path, encoding="utf-8") as f:
        inputs_json:dict[str,ArgumentType] = json.load(f)
        return { key:parse_argument_json_node(input_json)
                for key, input_json in inputs_json.items() }


def save_outputs(outputs_path: str, outputs: dict[str, ArgumentType]) -> None:
    """출력 인자 dict 를 JSON 파일로 저장한다."""
    outputs_json = { key: to_argument_json_node(output) for key, output in outputs.items() }
    with open(outputs_path, "w", encoding="utf-8") as f:
        json.dump(outputs_json, f, ensure_ascii=False, indent=2)


def run(file_path: str, *,
        inputs: dict[str, ArgumentType],
        mdt_manager: Optional[MDTInstanceManager] = None,) -> dict[str, ArgumentType]:
    """실제 처리 로직을 수행하고 출력 인자 dict 를 반환한다.

    이 함수 본문을 실제 동작으로 교체한다.
    """
    script = open(file_path, encoding="utf-8").read()
    args :dict[str,Any] = dict(inputs)
    if mdt_manager is not None:
        args['mdt_manager'] = mdt_manager

    outputs: dict[str, ArgumentType] = {}
    exec(script, args, outputs)
    return outputs


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    mdt_manager = None
    if args.mdt is not None:
        from mdtpy.instance import connect
        mdt_manager = connect(f'{args.mdt}/instance-manager')

    inputs = load_inputs(args.inputs)
    outputs = run(args.file, mdt_manager=mdt_manager, inputs=inputs)
    save_outputs(args.outputs, outputs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
