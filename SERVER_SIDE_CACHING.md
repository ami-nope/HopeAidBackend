# Server-Side Caching Setup (Redis)

## Hybrid Caching Architecture

**Frontend:**
- ✓ In-memory cache (session) - all data
- ✓ localStorage (persistent) - public/non-sensitive data only
- ✓ Server communication - all requests

**Backend:**
- ⚠️ TO BE IMPLEMENTED: Redis caching for all API responses
- Protects sensitive data (never stored in browser)
- Shared cache across all users/devices
- Fast access for repeated requests

## Implementation Steps for Backend

### 1. Install Redis dependency
```bash
pip install redis
```

### 2. Add to requirements.txt
```
redis==5.0.1
```

### 3. Create cache middleware in `app/core/cache.py`

```python
import redis
import json
from typing import Any, Optional
from functools import wraps
from app.core.config import settings

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
    decode_responses=True
)

def cache_response(ttl_seconds: int = 300):
    """Cache API responses in Redis"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from request path and params
            cache_key = f"api:{func.__name__}:{str(kwargs)}"
            
            # Check cache
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            redis_client.setex(
                cache_key,
                ttl_seconds,
                json.dumps(result, default=str)
            )
            
            return result
        return wrapper
    return decorator

def invalidate_cache(pattern: str = "*"):
    """Clear cache matching pattern"""
    keys = redis_client.keys(pattern)
    if keys:
        redis_client.delete(*keys)
```

### 4. Update API endpoints to use caching

```python
from app.core.cache import cache_response

@router.get("/cases")
@cache_response(ttl_seconds=180)  # 3 minutes
async def get_cases(
    page: int = 1,
    page_size: int = 20,
    organization_id: str = None,
):
    # Your existing code
    pass
```

### 5. Set environment variables

```
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 6. Add to docker-compose.yml

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  command: redis-server --appendonly yes

volumes:
  redis_data:
```

## Caching Strategy by Data Type

| Data | Browser | Server | TTL |
|------|---------|--------|-----|
| Dashboard counts | ✓ localStorage | ✓ Redis | 5 min |
| Case status/category | ✓ localStorage | ✓ Redis | 5 min |
| Volunteer counts | ✓ localStorage | ✓ Redis | 3 min |
| Full case data | ✗ Memory only | ✓ Redis | 3 min |
| Full volunteer data | ✗ Memory only | ✓ Redis | 3 min |
| Household details | ✗ None | ✓ Redis | 5 min |
| Contact info | ✗ None | ✓ Redis | 5 min |
| Medical data | ✗ None | ✓ Redis | 5 min |
| Alerts | ✓ localStorage | ✓ Redis | 1 min |
| Audit logs | ✗ Memory only | ✓ Redis | 5 min |

## Security Benefits

✓ Sensitive data never stored in browser  
✓ Contact info, medical records, addresses server-cached only  
✓ Even if XSS attack occurs, attacker can't access sensitive cached data  
✓ Shared cache improves performance across all users  

## Cache Invalidation

When data changes, invalidate server cache:

```python
from app.core.cache import invalidate_cache

@router.put("/cases/{case_id}")
async def update_case(case_id: str, data: CaseUpdate):
    # Update database
    case = await update_case_in_db(case_id, data)
    
    # Invalidate related caches
    invalidate_cache(f"api:get_cases:*")
    invalidate_cache(f"api:get_case_by_id:{case_id}")
    
    return case
```

## TODO
- [ ] Install Redis dependency
- [ ] Create cache middleware
- [ ] Add Redis environment variables
- [ ] Update API endpoints with @cache_response decorators
- [ ] Add cache invalidation on data mutations
- [ ] Update docker-compose.yml
- [ ] Test caching with Redis CLI
