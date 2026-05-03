import asyncio
import sys
import os
import time

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.core.resilience import circuit_breaker, CircuitBreakerOpenError

@circuit_breaker(name="test_breaker", failure_threshold=2, recovery_timeout=1.0)
async def failing_function():
    print("Function called")
    raise RuntimeError("External API failure")

@circuit_breaker(name="test_breaker", fallback=lambda: "Fallback value")
async def function_with_fallback():
    raise RuntimeError("Fail!")

async def verify_resilience():
    print("1. Testing circuit opening...")
    # Call 1: failure
    try:
        await failing_function()
    except Exception as e:
        print(f"Call 1 failed as expected: {e}")

    # Call 2: failure -> should open circuit
    try:
        await failing_function()
    except Exception as e:
        print(f"Call 2 failed as expected: {e}")

    # Call 3: circuit should be OPEN
    print("Call 3: Expecting CircuitBreakerOpenError")
    try:
        await failing_function()
    except CircuitBreakerOpenError as e:
        print(f"Call 3 correctly caught open circuit: {e}")
    except Exception as e:
        print(f"Call 3 raised unexpected error: {type(e)} {e}")

    print("\n2. Testing fallback...")
    result = await function_with_fallback()
    print(f"Fallback result: {result}")
    assert result == "Fallback value"

    print("\n3. Testing recovery...")
    print("Waiting for recovery timeout (1.1s)...")
    await asyncio.sleep(1.1)
    
    # This should be HALF_OPEN, then success transitions to CLOSED
    @circuit_breaker(name="test_breaker")
    async def successful_function():
        print("Successful function called")
        return "Success"

    result = await successful_function()
    print(f"Recovery call result: {result}")
    assert result == "Success"

    print("\nVerification Successful!")

if __name__ == "__main__":
    asyncio.run(verify_resilience())
