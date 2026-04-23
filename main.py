from fastmcp import FastMCP
import random
import json

# Create the MCP server instance
mcp = FastMCP("Simple Calculator Server")

# Tool 1: Add two numbers
@mcp.tool()
def add_numbers(a: float, b: float) -> float:
    """Add two numbers together.
        Args:
            a: First number
            b: Second number
        Returns:
            The sum of a and b
    """
    return a + b

# Tool 2: Generate a random number in a given range
@mcp.tool()
def random_number(min_value: int = 1, max_value: int = 100) -> int:
    """Generate a random integer between min_value and max_value.
        Args:
            min_val: Minimum value (default 1)
            max_val: Maximum value (default 100)
        Return:
            A random integer between min_val and max_val
    """
    
    return random.randint(min_value, max_value)


# Resource: Server information
@mcp.resource("info://server")
def server_info() -> str:
    """Get information about this server. """
    info = {
        "name": 'Simple Calculator Server',
        "version": '1.0.0',
        "description": 'A basic MCP server with math tools',
        "tools": '["add", "random_number"]',
        "author": 'Mr. Liaqat Ali Shaiz',
    }

    return json.dumps(info, indent=2)

# Run the server with HTTP transport
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
