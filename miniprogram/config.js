// 后端基址：
// - 本地开发调试：填电脑局域网 IP:8000（手机与电脑同一 WiFi）
// - TCB 部署：改为云托管默认域名（TCB 控制台 → 云托管 → 你的服务 → 服务详情 → 默认域名，
//   形如 https://xxx.ap-shanghai.cloudbaseapp.com 或 https://环境ID.service.tcloudbase.com）
const BASE_URL = 'http://localhost:8000' // TODO(部署时): 改为云托管默认域名
module.exports = { BASE_URL }
