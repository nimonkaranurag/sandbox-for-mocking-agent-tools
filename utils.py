from __future__ import annotations

from pathlib import Path
from typing import Union, Dict, Any, Optional, List
import hashlib
import json

from type import(
    ToolCall,
    MockedResponse,
    Recording,
    Tool,
)

def safe_mkdir(
        path: Union[str, Path]
) -> Path:
    
    if isinstance(path, str):
        path = Path(path)
    
    return path.mkdir(
        parents=True,
        exist_ok=True
    )

def stable_hash(*parts: Any) -> str:
    
    payload = json.dumps(
        parts,
        separators=(",", ":"),
        sort_keys=True,
        default=str
    )

    return hashlib.sha256(
        payload.encode("utf-8")
        ).hexdigest()[:16]

def pretty(obj: Any) -> str:
    return json.dumps(
        obj, 
        indent=2, 
        sort_keys=True, 
        ensure_ascii=False
        )

class Recorder:
    def __init__(
            self,
            output_dir: Optional[Union[str, Path]] = "recordings",      
    ):
        self.output_dir = safe_mkdir(output_dir)
    
    def record(
            self,
            invocation: ToolCall,
            response: MockedResponse,
    ) -> Path:
        
        recording = Recording(
            tool_id=invocation.tool_id,
            tool_name=invocation.tool_name,
            args=invocation.args,
            response=response,
            timestamp=invocation.timestamp
        )

        return recording.save(self.output_dir)

class ToolsRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}
    
    def register(
          self,
          tool: Tool,  
    ) -> None:
        
        if tool.name in self._tools:
            raise ValueError(
                f"Tool already registered."
                )
        
        self._tools[tool.name] = tool
    
    def get(
            self,
            tool_name: str
    ) -> Tool:
        
        if tool_name not in self._tools:
            raise KeyError(
                f"Tool not found: {tool_name}"
            )
        
        return self._tools[tool_name]
    
    def list(self) -> List[str]:
        return sorted(self._tools.keys())
        
        
