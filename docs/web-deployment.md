# Web 子路径部署

站点入口：`https://xuhuaai.top/xingyuan/`。

服务器使用 Nginx 终止 HTTPS，将 `/xingyuan/` 去掉前缀后转发到仅监听回环地址的容器端口。Nginx 固定设置 `X-Forwarded-Prefix: /xingyuan` 与 `X-Forwarded-Proto: https`。应用仅在显式设置 `XINGYUAN_TRUST_PROXY=1` 时信任一层代理头，不应将该配置下的应用端口直接暴露到公网。

部署环境：

| 变量 | 值 / 用途 |
| --- | --- |
| `XINGYUAN_HOME` | `/data`，认证与会话密钥目录 |
| `XINGYUAN_DB_PATH` | `/data/xingyuan.db`，SQLite 持久化位置 |
| `XINGYUAN_URL_PREFIX` | `/xingyuan`，生成链接和限制 Cookie 路径 |
| `XINGYUAN_TRUST_PROXY` | `1`，信任 Nginx 固定传入的代理头 |
| `XINGYUAN_HTTPS` | `1`，仅通过 HTTPS 发送会话 Cookie |
| `XINGYUAN_DEMO_MODE` | `0`，关闭一键演示管理员登录 |

Docker 使用 Gunicorn 和非 root 用户运行；数据库、管理员凭据及持久化签名密钥保存在宿主机 `/opt/xingyuan/data` 的挂载目录中，发布镜像时不上传开发机数据库。首次部署预先生成独立的随机管理员密码，避免使用本地默认管理员密码。登录信息单独交付，不进入 Git 或镜像。

当前发布使用独立容器 `xingyuan-20261106`，回环端口 `5053`；Nginx 子路径配置位于 `/etc/nginx/snippets/xingyuan.conf`。修改前的原站配置保存在 `/opt/xingyuan/backups/xuhua-before-20261106.conf`。恢复旧配置需要先执行 `nginx -t`，再重新加载 Nginx；数据库目录应保留。

更新前应备份 `/data`，使用新镜像验证 `/healthz`，确认登录跳转、CSS、JavaScript 和字体均带有正确前缀。配置变更后也要检查域名根路径的原站没有受到影响。

该部署保留当前 Web 功能；界面审查发现的业务与交互问题仍需单独修复，线上可访问不代表 UI 验收已通过。
