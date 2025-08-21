from typing import Dict, List

from type import (
    Operation,
)

class APIOperationsRouter:
    def __init__(self) -> None:
        self._ops: Dict[str, Operation] = {}
    
    def register_op(self, op: Operation) -> None:

        if op.name in self._ops:
            raise ValueError(f"Operation already registered: {op.name}")
        
        self._ops[op.name] = op
    
    def get_op(self, name: str) -> Operation:
        
        if name not in self._ops:
            raise KeyError(f"Unknown operation: {name}")
        
        return self._ops[name]
    
    def list_ops(self) -> List[str]:
        return sorted(self._ops.keys())
