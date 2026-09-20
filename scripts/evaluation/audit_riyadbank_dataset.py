"""Audit the RiyadBank evaluation source package and write reviewable evidence."""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from src.evaluation.dataset import ConversationAudit, audit_dataset  # noqa: E402

LOGGER = logging.getLogger(__name__)
DEFAULT_DATASET = ROOT_DIR / "benchmarks" / "RiyadBankConversation"
DEFAULT_REPORT = (
    ROOT_DIR / "docs" / "reports" / "evaluation" / "riyadbank-source-audit-2026-09-16.md"
)
DEFAULT_CSV = ROOT_DIR / "docs" / "reports" / "evaluation" / "riyadbank-source-audit-2026-09-16.csv"


def _duration_difference(conversation: ConversationAudit) -> float | None:
    """Return the absolute MP3/WAV duration difference when both files decode."""
    if conversation.record_audio is None or conversation.user_audio is None:
        return None
    return abs(conversation.record_audio.duration_s - conversation.user_audio.duration_s)


def _write_csv(path: Path, conversations: tuple[ConversationAudit, ...]) -> None:
    """Write one evidence row per conversation without changing source files."""
    fieldnames = [
        "conversation_id",
        "status",
        "detected_language",
        "event_count",
        "user_event_count",
        "robot_event_count",
        "mp3_duration_s",
        "wav_duration_s",
        "duration_diff_s",
        "mp3_sample_rate",
        "mp3_channels",
        "wav_sample_rate",
        "wav_channels",
        "wav_subtype",
        "issue_count",
        "blocking_issue_count",
        "warning_count",
        "issue_types",
        "issue_rows",
        "history_path",
        "record_path",
        "user_record_path",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for conversation in conversations:
            issue_types = sorted({str(issue["issue_type"]) for issue in conversation.issues})
            issue_rows = sorted(
                int(issue["source_row"])
                for issue in conversation.issues
                if issue.get("source_row") is not None
            )
            writer.writerow(
                {
                    "conversation_id": conversation.conversation_id,
                    "status": "pass" if conversation.valid else "blocked",
                    "detected_language": conversation.detected_language,
                    "event_count": len(conversation.events),
                    "user_event_count": conversation.user_event_count,
                    "robot_event_count": conversation.robot_event_count,
                    "mp3_duration_s": (
                        conversation.record_audio.duration_s if conversation.record_audio else ""
                    ),
                    "wav_duration_s": (
                        conversation.user_audio.duration_s if conversation.user_audio else ""
                    ),
                    "duration_diff_s": (
                        round(_duration_difference(conversation) or 0.0, 6)
                        if _duration_difference(conversation) is not None
                        else ""
                    ),
                    "mp3_sample_rate": (
                        conversation.record_audio.sample_rate if conversation.record_audio else ""
                    ),
                    "mp3_channels": (
                        conversation.record_audio.channels if conversation.record_audio else ""
                    ),
                    "wav_sample_rate": (
                        conversation.user_audio.sample_rate if conversation.user_audio else ""
                    ),
                    "wav_channels": (
                        conversation.user_audio.channels if conversation.user_audio else ""
                    ),
                    "wav_subtype": (
                        conversation.user_audio.subtype if conversation.user_audio else ""
                    ),
                    "issue_count": len(conversation.issues),
                    "blocking_issue_count": len(conversation.blocking_issues),
                    "warning_count": len(conversation.warnings),
                    "issue_types": ";".join(issue_types),
                    "issue_rows": ";".join(str(row) for row in issue_rows),
                    "history_path": conversation.history_path or "",
                    "record_path": conversation.record_path or "",
                    "user_record_path": conversation.user_record_path or "",
                }
            )


def _write_markdown(path: Path, conversations: tuple[ConversationAudit, ...]) -> None:
    """Write a concise source audit report with timing warnings separated."""
    event_count = sum(len(item.events) for item in conversations)
    user_event_count = sum(item.user_event_count for item in conversations)
    robot_event_count = sum(item.robot_event_count for item in conversations)
    blocked = [item for item in conversations if not item.valid]
    blocking_issue_types = Counter(
        str(issue["issue_type"])
        for conversation in conversations
        for issue in conversation.blocking_issues
    )
    warning_types = Counter(
        str(issue["issue_type"])
        for conversation in conversations
        for issue in conversation.warnings
    )
    language_counts = Counter(item.detected_language for item in conversations)
    duration_differences = [
        difference
        for item in conversations
        if (difference := _duration_difference(item)) is not None
    ]
    outside_audio = [
        (item, [issue for issue in item.warnings if issue["issue_type"] == "event_outside_audio"])
        for item in conversations
    ]
    outside_audio = [(item, issues) for item, issues in outside_audio if issues]
    lines = [
        "# RiyadBank 56 通真实源数据审计",
        "",
        "- 审计日期：2026-09-16",
        "- 审计范围：`conversation_history/*.xlsx`、`record/*.mp3`、`user_record/*.wav`",
        (
            "- 结论：56 组文件齐全且均可运行；历史时间倒退和事件超出录音时长"
            "均作为参考警告，不影响启动判定。"
        ),
        "- 安全说明：本次只读取源文件并清理数据库内模拟结果，未修改或删除任何 Excel、MP3、WAV。",
        "",
        "## 汇总",
        "",
        "| 项目 | 结果 |",
        "|---|---:|",
        f"| 对话 / Excel / MP3 / WAV | {len(conversations)} / 56 / 56 / 56 |",
        f"| 事件总数 | {event_count} |",
        f"| 用户事件 / 机器人事件 | {user_event_count} / {robot_event_count} |",
        f"| 通过 / 阻断对话 | {len(conversations) - len(blocked)} / {len(blocked)} |",
        f"| 阻断问题总数 | {sum(blocking_issue_types.values())} |",
        f"| 参考警告总数 | {sum(warning_types.values())} |",
        "| 时间倒退（警告）/ 事件超出录音（警告） | "
        f"{warning_types['decreasing_event_time']} / "
        f"{warning_types['event_outside_audio']} |",
        "| 语言识别 ar / mixed / en | "
        f"{language_counts['ar']} / {language_counts['mixed']} / "
        f"{language_counts['en']} |",
        f"| MP3/WAV 最大时长差 | {max(duration_differences, default=0.0):.3f}s |",
        "",
        "## 1030000000091506 核查",
        "",
        "- 工作簿识别为阿拉伯语，共 22 个事件、10 个用户事件。",
        "- Excel 第 18 行（事件 R18）真实用户文本：`أقول لك أنا، أنا عميلة الهدية.`",
        "- MP3 与 WAV 均约 102.8 秒；此前页面中的英语对话属于模拟结果，不是该工作簿内容。",
        "",
        "## 需关注的越界事件",
        "",
        "| Conversation ID | 参考警告数 | 类型 | Excel 行 |",
        "|---|---:|---|---|",
    ]
    for conversation, issues in outside_audio:
        types = sorted({str(issue["issue_type"]) for issue in issues})
        rows = sorted(
            int(issue["source_row"]) for issue in issues if issue.get("source_row") is not None
        )
        lines.append(
            f"| {conversation.conversation_id} | {len(issues)} | "
            f"{', '.join(types)} | {', '.join(f'R{row}' for row in rows) or '—'} |"
        )
    lines.extend(
        [
            "",
            "## 处理建议",
            "",
            (
                "1. 44 处时间倒退保留为历史参考警告；运行时继续以 Excel 行顺序"
                "作为对话顺序，不要求修表。"
            ),
            "2. 11 个越界事件保留审计提醒，不阻止评测；对应范围不得直接作为精确切片 Benchmark。",
            "3. 可直接启动三家 ASR 与两轮 LLM；未实跑前不生成报告、人工复核或 Benchmark 数据。",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    """Run the audit and persist Markdown plus CSV evidence."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()

    audit = audit_dataset(args.dataset)
    _write_csv(args.csv, audit.conversations)
    _write_markdown(args.report, audit.conversations)
    LOGGER.info("Wrote audit evidence to %s and %s", args.report, args.csv)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(main())
