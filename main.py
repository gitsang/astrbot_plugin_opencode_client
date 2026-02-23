import json
from typing import Optional
import httpx
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


class OpenCodeClient:
    def __init__(
        self, server_url: str, username: str, password: str, timeout: int = 300
    ):
        self.server_url = server_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _get_auth(self) -> Optional[tuple[str, str]]:
        return (self.username, self.password) if self.password else None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.server_url,
                auth=self._get_auth(),
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health(self) -> dict:
        client = await self._get_client()
        resp = await client.get("/global/health")
        resp.raise_for_status()
        return resp.json()

    async def list_sessions(self) -> list:
        client = await self._get_client()
        resp = await client.get("/session")
        resp.raise_for_status()
        return resp.json()

    async def create_session(self, title: Optional[str] = None) -> dict:
        client = await self._get_client()
        body = {}
        if title:
            body["title"] = title
        resp = await client.post("/session", json=body)
        resp.raise_for_status()
        return resp.json()

    async def get_session(self, session_id: str) -> dict:
        client = await self._get_client()
        resp = await client.get(f"/session/{session_id}")
        resp.raise_for_status()
        return resp.json()

    async def delete_session(self, session_id: str) -> bool:
        client = await self._get_client()
        resp = await client.delete(f"/session/{session_id}")
        resp.raise_for_status()
        return resp.json()

    async def send_message(
        self, session_id: str, text: str, model: Optional[dict] = None
    ) -> dict:
        client = await self._get_client()
        body: dict = {"parts": [{"type": "text", "text": text}]}
        if model:
            body["model"] = model
        resp = await client.post(f"/session/{session_id}/message", json=body)
        resp.raise_for_status()
        return resp.json()

    async def execute_command(
        self, session_id: str, command: str, args: Optional[dict] = None
    ) -> dict:
        client = await self._get_client()
        body: dict = {"command": command}
        if args:
            body["arguments"] = args
        resp = await client.post(f"/session/{session_id}/command", json=body)
        resp.raise_for_status()
        return resp.json()

    async def list_commands(self) -> list:
        client = await self._get_client()
        resp = await client.get("/command")
        resp.raise_for_status()
        return resp.json()

    async def get_messages(self, session_id: str, limit: int = 50) -> list:
        client = await self._get_client()
        resp = await client.get(
            f"/session/{session_id}/message", params={"limit": limit}
        )
        resp.raise_for_status()
        return resp.json()


def extract_text_from_parts(parts: list) -> str:
    texts = []
    for part in parts:
        if part.get("type") == "text":
            texts.append(part.get("text", ""))
    return "\n".join(texts)


