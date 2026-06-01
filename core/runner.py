"""Run an executable and return its combined stdout+stderr as text."""
import subprocess


def run_command(argv: list, timeout: int = 30) -> str:
    try:
        out = subprocess.check_output(argv, stderr=subprocess.STDOUT, timeout=timeout)
        return out.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError as e:
        return e.output.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {e}"
