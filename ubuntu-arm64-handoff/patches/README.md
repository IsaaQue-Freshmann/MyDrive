# 插件说明与本地补丁

本目录里的 `astrbot_plugin_astrbot_enhance_mode` 是 **0.2.4 的修改版**，不是原版直接下载。

## 修改内容

1. `plugin_config.py`
   - `active_reply_enabled` 不再强制依赖 React 模式。
   - 原因：React 模式会改写所有群的提示词，不符合“只有 866379084 自动回复，其他群保持原样”。

2. `main.py`
   - 主动回复时把 `Image` 组件转换成 `image_urls` 并传给主模型，修复“图片收不到”。
   - 在目标群（白名单命中）里，任何图片消息都绕过文字判定，直接触发视觉回复；单图、无配文也生效。
   - 图片请求附带“本轮包含图片”的提示，避免模型沿用旧的“没看到图”上下文。

3. `data/config/astrbot_plugin_astrbot_enhance_mode_config.json`
   - 只对 `866379084` 开启 `model_choice` 主动回复。
   - `model_choice_provider_id = deepseek-flash`
   - `model_stack_size = 1`
   - `model_history_messages = 10`
   - React/群历史/封禁/记忆/搜索/浏览器全部关闭。

## 注意

- 这是本地修改版；如果用 AstrBot 插件市场更新，可能覆盖补丁，更新后要重新检查。
- 原版依赖：`fastapi`、`uvicorn`。AstrBot 镜像通常已带，若有缺失再安装。
- 插件配置文件要放到 `data/config/astrbot_plugin_astrbot_enhance_mode_config.json`。

## 安全插件

`astrbot_plugin_safety_guard` 是本地独立插件，不依赖 enhance：

- 定时任务最短周期 **2 小时**
- 低于 2 小时直接发“检测到疑似攻击行为，请规避”
- 只有 AstrBot 管理员可以创建/修改定时任务
- 不用关键词枚举判断周期，直接解析实际 cron 表达式
- 2 小时及以上直接设置，不追加确认或生效时间追问
