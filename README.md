# 股票投研圆桌系统 · 云端版（TCB 部署手册）

把「主理人 + 6 专家」多 Agent 圆桌投研，封装成 **微信小程序 + 云端运行** 的可远程交互系统。
本机只是终端，**逻辑与数据全在云端**，关机照常运行；定时任务（盘前/午盘/尾盘/收盘）云端常驻。

> 本文件是给「部署者/使用者」的详细手册。代码已可本地 mock 跑通、真实取数已接入（见 §4）。
> 你（用户）真正需要动手的部分集中在 §6～§9，已逐条拆解成可操作步骤。

---

## 1. 功能范围（MVP）

- 单股深度圆桌、持仓组合诊断、板块/主题研判
- 条件选股 + 自选异动订阅
- 云端定时推送（盘前/午盘/尾盘/收盘）→ 消息中心 + 订阅消息 + 邮件兜底
- 小范围分享（白名单账号，数据隔离）
- 合规护栏内建（免责声明、禁指令词、数据标来源）

## 2. 目录结构

```
stock-roundtable-cloud/
├── app/
│   ├── main.py        # FastAPI 路由 + 后台任务
│   ├── config.py      # 环境变量配置（TCB 注入点）
│   ├── db.py          # 数据库引擎
│   ├── models.py      # 9 张数据表
│   ├── schemas.py     # 请求/响应
│   ├── llm.py         # LLM 客户端（mock + openai 兼容）
│   ├── fetcher.py     # 取数层（mock + 真实：腾讯实时/新浪K线/akshare兜底）
│   ├── tencent_provider.py # 腾讯实时行情 + 新浪日K（轻量、稳）
│   ├── experts.py     # 6 专家系统提示词（方法论）
│   ├── orchestrator.py# 圆桌引擎（并行调度 + 4 模块汇编）
│   ├── renderer.py    # md → 单文件 HTML（已接 COS，未配置回退本地）
│   ├── cron.py        # 定时任务逻辑
│   └── notify.py      # 推送（inbox + 邮件兜底）
├── miniprogram/       # 微信小程序前端骨架
├── requirements.txt / Dockerfile / docker-compose.yml / .env.example
└── reports/           # 本地验证生成的 H5 报告（部署后改存 COS）
```

## 3. 本地快速验证（mock 模式，无需任何 key）

```bash
pip install -r requirements.txt
cp .env.example .env        # 默认 LLM_MOCK=true FETCHER_MOCK=true
uvicorn app.main:app --port 8000 --reload
```
另开终端：
```bash
curl -X POST http://localhost:8000/api/roundtable \
  -H "Content-Type: application/json" \
  -d '{"query":"帮我看看比亚迪","symbols":["002594.SZ"],"type":"single"}'
# 返回 {"task_id":"rt_xxx","status":"pending"}
curl http://localhost:8000/api/roundtable/rt_xxx   # 轮询，status=done 后看 report_html_url
```

## 4. 真实取数（已接入，无需再写代码）

| 数据 | 真实源（已验证） | 失败兜底 |
|------|------------------|----------|
| 实时行情/估值(PE/PB) | 腾讯 `qt.gtimg.cn` | akshare 单只 hist |
| 历史日 K（60 根） | 新浪日 K 接口 | akshare `stock_zh_a_hist` |
| 财务/行业 | 腾讯 PE/PB + 尽力 akshare 行业 | （网络不可达时留空，不阻塞） |

特性：
- 取数层全部**延迟 import akshare**，mock 模式不依赖它也能跑。
- 行情/K 线均带**重试**（偶发网络重置自动恢复），已在 `tencent_provider.py` 与 `fetcher.py` 双层重试。
- 启用：`.env` 设 `FETCHER_MOCK=false` 即可（akshare 已装好）。

> 注：本地沙箱访问 akshare 的 eastmoney 接口偶发被重置，已用腾讯/新浪源规避；云端（腾讯云服务器）网络环境更优。

## 5. 切真实 LLM（部署前填 key）

`.env`：
```
LLM_MOCK=false
LLM_API_KEY=你的key
LLM_BASE_URL=https://api.deepseek.com/v1   # 或混元/通义兼容地址
LLM_MODEL=deepseek-chat
```
LLM 客户端为 openai 兼容，换模型只改这三个变量，业务代码不动。

---

## 6. 你需要做的：账号与前置准备（一次性）

| # | 要做的事 | 去哪做 | 拿到什么 |
|---|----------|--------|----------|
| 1 | 注册腾讯云账号并完成实名 | cloud.tencent.com | 账号 + 微信扫码登录 |
| 2 | 开通「云开发 CloudBase」 | 控制台搜「云开发」 | 一个**环境 ID**（如 `stock-rt-1gabc`） |
| 3 | 注册微信小程序账号 | mp.weixin.qq.com | **AppID**（开发者ID）+ 在「开发管理-开发设置」拿到 |
| 4 | 准备 LLM API key | DeepSeek/混元/通义控制台 | `LLM_API_KEY` |
| 5 | （可选）QQ 邮箱授权码 | QQ 邮箱 → 设置 → 账户 → 生成授权码 | `EMAIL_PASS`（用于邮件兜底） |

