# WooCommerce 订单状态与异常处理参考

## 资料定位

- 文档 ID：woocommerce_order_status_reference
- 适用地区：电商平台通用
- 业务领域：订单
- 风险等级：normal
- 更新说明：该文档用于订单后台状态理解，具体业务状态仍以项目真实订单系统为准。

## 权威来源

- Managing orders（WooCommerce Documentation，平台官方文档）：https://woocommerce.com/document/managing-orders/
- Order Statuses（WooCommerce Documentation，平台官方文档）：https://woocommerce.com/document/managing-orders/order-statuses/
- Troubleshooting Orders（WooCommerce Documentation，平台官方文档）：https://woocommerce.com/document/managing-orders/troubleshooting-orders/

## 客服处理摘要

- WooCommerce 订单状态资料适合帮助 Agent 理解 pending、processing、completed、refunded、failed 等订单状态语义。
- 订单异常处理应先确认支付状态、库存、物流履约、订单备注和后台状态变更记录。
- 这些资料是平台操作参考，不是用户权益或合规规则。

## 标准处理步骤

- 先查询订单状态、支付状态、物流状态和最近操作记录。
- 根据状态判断是支付待确认、处理中、已完成、失败、取消还是已退款。
- 后台状态和支付/物流事实不一致时，创建人工工单。
- 回复用户时使用业务语言解释状态，不暴露后台内部字段。

## 回答边界

- 不能把 WooCommerce 默认状态等同于本平台所有状态。
- 不能在后台和支付渠道状态不一致时直接判断责任。
- 不能向用户展示后台敏感操作日志或管理员信息。

## 人工升级触发条件

- 订单状态卡住、支付成功但订单失败、库存扣减异常。
- 已退款状态和用户到账情况不一致。
- 用户要求人工、投诉或监管介入。

## 典型用户问题

- WooCommerce Refunded 状态是什么意思？
- 订单一直 Processing 应该怎么排查？
- 支付成功但订单失败怎么办？

## 使用提醒

- 本文档是面向客服 Agent 的权威资料摘要，不是法律意见。
- 回答用户时应结合订单、商品、地区、平台规则和人工审核结果。
- 涉及投诉、赔偿、隐私、法律、监管举报等高风险事项时，应创建人工审核工单。
