FROM python:3.11-slim

WORKDIR /app

# Install common-mcp-submodule from parent directory
# In production, this would be installed from git submodule or PyPI
COPY ../.. /app/common-mcp-submodule
RUN pip install --no-cache-dir -e /app/common-mcp-submodule

# Copy the example application
COPY ../basic.py /app/

# Expose the API port
EXPOSE 8000

# Run the FastAPI application
CMD ["uvicorn", "basic:app", "--host", "0.0.0.0", "--port", "8000"]
