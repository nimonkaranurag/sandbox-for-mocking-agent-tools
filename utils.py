from __future__ import annotations

from pathlib import Path
from typing import Union, Any
import hashlib
import json

def safe_mkdir(
        path: Union[str, Path]
) -> Path:
    
    path = Path(path) if path is not None else Path("recordings")
    path.mkdir(
        parents=True,
        exist_ok=True
    )
    
    return path

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
        
        
