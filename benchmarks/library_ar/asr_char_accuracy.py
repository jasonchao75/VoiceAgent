#!/usr/bin/env python3
"""Calculate Arabic ASR character and word accuracy from an XLSX workbook.

The script intentionally uses only the Python standard library. It reads the
OOXML parts inside an .xlsx file, normalizes Arabic text, calculates character
and word edit metrics, and can validate matching WAV files.
"""

from __future__ import annotations

import argparse
import csv
import json
import posixpath
import re
import sys
import unicodedata
import wave
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"x": MAIN_NS, "r": DOC_REL_NS}

DEFAULT_REFERENCE_HEADER = "标注"
DEFAULT_FILE_HEADER = "文件名称"
DEFAULT_HYPOTHESIS_MARKER = "测试结果"

ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
DIGIT_TRANSLATION = str.maketrans(
    {
        **{char: str(index) for index, char in enumerate(ARABIC_DIGITS)},
        **{char: str(index) for index, char in enumerate(PERSIAN_DIGITS)},
    }
)
ARABIC_LETTER_TRANSLATION = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ة": "ه",
    }
)
ARABIC_MARKS_RE = re.compile(
    "["
    "\u0610-\u061A"
    "\u064B-\u065F"
    "\u0670"
    "\u06D6-\u06ED"
    "\u0640"
    "\u200B-\u200F"
    "\u202A-\u202E"
    "\u2060"
    "\uFEFF"
    "]"
)
THOUSANDS_SEPARATOR_RE = re.compile(r"(?<=\d)[,\u066C](?=\d)")
CELL_REF_RE = re.compile(r"([A-Z]+)")

# Keys are stored in their post-letter-normalization form.
NUMBER_WORD_VALUES = {
    "صفر": "0",
    "واحد": "1",
    "واحده": "1",
    "وحده": "1",
    "احد": "1",
    "اثنين": "2",
    "اثنان": "2",
    "اثنتين": "2",
    "ثنتين": "2",
    "ثنين": "2",
    "اثنينا": "2",
    "ثلاث": "3",
    "ثلاثه": "3",
    "اربع": "4",
    "اربعه": "4",
    "خمس": "5",
    "خمسه": "5",
    "ست": "6",
    "سته": "6",
    "سبع": "7",
    "سبعه": "7",
    "ثمان": "8",
    "ثماني": "8",
    "ثمانيه": "8",
    "تسع": "9",
    "تسعه": "9",
    "عشر": "10",
    "عشره": "10",
    "احدعشر": "11",
    "احدعشره": "11",
    "اثناعشر": "12",
    "اثنيعشر": "12",
    "اثينعشر": "12",
    "ثنتعشر": "12",
    "ثلاثتعشر": "13",
    "اربعتعشر": "14",
    "خمستعشر": "15",
    "ستعشر": "16",
    "سبعتعشر": "17",
    "ثمنطعشر": "18",
    "ثمانتعشر": "18",
    "تسعتعشر": "19",
    "عشرين": "20",
    "ثلاثين": "30",
    "اربعين": "40",
    "خمسين": "50",
    "ستين": "60",
    "سبعين": "70",
    "ثمانين": "80",
    "تسعين": "90",
    "ميه": "100",
    "مئه": "100",
    "مائه": "100",
    "ميتين": "200",
    "مئتين": "200",
    "مائتين": "200",
    "ثلاثميه": "300",
    "ثلاثمئه": "300",
    "اربعميه": "400",
    "اربعمئه": "400",
    "خمسميه": "500",
    "خمسمئه": "500",
    "ستميه": "600",
    "ستمئه": "600",
    "سبعميه": "700",
    "سبعمئه": "700",
    "ثمانميه": "800",
    "ثمانمئه": "800",
    "تسعميه": "900",
    "تسعمئه": "900",
    "الف": "1000",
    "الفين": "2000",
    "الاف": "1000",
}
NUMBER_CLITIC_PREFIXES = frozenset("وبلفك")
THOUSAND_SCALE_WORDS = frozenset({"الف", "الاف"})
MSA_SMALL_NUMBERS = {
    0: "صفر",
    1: "واحد",
    2: "اثنان",
    3: "ثلاثة",
    4: "أربعة",
    5: "خمسة",
    6: "ستة",
    7: "سبعة",
    8: "ثمانية",
    9: "تسعة",
    10: "عشرة",
    11: "أحد عشر",
    12: "اثنا عشر",
    13: "ثلاثة عشر",
    14: "أربعة عشر",
    15: "خمسة عشر",
    16: "ستة عشر",
    17: "سبعة عشر",
    18: "ثمانية عشر",
    19: "تسعة عشر",
}
MSA_TENS = {
    20: "عشرون",
    30: "ثلاثون",
    40: "أربعون",
    50: "خمسون",
    60: "ستون",
    70: "سبعون",
    80: "ثمانون",
    90: "تسعون",
}
MSA_HUNDREDS = {
    100: "مائة",
    200: "مائتان",
    300: "ثلاثمائة",
    400: "أربعمائة",
    500: "خمسمائة",
    600: "ستمائة",
    700: "سبعمائة",
    800: "ثمانمائة",
    900: "تسعمائة",
}


