"""Agent基类：推理五阶段公共逻辑（参考LangChain v2架构）

阶段一：消息组织   - 将用户输入追加到消息历史（由子类 run 组装 prompt）
阶段二：工具决策   - Agent判断是否需要调用外部工具（_tool_call_loop）
阶段三：外部执行   - 调用知识检索 / 业务API（_tool_call_loop）
阶段四：规则约束推理 - 严格遵循业务规则链（由子类 system_prompt 约束）
阶段五：多轮记忆闭环 - 回复写回消息历史供下一轮使用（由 add_messages reducer 完成）

工具调用兼容性说明：
- 优先使用OpenAI标准tool_calls协议（云端API/支持的本地服务）
- 本地GGUF小模型可能将 <tool_call>{...}</tool_call> 作为文本输出，
  _tool_call_loop 会自动从文本中解析并执行，保证本地部署也可用
"""
import json
import re
import time
from abc import ABC, abstractmethod

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from loguru import logger

from app.agents.graphs.state import AgentState
from app.config.settings import settings
from app.core.llm import get_llm_for_task

perf_logger = logger.bind(name="perf")

# Qwen2.5等模型文本形式的工具调用块
_TOOL_CALL_RE = re.compile(r"<tool_call>.*?</tool_call>", re.DOTALL)
# Qwen3 等模型可能输出 <think> 推理标签，需要清洗
_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_think_tags(text: str) -> str:
    """清除模型输出的 <think>...</think> 推理标签

    背景：Qwen3 等模型的"思考链"会以 <think>...</think> 包裹，
    这段内容不是给用户的答案，可能还很长（吃掉 token 预算）。
    统一在进入对话历史/返回前端前剥离，保证回给用户的是干净答案。
    """
    return _THINK_TAG_RE.sub("", text).strip()


def _try_load_json(text: str) -> dict | None:
    """容错解析JSON：兼容双花括号包裹 {{...}}、嵌套字符串、多余尾部括号等模型输出怪癖"""
    s = text.strip()
    if not s:
        return None
    for _ in range(5):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        # 处理 {{...}} 双花括号包裹
        if s.startswith("{{") and s.endswith("}}"):
            s = s[1:-1].strip()
            continue
        # 处理 regex 贪婪匹配多捕获一个尾部 } 的情况
        # 如 {{"name":"x"}} → regex 捕获 {"name":"x"}} → 多了一个 }
        if s.startswith("{") and s.endswith("}") and s.count("{") < s.count("}"):
            s = s[:-1].strip()
            continue
        return None
    return None


def parse_tool_calls_from_text(text: str) -> list[dict]:
    """从模型文本输出中解析 <tool_call> 块（本地 GGUF 模型兼容方案）

    背景：本地小模型（llama.cpp）对原生 function calling 支持有限，
    常把工具调用"说"成文本 <tool_call>{...}</tool_call>，
    因此需要从文本里解析；云端大模型走标准 tool_calls 协议，不走此分支。

    采用"括号层层剥离法"，兼容模型各种输出怪癖格式：
    1. <tool_call>{"name": "x", "arguments": {...}}</tool_call>  — 标准格式
    2. <tool_call>{{"name": "x", "arguments": {...}}}</tool_call> — 双花括号
    3. <tool_call>{{{"name": "x", ...}}}</tool_call>               — 三层花括号

    返回：[{"name": 工具名, "args": 参数字典, "id": 调用ID}, ...]
    """
    calls: list[dict] = []
    # 用非贪婪正则提取所有 <tool_call>...</tool_call> 块
    for block in re.findall(r"<tool_call>(.*?)</tool_call>", text or "", re.DOTALL):
        content = block.strip()
        if not content:
            continue
        # 逐层剥离外层花括号（最多 3 层），直到解析出合法 JSON
        payload = None
        for _ in range(3):
            try:
                payload = json.loads(content)
                if isinstance(payload, dict) and "name" in payload:
                    break
            except (json.JSONDecodeError, ValueError):
                pass
            if content.startswith("{") and content.endswith("}"):
                # 剥离一层花括号，并尝试多种候选：
                inner = content[1:-1].strip()
                #   - inner:         剥离 1 层（处理 {{...}} 标准双花括号）
                #   - inner + "}":   补 1 个 }（处理嵌套导致外层缺闭合）
                #   - inner[:-k]:    去掉 k 个多余尾 }（处理 }}}、}}}} 多层闭合）
                for candidate in [inner, inner + "}"] + [inner[:-k] for k in range(1, 4) if len(inner) > k and inner.endswith("}")]:
                    try:
                        payload = json.loads(candidate)
                        if isinstance(payload, dict) and "name" in payload:
                            break
                    except (json.JSONDecodeError, ValueError):
                        pass
                if payload is not None and "name" in payload:
                    break
                content = inner
            else:
                break
        if payload is None or "name" not in payload:
            continue

        # 参数可能是嵌套字符串（"arguments": "{\"...\"}"），需要二次解析
        args = payload.get("arguments", payload.get("args", {}))
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, ValueError):
                pass
        calls.append({"name": payload["name"], "args": args, "id": f"text_call_{len(calls)}"})
    return calls


