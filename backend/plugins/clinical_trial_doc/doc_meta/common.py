"""Shared clinical-trial metadata extraction rules and regex helpers."""

from __future__ import annotations

import re

from core.metadata.schemas import MetadataRule

_DATE_PART = (
    r"\d{4}[.年/-]\d{1,2}[.月/-]\d{1,2}日?"
    r"|Date_\d+"
)

_DATE_VALUE = _DATE_PART

_DATE_RANGE = rf"(?:{_DATE_PART})-(?:{_DATE_PART})"

_CUTOFF_BLOCK_SOURCES = ("title_block", "heading", "early_block")

COMMON_PREFIX_RULES: list[MetadataRule] = [
    MetadataRule(
        field_name="study_drug",
        pattern=(
            r"(?:代号|试验药物|研究药物|药物名称|试验药物名称)"
            r"[:：]\s*(?P<value>StudyDrug_\d+)"
        ),
        flags=re.IGNORECASE,
    ),
    MetadataRule(
        field_name="study_drug",
        pattern=r"^\s*(?P<value>StudyDrug_\d+)\s*$",
        flags=re.IGNORECASE,
        source_types=("file_name", "display_name", "title_block", "early_block"),
    ),
    MetadataRule(
        field_name="study_drug",
        pattern=r"(?P<value>StudyDrug_\d+)",
        flags=re.IGNORECASE,
        source_types=("file_name", "display_name", "title_block", "early_block"),
    ),
    MetadataRule(
        field_name="sponsor",
        pattern=r"(?:申办方|申办者)[:：]\s*(?P<value>Sponsor_\d+)",
        flags=re.IGNORECASE,
    ),
    MetadataRule(
        field_name="investigator",
        pattern=r"(?:主要研究者|研究者)[:：]\s*(?P<value>Investigator_\d+)",
        flags=re.IGNORECASE,
    ),
    MetadataRule(
        field_name="protocol_id",
        pattern=r"方案编号[:：]\s*(?P<value>Study_\d+|Protocol_\d+|[A-Za-z0-9][A-Za-z0-9_-]+)",
        flags=re.IGNORECASE,
    ),
    MetadataRule(
        field_name="protocol_id",
        pattern=r"Protocol(?:\s+No\.?|编号)[:：]?\s*(?P<value>Study_\d+|Protocol_\d+|[A-Za-z0-9][A-Za-z0-9_-]+)",
        flags=re.IGNORECASE,
    ),
    MetadataRule(
        field_name="protocol_id",
        pattern=r"(?P<value>Protocol_\d+)",
        flags=re.IGNORECASE,
        source_types=("file_name", "display_name", "title_block", "early_block"),
        multi=True,
    ),
    MetadataRule(
        field_name="version",
        pattern=r"(?:版本号|版本)[:：]\s*(?P<value>V?\d+(?:\.\d+)*)",
        flags=re.IGNORECASE,
    ),
    MetadataRule(
        field_name="document_date",
        pattern=rf"(?:版本日期|文件日期|报告日期|签发日期|批准日期)[:：]\s*(?P<value>{_DATE_VALUE})",
        flags=re.IGNORECASE,
    ),
]

COMMON_CUTOFF_RULES: list[MetadataRule] = [
    MetadataRule(
        field_name="cutoff_date",
        pattern=rf"(?:数据截至|数据截止日期)[:：]?\s*(?P<value>{_DATE_VALUE})",
        flags=re.IGNORECASE,
        source_types=_CUTOFF_BLOCK_SOURCES,
    ),
    MetadataRule(
        field_name="cutoff_date",
        pattern=rf"截至\s*(?P<value>{_DATE_VALUE})",
        flags=re.IGNORECASE,
        source_types=_CUTOFF_BLOCK_SOURCES,
    ),
    MetadataRule(
        field_name="cutoff_date",
        pattern=rf"基于截至(?P<value>{_DATE_VALUE})的",
        flags=re.IGNORECASE,
        source_types=_CUTOFF_BLOCK_SOURCES,
    ),
    MetadataRule(
        field_name="cutoff_date",
        pattern=rf"(?:数据库锁定日期|数据库锁库日期|锁库日期|数据锁定日期)[:：]\s*(?P<value>{_DATE_VALUE})",
        flags=re.IGNORECASE,
        source_types=_CUTOFF_BLOCK_SOURCES,
    ),
]
