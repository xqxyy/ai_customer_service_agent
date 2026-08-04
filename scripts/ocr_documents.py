"""
扫描件 PDF OCR 脚本

这个脚本读取 sources.json 中 need_ocr=true 的扫描 PDF，调用 PaddleOCR 提取文本，并写入 data/processed/ocr_texts/{doc_id}.txt
存在的原因是：扫描 PDF 不能像普通文本 PDF 一样直接 extract_text，必须先离线 OCR，才能进入 RAG 流水线

运行方式：
    python -m scripts.ocr_documents
"""

import json
from pathlib import Path


# 输入输出路径：OCR 结果会被 prepare_documents.py 当成普通文本继续处理
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = PROJECT_ROOT / "data" / "knowledge_base" / "sources.json"
OCR_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "ocr_texts"


# 读取知识源目录：只处理其中标记 need_ocr=true 的文件
def load_sources() -> list[dict]:
    return json.loads(SOURCES_FILE.read_text(encoding="utf-8"))


# 创建 PaddleOCR 客户端：兼容新版和旧版 PaddleOCR 的构造参数差异
def create_ocr_client():
    try:
        from paddleocr import PaddleOCR
    except ImportError as error:
        raise RuntimeError(
            "PaddleOCR is not installed. Run: pip install paddlepaddle paddleocr"
        ) from error

    try:
        return PaddleOCR(
            ocr_version="PP-OCRv4",
            lang="ch",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    except TypeError:
        return PaddleOCR(use_angle_cls=True, lang="ch")


# 从不同版本 PaddleOCR 返回结构中递归提取文字行
def extract_text_lines(result) -> list[str]:
    if result is None:
        return []

    if isinstance(result, tuple) and result and isinstance(result[0], str):
        return [result[0]]

    if isinstance(result, list):
        if (
            len(result) >= 2
            and isinstance(result[1], tuple)
            and result[1]
            and isinstance(result[1][0], str)
        ):
            return [result[1][0]]

        lines = []
        for item in result:
            lines.extend(extract_text_lines(item))
        return lines

    data = result
    result_json = getattr(result, "json", None)
    if result_json is not None:
        data = result_json() if callable(result_json) else result_json

    if isinstance(data, dict):
        payload = data.get("res", data)
        rec_texts = payload.get("rec_texts")
        if isinstance(rec_texts, list):
            return [text for text in rec_texts if isinstance(text, str) and text.strip()]

        lines = []
        for value in payload.values():
            if isinstance(value, (dict, list)):
                lines.extend(extract_text_lines(value))
        return lines

    return []


# 对单个扫描 PDF 执行 OCR，返回整理后的纯文本
def ocr_scanned_pdf(source_path: Path) -> str:
    ocr = create_ocr_client()

    if hasattr(ocr, "predict"):
        results = ocr.predict(input=str(source_path))
    else:
        results = ocr.ocr(str(source_path), cls=True)

    lines = []
    for result in results:
        lines.extend(extract_text_lines(result))

    return "\n".join(line.strip() for line in lines if line.strip())


# 脚本入口：遍历所有扫描件，生成 OCR 文本缓存文件
def main():
    OCR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for source in load_sources():
        if not source.get("need_ocr"):
            continue

        input_path = PROJECT_ROOT / source["source_path"]
        text = ocr_scanned_pdf(input_path)

        output_path = OCR_OUTPUT_DIR / f"{source['doc_id']}.txt"
        output_path.write_text(text, encoding="utf-8")
        print(f"OCR saved: {output_path}")


if __name__ == "__main__":
    main()
