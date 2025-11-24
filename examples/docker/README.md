# Docker Example - Container-First MCP Server

This example demonstrates the **recommended production pattern** for deploying an MCP server using common-mcp-submodule.

## Quick Start (Recommended)

```bash
cd examples/docker
docker compose up
```

Access the server at: http://localhost:8000

Test the MCP endpoint:
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo_pat_12345" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

## Production Deployment Pattern

### 1. Add common-mcp-submodule as Git Submodule

```bash
# In your project root
git submodule add https://github.com/Originate-Group/common-mcp-submodule.git
```

### 2. Install in Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy and install common-mcp-submodule
COPY common-mcp-submodule/ /app/common-mcp-submodule/
RUN pip install --no-cache-dir -e /app/common-mcp-submodule

# Copy your application requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY src/ /app/src/

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3. Use in Your FastAPI Application

```python
from fastapi import FastAPI
from common_mcp_server import MCPServer, PATConfig

app = FastAPI()

# Configure MCP server
mcp_server = MCPServer(
    name="my-mcp-server",
    version="1.0.0",
    pat_config=PATConfig(
        header_name="X-API-Key",
        verify_function=verify_pat_from_database,
    ),
)

# Mount MCP router
app.include_router(mcp_server.get_router(), prefix="/mcp")
```

### 4. Deploy with Docker Compose

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://user:pass@db:5432/mydb
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: your-password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## Why Container-First?

1. **Consistent Environment**: Same Python version, dependencies everywhere
2. **Production Parity**: Development matches production deployment
3. **Easy Deployment**: Single `docker compose up` command
4. **Isolation**: No conflicts with local Python installations
5. **Scalability**: Container orchestration (Kubernetes, ECS, etc.)

## Development Workflow

Enable hot-reload during development by uncommenting the volume mount in `docker-compose.yml`:

```yaml
volumes:
  - ../basic.py:/app/basic.py
command: uvicorn basic:app --host 0.0.0.0 --port 8000 --reload
```

Then edit `../basic.py` and see changes immediately without rebuilding.

## Real-World Examples

See how production projects use this pattern:

- **originate-raas-team**: OAuth + PAT authentication, Keycloak integration
  - [Dockerfile](https://github.com/Originate-Group/originate-raas-team/blob/main/Dockerfile)
  - [docker-compose.yml](https://github.com/Originate-Group/originate-raas-team/blob/main/docker-compose.yml)

- **originate-raas-core**: Solo developer mode, local deployment
  - [Dockerfile](https://github.com/Originate-Group/originate-raas-core/blob/main/Dockerfile)
  - [docker-compose.yml](https://github.com/Originate-Group/originate-raas-core/blob/main/docker-compose.yml)