@register(
    "astrbot_plugin_opencode_client", "gitsang", "OpenCode Server 连接器", "1.0.0"
)
class OpenCodeClientPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.client: Optional[OpenCodeClient] = None
        self._sessions: dict[str, str] = {}

    async def initialize(self):
        server_url = self.config.get("server_url", "http://localhost:4096")
        username = self.config.get("username", "opencode")
        password = self.config.get("password", "")
        timeout = self.config.get("timeout", 300)

        self.client = OpenCodeClient(
            server_url=server_url, username=username, password=password, timeout=timeout
        )

        try:
            health = await self.client.health()
            logger.info(
                f"OpenCode Client 已连接，版本: {health.get('version', 'unknown')}"
            )
        except Exception as e:
            logger.warning(f"OpenCode Server 连接失败: {e}")

    async def terminate(self):
        if self.client:
            await self.client.close()

    def _get_session_key(self, event: AstrMessageEvent) -> str:
        return f"{event.get_platform_name()}_{event.get_session_id()}"

    async def _get_or_create_session(self, event: AstrMessageEvent) -> str:
        key = self._get_session_key(event)
        if key not in self._sessions:
            if not self.client:
                raise RuntimeError("OpenCode Client 未初始化")
            title = f"AstrBot Session - {event.get_sender_name()}"
            session = await self.client.create_session(title=title)
            self._sessions[key] = str(session["id"])
            logger.info(f"创建新会话: {session['id']}")
        return self._sessions[key]

    @filter.command("oc")
    async def opencode_command(self, event: AstrMessageEvent):
        """OpenCode 指令处理器"""
        message_str = event.message_str.strip()
        parts = message_str.split(maxsplit=2)

        if len(parts) < 2:
            yield event.plain_result(
                "用法: /oc <command> [args]\n"
                "命令:\n"
                "  /oc chat <message>  - 与 AI 对话\n"
                "  /oc session         - 显示当前会话信息\n"
                "  /oc sessions        - 列出所有会话\n"
                "  /oc new             - 创建新会话\n"
                "  /oc clear           - 清除当前会话\n"
                "  /oc commands        - 列出可用命令\n"
                "  /oc cmd <cmd>       - 执行斜杠命令\n"
                "  /oc health          - 检查服务器状态"
            )
            return

        command = parts[1].lower()
        args = parts[2] if len(parts) > 2 else ""

        try:
            if not self.client:
                yield event.plain_result("OpenCode Client 未初始化，请检查配置")
                return

            if command == "chat":
                if not args:
                    yield event.plain_result("用法: /oc chat <message>")
                    return
                session_id = await self._get_or_create_session(event)
                yield event.plain_result("思考中...")
                result = await self.client.send_message(session_id, args)
                response_text = extract_text_from_parts(result.get("parts", []))
                yield event.plain_result(response_text or "(无响应)")

            elif command == "session":
                session_id = self._sessions.get(self._get_session_key(event))
                if not session_id:
                    yield event.plain_result("当前没有活跃会话，使用 /oc chat 开始对话")
                    return
                session = await self.client.get_session(session_id)
                yield event.plain_result(
                    f"当前会话:\n"
                    f"  ID: {session.get('id', 'N/A')}\n"
                    f"  标题: {session.get('title', 'N/A')}\n"
                    f"  创建时间: {session.get('created_at', 'N/A')}"
                )

            elif command == "sessions":
                sessions = await self.client.list_sessions()
                if not sessions:
                    yield event.plain_result("暂无会话")
                    return
                lines = ["会话列表:"]
                for i, s in enumerate(sessions[:10], 1):
                    lines.append(
                        f"  {i}. [{s.get('id', 'N/A')[:8]}] {s.get('title', 'N/A')}"
                    )
                yield event.plain_result("\n".join(lines))

            elif command == "new":
                title = args if args else f"New Session - {event.get_sender_name()}"
                session = await self.client.create_session(title=title)
                self._sessions[self._get_session_key(event)] = session["id"]
                yield event.plain_result(f"已创建新会话: {session['id']}")

            elif command == "clear":
                key = self._get_session_key(event)
                if key in self._sessions:
                    del self._sessions[key]
                    yield event.plain_result("已清除当前会话")
                else:
                    yield event.plain_result("没有活跃会话")

            elif command == "commands":
                commands = await self.client.list_commands()
                if not commands:
                    yield event.plain_result("暂无可用命令")
                    return
                lines = ["可用命令:"]
                for cmd in commands[:20]:
                    name = cmd.get("name", "N/A")
                    desc = cmd.get("description", "")[:30]
                    lines.append(f"  /{name} - {desc}")
                yield event.plain_result("\n".join(lines))

            elif command == "cmd":
                if not args:
                    yield event.plain_result("用法: /oc cmd <command> [args]")
                    return
                session_id = await self._get_or_create_session(event)
                cmd_parts = args.split(maxsplit=1)
                cmd_name = cmd_parts[0]
                cmd_args = json.loads(cmd_parts[1]) if len(cmd_parts) > 1 else None
                yield event.plain_result("执行命令中...")
                result = await self.client.execute_command(
                    session_id, cmd_name, cmd_args
                )
                response_text = extract_text_from_parts(result.get("parts", []))
                yield event.plain_result(response_text or "命令执行完成")

            elif command == "health":
                health = await self.client.health()
                yield event.plain_result(
                    f"OpenCode Server 状态:\n"
                    f"  健康: {health.get('healthy', False)}\n"
                    f"  版本: {health.get('version', 'N/A')}"
                )

            else:
                yield event.plain_result(f"未知命令: {command}\n使用 /oc 查看帮助")

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误: {e}")
            yield event.plain_result(f"请求失败: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"网络错误: {e}")
            yield event.plain_result(f"网络错误: {e}")
        except Exception as e:
            logger.error(f"错误: {e}")
            yield event.plain_result(f"错误: {e}")
