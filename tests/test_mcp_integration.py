import unittest
import subprocess
import sys
import json
import os
from pathlib import Path

class TestMCPIntegration(unittest.TestCase):
    def setUp(self):
        # Path to cli.py
        self.cli_path = Path("src/zimage/cli.py").resolve()
        # We use 'uv run' to execute the CLI to ensure environment is set up
        self.base_cmd = ["uv", "run", str(self.cli_path), "mcp", "--transport", "stdio"]

    def run_process(self, input_str):
        process = subprocess.Popen(
            self.base_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=os.environ
        )

        stdout, stderr = process.communicate(input=input_str, timeout=60)
        return stdout, stderr

    def test_initialize(self):
        req = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            },
            "id": 1
        }
        stdout, stderr = self.run_process(json.dumps(req) + "\n")

        response = None
        for line in stdout.splitlines():
            try:
                msg = json.loads(line)
                if msg.get("id") == 1:
                    response = msg
                    break
            except json.JSONDecodeError:
                continue

        self.assertIsNotNone(response, f"Did not receive JSON-RPC response. Stdout: {stdout}\nStderr: {stderr}")
        self.assertIn("result", response)
        self.assertIn("serverInfo", response["result"])
        self.assertEqual(response["result"]["serverInfo"]["name"], "Z-Image Studio")

    def test_call_list_models(self):
        # Send initialize -> initialized -> tools/call
        req_init = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            },
            "id": 1
        }

        req_notify = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }

        req_call = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "list_models",
                "arguments": {}
            },
            "id": 2
        }

        input_str = json.dumps(req_init) + "\n" + json.dumps(req_notify) + "\n" + json.dumps(req_call) + "\n"

        stdout, stderr = self.run_process(input_str)

        responses = []
        for line in stdout.splitlines():
             try:
                msg = json.loads(line)
                responses.append(msg)
             except:
                pass

        # Find response with id 2
        res = next((r for r in responses if r.get("id") == 2), None)
        self.assertIsNotNone(res, f"Did not receive call_tool response. Stdout: {stdout}\nStderr: {stderr}")

        if "error" in res:
             self.fail(f"Received error from tool: {res['error']}")

        self.assertIn("result", res)
        # Check if output contains text
        content = res["result"].get("content", [])
        self.assertTrue(len(content) > 0)
        text = content[0].get("text", "")
        self.assertIn("Available Models", text)

if __name__ == '__main__':
    unittest.main()
