# 公开客服数据集接入说明

本项目支持把公开客服数据集接入到本地数据库和评估流程中，用于扩大测试规模、验证工单路由、高风险识别和 Agent 工具调用稳定性。

## 数据类型边界

本项目现在把数据分成两类，避免把“历史工单库”和“正式知识库”混在一起：

```text
正式 RAG 知识库
  放政策、规则、SOP、FAQ、官方参考资料。
  Agent 回答政策类问题时会通过 search_knowledge_base 检索这里。

历史工单和公开客服数据
  放 tickets/messages/eval，用于扩大数据库规模、验证工单流程、生成测试集。
  当前 Agent 不会直接把历史工单当作正式政策依据回答用户。
```

## 国内权威 RAG 来源

国内外权威资料登记在：

```text
data/knowledge_base/authoritative_sources.json
```

生成脚本：

```powershell
python -m scripts.build_authoritative_knowledge
```

生成的 markdown 文档：

```text
data/knowledge_base/markdown/authoritative/
```

当前覆盖的主题：

| 主题 | 地区/来源 | 主要用途 | RAG 文档 ID |
|---|---|---|---|
| 消费者权益与售后争议 | 中国大陆 | 售后争议、赔偿、投诉边界 | `cn_consumer_rights_after_sales_reference` |
| 七日无理由退货 | 中国大陆 | 网购退货、例外商品、验货边界 | `cn_seven_day_return_reference` |
| 电子商务平台履约 | 中国大陆 | 订单履约、商品信息、平台规则 | `cn_ecommerce_platform_reference` |
| 快递服务与物流异常 | 中国大陆 | 签收争议、物流延误、快件异常 | `cn_express_delivery_reference` |
| 数电发票 | 中国大陆 | 发票开具、重开、抬头错误处理 | `cn_digital_invoice_reference` |
| 个人信息保护 | 中国大陆 | 隐私请求、删除导出、更正撤回授权 | `cn_personal_information_reference` |
| 投诉升级与监管争议 | 中国大陆 | 投诉、监管、法律风险、人工审核 | `cn_customer_complaint_escalation_reference` |
| FTC 在线购物交付、退货与退款 | 美国 | 网购未发货、扣款争议、退款证据 | `us_ftc_online_shopping_delivery_refunds_reference` |
| FTC Cooling-Off Rule | 美国 | 特定地点销售的取消权识别和人工升级 | `us_ftc_cooling_off_rule_reference` |
| eCFR 邮购/网购/电话订购商品规则 | 美国 | 发货承诺、延期通知、取消和退款参考 | `us_ecfr_mail_internet_order_rule_reference` |
| CFPB 金融消费者投诉数据库 | 美国 | 金融投诉识别、监管投诉边界 | `us_cfpb_financial_complaint_reference` |
| WooCommerce 订单退款 | 电商平台通用 | 后台退款、部分退款、支付网关异常 | `woocommerce_order_refund_reference` |
| WooCommerce 订单状态 | 电商平台通用 | 订单状态、支付成功但订单异常、已退款排查 | `woocommerce_order_status_reference` |

这些文档不是复制官方全文，而是面向客服 Agent 的处理摘要。每条记录都保留官方来源 URL、发布机构、适用地区、风险等级、处理步骤和人工升级条件。后续如果要做省市差异，可以继续在 `jurisdiction` 中增加 `广东`、`上海` 等地区标签；如果要做国家差异，可以增加 `美国`、`欧盟`、`英国` 等标签，再在检索层增加地区过滤。

## 数据集

| 数据集 | 用途 | 许可证 | 链接 |
|---|---|---|---|
| Tobi-Bueck/customer-support-tickets | 扩充 `tickets` 和 `messages`，用于工单列表、优先级、队列、标签和语言字段测试 | CC-BY-NC-4.0 | https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets |
| Bitext Customer Support Dataset | 生成更大的 Agent eval，用于测试工具路由和高风险兜底 | CDLA-Sharing-1.0 | https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset |

## 仓库策略

公开仓库只提交脚本、说明文档和少量项目自带示例数据。

以下目录由脚本在本地生成，默认不提交：

```text
data/external/    Hugging Face 原始下载文件
data/generated/   转换后的公开工单、公开 eval 和转换报告
data/public_samples/  可选的小样本导出目录
```

这样做有三个原因：

```text
1. 原始数据体积比项目自带示例数据大很多，不适合直接放进代码仓库。
2. 公开数据集有自己的许可证，仓库应保留脚本和来源说明，让使用者自行下载。
3. 本地可以全量导入和压力测试，GitHub 上仍保持轻量、干净、可复现。
```

## 推荐流程

```powershell
pip install -r requirements.txt

python -m scripts.download_public_data --dataset all --use-mirror
python -m scripts.convert_public_data --tobi-limit 10000 --bitext-limit 10000

python -m alembic upgrade head
python -m scripts.seed_public_tickets --limit 5000

python -m scripts.build_public_agent_eval --limit 300
python -m backend.app.evals.run_customer_service_eval --eval-file data/generated/public_customer_service_eval.json
```

第一次建议先用较小的 `limit` 验证流程，例如：

```powershell
python -m scripts.download_public_data --dataset all --limit 1000 --use-mirror
python -m scripts.convert_public_data --tobi-limit 1000 --bitext-limit 1000
python -m scripts.seed_public_tickets --limit 100 --dry-run
```

## 字段映射

Tobi 工单会被标准化为：

```text
source_dataset
external_id
title
description
answer
priority
category
queue
language
tags
risk_level
risk_reason
matched_keyword
```

其中 `source_dataset + external_id` 用于幂等导入，重复执行 seed 脚本不会重复插入。

Bitext 问句会被标准化为：

```text
question
reference_answer
category
intent
expected_tools
```

`expected_tools` 是基于关键词的粗规则推断，用来快速生成大规模回归测试初稿。生成后如果要作为强验证集，建议人工抽查和修正。
