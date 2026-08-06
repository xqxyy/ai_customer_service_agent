"""
下载公开客服数据集

这个脚本从 Hugging Face 下载两个公开数据集：
1. Tobi-Bueck/customer-support-tickets：更像真实工单，用于扩充 tickets/messages
2. Bitext customer support dataset：更像意图问答，用于扩充 Agent eval

原始数据会写入 data/external/，该目录已被 .gitignore 忽略，避免把大数据提交到 GitHub。

运行示例：
    python -m scripts.download_public_data --dataset all --use-mirror
    python -m scripts.download_public_data --dataset tobi --limit 5000 --use-mirror
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests

from scripts.public_data_utils import DATASET_CONFIGS, ensure_parent


# 直接读取 Hugging Face 仓库里的 CSV 文件；比 datasets 构建流程更适合小批量抽样验证。
def iter_csv_url_rows(url: str):
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        lines = response.iter_lines(decode_unicode=True)
        reader = csv.DictReader(line for line in lines if line)
        for row in reader:
            yield dict(row)


# 把 huggingface.co 的原始文件地址替换为镜像站地址；路径保持不变。
def rewrite_url_base(url: str, base_url: str | None) -> str:
    if not base_url:
        return url

    parsed_url = urlparse(url)
    parsed_base = urlparse(base_url)
    return urlunparse(
        (
            parsed_base.scheme or "https",
            parsed_base.netloc,
            parsed_url.path,
            parsed_url.params,
            parsed_url.query,
            parsed_url.fragment,
        )
    )


# 读取用户手动下载到本地的 CSV 文件；网络不通时用这个兜底。
def iter_csv_file_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            yield dict(row)


# 下载或导入单个数据集并保存成 JSONL。
def download_one(
    name: str,
    limit: int | None,
    force: bool,
    local_files: list[Path] | None = None,
    base_url: str | None = None,
) -> int:
    config = DATASET_CONFIGS[name]
    output_file = config["raw_file"]

    if output_file.exists() and not force:
        print(f"[skip] {output_file} 已存在；如需覆盖请加 --force")
        return 0

    print(f"[download] {config['hf_id']} -> {output_file}")

    ensure_parent(output_file)
    count = 0
    with output_file.open("w", encoding="utf-8") as file:
        sources = local_files or [
            rewrite_url_base(url, base_url)
            for url in config["raw_urls"]
        ]
        for source in sources:
            print(f"[source] {source}")
            if local_files:
                row_iter = iter_csv_file_rows(Path(source))
            else:
                row_iter = iter_csv_url_rows(str(source))

            try:
                for row in row_iter:
                    file.write(json.dumps(row, ensure_ascii=False) + "\n")
                    count += 1
                    if limit and count >= limit:
                        break
            except requests.RequestException as error:
                if not local_files:
                    raise SystemExit(
                        "无法连接 Hugging Face 下载公开数据。"
                        "可以在浏览器中手动下载 CSV 后，使用 --local-file 导入。\n"
                        f"失败地址：{source}\n"
                        f"错误：{error}"
                    ) from error
                raise
            if limit and count >= limit:
                break

    print(f"[done] {name}: {count} rows")
    return count


# 命令行参数：默认下载全部数据；调试时可以用 --limit 控制行数。
def parse_args():
    parser = argparse.ArgumentParser(description="下载公开客服数据集到 data/external")
    parser.add_argument(
        "--dataset",
        choices=["all", "tobi", "bitext"],
        default="all",
        help="选择要下载的数据集",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="每个数据集最多下载多少行；0 表示全部",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="覆盖已存在的原始 JSONL 文件",
    )
    parser.add_argument(
        "--local-file",
        action="append",
        type=Path,
        default=[],
        help="网络不通时，指定手动下载的 CSV 文件；可重复传入多个文件",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("HF_ENDPOINT", ""),
        help="替换 Hugging Face 域名的基础地址，例如 https://hf-mirror.com",
    )
    parser.add_argument(
        "--use-mirror",
        action="store_true",
        help="使用 https://hf-mirror.com 下载公开数据",
    )
    return parser.parse_args()


# 脚本入口：按参数下载一个或两个数据集。
def main():
    args = parse_args()
    if args.local_file and args.dataset == "all":
        raise SystemExit("--local-file 需要配合 --dataset tobi 或 --dataset bitext 使用")

    names = ["tobi", "bitext"] if args.dataset == "all" else [args.dataset]
    limit = args.limit or None
    base_url = "https://hf-mirror.com" if args.use_mirror else args.base_url or None

    total = 0
    for name in names:
        total += download_one(
            name,
            limit=limit,
            force=args.force,
            local_files=args.local_file or None,
            base_url=base_url,
        )

    print(f"[summary] downloaded_rows={total}")


if __name__ == "__main__":
    main()
