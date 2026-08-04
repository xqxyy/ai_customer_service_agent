"""
知识库源文件加载器

这个文件负责读取 markdown、txt、json FAQ、可复制文本 PDF 等不同格式的知识资料，并统一转换成字符串内容
存在的原因是：知识库数据来源格式不一致，RAG 入库前需要先做标准化，后面的切块和向量化才能复用同一套流程
"""

import json
from pathlib import Path

from pypdf import PdfReader


# 项目根目录：sources.json 里通常写相对路径，这里负责解析到真实文件位置
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 解析源文件路径
def resolve_path(path: str) -> Path:
    source_path = Path(path)
    if source_path.is_absolute():
        return source_path
    return PROJECT_ROOT / source_path


# 加载 markdown/txt 文本文件：直接按 UTF-8 读取并去掉首尾空白
def load_text_file(path: str) -> str:
    return resolve_path(path).read_text(encoding="utf-8").strip()


# 加载 FAQ JSON：把 question/answer 结构拼成适合 RAG 切块的自然语言文本
def load_json_faq(path: str) -> str:
    items = json.loads(resolve_path(path).read_text(encoding="utf-8"))

    texts = []
    for item in items:
        question = item.get("question", "").strip()
        answer = item.get("answer", "").strip()

        if question and answer:
            texts.append(f"问题：{question}\n回答：{answer}")

    return "\n\n".join(texts)


# 加载可复制文本 PDF：适用于普通 PDF，扫描件 PDF 会走 OCR 脚本
def load_text_pdf(path: str) -> str:
    reader = PdfReader(str(resolve_path(path)))

    texts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            texts.append(text.strip())

    return "\n\n".join(texts)


# 根据 sources.json 里的 doc_type 选择加载器，输出标准文本内容
def load_source_content(source: dict) -> str:
    if source.get("need_ocr"):
        raise NotImplementedError("扫描 PDF 暂时不进入 RAG，后续 OCR 阶段处理")

    doc_type = source["doc_type"]

    if doc_type in {"markdown", "txt"}:
        return load_text_file(source["source_path"])

    if doc_type == "json_faq":
        return load_json_faq(source["source_path"])

    if doc_type == "pdf":
        return load_text_pdf(source["source_path"])

    raise ValueError(f"Unsupported doc_type: {doc_type}")
