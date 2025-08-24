from typing import Optional, Dict, Any
import random
from datetime import datetime

from type import (
    JSON,
    OpenAPINormalized,
)
from utils import (
    resolve_schema,
)

class DataGenerator:

    def __init__(self, seed: Optional[int]=None) -> None:
        self.seed = seed if seed else int(
            datetime.now().timestamp()
            )
        self.rng = random.Random(self.seed)
    
    def _string(self, fmt: Optional[str]) -> str:
        
        if fmt == "date-time":
            return "2025-01-01T00:00:00Z"
        
        if fmt == "uuid":
            return f"{self.rng.getrandbits(128):032x}"
        
        if fmt == "date":
            return "2025-01-01"
        
        if fmt == "email":
            return f"user{self.rng.randint(1000,9999)}@example.com"
        
        if fmt in ("uri", "url"):
            return f"https://api.example.com/resource/{self.rng.randint(1,9999)}"
        
        return f"s_{self.rng.randrange(1_000_000)}"
    
    def generate(
            self,
            open_api_spec: OpenAPINormalized,
            schema: JSON,
            depth: int = 0,
    ) -> Any:
        if not isinstance(schema, dict):
            return None
        if depth > 6:
            return None
        
        if "example" in schema:
            return schema["example"]
        if "default" in schema:
            return schema["default"]
        if "enum" in schema \
            and isinstance(schema["enum"], list) \
                and schema["enum"]:
            return self.rng.choice(schema["enum"])
        
        if "$ref" in schema:
            schema = resolve_schema(
                open_api_spec=open_api_spec, 
                schema=schema
                )
        
        t = schema.get("type")
        if isinstance(t, list):
            t = next(
                (x for x in t if x != "null"), 
                "null"
                )
            if t == "null":
                return None

        if not t and "oneOf" in schema:
            choice = self.rng.choice(
                schema["oneOf"]
            )
            return self.generate(
                open_api_spec=open_api_spec,
                schema=resolve_schema(
                    open_api_spec,
                    choice,
                ),
                depth=depth+1
            )
        
        if not t and "anyOf" in schema:
            choice = self.rng.choice(
                schema["anyOf"]
            )
            return self.generate(
                open_api_spec=open_api_spec,
                schema=resolve_schema(
                    open_api_spec,
                    choice,
                ),
                depth=depth+1
            )
        
        if not t and "allOf" in schema:
            accumulator: JSON = {}
            for part in schema["allOf"]:
                resolved = resolve_schema(
                    open_api_spec=open_api_spec,
                    schema=part,
                )
                example = self.generate(
                    open_api_spec=open_api_spec,
                    schema=resolved,
                    depth=depth+1
                )
                if isinstance(example, dict):
                    accumulator.update(example)

            return accumulator
        
        if t == "object" or ("properties" in schema):
            properties = schema.get(
                "properties", 
                {}
                )
            required = set(
                schema.get(
                    "required", 
                    []
                    )
                )
            output: JSON = {}
            for name, sub_property in properties.items():
                resolved = resolve_schema(
                    open_api_spec=open_api_spec, 
                    schema=sub_property
                    )
                output[name] = self.generate(
                    open_api_spec=open_api_spec, 
                    schema=resolved, 
                    depth=depth+1
                    )
                
            # Ensure required keys present even if properties missing
            for name in required:
                output.setdefault(
                    name, 
                    self.generate_sensible_default()
                    )
            
            return output
        
        if t == "array":
            items = resolve_schema(
                open_api_spec=open_api_spec, 
                schema=schema.get(
                    "items", 
                    {
                        "type": "string"
                    },
                    )
                )
            
            min_items = int(schema.get("minItems", 1))
            max_items = int(schema.get(
                "maxItems", 
                max(1, min_items + 2)
                )
                )
            length = self.rng.randint(
                min_items, 
                min(max_items, min_items + 2)
                )
            
            return [
                self.generate(
                open_api_spec=open_api_spec, 
                schema=items, 
                depth=depth + 1
                ) for _ in range(length)
                ]

        if t == "string" or (
            t is None and "properties" not in schema \
                and "items" not in schema):
            fmt = schema.get("format")
            
            min_len = int(schema.get("minLength", 1))
            max_len = int(schema.get("maxLength", max(8, min_len)))

            pattern = schema.get("pattern")
            if pattern:
                return f"match:{pattern}"
            if fmt:
                return self._string(fmt)
            
            n = self.rng.randint(min_len, max_len)

            alphabet = "abcdefghijklmnopqrstuvwxyz"

            return "".join(self.rng.choice(alphabet) for _ in range(n))

        if t == "integer":
            low = int(schema.get("minimum", 0))
            high = int(schema.get("maximum", max(low, 1000)))
            return int(self.rng.randint(low, high))

        if t == "number":
            low = float(schema.get("minimum", 0.0))
            high = float(schema.get("maximum", max(low, 1000.0)))
            return float(self.rng.uniform(low, high))

        if t == "boolean":
            return bool(self.rng.getrandbits(1))
        
        return self.generate_sensible_default()
    
    def generate_sensible_default(
            self,
    ) -> Any:
        return {
            "value": None,
            "note": "auto-generated fallback; please refine via schema examples/defaults/enums"
        }
    
    def generate_id(self) -> int:
        
        return int(
            self.rng.randint(1, 10_000)
            )