@dataclass(frozen=True)
class SheetInfo:
    name: str
    part_path: str


@dataclass(frozen=True)
class Record:
    order: int
    record_id: str
    excel_row: int
    reference: str
    hypotheses: dict[str, str]


@dataclass(frozen=True)
class EditCounts:
    substitutions: int
    deletions: int
    insertions: int

    @property
    def total(self) -> int:
        return self.substitutions + self.deletions + self.insertions


@dataclass(frozen=True)
class NumberAtom:
    value: int
    is_thousand_scale: bool
    leading_and: bool


@dataclass(frozen=True)
class RowScore:
    profile: str
    run_header: str
    record_id: str
    record_order: int
    excel_row: int
    reference: str
    hypothesis: str
    normalized_reference: str
    normalized_hypothesis: str
    normalized_reference_words: str
    normalized_hypothesis_words: str
    reference_chars: int
    hypothesis_chars: int
    reference_words: int
    hypothesis_words: int
    substitutions: int
    deletions: int
    insertions: int
    errors: int
    cer: float
    char_accuracy: float
    word_substitutions: int
    word_deletions: int
    word_insertions: int
    word_errors: int
    wer: float
    word_accuracy: float
    is_empty: bool
    is_under_half: bool


class XlsxReader:
    """Read the cell values needed for this analysis directly from OOXML."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.archive = zipfile.ZipFile(path)
        self.shared_strings = self._load_shared_strings()
        self.sheets = self._load_sheet_info()

    def __enter__(self) -> "XlsxReader":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.archive.close()

    def _read_xml(self, part_path: str) -> ET.Element:
        try:
            return ET.fromstring(self.archive.read(part_path))
        except KeyError as exc:
            raise ValueError(f"XLSX 缺少必要部件：{part_path}") from exc

    def _load_shared_strings(self) -> list[str]:
        try:
            root = self._read_xml("xl/sharedStrings.xml")
        except ValueError:
            return []

        values: list[str] = []
        text_tag = f"{{{MAIN_NS}}}t"
        for string_item in root.findall("x:si", NS):
            values.append("".join(node.text or "" for node in string_item.iter(text_tag)))
        return values

    def _load_sheet_info(self) -> list[SheetInfo]:
        workbook = self._read_xml("xl/workbook.xml")
        relationships = self._read_xml("xl/_rels/workbook.xml.rels")
        relationship_map = {
            node.attrib["Id"]: node.attrib["Target"]
            for node in relationships.findall(f"{{{PKG_REL_NS}}}Relationship")
        }

        sheets: list[SheetInfo] = []
        for node in workbook.findall("x:sheets/x:sheet", NS):
            relation_id = node.attrib[f"{{{DOC_REL_NS}}}id"]
            target = relationship_map[relation_id]
            if target.startswith("/"):
                part_path = target.lstrip("/")
            else:
                part_path = posixpath.normpath(posixpath.join("xl", target))
            sheets.append(SheetInfo(name=node.attrib["name"], part_path=part_path))
        return sheets

    def read_sheet(self, sheet_name: str) -> dict[int, dict[int, str]]:
        sheet = next((item for item in self.sheets if item.name == sheet_name), None)
        if sheet is None:
            available = "、".join(item.name for item in self.sheets)
            raise ValueError(f"找不到工作表“{sheet_name}”。可用工作表：{available}")

        root = self._read_xml(sheet.part_path)
        rows: dict[int, dict[int, str]] = {}
        for row_node in root.findall("x:sheetData/x:row", NS):
            row_number = int(row_node.attrib["r"])
            row_values: dict[int, str] = {}
            for cell in row_node.findall("x:c", NS):
                cell_ref = cell.attrib.get("r", "")
                match = CELL_REF_RE.match(cell_ref)
                if match is None:
                    continue
                column_index = column_letters_to_index(match.group(1))
                row_values[column_index] = self._cell_value(cell)
            rows[row_number] = row_values
        return rows

    def _cell_value(self, cell: ET.Element) -> str:
        cell_type = cell.attrib.get("t")
        value_node = cell.find("x:v", NS)

        if cell_type == "s" and value_node is not None:
            index = int(value_node.text or "0")
            return self.shared_strings[index]
        if cell_type == "inlineStr":
            text_tag = f"{{{MAIN_NS}}}t"
            return "".join(node.text or "" for node in cell.iter(text_tag))
        if value_node is None:
            return ""
        return value_node.text or ""


def column_letters_to_index(letters: str) -> int:
    result = 0
    for char in letters:
        result = result * 26 + ord(char) - ord("A") + 1
    return result


def column_index_to_letters(index: int) -> str:
    letters: list[str] = []
    while index:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def prepare_arabic_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or "")).lower()
    normalized = normalized.translate(DIGIT_TRANSLATION)
    normalized = THOUSANDS_SEPARATOR_RE.sub("", normalized)
    normalized = ARABIC_MARKS_RE.sub("", normalized)
    return normalized.translate(ARABIC_LETTER_TRANSLATION)


def is_letter_or_number(char: str) -> bool:
    return unicodedata.category(char)[:1] in {"L", "N"}


def split_number_tokens(text: str) -> list[str]:
    """Split punctuation and letter/number transitions for number parsing."""

    tokens: list[str] = []
    current: list[str] = []
    current_kind = ""
    for char in text:
        category = unicodedata.category(char)
        kind = category[:1] if category[:1] in {"L", "N"} else ""
        if not kind:
            if current:
                tokens.append("".join(current))
                current = []
                current_kind = ""
            continue
        if current and kind != current_kind:
            tokens.append("".join(current))
            current = []
        current.append(char)
        current_kind = kind
    if current:
        tokens.append("".join(current))
    return tokens


def token_tail_is_number(token: str) -> bool:
    remainder = token
    for _ in range(4):
        if remainder in NUMBER_WORD_VALUES:
            return True
        if remainder.isascii() and remainder.isdigit():
            return True
        if len(remainder) < 2 or remainder[0] not in NUMBER_CLITIC_PREFIXES:
            return False
        remainder = remainder[1:]
    return False


def parse_number_atom(token: str) -> tuple[str, NumberAtom] | None:
    remainder = token
    retained_prefix = ""
    leading_and = False

    if remainder not in NUMBER_WORD_VALUES and not (
        remainder.isascii() and remainder.isdigit()
    ):
        for _ in range(4):
            if len(remainder) < 2 or remainder[0] not in NUMBER_CLITIC_PREFIXES:
                break
            candidate = remainder[1:]
            if not token_tail_is_number(candidate):
                break
            if remainder[0] == "و":
                leading_and = True
            else:
                retained_prefix += remainder[0]
            remainder = candidate

    if remainder in NUMBER_WORD_VALUES:
        value = int(NUMBER_WORD_VALUES[remainder])
        is_thousand_scale = remainder in THOUSAND_SCALE_WORDS
    elif remainder.isascii() and remainder.isdigit():
        value = int(remainder)
        is_thousand_scale = False
    else:
        return None

    return retained_prefix, NumberAtom(
        value=value,
        is_thousand_scale=is_thousand_scale,
        leading_and=leading_and,
    )


def parse_under_100(atoms: Sequence[NumberAtom]) -> int | None:
    if len(atoms) == 1 and not atoms[0].is_thousand_scale:
        value = atoms[0].value
        return value if 0 <= value < 100 else None
    if len(atoms) == 2 and not any(atom.is_thousand_scale for atom in atoms):
        units = atoms[0].value
        tens = atoms[1].value
        if 1 <= units <= 9 and tens in MSA_TENS:
            return units + tens
    return None


def parse_under_1000(atoms: Sequence[NumberAtom]) -> int | None:
    if not atoms:
        return 0
    if len(atoms) == 1 and not atoms[0].is_thousand_scale:
        value = atoms[0].value
        return value if 0 <= value < 1000 else None

    first = atoms[0]
    if (
        not first.is_thousand_scale
        and first.value in MSA_HUNDREDS
    ):
        remainder = parse_under_100(atoms[1:])
        if remainder is not None:
            return first.value + remainder
    return parse_under_100(atoms)


def evaluate_number_atoms(atoms: Sequence[NumberAtom]) -> int | None:
    if not atoms:
        return None

    scale_indexes = [
        index for index, atom in enumerate(atoms) if atom.is_thousand_scale
    ]
    if scale_indexes:
        if len(scale_indexes) != 1:
            return None
        scale_index = scale_indexes[0]
        multiplier = parse_under_1000(atoms[:scale_index])
        if multiplier is None:
            return None
        if scale_index == 0:
            multiplier = 1
        remainder = parse_under_1000(atoms[scale_index + 1 :])
        if remainder is None:
            return None
        return multiplier * 1000 + remainder

    first = atoms[0]
    if first.value >= 1000:
        if len(atoms) == 1:
            return first.value
        remainder = parse_under_1000(atoms[1:])
        if remainder is not None:
            return first.value + remainder
        return None
    return parse_under_1000(atoms)


def spell_msa_under_100(value: int) -> str:
    if value < 20:
        return MSA_SMALL_NUMBERS[value]
    if value in MSA_TENS:
        return MSA_TENS[value]
    units = value % 10
    tens = value - units
    return f"{MSA_SMALL_NUMBERS[units]} و{MSA_TENS[tens]}"


def spell_msa_under_1000(value: int) -> str:
    if value < 100:
        return spell_msa_under_100(value)
    if value in MSA_HUNDREDS:
        return MSA_HUNDREDS[value]
    hundreds = (value // 100) * 100
    remainder = value % 100
    return f"{MSA_HUNDREDS[hundreds]} و{spell_msa_under_100(remainder)}"


def spell_msa_scaled(
    value: int,
    scale: int,
    singular: str,
    dual: str,
    plural: str,
) -> str:
    count = value // scale
    remainder = value % scale
    if count == 1:
        scaled = singular
    elif count == 2:
        scaled = dual
    elif 3 <= count <= 10:
        scaled = f"{spell_msa_number(count)} {plural}"
    else:
        scaled = f"{spell_msa_number(count)} {singular}"
    if remainder:
        return f"{scaled} و{spell_msa_number(remainder)}"
    return scaled


def spell_msa_number(value: int) -> str:
    """Return a deterministic MSA cardinal spelling for a non-negative integer."""

    if value < 0:
        return f"سالب {spell_msa_number(abs(value))}"
    if value < 100:
        return spell_msa_under_100(value)
    if value < 1000:
        return spell_msa_under_1000(value)
    if value < 1_000_000:
        return spell_msa_scaled(value, 1000, "ألف", "ألفان", "آلاف")
    if value < 1_000_000_000:
        return spell_msa_scaled(
            value,
            1_000_000,
            "مليون",
            "مليونان",
            "ملايين",
        )
    if value < 1_000_000_000_000:
        return spell_msa_scaled(
            value,
            1_000_000_000,
            "مليار",
            "ملياران",
            "مليارات",
        )
    return str(value)


def canonicalize_number_run(atoms: Sequence[NumberAtom]) -> list[tuple[str, bool]]:
    output: list[tuple[str, bool]] = []
    index = 0
    while index < len(atoms):
        chosen_end = index + 1
        chosen_value = atoms[index].value
        for end in range(len(atoms), index, -1):
            value = evaluate_number_atoms(atoms[index:end])
            if value is not None:
                chosen_end = end
                chosen_value = value
                break
        if index > 0 and atoms[index].leading_and:
            output.append(("و", False))
        output.append((spell_msa_number(chosen_value), True))
        index = chosen_end
    return output


def normalize_combined_units(text: str) -> list[tuple[str, bool]]:
    source_tokens = split_number_tokens(prepare_arabic_text(text))
    output: list[tuple[str, bool]] = []
    pending: list[NumberAtom] = []

    def flush_pending() -> None:
        nonlocal pending
        if pending:
            output.extend(canonicalize_number_run(pending))
            pending = []

    for token in source_tokens:
        mapping = parse_number_atom(token)
        if mapping is None:
            flush_pending()
            output.append((token, False))
            continue

        retained_prefix, atom = mapping
        if retained_prefix:
            flush_pending()
            if atom.leading_and:
                output.append(("و", False))
            output.append((retained_prefix, False))
            pending = [
                NumberAtom(
                    value=atom.value,
                    is_thousand_scale=atom.is_thousand_scale,
                    leading_and=False,
                )
            ]
            continue

        if not pending:
            if atom.leading_and:
                output.append(("و", False))
            pending = [
                NumberAtom(
                    value=atom.value,
                    is_thousand_scale=atom.is_thousand_scale,
                    leading_and=False,
                )
            ]
        elif atom.leading_and or atom.is_thousand_scale:
            pending.append(atom)
        else:
            flush_pending()
            pending = [atom]

    flush_pending()
    return output


def normalize_combined(text: str) -> str:
    """Apply basic Arabic cleanup and canonical MSA number normalization."""

    output: list[str] = []
    for token, is_number in normalize_combined_units(text):
        if is_number:
            output.append(
                "".join(char for char in token if is_letter_or_number(char))
            )
        else:
            output.append(token)
    return "".join(output)


def normalize_combined_words(text: str) -> list[str]:
    """Apply combined normalization and retain one token per numeric phrase."""

    output: list[str] = []
    for token, is_number in normalize_combined_units(text):
        if is_number:
            output.append(f"<NUM:{token.replace(' ', '_')}>")
        else:
            output.append(token)
    return output


NORMALIZATION_PROFILE = "combined"


def levenshtein_counts(
    reference: Sequence[str],
    hypothesis: Sequence[str],
) -> EditCounts:
    """Return substitution, deletion, and insertion counts.

    In an equal-cost backtrace tie, substitution is preferred, followed by
    deletion and insertion. The total edit distance is independent of this
    deterministic tie-breaking rule.
    """

    ref_len = len(reference)
    hyp_len = len(hypothesis)
    matrix = [[0] * (hyp_len + 1) for _ in range(ref_len + 1)]

    for ref_index in range(ref_len + 1):
        matrix[ref_index][0] = ref_index
    for hyp_index in range(hyp_len + 1):
        matrix[0][hyp_index] = hyp_index

    for ref_index in range(1, ref_len + 1):
        ref_char = reference[ref_index - 1]
        for hyp_index in range(1, hyp_len + 1):
            substitution_cost = 0 if ref_char == hypothesis[hyp_index - 1] else 1
            matrix[ref_index][hyp_index] = min(
                matrix[ref_index - 1][hyp_index] + 1,
                matrix[ref_index][hyp_index - 1] + 1,
                matrix[ref_index - 1][hyp_index - 1] + substitution_cost,
            )

    substitutions = 0
    deletions = 0
    insertions = 0
    ref_index = ref_len
    hyp_index = hyp_len

    while ref_index > 0 or hyp_index > 0:
        if (
            ref_index > 0
            and hyp_index > 0
            and reference[ref_index - 1] == hypothesis[hyp_index - 1]
            and matrix[ref_index][hyp_index] == matrix[ref_index - 1][hyp_index - 1]
        ):
            ref_index -= 1
            hyp_index -= 1
            continue
        if (
            ref_index > 0
            and hyp_index > 0
            and matrix[ref_index][hyp_index]
            == matrix[ref_index - 1][hyp_index - 1] + 1
        ):
            substitutions += 1
            ref_index -= 1
            hyp_index -= 1
            continue
        if (
            ref_index > 0
            and matrix[ref_index][hyp_index] == matrix[ref_index - 1][hyp_index] + 1
        ):
            deletions += 1
            ref_index -= 1
            continue
        insertions += 1
        hyp_index -= 1

    return EditCounts(
        substitutions=substitutions,
        deletions=deletions,
        insertions=insertions,
    )


def canonical_record_id(value: str, fallback: int) -> str:
    stripped = str(value or "").strip()
    if not stripped:
        return str(fallback)
    try:
        numeric = float(stripped)
    except ValueError:
        return stripped
    if numeric.is_integer():
        return str(int(numeric))
    return stripped


def select_sheet(
    reader: XlsxReader,
    requested_sheet: str | None,
    header_row: int,
    reference_header: str,
) -> tuple[str, dict[int, dict[int, str]]]:
    if requested_sheet:
        return requested_sheet, reader.read_sheet(requested_sheet)

    candidates: list[tuple[int, str, dict[int, dict[int, str]]]] = []
    for sheet in reader.sheets:
        rows = reader.read_sheet(sheet.name)
        headers = rows.get(header_row, {})
        reference_columns = [
            column for column, value in headers.items() if value.strip() == reference_header
        ]
        if not reference_columns:
            continue
        reference_column = reference_columns[0]
        populated = sum(
            1
            for row_number, values in rows.items()
            if row_number > header_row and values.get(reference_column, "").strip()
        )
        candidates.append((populated, sheet.name, rows))

    if not candidates:
        available = "、".join(sheet.name for sheet in reader.sheets)
        raise ValueError(
            f"没有工作表包含表头“{reference_header}”。可用工作表：{available}"
        )
    _, sheet_name, rows = max(candidates, key=lambda item: item[0])
    return sheet_name, rows


def build_records(
    rows: dict[int, dict[int, str]],
    header_row: int,
    reference_header: str,
    file_header: str,
    requested_hypothesis_headers: Sequence[str] | None,
) -> tuple[list[Record], dict[str, int]]:
    headers_by_column = {
        column: value.strip() for column, value in rows.get(header_row, {}).items()
    }
    columns_by_header = {
        header: column for column, header in headers_by_column.items() if header
    }

    if reference_header not in columns_by_header:
        available = "、".join(headers_by_column.values())
        raise ValueError(
            f"找不到标注列“{reference_header}”。当前表头：{available}"
        )
    reference_column = columns_by_header[reference_header]
    file_column = columns_by_header.get(file_header)

    if requested_hypothesis_headers:
        missing = [
            header
            for header in requested_hypothesis_headers
            if header not in columns_by_header
        ]
        if missing:
            available = "、".join(headers_by_column.values())
            raise ValueError(
                f"找不到结果列：{'、'.join(missing)}。当前表头：{available}"
            )
        hypothesis_headers = list(requested_hypothesis_headers)
    else:
        hypothesis_headers = [
            header
            for _, header in sorted(headers_by_column.items())
            if DEFAULT_HYPOTHESIS_MARKER in header
        ]
        if not hypothesis_headers:
            available = "、".join(headers_by_column.values())
            raise ValueError(
                f"没有自动找到包含“{DEFAULT_HYPOTHESIS_MARKER}”的结果列。"
                f"当前表头：{available}"
            )

    hypothesis_columns = {
        header: columns_by_header[header] for header in hypothesis_headers
    }
    records: list[Record] = []
    for row_number in sorted(rows):
        if row_number <= header_row:
            continue
        values = rows[row_number]
        reference = values.get(reference_column, "").strip()
        if not reference:
            continue
        order = row_number - header_row
        file_value = values.get(file_column, "") if file_column else ""
        record_id = canonical_record_id(file_value, fallback=order)
        hypotheses = {
            header: values.get(column, "").strip()
            for header, column in hypothesis_columns.items()
        }
        records.append(
            Record(
                order=order,
                record_id=record_id,
                excel_row=row_number,
                reference=reference,
                hypotheses=hypotheses,
            )
        )

    if not records:
        raise ValueError("标注列中没有可计算的数据行。")

    selected_columns = {
        reference_header: reference_column,
        **hypothesis_columns,
    }
    if file_column is not None:
        selected_columns[file_header] = file_column
    return records, selected_columns


def score_records(
    records: Sequence[Record],
    run_header: str,
    profile: str,
    normalizer: Callable[[str], str],
    word_normalizer: Callable[[str], list[str]],
) -> list[RowScore]:
    scores: list[RowScore] = []
    for record in records:
        normalized_reference = normalizer(record.reference)
        normalized_hypothesis = normalizer(record.hypotheses[run_header])
        normalized_reference_words = word_normalizer(record.reference)
        normalized_hypothesis_words = word_normalizer(record.hypotheses[run_header])
        if not normalized_reference:
            raise ValueError(
                f"记录 {record.record_id} 的标注在归一化后为空，无法计算。"
            )
        if not normalized_reference_words:
            raise ValueError(
                f"记录 {record.record_id} 的标注在词归一化后为空，无法计算。"
            )

        edits = levenshtein_counts(normalized_reference, normalized_hypothesis)
        word_edits = levenshtein_counts(
            normalized_reference_words,
            normalized_hypothesis_words,
        )
        reference_chars = len(normalized_reference)
        hypothesis_chars = len(normalized_hypothesis)
        reference_words = len(normalized_reference_words)
        hypothesis_words = len(normalized_hypothesis_words)
        cer = edits.total / reference_chars
        wer = word_edits.total / reference_words
        scores.append(
            RowScore(
                profile=profile,
                run_header=run_header,
                record_id=record.record_id,
                record_order=record.order,
                excel_row=record.excel_row,
                reference=record.reference,
                hypothesis=record.hypotheses[run_header],
                normalized_reference=normalized_reference,
                normalized_hypothesis=normalized_hypothesis,
                normalized_reference_words=" ".join(normalized_reference_words),
                normalized_hypothesis_words=" ".join(normalized_hypothesis_words),
                reference_chars=reference_chars,
                hypothesis_chars=hypothesis_chars,
                reference_words=reference_words,
                hypothesis_words=hypothesis_words,
                substitutions=edits.substitutions,
                deletions=edits.deletions,
                insertions=edits.insertions,
                errors=edits.total,
                cer=cer,
                char_accuracy=1.0 - cer,
                word_substitutions=word_edits.substitutions,
                word_deletions=word_edits.deletions,
                word_insertions=word_edits.insertions,
                word_errors=word_edits.total,
                wer=wer,
                word_accuracy=1.0 - wer,
                is_empty=hypothesis_chars == 0,
                is_under_half=hypothesis_chars < reference_chars * 0.5,
            )
        )
    return scores


def summarize_scores(scores: Sequence[RowScore]) -> dict:
    if not scores:
        raise ValueError("没有可汇总的评分记录。")

    reference_chars = sum(item.reference_chars for item in scores)
    hypothesis_chars = sum(item.hypothesis_chars for item in scores)
    reference_words = sum(item.reference_words for item in scores)
    hypothesis_words = sum(item.hypothesis_words for item in scores)
    substitutions = sum(item.substitutions for item in scores)
    deletions = sum(item.deletions for item in scores)
    insertions = sum(item.insertions for item in scores)
    errors = substitutions + deletions + insertions
    word_substitutions = sum(item.word_substitutions for item in scores)
    word_deletions = sum(item.word_deletions for item in scores)
    word_insertions = sum(item.word_insertions for item in scores)
    word_errors = word_substitutions + word_deletions + word_insertions
    cer = errors / reference_chars
    wer = word_errors / reference_words
    worst = sorted(scores, key=lambda item: (item.cer, item.errors), reverse=True)

    return {
        "files": len(scores),
        "nonempty_files": sum(not item.is_empty for item in scores),
        "empty_files": sum(item.is_empty for item in scores),
        "empty_record_ids": [item.record_id for item in scores if item.is_empty],
        "under_half_files": sum(item.is_under_half for item in scores),
        "exact_files": sum(item.errors == 0 for item in scores),
        "reference_chars": reference_chars,
        "hypothesis_chars": hypothesis_chars,
        "hypothesis_reference_length_ratio": hypothesis_chars / reference_chars,
        "reference_words": reference_words,
        "hypothesis_words": hypothesis_words,
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "errors": errors,
        "cer": cer,
        "cer_percent": cer * 100,
        "char_accuracy": 1.0 - cer,
        "char_accuracy_percent": (1.0 - cer) * 100,
        "word_substitutions": word_substitutions,
        "word_deletions": word_deletions,
        "word_insertions": word_insertions,
        "word_errors": word_errors,
        "wer": wer,
        "wer_percent": wer * 100,
        "word_accuracy": 1.0 - wer,
        "word_accuracy_percent": (1.0 - wer) * 100,
        "worst_records": [
            {
                "record_id": item.record_id,
                "excel_row": item.excel_row,
                "reference_chars": item.reference_chars,
                "errors": item.errors,
                "cer_percent": item.cer * 100,
                "reference_words": item.reference_words,
                "word_errors": item.word_errors,
                "wer_percent": item.wer * 100,
            }
            for item in worst[:10]
        ],
    }


def summarize_by_split(scores: Sequence[RowScore], split: int | None) -> dict:
    summary = {"all": summarize_scores(scores)}
    if split is None:
        return summary

    first = [item for item in scores if item.record_order <= split]
    second = [item for item in scores if item.record_order > split]
    if first:
        summary[f"1-{split}"] = summarize_scores(first)
    if second:
        summary[f"{split + 1}-{max(item.record_order for item in scores)}"] = (
            summarize_scores(second)
        )
    return summary


def validate_audio_directory(audio_dir: Path, records: Sequence[Record]) -> dict:
    wav_files = sorted(audio_dir.glob("*.wav"))
    numeric_files: dict[int, Path] = {}
    invalid_names: list[str] = []
    read_errors: list[str] = []
    format_counts: dict[tuple[int, int, int, str], int] = {}
    durations: list[float] = []

    for wav_path in wav_files:
        try:
            file_id = int(wav_path.stem)
        except ValueError:
            invalid_names.append(wav_path.name)
            continue
        numeric_files[file_id] = wav_path
        try:
            with wave.open(str(wav_path), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_width_bits = wav_file.getsampwidth() * 8
                sample_rate = wav_file.getframerate()
                compression = wav_file.getcomptype()
                frame_count = wav_file.getnframes()
                duration = frame_count / sample_rate if sample_rate else 0.0
        except (wave.Error, OSError) as exc:
            read_errors.append(f"{wav_path.name}: {exc}")
            continue

        key = (channels, sample_rate, sample_width_bits, compression)
        format_counts[key] = format_counts.get(key, 0) + 1
        durations.append(duration)

    expected_numeric_ids = {
        int(record.record_id)
        for record in records
        if record.record_id.isascii() and record.record_id.isdigit()
    }
    actual_ids = set(numeric_files)
    formats = [
        {
            "count": count,
            "channels": key[0],
            "sample_rate_hz": key[1],
            "sample_width_bits": key[2],
            "compression": key[3],
        }
        for key, count in sorted(format_counts.items())
    ]
    return {
        "audio_dir": str(audio_dir.resolve()),
        "wav_file_count": len(wav_files),
        "invalid_file_names": invalid_names,
        "missing_record_ids": sorted(expected_numeric_ids - actual_ids),
        "extra_audio_ids": sorted(actual_ids - expected_numeric_ids),
        "read_errors": read_errors,
        "formats": formats,
        "total_duration_minutes": sum(durations) / 60.0,
        "minimum_duration_seconds": min(durations) if durations else None,
        "maximum_duration_seconds": max(durations) if durations else None,
    }


def write_json_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_detail_csv(path: Path, scores: Iterable[RowScore]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(RowScore.__dataclass_fields__)
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for score in scores:
            writer.writerow(asdict(score))


def print_summary(
    workbook_path: Path,
    sheet_name: str,
    record_count: int,
    selected_columns: dict[str, int],
    summaries: dict[str, dict[str, dict]],
    audio_summary: dict | None,
) -> None:
    print(f"工作簿：{workbook_path.resolve()}")
    print(f"工作表：{sheet_name}")
    print(f"有效标注：{record_count} 条")
    print(
        "使用列："
        + "；".join(
            f"{column_index_to_letters(column)}={header}"
            for header, column in selected_columns.items()
        )
    )

    for profile, runs in summaries.items():
        print()
        print(f"[{profile}]")
        for run_header, segments in runs.items():
            overall = segments["all"]
            print(
                f"- {run_header}: 字准确率 {overall['char_accuracy_percent']:.2f}%"
                f"，CER {overall['cer_percent']:.2f}%"
                f"，词准确率 {overall['word_accuracy_percent']:.2f}%"
                f"，WER {overall['wer_percent']:.2f}%"
                f"，有效输出 {overall['nonempty_files']}/{overall['files']}"
            )
            for segment_name, segment in segments.items():
                if segment_name == "all":
                    continue
                print(
                    f"  - {segment_name}: 字准确率 "
                    f"{segment['char_accuracy_percent']:.2f}%"
                    f"，CER {segment['cer_percent']:.2f}%"
                    f"，词准确率 {segment['word_accuracy_percent']:.2f}%"
                    f"，WER {segment['wer_percent']:.2f}%"
                )
            if overall["empty_record_ids"]:
                print(f"  - 空结果编号：{', '.join(overall['empty_record_ids'])}")
            print(
                f"  - 输出/标注长度比："
                f"{overall['hypothesis_reference_length_ratio']:.2%}"
                f"，不足一半：{overall['under_half_files']} 条"
            )

    if audio_summary is not None:
        print()
        print("[音频校验]")
        print(
            f"- WAV 数量：{audio_summary['wav_file_count']}"
            f"，总时长：{audio_summary['total_duration_minutes']:.2f} 分钟"
        )
        if audio_summary["formats"]:
            format_text = "；".join(
                f"{item['count']} 个/{item['sample_rate_hz']}Hz/"
                f"{item['sample_width_bits']}bit/{item['channels']}声道/"
                f"{item['compression']}"
                for item in audio_summary["formats"]
            )
            print(f"- 格式：{format_text}")
        if audio_summary["missing_record_ids"]:
            print(f"- 缺少音频：{audio_summary['missing_record_ids']}")
        if audio_summary["extra_audio_ids"]:
            print(f"- 多余音频：{audio_summary['extra_audio_ids']}")
        if audio_summary["invalid_file_names"]:
            print(f"- 非数字文件名：{audio_summary['invalid_file_names']}")
        if audio_summary["read_errors"]:
            print(f"- WAV 读取失败：{audio_summary['read_errors']}")


def run_self_test() -> None:
    cases = [
        (
            "basic cleanup",
            normalize_combined("أهلاً، يا فتى!"),
            "اهلايافتي",
        ),
        (
            "number 1500",
            normalize_combined("ألف وخمسمية ريال"),
            normalize_combined("1500 ريال"),
        ),
        (
            "number 25",
            normalize_combined("خمسة وعشرين ألف"),
            normalize_combined("25 ألف"),
        ),
        (
            "attached number",
            normalize_combined("بخمسين ريال"),
            normalize_combined("ب 50 ريال"),
        ),
    ]
    for name, actual, expected in cases:
        if actual != expected:
            raise AssertionError(f"{name}: {actual!r} != {expected!r}")

    edits = levenshtein_counts("kitten", "sitting")
    if edits.total != 3:
        raise AssertionError(f"Levenshtein test failed: {edits}")
    word_edits = levenshtein_counts(
        normalize_combined_words("ألف وخمسمية ريال"),
        normalize_combined_words("1500 ريال"),
    )
    if word_edits.total != 0:
        raise AssertionError(f"Word normalization test failed: {word_edits}")
    expected_number_token = "<NUM:ألف_وخمسمائة>"
    actual_number_tokens = normalize_combined_words("1500 ريال")
    if actual_number_tokens[0] != expected_number_token:
        raise AssertionError(
            f"Single number token test failed: {actual_number_tokens}"
        )
    if normalize_combined("1500") == normalize_combined("1000500"):
        raise AssertionError("Distinct numeric values collided after normalization.")
    coordinated = normalize_combined_words("4 و5")
    if len(coordinated) != 3 or coordinated[1] != "و":
        raise AssertionError(f"Invalid numeric phrase merge: {coordinated}")
    print("自检通过：归一化与编辑距离测试均成功。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="读取 XLSX 中的阿拉伯语 ASR 标注和批跑结果，计算字/词准确率。"
    )
    parser.add_argument("xlsx", nargs="?", type=Path, help="输入 .xlsx 工作簿")
    parser.add_argument("--sheet", help="工作表名称；省略时选择有效标注最多的表")
    parser.add_argument("--header-row", type=int, default=1, help="表头行号，默认 1")
    parser.add_argument(
        "--reference-header",
        default=DEFAULT_REFERENCE_HEADER,
        help=f"标注列表头，默认“{DEFAULT_REFERENCE_HEADER}”",
    )
    parser.add_argument(
        "--file-header",
        default=DEFAULT_FILE_HEADER,
        help=f"文件名列表头，默认“{DEFAULT_FILE_HEADER}”",
    )
    parser.add_argument(
        "--hyp-header",
        action="append",
        help="结果列表头，可重复传入；省略时自动选择包含“测试结果”的列",
    )
    parser.add_argument(
        "--split",
        type=int,
        help="按记录顺序分段汇总，例如 --split 100",
    )
    parser.add_argument("--audio-dir", type=Path, help="可选：对应 WAV 文件目录")
    parser.add_argument("--output-json", type=Path, help="可选：保存汇总 JSON")
    parser.add_argument("--output-csv", type=Path, help="可选：保存逐条明细 CSV")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="运行内置归一化和编辑距离自检",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.self_test:
        run_self_test()
        if args.xlsx is None:
            return 0
    if args.xlsx is None:
        parser.error("必须提供 XLSX 路径，或单独使用 --self-test。")
    if not args.xlsx.is_file():
        parser.error(f"找不到 XLSX 文件：{args.xlsx}")
    if args.xlsx.suffix.lower() != ".xlsx":
        parser.error("当前脚本只支持 .xlsx，不支持旧版 .xls。")
    if args.audio_dir is not None and not args.audio_dir.is_dir():
        parser.error(f"找不到音频目录：{args.audio_dir}")
    if args.split is not None and args.split < 1:
        parser.error("--split 必须大于 0。")

    try:
        with XlsxReader(args.xlsx) as reader:
            sheet_name, rows = select_sheet(
                reader=reader,
                requested_sheet=args.sheet,
                header_row=args.header_row,
                reference_header=args.reference_header,
            )
            records, selected_columns = build_records(
                rows=rows,
                header_row=args.header_row,
                reference_header=args.reference_header,
                file_header=args.file_header,
                requested_hypothesis_headers=args.hyp_header,
            )
    except (ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
        print(f"读取工作簿失败：{exc}", file=sys.stderr)
        return 2

    profiles = [NORMALIZATION_PROFILE]
    hypothesis_headers = list(records[0].hypotheses)
    summaries: dict[str, dict[str, dict]] = {}
    all_scores: list[RowScore] = []

    profile = NORMALIZATION_PROFILE
    summaries[profile] = {}
    for run_header in hypothesis_headers:
        scores = score_records(
            records=records,
            run_header=run_header,
            profile=profile,
            normalizer=normalize_combined,
            word_normalizer=normalize_combined_words,
        )
        all_scores.extend(scores)
        summaries[profile][run_header] = summarize_by_split(scores, args.split)

    audio_summary = (
        validate_audio_directory(args.audio_dir, records)
        if args.audio_dir is not None
        else None
    )
    report = {
        "workbook": str(args.xlsx.resolve()),
        "sheet": sheet_name,
        "record_count": len(records),
        "selected_columns": {
            header: {
                "index": column,
                "letter": column_index_to_letters(column),
            }
            for header, column in selected_columns.items()
        },
        "profiles": profiles,
        "split": args.split,
        "summaries": summaries,
        "audio_validation": audio_summary,
    }

    print_summary(
        workbook_path=args.xlsx,
        sheet_name=sheet_name,
        record_count=len(records),
        selected_columns=selected_columns,
        summaries=summaries,
        audio_summary=audio_summary,
    )
    if args.output_json is not None:
        write_json_report(args.output_json, report)
        print(f"\n已保存汇总 JSON：{args.output_json.resolve()}")
    if args.output_csv is not None:
        write_detail_csv(args.output_csv, all_scores)
        print(f"已保存逐条 CSV：{args.output_csv.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
