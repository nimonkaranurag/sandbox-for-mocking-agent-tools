from __future__ import annotations

import dataclasses as dc
from typing import Optional, Dict, List, Tuple, Any, Callable, Union
from pathlib import Path
import json
import random
import hashlib

from utils import safe_mkdir

@dc.dataclass
class ToolCall:
    tool_name: str
    args: Dict[str, Any]
    tool_id: str
    timestamp: str

@dc.dataclass
class MockedResponse:
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: int = 0

    def to_json(self) -> Dict[str, Any]:
        return dc.asdict(self)

@dc.dataclass
class Policy:
    """
    Minimal policy enforcement:
        - maintains allowed/denied lists of tool names
    """

    allowed_tools: Optional[List[str]] = None
    unallowed_tools: Optional[List[str]] = None
    
    # TODO: wire-up properly later
    rate_limit_per_min: Optional[int] = None

    def is_allowed(self, tool_name: str) -> Tuple[bool, Optional[str]]:

        if self.unallowed_tools and tool_name in self.unallowed_tools:
            return (
                False,
                f"Tool '{tool_name}' is denied by policy."
            )
        
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return (
                False,
                f"Tool '{tool_name}' is denied by policy."
            )
        
        return (
            True,
            None
        ) # permitted to call this tool
    
@dc.dataclass
class Recording:
    tool_id: str
    tool_name: str
    args: Dict[str, Any]
    response: MockedResponse
    timestamp: Union[float, str]

    def save(
            self,
            dir: Path
    ) -> Path:
        
        output_file_path = safe_mkdir(
            dir
        ) / f"{self.tool_id}.json"

        with output_file_path.open("w", encoding="utf-8") as output_file:
            json.dump(
                {
                    "id": self.tool_id,
                    "tool": self.tool_name,
                    "args": self.args,
                    "response": self.response.to_json(),
                    "time": self.timestamp,
                },
                output_file,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )

        return output_file_path
    
    @staticmethod
    def load(
        path: Path
    ) -> "Recording":
        
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        
        response = MockedResponse(**payload["response"])

        return Recording(
            tool_id=payload["id"],
            tool_name=payload["tool"],
            args=payload["args"],
            response=response,
            timestamp=payload["time"]
        )
    
@dc.dataclass
class FaultProfile:
    """
    Simulates deterministic, real API-chaos(latency, random failures, etc.)
    """
    seed: int = 42
    min_latency_ms: int = 10
    max_latency_ms: int = 120
    error_rate: float = 0.0 # set to 0.2 to see ~20% failures, etc.

    def rng(self, key: str) -> random.Random:
       
        # Ensure determinism per (seed, key)
        h = hashlib.sha256(
        f"{self.seed}:{key}".encode("utf-8")
        ).digest()

        seed_int = int.from_bytes(
            h[:8], "big", signed=False
            )
        
        return random.Random(seed_int)
    
    def sample_latency(self, key: str) -> int:
        r = self.rng(key)

        return int(
            r.uniform(
                self.min_latency_ms, 
                self.max_latency_ms)
                )
    
    def should_error(self, key: str) -> bool:
        if self.error_rate <= 0:
            return False
        
        r = self.rng(key)

        return r.random() < self.error_rate
    
@dc.dataclass
class FixtureMetaData:
    created_at: str
    signature: str
    seed: Optional[str] = None
    profile: Optional[str] = None
    policy_hash: Optional[str] = None
    notes: Optional[str] = None

@dc.dataclass
class Fixture:
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: int = 0
    metadata: Optional[FixtureMetaData] = None

    def to_json(self) -> Dict[str, Any]:
        payload = {
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "metadata": dc.asdict(self.metadata) if self.metadata else None
        }
        return payload
    
    @staticmethod
    def load_from_json(
        fixture: Dict[str, Any],
        ) -> "Fixture":

        metadata = fixture.get("metadata")
        meta_obj = FixtureMetaData(**metadata) if metadata else None

        return Fixture(
            ok=fixture.get("ok"),
            data=fixture.get("data"),
            error=fixture.get("error"),
            latency_ms=fixture.get("latency_ms", 0),
            metadata=meta_obj,
        )

@dc.dataclass
class Operation:
    name: str
    param_schema: Dict[str, Any]
    result_schema: Dict[str, Any]
    description: str = ""
    version: str = "v1"





