"""Run the sample invoices through the real model and score each field against
what is printed on the document.

    .venv/Scripts/python scripts/sample_invoices.py samples-out
    .venv/Scripts/python scripts/invoice_accuracy.py samples-out

Reads the provider settings from backend/.env. Each file is one model call.
"""

import asyncio
import json
import re
import sys
import time
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.core.llm import LLMError, get_provider  # noqa: E402
from app.demos.invoices.checks import run_checks  # noqa: E402
from app.demos.invoices.document import read_document  # noqa: E402
from app.demos.invoices.extract import extract_invoice  # noqa: E402
from app.demos.invoices.schema import InvoiceFields  # noqa: E402
from scripts.sample_invoices import SAMPLES, Sample  # noqa: E402

TODAY = date(2026, 10, 16)


def truth(sample: Sample) -> dict:
    data = asdict(sample)
    for key in ("file_name", "expected_checks", "shipped"):
        data.pop(key)
    return json.loads(InvoiceFields.model_validate(data).model_dump_json())


def same(expected: Any, got: Any) -> bool:
    if expected is None or got is None:
        return expected is got
    try:
        return Decimal(str(expected)) == Decimal(str(got))
    except ArithmeticError:
        fold = lambda s: re.sub(r"[\W_]+", "", str(s)).lower()  # noqa: E731
        return fold(expected) == fold(got)


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            out.update(flatten(item, f"{prefix}{key}."))
        return out
    if isinstance(value, list):
        out = {f"{prefix}count": len(value)}
        for n, item in enumerate(value):
            out.update(flatten(item, f"{prefix}{n}."))
        return out
    return {prefix.rstrip("."): value}


async def main(folder: Path) -> None:
    for sample in SAMPLES:
        own = {c.name.value: c.status for c in run_checks(InvoiceFields.model_validate(truth(sample)), TODAY)}
        assert own == sample.expected_checks, f"{sample.file_name}: ground truth checks {own}"

    settings = get_settings()
    llm = get_provider(settings, {})
    totals = [0, 0]
    try:
        for sample in SAMPLES:
            data = (folder / sample.file_name).read_bytes()
            document = read_document(data, max_mb=settings.max_file_mb, max_pages=settings.invoice_max_pages)
            started = time.perf_counter()
            try:
                invoice = await extract_invoice(llm, document, TODAY)
            except LLMError as exc:
                print(f"\n{sample.file_name}: not extracted ({exc.message})")
                continue
            seconds = time.perf_counter() - started
            got = json.loads(invoice.model_dump_json())
            expected = flatten(truth(sample))
            actual = flatten({k: v for k, v in got.items() if k != "checks"})
            wrong = [(k, v, actual.get(k)) for k, v in expected.items() if not same(v, actual.get(k))]
            extra = sorted(set(actual) - set(expected))
            totals[0] += len(expected) - len(wrong)
            totals[1] += len(expected)
            checks = {c["name"]: c["status"] for c in got["checks"]}
            print(f"\n{sample.file_name}: {len(expected) - len(wrong)}/{len(expected)} fields right, {seconds:.1f}s")
            for key, want, have in wrong:
                print(f"  {key}: expected {want!r}, got {have!r}")
            if extra:
                print(f"  extra fields: {extra}")
            print(f"  checks: {checks}")
            if checks != sample.expected_checks:
                print(f"  CHECKS DIFFER from expected {sample.expected_checks}")
            for c in got["checks"]:
                if c["status"] == "fail":
                    print(f"  failed {c['name']}: {c['detail']}")
    finally:
        await llm.aclose()
    print(f"\nall files: {totals[0]}/{totals[1]} fields right")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