> 费用提示：TCB 按量 + 基础套餐，个人低频月几十元级；LLM 按 token 另计。

---

## 7. 你需要做的：TCB 后端部署（逐步）

### 7.1 建数据库
1. 云开发控制台 → 你的环境 → **数据库** → 新建 **MySQL**（或「云数据库 MySQL」）。
2. 创建后进入实例，记下**连接串**（形如 `mysql://user:pwd@host:3306/cloudbase`）。
3. 把连接串填进后端环境变量 `DATABASE_URL`。容器启动时 `init_db()` 会自动建 9 张表，**你不用手写 SQL**。

### 7.2 建缓存（可选但建议）
- 环境 → **Redis**（或另购云数据库 Redis），拿到 `REDIS_URL` 填环境变量。不填也不影响跑，只是少了限流/行情缓存。

### 7.3 部署后端到云托管容器（核心）
1. 环境 → **云托管** → 新建服务（如 `stock-roundtable`）。
2. 部署方式选「**代码包 / 镜像**」：上传本仓库，或用 Dockerfile 构建镜像。
3. **监听端口**填 `8000`。
4. **高级设置 → 超时** 设 `300` 秒（圆桌 6 专家并行，可能分钟级，务必设长）。
5. **最小实例数** 设 `1`（避免冷启动延迟，定时任务也能随时响应）。
6. 部署完成后，云托管会给一个**默认域名**（形如 `stock-roundtable-xxx.ap-shanghai.run.tcloudbase.com`）——这就是小程序的 `BASE_URL`，且**免 ICP 备案**。

### 7.4 配置环境变量（在云托管服务「环境变量」页逐项添加）
```
DATABASE_URL=上面 7.1 的连接串
LLM_MOCK=false
LLM_API_KEY=第6步的key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
FETCHER_MOCK=false
REDIS_URL=（7.2，可选）
COS_BUCKET=（7.5，可选先留空）
BASE_URL=云托管默认域名
EMAIL_USER=（可选）
EMAIL_PASS=（可选）
```

### 7.5 报告存 COS（✅ 已完成）
- `renderer.py` 已支持上传 COS：配置 `COS_BUCKET` + `COS_REGION` + `COS_SECRET_ID` + `COS_SECRET_KEY` 四项后，报告自动上传到 `roundtable/{task_id}.html` 并返回 `https://{bucket}.cos.{region}.myqcloud.com/...`（容器重建不丢，适合小程序 `web-view`/分享）。
- **未配置时自动回退本地 `./reports`**（仅本地验证用，容器重建会丢）。
- 在云开发「存储」开一个桶，拿到上述四项填环境变量即可，无需改代码。
- 依赖 `cos-python-sdk-v5`（已注释在 `requirements.txt`，部署时在容器内安装）。

### 7.6 定时触发器（让本机不在线也跑）
用**云函数 SCF 定时触发器**调你的容器：
1. 环境 → **云函数** → 新建（Python）→ 函数代码直接复制仓库 `tcb/cron_trigger.py`（已写好，只需配环境变量 `ROUNDTABLE_BASE`=云托管默认域名）。详见该文件注释。
2. 给该函数加**定时触发器**，按表配置（Cron 为北京时间）：
   | 触发器 | Cron | 调 |
   |--------|------|----|
   | 盘前早报 | `30 8 * * 1-5` | `/internal/cron/pre` |
   | 午盘复盘 | `35 11 * * 1-5` | `/internal/cron/noon` |
   | 尾盘信号 | `30 14 * * 1-5` | `/internal/cron/tail` |
   | 收盘诊断 | `5 15 * * 1-5` | `/internal/cron/close` |
3. 云函数调 `/internal/cron/{phase}` 会**立即返回**，圆桌在容器内后台线程并发跑（详见 §10）。跑完 → 写消息中心 + 发订阅消息/邮件。

---

## 8. 你需要做的：微信小程序配置（逐步）

1. 微信开发者工具 → 导入项目 → 选本仓库 `miniprogram/` 目录 → 填你的 **AppID**。
2. 打开 `miniprogram/config.js`：
   - `BASE_URL` 填云托管默认域名（本地调试填 `http://你的局域网IP:8000`）。
3. 小程序后台 → **开发管理 → 开发设置 → 服务器域名**：
   - 在 **request 合法域名** 添加云托管默认域名（以及 `https://qt.gtimg.cn`、`https://money.finance.sina.com.cn` 如小程序端直接取数；本系统取数在后端，故只需云托管域名）。
   - 若报告页用 `web-view` 加载 H5，还需在 **业务域名** 添加报告托管域名（COS/CDN）。未配时代码会自动回退到「自绘 JSON」卡片，不影响主流程。
