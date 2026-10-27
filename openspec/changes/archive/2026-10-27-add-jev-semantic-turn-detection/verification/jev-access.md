# Jev官方接入入口（2026-10-22只读核查）

- 官方控制台：https://console.typesafe.ai/ 。通过Google或邮箱登录/注册；官方SDK文档将API Key创建入口链接至此。
- 官方快速开始：https://docs.typesafe.ai/introduction/quickstart 。
- 官方接口参考：https://docs.typesafe.ai/api/system-one 。
- 标准请求：POST https://api.typesafe.ai/v1/systemone ，Authorization: Bearer <API Key>，JSON包含model/state/questions；快速开始示例使用jev-latest。
- 本轮仅查阅公开网页，没有注册、创建Key、充值、查询账户额度或发送收费推理请求。账号权限与当前额度必须以登录后的官方控制台为准。
- 用户保管真实凭证，不发聊天；实际配置入口确认后再填入。准备Key不等于授权收费测试，需另批确认数据/厂商/费用上限/停止条件。
