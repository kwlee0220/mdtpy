.PHONY: test test-cov install-dev clean

# ROS2 환경(/opt/ros/humble/...)을 source한 쉘에서는 launch_pytest 플러그인이
# 자동 로드되어 yaml 누락으로 충돌하므로, .env의 PYTEST_DISABLE_PLUGIN_AUTOLOAD를
# uv 명령에 명시적으로 주입한다.

test:
	uv run --env-file .env pytest

test-cov:
	uv run --env-file .env pytest --cov=mdtpy --cov-report=term-missing

install-dev:
	uv sync --group dev

clean:
	rm -rf .pytest_cache .coverage build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