4. 上传 → 提交审核/或直接「真机预览」测试。

> 小程序需企业/个体户主体才能用 `web-view` 与部分能力；个人主体可用自绘卡片方案（已在代码内兼容）。

---

## 9. 你需要做的：推送与合规

- **订阅消息**：在小程序内引导用户授权「收盘诊断」等场景（调 `POST /api/subscription`）。未授权则只进消息中心 + 邮件兜底。
- **白名单**：`whitelist` 表控制小范围分享。首次部署后，手动往表里插允许的 openid（或用 `user` 表 `role` 字段）。
- **合规**：免责声明、禁指令词已内建，勿删。对外公开前评估微信金融类目资质（小范围分享风险较低，但仍建议强化免责文案）。

---

## 10. 部署前需补的两处代码（✅ 已补全并本地验证）

1. **`renderer.py` 报告上传 COS**：已完成。逻辑见 §7.5。本地 mock 验证：未配置 COS 时正确回退本地路径，前端 `GET /api/roundtable/{task_id}` 正常返回 `report_html_url`。
2. **`cron.py` 四个 phase 任务体**：已完成。
   - 修复原骨架「只写 `Report` 表、不写 `Task` 表」导致前端查询返回 `not_found` 的问题；
   - 改为：收集有持仓/自选的用户 → **线程池并发（上限 3，控容器压力）** → 每用户写 `Task(done)` + 跑圆桌 + 写 `Report` + 推 inbox/邮件；
   - 触发请求**立即返回**，圆桌在容器内后台跑，契合「云函数短超时 + 容器长任务」。
   - 本地 mock 验证：构造 demo 用户 + 持仓后跑 `close` phase，`Task`/`Report`/`Inbox` 均正确生成，前端查询返回 `done`（不再是 `not_found`）。

> 这两处是「从能跑通到能上线」的最后拼图，现已补齐。代码层面 MVP 后端已闭环。

---

## 11. 验证 Checklist（部署后逐项打勾）

- [ ] 云托管容器健康：`GET 云托管域名/` 返回 `{"status":"ok",...}`
- [ ] 小程序提问页发请求 → 收到 `task_id` → 轮询 `status=done` → 看到 H5/自绘报告
- [ ] 消息中心能看到历史报告
- [ ] 设 `FETCHER_MOCK=false` 后，报告里的价格/K线/PE 是真实数据
- [ ] 设 `LLM_MOCK=false` 后，专家观点是真实 LLM 生成（非占位）
- [ ] 定时触发器到点后，消息中心出现对应报告（本机关机也能收到）
- [ ] 邮件兜底：关键报告同时进了 QQ 邮箱

## 12. 成本与风险

- 成本：云开发按量 + 基础套餐月几十元级；LLM 按 token 计，缓存命中可降本。
- 风险：① 微信金融类目资质（对外需评估）；② 订阅消息需用户授权；③ akshare 源偶发不稳（已用腾讯/新浪规避，仍有兜底）；④ 容器冷启动（设最小实例 1）。

---

## 13. 部署常见问题（用户真实踩坑记录）

### Q1：云托管构建失败 `lstat stock-roundtable-cloud: no such file or directory`
**原因**：云托管「构建目录/代码目录」填了 `stock-roundtable-cloud`，但仓库根目录下没有这个子目录。  
**解决**：
- **最快方案（推荐）**：改用「本地上传」。把 `stock-roundtable-cloud/` 目录整体压缩成 zip（zip 根目录直接是 `app/`、`Dockerfile`、`requirements.txt`），在云托管「重新部署 → 本地上传」里上传，构建目录保持默认（`/`）。
- 坚持用 Git：打开仓库确认根目录下是否有 `stock-roundtable-cloud/` 文件夹。
  - 有 → 云托管构建目录填 `stock-roundtable-cloud`。
  - 没有 → 构建目录填 `/` 或留空，Dockerfile 路径填 `Dockerfile`。

### Q2：COS 开了「公读私写」，但找不到「访问管理」拿 SecretId/SecretKey
**说明**：COS 控制台本身没有访问管理入口。COS 的「公读私写」只让对象 URL 可被公开访问，**上传文件仍需 SecretId/SecretKey**。  
**解决**：
- 拿密钥：腾讯云控制台 → 右上角头像 → **访问管理** → **API 密钥管理** → 新建密钥（直达 [console.cloud.tencent.com/cam/capi](https://console.cloud.tencent.com/cam/capi)）。把 `SecretId`/`SecretKey` 填进云托管环境变量。
- 如果暂时拿不到/不想用永久密钥：把 `COS_BUCKET` 留空，系统会自动回退到写容器本地磁盘（`./reports`），仍可跑通；上线后再补 COS 密钥即可。

### Q3：云托管部署方式选「代码仓库」还是「本地上传」？
- 想省事、第一次部署：**本地上传**最快，不会遇到 Git 路径问题。
- 想持续集成：用 Git，但要确保仓库结构与云托管「构建目录」一致。

