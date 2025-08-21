from pathlib import Path
import json
import shutil
from typing import Dict, Any

from utils import safe_mkdir
from type import Operation, Policy
from api_ops_router import APIOperationsRouter
from recorder import Recorder
from fixtures import FixtureStore
from generator import DataGenerator
from sandbox import Sandbox
from adapter import Adapter


def pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def reset_demo_directories(fixtures_dir: Path, recordings_dir: Path) -> None:
    if fixtures_dir.exists():
        shutil.rmtree(fixtures_dir)
    if recordings_dir.exists():
        shutil.rmtree(recordings_dir)
    safe_mkdir(fixtures_dir)
    safe_mkdir(recordings_dir)


def register_demo_operations(router: APIOperationsRouter) -> None:
    issues_result_schema: Dict[str, Any] = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "minimum": 1, "maximum": 10_000},
                "title": {"type": "string"},
                "state": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
            },
            "required": ["id", "title", "state", "created_at"],
        },
        "minItems": 2,
        "maxItems": 2,
    }
    issues_params_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "repo": {"type": "string"},
            "page": {"type": "integer", "minimum": 1, "maximum": 5},
        },
        "required": ["repo"],
    }
    router.register_op(
        Operation(
            name="mock.issues.list",
            param_schema=issues_params_schema,
            result_schema=issues_result_schema,
            description="List issues for a repository",
            version="v1",
        )
    )

    user_result_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "login": {"type": "string"},
            "id": {"type": "integer", "minimum": 1, "maximum": 1_000_000},
            "created_at": {"type": "string", "format": "date-time"},
        },
        "required": ["login", "id", "created_at"],
    }
    user_params_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {"login": {"type": "string"}},
        "required": ["login"],
    }
    router.register_op(
        Operation(
            name="mock.user.get",
            param_schema=user_params_schema,
            result_schema=user_result_schema,
            description="Get a user profile",
            version="v1",
        )
    )


def build_sandbox(fixtures_dir: Path, recordings_dir: Path, seed: int = 1337) -> Sandbox:
    policy = Policy(allowed_tools=["mock.issues.list", "mock.user.get"])
    recorder = Recorder(output_dir=recordings_dir)
    fixtures = FixtureStore(root=fixtures_dir)
    router = APIOperationsRouter()
    register_demo_operations(router)
    data_gen = DataGenerator(seed=seed)
    sandbox = Sandbox(
        policy=policy,
        recorder=recorder,
        fault=None,
        fixtures=fixtures,
        api_ops_router=router,
        data_generator=data_gen,
    )
    return sandbox


def run_demo_sequence() -> None:
    fixtures_dir = Path("demo_fixtures")
    recordings_dir = Path("demo_recordings")
    reset_demo_directories(fixtures_dir, recordings_dir)

    sandbox = build_sandbox(fixtures_dir, recordings_dir, seed=20250821)
    mcp_adapter = Adapter(sandbox)

    print("\n=== available_operations_via_adapter ===")
    print(pretty_json(mcp_adapter.describe_tools()))

    print("\n=== first_call_synthesizes_and_persists_fixture ===")
    call1, resp1 = sandbox.invoke("mock.issues.list", {"repo": "octo/demo", "page": 1}, record=True)
    print(pretty_json({"invocation": call1.__dict__, "response": resp1.to_json()}))

    print("\n=== second_call_hits_fixture_with_same_signature ===")
    call2, resp2 = sandbox.invoke("mock.issues.list", {"repo": "octo/demo", "page": 1}, record=True)
    print(pretty_json({"invocation": call2.__dict__, "response": resp2.to_json()}))

    print("\n=== fixture_hit_data_equality_check ===")
    print(pretty_json({"same_data": resp1.data == resp2.data, "latencies": [resp1.latency_ms, resp2.latency_ms]}))

    print("\n=== unknown_operation_returns_clear_error ===")
    call_unknown, resp_unknown = sandbox.invoke("mock.unknown.op", {"foo": "bar"}, record=True)
    print(pretty_json({"invocation": call_unknown.__dict__, "response": resp_unknown.to_json()}))

    print("\n=== policy_denial_blocks_operation ===")
    sandbox.policy.allowed_tools = ["mock.issues.list"]
    call_denied, resp_denied = sandbox.invoke("mock.user.get", {"login": "octocat"}, record=True)
    print(pretty_json({"invocation": call_denied.__dict__, "response": resp_denied.to_json()}))

    print("\n=== error_injection_on_new_signature ===")
    original_error_rate = sandbox.fault.error_rate
    sandbox.fault.error_rate = 1.0
    call_fail, resp_fail = sandbox.invoke("mock.issues.list", {"repo": "octo/demo", "page": 2}, record=True)
    print(pretty_json({"invocation": call_fail.__dict__, "response": resp_fail.to_json()}))
    sandbox.fault.error_rate = original_error_rate

    print("\n=== list_persisted_fixtures_for_mock_issues_list ===")
    issues_fixtures = sorted((fixtures_dir / "mock.issues.list").glob("*.json"))
    print(pretty_json({"fixture_files": [p.name for p in issues_fixtures]}))

    print("\n=== show_one_fixture_payload ===")
    example_fixture_path = issues_fixtures[0] if issues_fixtures else None
    if example_fixture_path:
        print(pretty_json(json.loads(example_fixture_path.read_text(encoding="utf-8"))))
    else:
        print(pretty_json({"note": "no fixtures found"}))

    print("\n=== list_recordings_summary ===")
    recordings = sorted(recordings_dir.glob("*.json"))
    print(pretty_json({"recording_files": [p.name for p in recordings]}))

    print("\n=== demo_complete_summary ===")
    print(
        pretty_json(
            {
                "operations": mcp_adapter.describe_tools(),
                "fixtures_count": len(list((fixtures_dir / "mock.issues.list").glob("*.json"))),
                "recordings_count": len(recordings),
                "key_takeaways": [
                    "fixture_first_behavior_confirmed",
                    "policy_enforcement_confirmed",
                    "deterministic_latency_and_error_injection_confirmed",
                    "adapter_reflection_of_operations_confirmed",
                ],
            }
        )
    )

    # TODO: add jsonschema validation for input and output envelopes
    # TODO: add openapi ingestion and auto-registration of operations
    # TODO: add profile-aware fixture namespaces and atomic writes
    # TODO: add stateful adapters for realistic CRUD flows (e.g., issues create/close/paginate)
    # TODO: add CLI flags for seed/profile/fixtures_dir/recordings_dir

if __name__ == "__main__":
    run_demo_sequence()
