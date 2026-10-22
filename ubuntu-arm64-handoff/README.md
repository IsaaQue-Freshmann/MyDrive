# 鲸鲸 QQ + DeepSeek：Ubuntu ARM64 重新落地交接手册

> 目标：在一台 **Ubuntu ARM64** 机器上重建当前 Mac 上的“QQ 个人号 + AstrBot + DeepSeek”方案。  
> 方案主体：**AstrBot Docker + NapCat Docker（MODE=astrbot）**。  
> 不包含任何 API Key、面板密码或 NapCat Token；这些需要在新机器上重新填写/生成。

---

## 0. 最终架构

```text
QQ 用户 / 群友
      │
      ▼
QQ 服务器
      │
      ▼
NapCat（Docker，登录 鲸鲸 2839347610）
      │  OneBot v11 反向 WebSocket（Docker 内网 ws://astrbot:6199/ws）
      ▼
AstrBot（Docker，WebUI 6185）
      │
      ▼
DeepSeek API（deepseek-flash，支持文本/图片）
```

关键账号与范围：

- 机器人 QQ：`鲸鲸 / 2839347610`
- 主号/管理员：`2458273469`
- 自动接话群：`866379084（传奇转点）`
- 其他群：保持原来的“@ 或 `/` 开头才回复”
- 定时任务：只有主号可创建；最短周期 2 小时；低于 2 小时警告

> NapCat 是第三方协议端，个人 QQ 接入有风控风险。继续使用备用号，不要用主号。

---

## 1. 前置条件

- Ubuntu 24.04 LTS **ARM64 / aarch64**（Server 或 Desktop 均可；推荐 Server）
- 2 核 4GB 内存以上，20GB 可用磁盘
- 能访问 Docker Hub、GitHub、DeepSeek API
- 已安装 Docker Engine + Docker Compose v2
- 手机能扫码登录 `鲸鲸`，且该号已在 `866379084` 群内
- DeepSeek API Key（`platform.deepseek.com`，API 与网页版会员不是一回事，需要单独余额）

先检查架构：

```bash
uname -m
# 必须输出 aarch64
```

---

## 2. 安装 Docker

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
newgrp docker
```

验证：

```bash
docker version
docker compose version
```

如果 Ubuntu 仓库没有 `docker-compose-v2`，按 Docker 官方文档安装 Docker Engine 和 Compose 插件。

AstrBot 官方镜像是多架构的，ARM64 会拉取 `linux/arm64` 变体；如果拉取失败，可以换国内镜像（见第 11 节）。

---

## 3. 建立目录并放入文件

在 Ubuntu 上：

```bash
mkdir -p ~/whale-bot
cd ~/whale-bot
```

把交接包里的文件放进去。假设交接包已经解压到 `~/ubuntu-arm64-handoff`：

```bash
cp ~/ubuntu-arm64-handoff/compose.yaml ~/whale-bot/compose.yaml
mkdir -p ~/whale-bot/data
cp -a ~/ubuntu-arm64-handoff/plugins ~/whale-bot/data/
mkdir -p ~/whale-bot/data/config
cp -a ~/ubuntu-arm64-handoff/data/config/. ~/whale-bot/data/config/
```

目录应类似：

```text
~/whale-bot/
├── compose.yaml
└── data/
    ├── plugins/
    │   ├── astrbot_plugin_astrbot_enhance_mode/
    │   └── astrbot_plugin_safety_guard/
    └── config/
        └── astrbot_plugin_astrbot_enhance_mode_config.json
```

`data/` 是 AstrBot 的持久化数据目录，后续还会生成 `cmd_config.json`、数据库、插件配置等。

创建 `.env`：

```bash
cd ~/whale-bot
cat > .env <<EOF
NAPCAT_UID=$(id -u)
NAPCAT_GID=$(id -g)
TZ=Asia/Shanghai
EOF
chmod 600 .env
```

---

## 4. 启动容器

```bash
cd ~/whale-bot
docker compose up -d
docker compose ps
```

首次启动会拉取镜像。两个容器都应为 `running`：

```text
napcat    ... Up
astrbot   ... Up
```

查看日志：

```bash
docker compose logs -f astrbot
```

另开一个终端查看 NapCat：

```bash
docker compose logs -f napcat
```

### 端口安全

`compose.yaml` 已经设置为：

- AstrBot WebUI：`127.0.0.1:6185`
- NapCat WebUI：`127.0.0.1:6099`
- AstrBot 的 6199 **不映射到宿主机**，只在 Docker 内网供 NapCat 连接

从 Mac 访问时用 SSH 隧道：

```bash
ssh -N \
  -L 6185:127.0.0.1:6185 \
  -L 6099:127.0.0.1:6099 \
  <user>@<server>
```

然后在本机浏览器打开：

- AstrBot：`http://127.0.0.1:6185`
- NapCat：`http://127.0.0.1:6099`

