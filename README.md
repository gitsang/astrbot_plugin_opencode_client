# astrbot-plugin-opencode-client

连接 OpenCode Server 的 AstrBot 插件

## 功能

- 连接远程 OpenCode Server
- 支持 HTTP Basic Auth 认证
- 在聊天平台中使用 OpenCode 的 AI 能力

## 安装

将此插件放置在 AstrBot 的 `data/plugins/astrbot_plugin_opencode_client` 目录下。

## 配置

在 AstrBot 管理面板中配置以下选项：

| 配置项 | 描述 | 默认值 |
|--------|------|--------|
| server_url | OpenCode Server 地址 | http://localhost:4096 |
| username | Basic Auth 用户名 | opencode |
| password | Basic Auth 密码 | (空) |
| timeout | 请求超时时间(秒) | 300 |

## 使用

```
/oc <command> [args]
```

### 命令列表

| 命令 | 描述 |
|------|------|
| `/oc chat <message>` | 与 AI 对话 |
| `/oc session` | 显示当前会话信息 |
| `/oc sessions` | 列出所有会话 |
| `/oc new [title]` | 创建新会话 |
| `/oc clear` | 清除当前会话 |
| `/oc commands` | 列出可用命令 |
| `/oc cmd <cmd> [args]` | 执行斜杠命令 |
| `/oc health` | 检查服务器状态 |

### 示例

```
/oc chat 你好，请介绍一下自己
/oc new 我的第一个会话
/oc session
/oc health
```

## 相关链接

- [AstrBot](https://github.com/AstrBotDevs/AstrBot)
- [OpenCode](https://opencode.ai)
- [OpenCode Server 文档](https://opencode.ai/docs/zh-cn/server/)
- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)
