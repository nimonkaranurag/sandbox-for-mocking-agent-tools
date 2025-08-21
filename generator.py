from typing import Optional, Dict, Any

SEED = 1337

class DataGenerator:
    #TODO: Currently good enough to boot-strap fixtures, needs to be upgraded.
    # Use an LLM for this?

    def __init__(self, seed: int = SEED) -> None:
        import random
        self._rng = random.Random(seed)
    
    def _string(self, format: Optional[str]) -> str:
        if format == "date-time":
            return "2025-01-01T00:00:00Z"
        
        if format == "uuid":
            # naive uuid-like hex
            return f"{self._rng.getrandbits(128):032x}"
        
        return f"s_{self._rng.randrange(1_000_000)}"
    
    def generate(
            self,
            schema: Dict[str, Any]
    ) -> Any:
        
        if not isinstance(schema, dict):
            return None
        
        t = schema.get("type", "object") # type

        if t == "string":
            return self._string(schema.get("format"))
        
        if t == "integer":

            low = schema.get("minimum", 0)
            high = schema.get("maximum", 1000)

            return int(
                self._rng.randint(
                    low, 
                    high
                ))
        
        if t == "number":

            low = schema.get("minimum", 0)
            high = schema.get("maximum", 1000)

            return float(
                self._rng.uniform(
                    low,
                    high
                ))
        
        if t == "boolean":
            return bool(
                self._rng.getrandbits(1)
                )
        
        if t == "array":
            items = schema.get("items", {"type": "string"})

            n = max(1, min(int(schema.get("minItems", 1) or 1), 3))

            return [self.generate(items) for _ in range(n)]
        
        # default object
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        output = {}

        for key, ps in properties.items():
            output[key] = self.generate(ps) # ps -> property schema
        
        # ensure required keys are present
        for key in required:
            output.setdefault(
                key,
                self.generate(
                    properties.get(
                        key,
                        {
                            "type": "string"
                        },
                    )
                )
            )
        
        return output