不要把 6099/6185 直接暴露到公网。

---

## 5. AstrBot 初始化

### 5.1 获取初始密码

```bash
docker compose logs astrbot 2>&1 | grep -a "Initial password" | tail -1
```

用日志中的用户名/密码登录：

- 用户名：`astrbot`
- 密码：日志里的 `Initial password`

登录后先修改面板密码。

### 5.2 配置 DeepSeek

WebUI 路径大致为：

**模型提供商 → 对话 → 新增**

填写：

- 类型：DeepSeek（或 OpenAI Compatible）
- API Base：`https://api.deepseek.com/v1`
- API Key：你的 DeepSeek Key
- 模型：`deepseek-flash`
- 模型能力/模态：`text`、`image`、`tool_use`（至少要有 `image`）

保存并获取模型；如果列表没有 `deepseek-flash`，用“自定义模型”手动填入。  
把默认对话模型设为 `deepseek-flash`。

> 当前 Mac 上验证过：DeepSeek 直连图片输入可用。新机器必须确认提供商配置里的 **modalities 包含 image**，否则 AstrBot 会在交给模型前丢弃图片。

### 5.3 创建 OneBot v11 机器人

**机器人 → 创建机器人 → OneBot v11 / QQ 个人号**

填写：

- ID：`napcat`
- 启用：开
- 反向 WebSocket 主机：`0.0.0.0`
- 反向 WebSocket 端口：`6199`
- Token：留空（仅 Docker 内网；如果你自行加 Token，NapCat 那边必须同步）

保存后查看 AstrBot 日志，应出现：

```text
aiocqhttp(OneBot v11) 适配器已连接。
```

如果是用 NapCat Docker 的 `MODE=astrbot`，它会自动连到 `ws://astrbot:6199/ws`，不需要手动把 6199 映射到宿主机。

### 5.4 管理员与权限

**配置 → 访问控制 → 管理员 → 管理员 ID**

填入：

```text
2458273469
astrbot
```

**配置 → AI → 能力 → Agent Computer Use**

设置为：

- Runtime：**local（本机环境）**
- admin（2458273469）：
  - 文件范围：`workspace`
  - 执行：允许
  - 执行联网：允许
- member（其他所有人）：
  - 文件范围：`none`
  - 执行：禁止
  - 执行联网：禁止

注意：这里虽然叫 `local`，但 AstrBot 在 Docker 里，所以 admin 的 shell/Python 实际运行在 **AstrBot 容器内部**，不是 Ubuntu 宿主机；`workspace` 也是容器内工作区。需要操作宿主机时应另做明确的挂载/服务，不要为了省事给容器 Docker socket 或宿主机根目录。

如果日志提示 Local 进程隔离不可用，执行权限会被 AstrBot 主动禁用。此时优先关闭 admin 的“执行”权限，不要为了绕过隔离去挂载宿主机根目录或开放 Docker socket。

### 5.5 回复设置

在 **配置 → 普通配置** 中设置：

- `wake_prefix`：`["/"]`
- `provider_settings.identifier`：开
- `provider_settings.group_name_display`：开
- `platform_settings.reply_with_mention`：关
- `platform_settings.reply_with_quote`：关
- `platform_settings.ignore_bot_self_message`：开
- 分段回复：
  - 开启
  - 只对 LLM 结果
  - 阈值：`500`
  - 模式：`words`
  - 分隔词：`。 ！ ？ ! ? … 换行`
  - 间隔：`0.8,1.6`
- 时区：`Asia/Shanghai`

这些设置对应：

- 一条回复默认不超过 35 个汉字
- 需要补充时按句拆成 2～3 条短消息
- 群聊不每条都 @ 提问者

### 5.6 人格

在 **人格** 中编辑 `default`，把交接包中：

```text
private/persona.txt
```

的内容粘贴进去。这个文件包含主号、群友等私人设定，**不要公开分享**。

---

## 6. NapCat 登录鲸鲸

先确保 Mac 上的鲸鲸/NapCat 已经停止，否则同一个 QQ 号会在 PC 端互踢。主号 `2458273469` 建议继续留在手机上使用，不要在 Ubuntu 上再开一个 QQ 客户端。

查看日志或通过 SSH 隧道打开 NapCat WebUI：

```bash
docker compose logs -f napcat
```

用手机 QQ 扫码登录：

- 账号：`鲸鲸 2839347610`
- 登录后确认账号在线
- 查看 NapCat 与 AstrBot 的连接；AstrBot 日志出现“适配器已连接”即成功

如 NapCat WebUI 需要 Token，Token 会在启动日志或 `./napcat/config/webui.json` 中，不要发到群里。

---

## 7. 插件已经预置

交接包内已经包含：

### 7.1 `astrbot_plugin_astrbot_enhance_mode`

