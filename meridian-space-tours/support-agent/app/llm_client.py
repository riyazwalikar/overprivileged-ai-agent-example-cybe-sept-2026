"""Thin LLM provider abstraction shared by both services (keep both copies in sync).

Provider chosen by env:
  LLM_PROVIDER=bedrock -> Amazon Bedrock Converse API (IAM, no API key in env)
  LLM_PROVIDER=http    -> OpenAI-compatible POST /chat/completions endpoint

Model id, temperature and top_p come from env; pinned for the demo
(temperature 0, top_p 1, single model id).
"""
import json
import os

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError

MAX_TURNS = 6  # cap the tool loop so a stuck model cannot stall the demo


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "bedrock").strip().lower()
        self.model_id = os.getenv(
            "MODEL_ID", "us.amazon.nova-pro-v1:0"
        )
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.temperature = float(os.getenv("TEMPERATURE", "0"))
        self.top_p = float(os.getenv("TOP_P", "1"))
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")

    # -- public ---------------------------------------------------------

    def chat(self, system_prompt, messages, tool_schemas, run_tool):
        """Run one model turn with function calling.

        messages: [{"role": "user"|"assistant", "content": str}]
        tool_schemas: {"name": {"description": str, "parameters": dict}}
        run_tool: callable(name, args) -> str

        Returns (reply_text, tool_calls) where
        tool_calls = [{"name", "args", "output"}].
        """
        if self.provider == "bedrock":
            return self._chat_bedrock(system_prompt, messages, tool_schemas, run_tool)
        return self._chat_http(system_prompt, messages, tool_schemas, run_tool)

    # -- Bedrock Converse ------------------------------------------------

    def _bedrock_tool_specs(self, tool_schemas):
        return [
            {
                "toolSpec": {
                    "name": name,
                    "description": spec["description"],
                    "inputSchema": {"json": spec["parameters"]},
                }
            }
            for name, spec in tool_schemas.items()
        ]

    def _chat_bedrock(self, system_prompt, messages, tool_schemas, run_tool):
        client = boto3.client("bedrock-runtime", region_name=self.region)
        convo = [{"role": m["role"], "content": [{"text": m["content"]}]} for m in messages]
        tool_calls = []

        for _ in range(MAX_TURNS):
            try:
                # Anthropic models reject top_p when temperature is also given;
                # top_p 1.0 is the default, so only send it when overridden.
                inference_config = {"temperature": self.temperature}
                if self.top_p != 1.0:
                    inference_config["topP"] = self.top_p
                resp = client.converse(
                    modelId=self.model_id,
                    messages=convo,
                    system=[{"text": system_prompt}],
                    inferenceConfig=inference_config,
                    toolConfig={"tools": self._bedrock_tool_specs(tool_schemas)},
                )
            except (BotoCoreError, ClientError) as exc:
                raise LLMError(f"Bedrock error: {exc}") from exc

            convo.append(resp["output"]["message"])

            if resp["stopReason"] != "tool_use":
                text = "".join(
                    b.get("text", "") for b in resp["output"]["message"]["content"]
                ).strip()
                return text, tool_calls

            # execute every requested tool, feed results back
            tool_results = []
            for block in resp["output"]["message"]["content"]:
                if "toolUse" not in block:
                    continue
                tool = block["toolUse"]
                name, tool_id = tool["name"], tool["toolUseId"]
                args = tool.get("input", {})
                output = run_tool(name, args)
                tool_calls.append({"name": name, "args": args, "output": output})
                tool_results.append(
                    {
                        "toolResult": {
                            "toolUseId": tool_id,
                            "content": [{"text": output}],
                        }
                    }
                )
            convo.append({"role": "user", "content": tool_results})

        raise LLMError("Tool loop exceeded MAX_TURNS")

    # -- OpenAI-compatible HTTP -----------------------------------------

    def _http_tools(self, tool_schemas):
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": spec["description"],
                    "parameters": spec["parameters"],
                },
            }
            for name, spec in tool_schemas.items()
        ]

    def _chat_http(self, system_prompt, messages, tool_schemas, run_tool):
        convo = [
            {"role": "system", "content": system_prompt},
            *[{"role": m["role"], "content": m["content"]} for m in messages],
        ]
        tool_calls = []
        payload = {
            "model": self.model_id,
            "messages": convo,
            "tools": self._http_tools(tool_schemas),
            "tool_choice": "auto",
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        for _ in range(MAX_TURNS):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=60,
                )
                resp.raise_for_status()
                choice = resp.json()["choices"][0]
            except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
                raise LLMError(f"Provider error: {exc}") from exc

            message = choice["message"]
            convo.append(message)
            tool_requests = message.get("tool_calls") or []

            if choice["finish_reason"] != "tool_calls" or not tool_requests:
                return (message.get("content") or "").strip(), tool_calls

            results = []
            for call in tool_requests:
                fn = call["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except ValueError:
                    args = {}
                output = run_tool(name, args)
                tool_calls.append({"name": name, "args": args, "output": output})
                results.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": output,
                    }
                )
            convo.extend(results)

        raise LLMError("Tool loop exceeded MAX_TURNS")
