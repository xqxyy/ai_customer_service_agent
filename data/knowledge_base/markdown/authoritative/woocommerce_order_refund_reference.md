# WooCommerce 订单退款操作参考

## 资料定位

- 文档 ID：woocommerce_order_refund_reference
- 适用地区：电商平台通用
- 业务领域：售后
- 风险等级：normal
- 更新说明：该文档用于电商后台流程参考，不替代项目自己的售后政策。

## 权威来源

- Refunding Orders in WooCommerce（WooCommerce Documentation，平台官方文档）：https://woocommerce.com/document/woocommerce-refunds/
- WooCommerce REST API Documentation（WooCommerce Developer Docs，平台开发者文档）：https://woocommerce.github.io/woocommerce-rest-api-docs/

## 客服处理摘要

- WooCommerce 资料适合做电商订单、退款和后台操作流程参考，不是消费者权益法律文本。
- 退款处理应区分手动退款、支付网关退款、部分退款、库存回补和订单备注。
- 客服 Agent 可根据这些资料理解订单退款操作链路，但最终仍要依据本项目平台政策和真实订单状态。

## 标准处理步骤

- 确认订单状态、支付方式、可退款金额、退款原因和是否需要退回库存。
- 如果是后台操作问题，记录订单号、退款金额、退款原因和支付网关。
- 如果用户要求立即到账，说明到账时间受支付渠道影响，不能直接承诺。
- 涉及大额退款、重复退款、支付网关失败时创建人工工单。

## 回答边界

- 不能把 WooCommerce 操作文档当作本平台对用户的退款承诺。
- 不能在未核验订单和支付渠道前承诺退款成功。
- 不能暴露后台密钥、API key 或管理员操作权限。

## 人工升级触发条件

- 退款金额异常、重复退款、支付网关失败。
- 用户投诉不到账或要求赔偿。
- 后台订单状态和支付状态不一致。

## 典型用户问题

- WooCommerce 后台怎么给订单退款？
- WooCommerce 可以部分退款吗？
- 退款后订单状态为什么还没有变化？

## 使用提醒

- 本文档是面向客服 Agent 的权威资料摘要，不是法律意见。
- 回答用户时应结合订单、商品、地区、平台规则和人工审核结果。
- 涉及投诉、赔偿、隐私、法律、监管举报等高风险事项时，应创建人工审核工单。