修改版 0.2.4，负责：

- 只在 `866379084` 启用 `model_choice` 主动接话
- 其他群不主动回复
- 自动回复时把图片一起传给 DeepSeek
- 目标群内任何人的图片，即使单图无文字，也直接触发视觉回复

配置文件：

```text
data/config/astrbot_plugin_astrbot_enhance_mode_config.json
```

> 不要同时开启 AstrBot 内置的“主动回复”和“群聊上下文感知”；本项目由 enhance 插件负责这一层，双重开启会导致重复回复或上下文重复注入。

关键值：

```json
{
  "active_reply": {
    "enable": true,
    "mode": "model_choice",
    "model_stack_size": 1,
    "model_history_messages": 10,
    "model_choice_provider_id": "deepseek-flash",
    "whitelist": "866379084,napcat:GroupMessage:866379084"
  },
  "group_features": {
    "react_mode_enable": false,
    "ban_control_enable": false
  },
  "group_history_enhancement": {"enable": false},
  "web_search": {"enable": false},
  "browser_tool": {"enable": false},
  "memory_rag": {"enable": false},
  "memory_rag_webui": {"enable": false}
}
```

### 7.2 `astrbot_plugin_safety_guard`

本地插件，负责：

- 定时任务最短周期 **2 小时**
- 低于 2 小时：直接通过 QQ 发送“检测到疑似攻击行为，请规避”
- 只有管理员能创建/修改定时任务
- 2 小时及以上直接设置，不追加确认、不追问生效时间
- 不靠关键词表判断周期，直接解析实际 cron 表达式

启动后检查日志：

```bash
docker compose logs astrbot 2>&1 | grep -E "enhance-mode \| loaded|safety-guard"
```

应看到：

```text
safety-guard | future_task protection installed
safety-guard | loaded with 2-hour minimum schedule period
enhance-mode | loaded | ... active_reply=True ...
```

如果插件没有加载：

```bash
docker compose logs astrbot | tail -100
ls -la data/plugins
```

确认目录名、`metadata.yaml`、`main.py` 都存在，且容器用户可读。

---

## 8. 群聊与图片

1. 先把 `鲸鲸` 拉进/确认在 `866379084`。
2. 在 `866379084` 里 @ 她一次，例如“鲸鲸在吗”。  
   这一步会建立该群的对话上下文。
3. 之后在这个群发不带 @ 的消息，她会先经过 `model_choice` 判断：
   - 判定 REPLY：用人格回复
   - 判定 SKIP：不说话
4. 任何人在 `866379084` 发图片，都会直接进入视觉回复。
5. 其他群仍保持 @ 或 `/` 前缀才回复，不受这个插件影响。

如果自动回复没有触发，重点看：

```bash
docker compose logs astrbot 2>&1 | grep -E "model_choice|active_reply|图片|image"
```

常见原因：

- 该群还没有对话（先 @ 一次）
- DeepSeek provider ID 不是 `deepseek-flash`
- 插件白名单没有匹配
- 图片能力 `modalities` 没有 `image`

---

## 9. 定时任务规则

- 主号 `2458273469` 可以创建/修改定时任务
- 其他成员不能创建或修改
- 最短 2 小时
- 允许：每天、每周、每月、每 2 小时、每 12 小时
- 拦截：每 10 分钟、每小时、每 7 小时等低于 2 小时的任务
- 低于 2 小时会直接发警告，不等待模型转述
- 2 小时及以上不会再问“确定吗”或要求确认生效时间

测试：

```text
每2小时提醒我喝水
```

应直接设置。

```text
每小时提醒我喝水
```

应收到“检测到疑似攻击行为，请规避”的警告。

---

## 10. 运维

### 重启/查看

```bash
cd ~/whale-bot
docker compose ps
docker compose logs -f --tail=100 astrbot
docker compose logs -f --tail=100 napcat
docker compose restart astrbot
docker compose restart napcat
docker compose down
docker compose up -d
```

### 备份

```bash
cd ~
sudo tar -czf "whale-bot-backup-$(date +%F-%H%M).tgz" whale-bot
```

备份包含 QQ 登录数据、AstrBot 数据库、API Key 和人格，务必妥善保管，不要上传公开仓库。

### 开机自启

`compose.yaml` 已设置 `restart: unless-stopped`，并启用 Docker 服务：

```bash
sudo systemctl enable docker
```

---

## 11. 常见问题

### 镜像拉取失败

AstrBot 官方文档建议国内可替换为：

```text
m.daocloud.io/docker.io/soulter/astrbot:latest
```

NapCat 镜像类似替换仓库前缀即可；如果 Docker daemon 配了代理，镜像拉取使用 daemon 代理，和普通 curl 代理不是一回事。

### `exec format error`

说明拉到了错误架构的镜像：

