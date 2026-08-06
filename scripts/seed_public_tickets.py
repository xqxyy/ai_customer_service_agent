"""
把公开客服工单导入项目数据库

这个脚本读取 data/generated/public_tickets.jsonl，把 Tobi-Bueck 数据集转换后的工单写入：
1. tickets 表：形成更大的工单数据库
2. messages 表：可选写入用户问题和公开数据中的参考回复，形成更大的会话数据

脚本是幂等的：同一个 source_dataset + external_id 已存在时会跳过，不会重复插入。

运行前请先执行：
    python -m alembic upgrade head

运行示例：
    python -m scripts.seed_public_tickets --limit 5000
    python -m scripts.seed_public_tickets --limit 100 --dry-run
    python -m scripts.seed_public_tickets --limit 5000 --without-messages
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import datetime

from scripts.public_data_utils import PUBLIC_TICKETS_FILE, clean_text, read_jsonl


# 用公开数据来源和外部 ID 生成稳定 ticket_id，重复运行脚本也能命中同一条记录。
def build_ticket_id(source_dataset: str, external_id: str) -> str:
    digest = hashlib.sha1(f"{source_dataset}:{external_id}".encode("utf-8")).hexdigest()[:16]
    return f"PUBLIC-{digest.upper()}"


# 把转换后的公开工单记录映射成 Ticket ORM 对象；Ticket 类由调用方传入，避免 --help 时提前连数据库。
def build_ticket(record: dict, ticket_model):
    source_dataset = clean_text(record.get("source_dataset")) or "public_dataset"
    external_id = clean_text(record.get("external_id"))
    risk_level = clean_text(record.get("risk_level")) or "normal"
    status = "pending_review" if risk_level == "high" else "open"

    return ticket_model(
        ticket_id=build_ticket_id(source_dataset, external_id),
        session_id=f"public-{source_dataset}-{external_id}",
        user_id=f"public-user-{clean_text(record.get('language')) or 'unknown'}",
        title=clean_text(record.get("title"))[:200] or "公开客服工单",
        description=clean_text(record.get("description")),
        priority=clean_text(record.get("priority")) or "normal",
        risk_level=risk_level,
        risk_reason=clean_text(record.get("risk_reason")),
        matched_keyword=clean_text(record.get("matched_keyword"))[:100],
        source_dataset=source_dataset,
        external_id=external_id,
        category=clean_text(record.get("category"))[:100] or None,
        queue=clean_text(record.get("queue"))[:100] or None,
        language=clean_text(record.get("language"))[:30] or None,
        tags=record.get("tags") or [],
        status=status,
    )


# 给公开工单补一组消息记录，让 messages 表也能用于更大规模展示和查询。
def build_messages(ticket, record: dict, message_model) -> list:
    run_id = f"seed-{ticket.ticket_id}"
    messages = [
        message_model(
            run_id=run_id,
            session_id=ticket.session_id,
            user_id=ticket.user_id,
            role="user",
            content=ticket.description,
            created_at=datetime.utcnow(),
        )
    ]

    answer = clean_text(record.get("answer"))
    if answer:
        messages.append(
            message_model(
                run_id=run_id,
                session_id=ticket.session_id,
                user_id=ticket.user_id,
                role="assistant",
                content=answer,
                created_at=datetime.utcnow(),
            )
        )

    return messages


# 确认数据库表已经迁移到最新版本，否则导入时会因为缺字段失败。
def assert_database_ready():
    from sqlalchemy import inspect

    from backend.app.db.session import check_database_health
    from backend.app.db.session_sqlalchemy import engine

    health = check_database_health()
    if not health["ok"]:
        raise SystemExit(
            f"数据库未就绪：{health}。请先执行 python -m alembic upgrade head"
        )

    required_ticket_columns = {
        "source_dataset",
        "external_id",
        "category",
        "queue",
        "language",
        "tags",
    }
    inspector = inspect(engine)
    ticket_columns = {
        column["name"]
        for column in inspector.get_columns("tickets")
    }
    missing_columns = sorted(required_ticket_columns - ticket_columns)
    if missing_columns:
        raise SystemExit(
            f"tickets 表缺少公开数据字段：{missing_columns}。"
            "请先执行 python -m alembic upgrade head"
        )


# 执行导入；按 source_dataset + external_id 去重，支持 dry-run 预览。
def seed_tickets(
    limit: int | None,
    with_messages: bool,
    dry_run: bool,
    replace_source: bool,
) -> dict:
    from sqlalchemy import delete, select

    from backend.app.db.models_sqlalchemy import Message, Ticket
    from backend.app.db.session_sqlalchemy import SessionLocal

    if not PUBLIC_TICKETS_FILE.exists():
        raise SystemExit(
            f"找不到 {PUBLIC_TICKETS_FILE}。请先运行 python -m scripts.convert_public_data"
        )

    assert_database_ready()
    stats = {
        "read": 0,
        "inserted": 0,
        "skipped_existing": 0,
        "messages_inserted": 0,
    }

    with SessionLocal() as db:
        if replace_source and not dry_run:
            # 先删 messages 再删 tickets，避免清理旧公开导入数据时留下孤立会话消息。
            db.execute(
                delete(Message).where(
                    Message.session_id.like("public-tobi_customer_support_tickets-%")
                )
            )
            db.execute(
                delete(Ticket).where(
                    Ticket.source_dataset == "tobi_customer_support_tickets"
                )
            )
            db.commit()

        for record in read_jsonl(PUBLIC_TICKETS_FILE, limit=limit):
            stats["read"] += 1
            source_dataset = clean_text(record.get("source_dataset"))
            external_id = clean_text(record.get("external_id"))

            existing = db.execute(
                select(Ticket.id).where(
                    Ticket.source_dataset == source_dataset,
                    Ticket.external_id == external_id,
                )
            ).scalar_one_or_none()

            if existing is not None:
                stats["skipped_existing"] += 1
                continue

            ticket = build_ticket(record, Ticket)
            stats["inserted"] += 1

            if dry_run:
                continue

            db.add(ticket)

            if with_messages:
                messages = build_messages(ticket, record, Message)
                for message in messages:
                    db.add(message)
                stats["messages_inserted"] += len(messages)

            if stats["inserted"] % 500 == 0:
                db.commit()

        if not dry_run:
            db.commit()

    return stats


# 命令行参数：默认导入 5000 条，避免第一次运行就把数据库塞太满。
def parse_args():
    parser = argparse.ArgumentParser(description="把公开客服工单导入 tickets/messages 表")
    parser.add_argument("--limit", type=int, default=5000, help="最多导入多少条；0 表示全部")
    parser.add_argument(
        "--without-messages",
        action="store_true",
        help="只导入 tickets，不导入 messages",
    )
    parser.add_argument(
        "--replace-source",
        action="store_true",
        help="导入前清理旧的 Tobi 公开工单和对应消息，适合重新全量导入",
    )
    parser.add_argument("--dry-run", action="store_true", help="只统计不写库")
    return parser.parse_args()


# 脚本入口：执行导入并打印统计。
def main():
    args = parse_args()
    stats = seed_tickets(
        limit=args.limit or None,
        with_messages=not args.without_messages,
        dry_run=args.dry_run,
        replace_source=args.replace_source,
    )
    print(stats)


if __name__ == "__main__":
    main()