class BaseAgent(ABC):
    name: str = "base"
    description: str = ""
    system_prompt: str = ""
    max_tokens: int = 320  # 子类可覆盖；禁思考后生成显著变短，收紧预算降低CPU耗时

    def __init__(self) -> None:
        """初始化：创建带指标采集的 LLM 客户端，并绑定本 Agent 的工具集

        - llm：MetricChatOpenAI（自动记录调用耗时/token，按 task 打标）
        - tools：register_tools() 返回的工具列表
        - llm_with_tools：绑定了工具描述的 LLM（云端 tool-calling 专用）
        """
        self.llm = get_llm_for_task(self.name, max_tokens=self.max_tokens)
        self.tools = self.register_tools()
        self.llm_with_tools = self.llm.bind_tools(self.tools) if self.tools else self.llm

    @abstractmethod
    def register_tools(self) -> list[BaseTool]:
        """注册本Agent可用的工具（来自 app.tools）"""
        ...

    @abstractmethod
    async def run(self, state: AgentState) -> dict:
        """作为LangGraph节点执行，返回需要合并进状态的字段"""
        ...

    async def _execute_tool_call(self, tc: dict) -> str:
        """执行单个工具调用，返回结果文本（异常不阻断）

        参数 tc：{"name": 工具名, "args": 参数字典}
        返回：工具结果的字符串（JSON 或自然语言），失败返回错误提示，
        后续由 LLM 基于该结果组织客服话术。
        """
        from app.agents.trace import get_current_trace_id, trace_store
        from app.core.metrics import TOOL_ERRORS
        from app.tools.registry import is_enabled

        trace_id = get_current_trace_id()
        tool = next((t for t in self.tools if t.name == tc["name"]), None)
        if tool is None:
            trace_store.record_tool(trace_id, tc["name"], tc.get("args"), "工具不存在", "error", 0)
            TOOL_ERRORS.labels(tool=tc["name"]).inc()
            return f"未找到工具: {tc['name']}"
        if not is_enabled(tc["name"]):
            trace_store.record_tool(trace_id, tc["name"], tc.get("args"), "工具已停用", "disabled", 0)
            return f"工具 {tc['name']} 已停用，请改用其他方式处理。"
        try:
            t0 = time.perf_counter()
            result = str(await tool.ainvoke(tc["args"]))
            elapsed = time.perf_counter() - t0
            # 指标采集：工具调用次数/耗时（Agent 平台统计看板）
            from app.core.metrics import TOOL_CALLS, TOOL_DURATION
            TOOL_CALLS.labels(tool=tc["name"]).inc()
            TOOL_DURATION.labels(tool=tc["name"]).observe(elapsed)
            trace_store.record_tool(trace_id, tc["name"], tc.get("args"), result, "ok", elapsed * 1000)
            perf_logger.info(f"[{self.name}] tool={tc['name']}: {elapsed * 1000:.0f}ms")
            return result
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000 if 't0' in locals() else 0.0
            trace_store.record_tool(trace_id, tc["name"], tc.get("args"), str(exc), "error", elapsed)
            TOOL_ERRORS.labels(tool=tc["name"]).inc()
            perf_logger.warning(f"[{self.name}] tool={tc['name']} FAILED: {exc}")
            return f"工具执行失败: {exc}"

    async def _tool_call_loop(self, messages: list, max_rounds: int = 3) -> list:
        """阶段二~三：LLM 工具决策 → 执行工具 → 结果回填 → 再决策 的循环。

        每轮调用LLM：若响应携带tool_calls（标准协议）或文本中包含
        <tool_call>块（本地GGUF兼容），则执行对应工具并回填结果，
        直到LLM不再请求工具（产生最终回答）或达到轮次上限。

        说明：
        - 本地模型：把工具指令注入第一条 SystemMessage（llama.cpp 原生
          function calling 支持有限，用文本协议代替）
        - 云端模型：直接使用 OpenAI 标准 tool_calls，LangChain 自动处理
        """
        # 本地模型：把工具描述与使用格式注入系统提示词
        if settings.llm_provider in ("local", "existing") and messages and hasattr(messages[0], "content"):
            # 禁止 Qwen3 推理链，直接输出答案
            messages[0].content += "\n\n【重要】直接回答，不要使用 <think> 标签输出推理过程。"
            if self.tools:
                tool_descs = "\n".join(f"- {t.name}: {t.description}" for t in self.tools)
                tool_prompt = (
                    f"\n\n【可用工具】\n{tool_descs}\n\n"
                    "使用工具时，严格按照以下格式输出（只输出工具调用，不要加任何解释）：\n"
                    '<tool_call>{"name": "工具名", "arguments": {"参数名": "参数值"}}</tool_call>\n'
                    "工具返回结果后，请基于结果组织回答。"
                )
                messages[0].content += tool_prompt

        t_start = time.perf_counter()
        for round_idx in range(max_rounds):
            t0 = time.perf_counter()
            resp = await self.llm_with_tools.ainvoke(messages)
            t_llm = time.perf_counter() - t0

            # 清洗思考标签（Qwen3 等模型思考链会进入 content）
            if resp.content:
                resp.content = _strip_think_tags(resp.content)

            # ① 标准 OpenAI 协议 tool_calls（云端大模型）
            tool_calls = list(getattr(resp, "tool_calls", None) or [])
            # ② 本地 GGUF 兼容：从文本解析 <tool_call> 块
            if not tool_calls and resp.content:
                tool_calls = parse_tool_calls_from_text(resp.content)
                if not tool_calls and "<tool_call>" in resp.content:
                    perf_logger.warning(f"[{self.name}] LLM output has <tool_call> but parse failed, content[:300]={resp.content[:300]!r}")
                if tool_calls:
                    resp.content = _TOOL_CALL_RE.sub("", resp.content).strip()
            # 把当前轮 LLM 响应追加进消息历史（供下一轮看到自己说过什么）
            messages.append(resp)

            gen_len = len(resp.content) if resp.content else 0
            perf_logger.info(f"[{self.name}] LLM round={round_idx + 1}: {t_llm * 1000:.0f}ms, gen_tokens~{gen_len}, tool_calls={len(tool_calls)}")

            if not tool_calls:
                perf_logger.info(f"[{self.name}] _tool_call_loop TOTAL: {(time.perf_counter() - t_start) * 1000:.0f}ms (rounds={round_idx + 1})")
                break  # LLM产生最终回答

            # ③ 执行所有工具调用，并把结果以 HumanMessage 回填
            #    （对本地 llama.cpp 服务来说 HumanMessage 兼容性最好）
            for tc in tool_calls:
                result = await self._execute_tool_call(tc)
                # 用HumanMessage回填结果（对本地llama.cpp服务兼容性最好）
                messages.append(
                    HumanMessage(
                        content=f"[工具 {tc['name']} 返回结果]：{result}\n请根据该结果回答用户的问题，不要再调用工具。"
                    )
                )
        return messages