```bash
uname -m                 # 应为 aarch64
docker image inspect soulter/astrbot:latest --format '{{.Architecture}}'
```

AstrBot 镜像应是 `arm64`。

### NapCat 二维码不出现

```bash
docker compose logs -f napcat
```

确认 `NAPCAT_UID/GID` 与当前用户一致，`./ntqq` 可写；也可以打开 6099 WebUI 查看登录二维码。

### AstrBot 说连不上 NapCat

- AstrBot 机器人端口应为 `6199`
- Docker 内 NapCat 的 `MODE=astrbot` 会自动向 `astrbot:6199` 连接
- 不要改成 `127.0.0.1`（容器里的 127.0.0.1 不是 AstrBot 容器）
- 检查两个容器是否在同一个 Docker network

### 图片仍然提示“没收到”

- 检查 DeepSeek provider 的 `modalities` 是否包含 `image`
- 检查 `data/plugins/...enhance.../main.py` 是否是交接包里的修改版
- 查看 AstrBot 日志是否还有 `does not support image input`

### 自动回复失效

- 确认 `active_reply.enable=true`
- 确认 `whitelist` 包含 `866379084` 或对应 UMO
- 先在该群 @ 一次建立 conversation
- 检查 `model_choice` 判定日志

---

## 12. 与 Mac 端的差异 / 不要照搬的东西

不要复制到 Linux：

- `/Applications/QQ.app` 的 `package.json` 补丁
- `~/Library/Containers/.../loadNapCat.js`
- NapCat macOS 安装器
- `启动鲸鲸Bot.command`、`停止鲸鲸Bot.command`
- macOS 的 `pmset` 设置
- Mac 上 `~/.astrbot/data/cmd_config.json`（里面含 API Key、macOS 路径、旧 Token）

Linux 侧对应关系：

| Mac | Ubuntu ARM64 |
|---|---|
| AstrBot.app | AstrBot Docker 容器 |
| NapCat Mac Installer/QQ.app 注入 | NapCat Docker（MODE=astrbot） |
| `ws://127.0.0.1:6199/ws` | Docker 内网 `ws://astrbot:6199/ws` |
| `~/Applications/*.command` | `docker compose up -d/restart` |
| `pmset` | 无需；服务器常开 |
| App 管理授权 | 无需 |

---

## 13. 可选：ZCode Linux ARM64

ZCode 不是运行机器人必需的，只是如果要在新机器上继续使用 ZCode 编辑/运维，可以装 Linux ARM64 版：

- AppImage：`https://cdn-zcode.z.ai/zcode/electron/releases/3.16.2/linux-arm64/ZCode-3.16.2-linux-arm64.AppImage`
- DEB：`https://cdn-zcode.z.ai/zcode/electron/releases/3.16.2/linux-arm64/ZCode-3.16.2-linux-arm64.deb`
- RPM：`https://cdn-zcode.z.ai/zcode/electron/releases/3.16.2/linux-arm64/ZCode-3.16.2-linux-arm64.rpm`

Ubuntu 建议：

```bash
sudo apt install ./ZCode-3.16.2-linux-arm64.deb
```

Linux 版可能仍带 Beta 标记；不装它不影响鲸鲸运行。

## 14. 官方参考

- AstrBot Docker 部署：https://docs.astrbot.app/deploy/astrbot/docker.html
- AstrBot 启动器（桌面）：https://docs.astrbot.app/deploy/astrbot/launcher.html
- NapCat Shell / Linux 安装：https://napneko.github.io/guide/boot/Shell
- NapCat-Docker 官方 AstrBot Compose：https://github.com/NapNeko/NapCat-Docker/blob/main/compose/astrbot.yml
- DeepSeek API 文档：https://api-docs.deepseek.com/
- 当前使用的 enhance 插件：https://github.com/Axi404/astrbot_plugin_astrbot_enhance_mode

---

## 15. 最小验证清单

- [ ] `docker compose ps` 两个容器 running
- [ ] AstrBot 6185 可通过 SSH 隧道打开，初始密码已修改
- [ ] DeepSeek 提供商测试 `available`，`modalities` 含 `image`
- [ ] AstrBot 日志出现 `aiocqhttp(OneBot v11) 适配器已连接`
- [ ] NapCat 登录 `鲸鲸 2839347610` 在线
- [ ] `866379084` 中 @ 一次可回复
- [ ] `866379084` 中不 @ 也能按判定回复
- [ ] `866379084` 中任何成员发单图，能识别并回复
- [ ] 其他群仅 @ 或 `/` 触发，不自动接话
- [ ] 主号设置“每2小时”任务直接成功，不追问
- [ ] “每小时”任务被拦截并收到警告
- [ ] 非管理员无法创建定时任务
- [ ] `docker compose logs astrbot` 中有 safety-guard 和 enhance 加载日志
