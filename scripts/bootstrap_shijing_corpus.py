from __future__ import annotations

import argparse
import functools
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from common import (
    MANIFESTS_DIR,
    REPO_ROOT,
    clean_wikitext,
    page_to_raw_url,
    resolve_redirect_raw,
    section_export_paths,
    title_from_url,
    write_json,
    write_jsonl,
)
from shijing_quality import shijing_witness_metadata
from shijing_verification import (
    build_verification_index,
    load_shijing_verification_ledger,
    validate_verification_coverage,
    verification_entry_is_exportable,
)

WORK_ID = "shijing"
MANIFEST_PATH = MANIFESTS_DIR / f"{WORK_ID}.yml"
INVENTORY_PATH = MANIFESTS_DIR.parent / "shijing_poem_inventory.yml"
RAW_DIR = REPO_ROOT / "corpus" / "raw" / "wikisource"
CHINESE_DIR = REPO_ROOT / "corpus" / "processed" / "chinese_base_texts"
TRANSLATION_DIR = REPO_ROOT / "corpus" / "processed" / "translations"
ALIGNMENT_DIR = REPO_ROOT / "corpus" / "processed" / "alignments"
ACCESS_DATE = "2026-05-30"
SOURCE_SUFFIX = "zhwikisource-20260530"
STANDALONE_TARGET_SOURCE_SUFFIX = "legge-sheking-1871"
SBE_TARGET_SOURCE_SUFFIX = "legge-sbe-v3-1879"
OCR_TARGET_SOURCE_SUFFIX = "legge-sheking-1871-ocr"
HOCR_TARGET_SOURCE_SUFFIX = "legge-sheking-1871-hocr"
LEGGE_SHEKING_1871_PART_1_ITEM_URL = "https://archive.org/details/chineseclassics41legg"
LEGGE_SHEKING_1871_PART_1_OCR_URL = (
    "https://archive.org/download/chineseclassics41legg/chineseclassics41legg_djvu.txt"
)
LEGGE_SHEKING_1871_PART_1_HOCR_URL = (
    "https://archive.org/download/chineseclassics41legg/chineseclassics41legg_hocr.html"
)
LEGGE_SHEKING_1871_PART_2_ITEM_URL = "https://archive.org/details/chineseclassics42legg"
LEGGE_SHEKING_1871_PART_2_OCR_URL = (
    "https://archive.org/download/chineseclassics42legg/chineseclassics42legg_djvu.txt"
)
LEGGE_SHEKING_1871_PART_2_HOCR_URL = (
    "https://archive.org/download/chineseclassics42legg/chineseclassics42legg_hocr.html"
)
LEGGE_SHEKING_1871_OCR_ACCESS_DATE = "2026-05-30"
LEGGE_SHEKING_1871_OCR_RAW_PATHS = {
    "part-1": Path("corpus/raw/internet_archive/legge-sheking-1871-part-1__ocr.txt"),
    "part-2": Path("corpus/raw/internet_archive/legge-sheking-1871-part-2__ocr.txt"),
}
LEGGE_SHEKING_1871_HOCR_RAW_PATHS = {
    "part-1": Path("corpus/raw/internet_archive/legge-sheking-1871-part-1__hocr.html"),
    "part-2": Path("corpus/raw/internet_archive/legge-sheking-1871-part-2__hocr.html"),
}
TITLE_ONLY_SORT_KEYS = {171, 172, 173, 176, 177, 178}

ZH_INDEX_URL = "https://zh.wikisource.org/wiki/詩經"
ZH_INDEX_RAW_PATH = RAW_DIR / f"{WORK_ID}__index__{SOURCE_SUFFIX}__raw.wikitext"
FULL_TEXT_WITNESS_URL = "https://en.wikisource.org/wiki/Sacred_Books_of_the_East/Volume_3/The_Shih"
FULL_TEXT_WITNESS_GUTENBERG_URL = "https://archive.org/download/theshihking09394gut/7shih10.txt"
SBE_ALLPAGES_URL = (
    "https://en.wikisource.org/w/api.php?"
    "action=query&list=allpages&apprefix=Sacred%20Books%20of%20the%20East/Volume%203/The%20Shih"
    "&apnamespace=0&aplimit=max&format=json"
)


def build_ingestion_policy() -> dict[str, Any]:
    return {
        "inventory_required": True,
        "inventory_path": "metadata/shijing_poem_inventory.yml",
        "inventory_unit_key": "poems",
        "inventory_derivation": "canonical_wikisource_index_with_title_only_lost_text_entries",
        "ingestion_plan_required": True,
        "ingestion_plan_path": "documentation/shijing_ingestion_plan.md",
        "source_audit_required": True,
        "source_audit_path": "documentation/shijing_ingestion_plan.md",
        "granularity_policy_required": True,
        "granularity_policy_path": "documentation/alignment_granularity_policy.md",
        "section_unit": "poem",
        "preferred_segment_unit": "stanza",
        "minimum_required_alignment_scope": "poem",
        "maximum_exact_alignment_scope": "poem",
        "allowed_segment_units": ["stanza", "poem"],
        "coarse_alignment_units": ["poem"],
        "granularity_order": ["stanza", "poem"],
        "metadata_only_allowed": True,
        "missing_text_policy": "retain_title_only_or_unverified_units_as_metadata_only_and_non_exportable",
        "commentary_policy": "exclude_commentary_and_notes_from_exact_alignments_and_tmx",
        "rights_policy": "public_domain_only_for_export",
        "allowed_export_rights_statuses": ["public_domain"],
        "section_group_export_policy": "forbidden",
        "completion_definition": (
            "An extant Shijing poem is complete only when it has a Chinese base text, a public-domain English witness, "
            "and at least one exact alignment no broader than a single poem; stanza-level alignment is preferred where safe."
        ),
    }
SBE_CATALOG_PATH = RAW_DIR / f"{WORK_ID}__catalog__{SBE_TARGET_SOURCE_SUFFIX}__allpages.json"

MAJOR_DIVISION_CODES = {
    "國風": "guofeng",
    "小雅": "xiaoya",
    "大雅": "daya",
    "頌": "song",
}

SUBDIVISION_CODES = {
    "周南": "zhounan",
    "召南": "zhaonan",
    "邶風": "beifeng",
    "鄘風": "yongfeng",
    "衛風": "weifeng",
    "王風": "wangfeng",
    "鄭風": "zhengfeng",
    "齊風": "qifeng",
    "魏風": "weifeng-state",
    "唐風": "tangfeng",
    "秦風": "qinfeng",
    "陳風": "chenfeng",
    "檜風": "kuaifeng",
    "曹風": "caofeng",
    "豳風": "binfeng",
    "鹿鳴之什": "luming",
    "南有嘉魚之什": "nanyoujiayu",
    "鴻雁之什": "hongyan",
    "鴻鴈之什": "hongyan",
    "節南山之什": "jienanshan",
    "谷風之什": "gufeng",
    "甫田之什": "futian",
    "魚藻之什": "yuzao",
    "文王之什": "wenwang",
    "生民之什": "shengmin",
    "蕩之什": "dang",
    "清廟之什": "qingmiao",
    "臣工之什": "chengong",
    "閔予小子之什": "minyuxiaozi",
    "周頌": "zhousong",
    "魯頌": "lusong",
    "商頌": "shangsong",
}

SECTION_CATALOG: list[dict[str, Any]] = [
    {
        "section_id": "guofeng-zhounan-001-guanju",
        "label": "關雎",
        "canonical_ref": "詩經·國風·周南·001",
        "sort_key": 1,
        "major_division": "國風",
        "subdivision": "周南",
        "poem_number": 1,
        "legge_section_alias": "Guan ju",
        "pinyin_alias": "Guān Jū",
        "zh_page_url": "https://zh.wikisource.org/wiki/詩經/關雎",
        "zh_section_heading": "國風‧周南‧關雎",
        "en_page_url": "https://en.wikisource.org/wiki/Guan_ju",
        "en_page_title": "Guan ju",
        "target_source_suffix": STANDALONE_TARGET_SOURCE_SUFFIX,
        "english_witness": "standalone_sheking",
    }
]

ZHOUNAN_OCR_PILOT_SORT_KEYS = set(range(2, 12))
REVIEWED_LEGGE_OCR_POEM_BLOCKS: dict[int, dict[str, Any]] = {
    2: {
        "legge_section_alias": "Koh t'an",
        "english_blocks": [
            "\n".join(
                [
                    "How the dolichos spreads out,",
                    "And extends over the valley.",
                    "The yellow birds fly about,",
                    "And collect on the thick foliage.",
                ]
            ),
            "\n".join(
                [
                    "I cut it and I boiled it,",
                    "And made both fine cloth and coarse,",
                    "Which I will wear without getting tired of it.",
                ]
            ),
            "\n".join(
                [
                    "I have told the matron,",
                    "Who will announce that I am going to see my parents.",
                    "I will wash my private clothes clean,",
                    "And I will rinse my robes.",
                    "Which need to be rinsed, and which do not?",
                    "I am going back to visit my parents.",
                ]
            ),
        ],
    },
    3: {
        "legge_section_alias": "Keuen-urh",
        "english_blocks": [
            "\n".join(
                [
                    "I was gathering and gathering the mouse-ear,",
                    "But could not fill my shallow basket.",
                    "With a sigh for the man of my heart,",
                    "I placed it on the high road.",
                ]
            ),
            "\n".join(
                [
                    "I was ascending that rock-covered height,",
                    "But my horses were too tired to breast it.",
                    "I will now pour a cup from that gilded vase,",
                    "Hoping I may not have to think of him long.",
                ]
            ),
            "\n".join(
                [
                    "I was ascending that lofty ridge,",
                    "But my horses turned of a dark yellow.",
                    "I will now take a cup from that rhinoceros-horn cup,",
                    "Hoping I may not have long to sorrow.",
                ]
            ),
            "\n".join(
                [
                    "I was ascending that flat-topped height,",
                    "But my horses became quite disabled,",
                    "And my servants were also disabled.",
                    "Oh! how great is my sorrow!",
                ]
            ),
        ],
    },
    4: {
        "legge_section_alias": "K'ew muh",
        "english_blocks": [
            "\n".join(
                [
                    "In the south are the trees with curved drooping branches,",
                    "With the dolichos creepers clinging to them.",
                    "To be rejoiced in is our princely lady:",
                    "May she repose in her happiness and dignity!",
                ]
            ),
            "\n".join(
                [
                    "In the south are the trees with curved drooping branches,",
                    "Covered by the dolichos creepers.",
                    "To be rejoiced in is our princely lady:",
                    "May she be great in her happiness and dignity!",
                ]
            ),
            "\n".join(
                [
                    "In the south are the trees with curved drooping branches,",
                    "Round which the dolichos creepers twine.",
                    "To be rejoiced in is our princely lady:",
                    "May she be complete in her happiness and dignity!",
                ]
            ),
        ],
    },
    5: {
        "legge_section_alias": "Chung-sze",
        "english_blocks": [
            "\n".join(
                [
                    "Ye locusts, winged tribes,",
                    "How harmoniously you collect together!",
                    "Right is it that your descendants",
                    "Should be multitudinous!",
                ]
            ),
            "\n".join(
                [
                    "Ye locusts, winged tribes,",
                    "How sound your wings in flight!",
                    "Right is it that your descendants",
                    "Should be as in unbroken strings!",
                ]
            ),
            "\n".join(
                [
                    "Ye locusts, winged tribes,",
                    "How you cluster together!",
                    "Right is it that your descendants",
                    "Should be in swarms!",
                ]
            ),
        ],
    },
    6: {
        "legge_section_alias": "T'aou yaou",
        "english_blocks": [
            "\n".join(
                [
                    "The peach tree is young and elegant;",
                    "Brilliant are its flowers.",
                    "This young lady is going to her future home,",
                    "And will order well her chamber and house.",
                ]
            ),
            "\n".join(
                [
                    "The peach tree is young and elegant;",
                    "Abundant will be its fruit.",
                    "This young lady is going to her future home,",
                    "And will order well her house and chamber.",
                ]
            ),
            "\n".join(
                [
                    "The peach tree is young and elegant;",
                    "Luxuriant are its leaves.",
                    "This young lady is going to her future home,",
                    "And will order well her family.",
                ]
            ),
        ],
    },
    7: {
        "legge_section_alias": "T'oo tseu",
        "english_blocks": [
            "\n".join(
                [
                    "Carefully adjusted are the rabbit nets;",
                    "Clang clang go the blows on the pegs.",
                    "That stalwart, martial man",
                    "Might be shield and wall to his prince.",
                ]
            ),
            "\n".join(
                [
                    "Carefully adjusted are the rabbit nets,",
                    "And placed where many ways meet.",
                    "That stalwart, martial man",
                    "Would be a good companion for his prince.",
                ]
            ),
            "\n".join(
                [
                    "Carefully adjusted are the rabbit nets,",
                    "And placed in the midst of the forest.",
                    "That stalwart, martial man",
                    "Might be head and heart to his prince.",
                ]
            ),
        ],
    },
    8: {
        "legge_section_alias": "Fow-e",
        "english_blocks": [
            "\n".join(
                [
                    "We gather and gather the plantains;",
                    "Now we may gather them.",
                    "We gather and gather the plantains;",
                    "Now we have got them.",
                ]
            ),
            "\n".join(
                [
                    "We gather and gather the plantains;",
                    "Now we pluck their ears.",
                    "We gather and gather the plantains;",
                    "Now we seize them in our hands.",
                ]
            ),
            "\n".join(
                [
                    "We gather and gather the plantains;",
                    "Now we lap them in our skirts.",
                    "We gather and gather the plantains;",
                    "Now we tuck them in our girdles.",
                ]
            ),
        ],
    },
    9: {
        "legge_section_alias": "Han kwang",
        "english_blocks": [
            "\n".join(
                [
                    "In the south rise the trees without branches,",
                    "Affording no shelter.",
                    "By the Han are girls rambling about,",
                    "But it is vain to solicit them.",
                    "The breadth of the Han",
                    "Cannot be dived across;",
                    "The length of the Keang",
                    "Cannot be navigated with a raft.",
                ]
            ),
            "\n".join(
                [
                    "Many are the bundles of firewood;",
                    "I would cut down the thorns to form more.",
                    "Those girls that are going to their future home,",
                    "I would feed their horses.",
                    "The breadth of the Han",
                    "Cannot be dived across;",
                    "The length of the Keang",
                    "Cannot be navigated with a raft.",
                ]
            ),
            "\n".join(
                [
                    "Many are the bundles of firewood;",
                    "I would cut down the southernwood to form more.",
                    "Those girls that are going to their future home,",
                    "I would feed their colts.",
                    "The breadth of the Han",
                    "Cannot be dived across;",
                    "The length of the Keang",
                    "Cannot be navigated with a raft.",
                ]
            ),
        ],
    },
    10: {
        "legge_section_alias": "Joo fun",
        "english_blocks": [
            "\n".join(
                [
                    "Along those raised banks of the Joo,",
                    "I cut down the branches and slender stems.",
                    "While I could not see my lord,",
                    "I felt as it were pangs of great hunger.",
                ]
            ),
            "\n".join(
                [
                    "Along those raised banks of the Joo,",
                    "I cut down the branches and fresh twigs.",
                    "I have seen my lord;",
                    "He has not cast me away.",
                ]
            ),
            "\n".join(
                [
                    "The bream is showing its tail all red;",
                    "The royal House is like a blazing fire.",
                    "Though it be like a blazing fire,",
                    "Your parents are very near.",
                ]
            ),
        ],
    },
    11: {
        "legge_section_alias": "Lin che che",
        "english_blocks": [
            "\n".join(
                [
                    "The feet of the lin:—",
                    "The noble sons of our prince,",
                    "Ah! they are the lin!",
                ]
            ),
            "\n".join(
                [
                    "The forehead of the lin:—",
                    "The noble grandsons of our prince,",
                    "Ah! they are the lin!",
                ]
            ),
            "\n".join(
                [
                    "The horn of the lin:—",
                    "The noble kindred of our prince,",
                    "Ah! they are the lin!",
                ]
            ),
        ],
    },
    12: {
        "legge_section_alias": "Ts'eoh chlaou",
        "review_note": (
            "Recovered reviewed poem text from inspected Legge hOCR page-head lines; "
            "kept poem-level alignment until stanza-safe OCR segmentation is reworked."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "Magpie has made its nest,",
                    "And the dove occupies it.",
                    "This young lady is going to her future home,",
                    "With a hundred chariots to escort her.",
                ]
            ),
            "\n".join(
                [
                    "Magpie has made its nest,",
                    "And the dove fills it.",
                    "This young lady is going to her future home,",
                    "With a hundred chariots all complete.",
                ]
            ),
            "\n".join(
                [
                    "Magpie has made its nest,",
                    "And the dove is in it.",
                    "This young lady is going to her future home,",
                    "With a hundred chariots as attendants.",
                ]
            ),
        ],
    },
    25: {
        "legge_section_alias": "Tsow-yu",
        "review_note": (
            "Recovered reviewed poem text from inspected Legge hOCR page-head lines; "
            "kept poem-level alignment until stanza-safe OCR segmentation is reworked."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "There is the Tsow-yu; there is the Tsow-yu;",
                    "In the fifth month he comes forth with slow and leisurely movements.",
                    "There is the white tiger; there is the white tiger;",
                    "Its paws are seized, and there are leisurely movements.",
                ]
            ),
            "\n".join(
                [
                    "There is the Tsow-yu; there is the Tsow-yu;",
                    "Its feet are seized, and there are leisurely movements.",
                    "There is the white tiger; there is the white tiger;",
                    "Its feet are seized, and there are leisurely movements.",
                ]
            ),
        ],
    },
    57: {
        "legge_section_alias": "Shih jin",
        "review_note": (
            "Recovered reviewed poem text from inspected Legge hOCR lines after the automatic section boundary "
            "bled in the preceding poem; kept poem-level alignment until stanza-safe OCR segmentation is reworked."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "Large was she and tall,",
                    "In her embroidered robe, with a [plain] single garment over it: —",
                    "The daughter of the marquis of Ts'e,",
                    "The wife of the marquis of Wei,",
                    "The sister of the heir-son of Ts'e,",
                    "The sister-in-law of the marquis of Hing,",
                    "The viscount of Tan also her brother-in-law.",
                ]
            ),
            "\n".join(
                [
                    "Her fingers were like the blades of the young white-grass;",
                    "Her skin was like congealed ointment;",
                    "Her neck was like the tree-grub;",
                    "Her teeth were like melon seeds;",
                    "Her forehead cicada-like; her eyebrows like [the antennae of]",
                    "the silkworm moth;",
                    "What dimples, as she artfully smiled!",
                ]
            ),
            "\n".join(
                [
                    "Large was she and tall,",
                    "When she halted in the cultivated suburbs.",
                    "Strong looked her four horses,",
                    "With the red ornaments so rich about their bits.",
                    "Thus in her carriage, with its screens of pheasant feathers,",
                    "she proceeded to our court.",
                    "Early retire, ye great officers,",
                    "And do not make the marquis fatigued!",
                ]
            ),
            "\n".join(
                [
                    "The waters of the Ho, wide and deep,",
                    "Flow northwards in majestic course.",
                    "The nets are dropt into them with a plashing sound,",
                    "Among shoals of sturgeon, large and small,",
                    "While the rushes and sedges are rank about.",
                    "Splendidly adorned were her sister ladies;",
                    "Martial looked the attendant officers.",
                ]
            ),
        ],
    },
    61: {
        "legge_section_alias": "Ho kwang",
        "review_note": (
            "Recovered reviewed poem text from inspected Legge hOCR page-head lines; "
            "kept poem-level alignment until stanza-safe OCR segmentation is reworked."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "How wide is the Ho!",
                    "Yet it may be passed in a raft.",
                    "That Song is far off,",
                    "Yet it may be reached by a day's journey.",
                ]
            ),
            "\n".join(
                [
                    "How wide is the Ho!",
                    "Yet it may be passed in a boat.",
                    "That Song is far off,",
                    "Yet it may be reached by fording.",
                ]
            ),
        ],
    },
    90: {
        "legge_section_alias": "Fung y",
        "review_note": (
            "Recovered reviewed poem text from inspected Legge hOCR page-head lines; "
            "kept poem-level alignment until stanza-safe OCR segmentation is reworked."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "When the wind is cold and rain comes,",
                    "The cock crows with the glooming.",
                    "When we see our superior man,",
                    "Clouds of sorrow pass away.",
                ]
            ),
            "\n".join(
                [
                    "When the wind whistles and the rain darkens,",
                    "The cock crows and is choking.",
                    "When we see our superior man,",
                    "We are at our ease and glad.",
                ]
            ),
            "\n".join(
                [
                    "The wind and rain unite in violence;",
                    "The cock crows without ceasing.",
                    "When we see our superior man,",
                    "We are happy and pleased.",
                ]
            ),
        ],
    },
    91: {
        "legge_section_alias": "Tsz Klen",
        "review_note": (
            "Recovered reviewed poem text from inspected Legge hOCR lines and trimmed away the following poem that the "
            "automatic section boundary had appended; kept poem-level alignment until stanza-safe OCR segmentation is reworked."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "O you, with the blue collar,",
                    "Prolonged is the anxiety of my heart.",
                    "Although I do not go [to you],",
                    "Why do you not continue your messages [to me]?",
                ]
            ),
            "\n".join(
                [
                    "O you with the blue [strings to your] girdle-gems,",
                    "Long, long do I think of you.",
                    "Although I do not go [to you],",
                    "Why do you not come [to me]?",
                ]
            ),
            "\n".join(
                [
                    "How volatile are you and dissipated,",
                    "By the look-out tower on the wall!",
                    "One day without the sight of you",
                    "Is like three months.",
                ]
            ),
        ],
    },
    92: {
        "legge_section_alias": "Yang che shwuy",
        "review_note": (
            "Recovered reviewed poem text from inspected Legge hOCR page-head lines; "
            "kept poem-level alignment until stanza-safe OCR segmentation is reworked."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "The waters of the Yangtze are sent forth,",
                    "And there is a white stone left bare.",
                    "The lad must think of his kindred,",
                    "And then he can be spoken with.",
                ]
            ),
            "\n".join(
                [
                    "The waters of the Yangtze are sent forth,",
                    "And there is a white stone like a comb.",
                    "The lad must think of his kindred,",
                    "And then he can be spoken with.",
                ]
            ),
            "\n".join(
                [
                    "The waters of the Yangtze are sent forth,",
                    "And there is a white stone like a tooth.",
                    "The lad must think of his kindred,",
                    "And then he can be spoken with.",
                ]
            ),
        ],
    },
    122: {
        "legge_section_alias": "Woo e",
        "review_note": (
            "Recovered reviewed poem text from inspected Legge hOCR page-head lines; "
            "kept poem-level alignment until stanza-safe OCR segmentation is reworked."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "How do we proceed without clothes?",
                    "We have your lower garments and your upper.",
                    "He has repaired our halberds and spears,",
                    "And we will seek our revenge.",
                ]
            ),
            "\n".join(
                [
                    "How do we proceed without clothes?",
                    "We have your skirts and robes.",
                    "He has repaired our spears and halberds,",
                    "And we will make him our comrade.",
                ]
            ),
            "\n".join(
                [
                    "How do we proceed without clothes?",
                    "We have your capes and tunics.",
                    "He has repaired our armour and helmets,",
                    "And we will go with him.",
                ]
            ),
        ],
    },
    149: {
        "legge_section_alias": "Fei fung",
        "review_note": (
            "Recovered reviewed poem text from inspected Legge hOCR page-head lines; "
            "kept poem-level alignment until stanza-safe OCR segmentation is reworked."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "Not for the violence of the wind;",
                    "Not for the rushing storm;",
                    "Do I long and retire,",
                    "But because of my old age, and sad.",
                ]
            ),
            "\n".join(
                [
                    "Not for the violence of the wind;",
                    "Not for the rushing storm;",
                    "Do I go forward, and come back,",
                    "But because of my old age, and sad.",
                ]
            ),
            "\n".join(
                [
                    "Who is it there?",
                    "The butterfly wheeling about.",
                    "Ah! we who encounter our troubles,",
                    "Ought not to be like this.",
                ]
            ),
        ],
    },
    158: {
        "legge_section_alias": "Fall ho",
        "review_note": (
            "Recovered reviewed poem text from inspected Legge hOCR page-head lines; "
            "kept poem-level alignment until stanza-safe OCR segmentation is reworked."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "How he hews an axe-handle!",
                    "How he hews it, indeed!",
                    "It is not far to seek;",
                    "In your wife you have the pattern.",
                ]
            ),
            "\n".join(
                [
                    "How he hews an axe-handle!",
                    "How he hews it, indeed!",
                    "It is not far to seek;",
                    "The man and the woman are distinguished.",
                ]
            ),
        ],
    },
    170: {
        "legge_section_alias": "Yu le",
        "review_note": (
            "Recovered reviewed poem text from inspected Legge hOCR page-head lines after the automatic section map "
            "drifted into a title-only entry; kept poem-level alignment until stanza-safe OCR segmentation is reworked."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "The fish lie in the basket,",
                    "And the bream is in the pot.",
                    "The lovely and virtuous lady —",
                    "May there be to her spirits tranquillity and repose.",
                ]
            ),
            "\n".join(
                [
                    "The fish lie in the basket,",
                    "And the tench and ide are in it.",
                    "The lovely and virtuous lady —",
                    "May there be to her plenty of repose.",
                ]
            ),
            "\n".join(
                [
                    "The fish lie in the basket,",
                    "And the black skirts are in it.",
                    "The lovely and virtuous lady —",
                    "May there be to her rest in her apartment.",
                ]
            ),
            "\n".join(
                [
                    "The fish lie in the basket,",
                    "And the salmon and hwang are in it.",
                    "The lovely and virtuous lady —",
                    "May there be to her congratulation from the spirits.",
                ]
            ),
            "\n".join(
                [
                    "The fish lie in the basket,",
                    "And the bull-head and carp are in it.",
                    "The lovely and virtuous lady —",
                    "May there be to her bright fame from the spirits.",
                ]
            ),
            "\n".join(
                [
                    "The things in the basket are of dried grass;",
                    "The things in the pot are of vegetables.",
                    "The lovely and virtuous lady —",
                    "May there be to her vigorous health from the spirits.",
                ]
            ),
        ],
    },
    174: {
        "legge_section_alias": "Nan yew k'ea yu",
        "review_note": (
            "Recovered reviewed poem text from inspected Legge hOCR page-head lines after the automatic section map "
            "crossed a heading boundary; kept poem-level alignment until stanza-safe OCR segmentation is reworked."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "In the south are the barbel fish;",
                    "The royal way is very easy.",
                    "The gentleman goes to the banquet,",
                    "There are admirable spirits and wine.",
                ]
            ),
            "\n".join(
                [
                    "In the south are the white bream;",
                    "The royal way is very pure and good.",
                    "The gentleman goes to the banquet,",
                    "There are guests with lutes and drums.",
                ]
            ),
            "\n".join(
                [
                    "In the south are the trees of sapan wood;",
                    "The royal way is very quiet and correct.",
                    "The gentleman goes to the banquet,",
                    "There are guests with lutes, bells, and drums.",
                ]
            ),
            "\n".join(
                [
                    "In the south are the trees of prickly ash;",
                    "The royal way is very observant of duty.",
                    "The gentleman goes to the banquet,",
                    "There are guests with lutes, large and small.",
                ]
            ),
        ],
    },
}

EXTRACTION_FAILED_METADATA_ONLY_SORT_KEYS = {44, 144}


class BlockCenterExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[list[str]] = []
        self._capture_depth = 0
        self._ignored_depth = 0
        self._current_parts: list[str] = []
        self._current_block_lines: list[str] = []
        self._current_paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "div" and "wst-block-center" in (attributes.get("class") or ""):
            self._capture_depth += 1
            return
        if self._capture_depth == 0:
            return
        if tag in {"style", "script"}:
            self._ignored_depth += 1
            return
        if tag == "sup" and "reference" in (attributes.get("class") or ""):
            self._ignored_depth += 1
            return
        if tag == "br":
            self._current_parts.append("\n")
        elif tag == "p":
            self._current_parts = []

    def handle_endtag(self, tag: str) -> None:
        if self._capture_depth == 0:
            return
        if self._ignored_depth and tag in {"style", "script", "sup"}:
            self._ignored_depth -= 1
            return
        if tag == "p":
            paragraph = html.unescape("".join(self._current_parts))
            cleaned_lines = [normalize_english_line(line) for line in paragraph.splitlines()]
            lines = [line for line in cleaned_lines if line]
            if lines:
                self._current_paragraphs.append("\n".join(lines))
            self._current_parts = []
        elif tag == "div":
            self._capture_depth -= 1
            if self._capture_depth == 0 and self._current_paragraphs:
                self.blocks.append(self._current_paragraphs)
                self._current_paragraphs = []
                self._current_block_lines = []

    def handle_data(self, data: str) -> None:
        if self._capture_depth > 0 and self._ignored_depth == 0:
            self._current_parts.append(data)


def request_text(url: str, *, retries: int = 5) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; CopilotCLI/1.0)"}
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
                time.sleep(0.5)
                return body
        except urllib.error.HTTPError as exc:
            last_error = exc
            if attempt == retries - 1:
                break
            retry_after = exc.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                time.sleep(int(retry_after))
            elif exc.code == 429:
                time.sleep(15 * (attempt + 1))
            else:
                time.sleep(2**attempt)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == retries - 1:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"Could not fetch {url}") from last_error


def fetch_cached_text(url: str, path: Path, *, skip_fetch: bool) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    if skip_fetch:
        raise FileNotFoundError(f"Missing cached raw capture: {path}")
    text = request_text(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def fetch_rendered_html(page_title: str, path: Path, *, skip_fetch: bool) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    if skip_fetch:
        raise FileNotFoundError(f"Missing cached rendered HTML: {path}")
    params = urllib.parse.urlencode({"action": "parse", "page": page_title, "prop": "text", "format": "json"})
    html_text = request_text(f"https://en.wikisource.org/w/api.php?{params}")
    payload = json.loads(html_text)
    rendered_html = payload["parse"]["text"]["*"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered_html, encoding="utf-8")
    return rendered_html


def source_ids(section: dict[str, Any]) -> tuple[str, str]:
    target_suffix = section["target_source_suffix"]
    return (f"{section['section_id']}__{SOURCE_SUFFIX}", f"{section['section_id']}__{target_suffix}")


def section_paths(section: dict[str, Any]) -> dict[str, Path]:
    base_name = f"{WORK_ID}__{section['section_id']}"
    target_suffix = section["target_source_suffix"]
    paths = {
        "zh_raw": RAW_DIR / f"{base_name}__{SOURCE_SUFFIX}__raw.wikitext",
        "en_raw": (
            REPO_ROOT
            / Path(
                section["candidate_en_hocr_path"]
                if section["english_witness"] == "legge_hocr"
                else section["candidate_en_raw_path"]
            )
            if section["english_witness"] in {"legge_ocr_reviewed", "legge_hocr"}
            else RAW_DIR / f"{base_name}__{target_suffix}__raw.wikitext"
        ),
        "zh_base": CHINESE_DIR / f"{base_name}__{SOURCE_SUFFIX}__base.txt",
        "zh_segments": CHINESE_DIR / f"{base_name}__{SOURCE_SUFFIX}__segments.jsonl",
        "en_text": TRANSLATION_DIR / f"{base_name}__{target_suffix}__translation.txt",
        "en_segments": TRANSLATION_DIR / f"{base_name}__{target_suffix}__segments.jsonl",
        "alignments": ALIGNMENT_DIR / f"{base_name}__{SOURCE_SUFFIX}__{target_suffix}__alignments.jsonl",
    }
    if section["english_witness"] == "sbe_shih":
        paths["en_rendered"] = RAW_DIR / f"{base_name}__{target_suffix}__rendered.html"
    return paths


def url_for_page(base_url: str, page_title: str) -> str:
    encoded_title = urllib.parse.quote(page_title.replace(" ", "_"), safe="/():")
    return f"{base_url}/{encoded_title}"


def section_id_for_catalog_entry(entry: dict[str, Any]) -> str:
    if entry["sort_key"] == 1:
        return "guofeng-zhounan-001-guanju"
    division_code = MAJOR_DIVISION_CODES[entry["major_division"]]
    subdivision_code = SUBDIVISION_CODES[entry["subdivision"]]
    return f"{division_code}-{subdivision_code}-{entry['local_index']:03d}"


def legge_ocr_witness_for_entry(entry: dict[str, Any]) -> dict[str, str]:
    if entry["major_division"] == "國風":
        return {
            "candidate_en_page_url": FULL_TEXT_WITNESS_URL,
            "candidate_en_text_url": FULL_TEXT_WITNESS_GUTENBERG_URL,
            "candidate_en_ocr_url": LEGGE_SHEKING_1871_PART_1_OCR_URL,
            "candidate_en_hocr_url": LEGGE_SHEKING_1871_PART_1_HOCR_URL,
            "candidate_en_raw_path": str(LEGGE_SHEKING_1871_OCR_RAW_PATHS["part-1"]),
            "candidate_en_hocr_path": str(LEGGE_SHEKING_1871_HOCR_RAW_PATHS["part-1"]),
            "candidate_en_source_id": "legge-sbe-v3-1879-fulltext",
            "candidate_en_backup_page_url": LEGGE_SHEKING_1871_PART_1_ITEM_URL,
            "candidate_en_backup_source_id": "legge-sheking-1871-part-1-hocr",
        }
    return {
        "candidate_en_page_url": FULL_TEXT_WITNESS_URL,
        "candidate_en_text_url": FULL_TEXT_WITNESS_GUTENBERG_URL,
        "candidate_en_ocr_url": LEGGE_SHEKING_1871_PART_2_OCR_URL,
        "candidate_en_hocr_url": LEGGE_SHEKING_1871_PART_2_HOCR_URL,
        "candidate_en_raw_path": str(LEGGE_SHEKING_1871_OCR_RAW_PATHS["part-2"]),
        "candidate_en_hocr_path": str(LEGGE_SHEKING_1871_HOCR_RAW_PATHS["part-2"]),
        "candidate_en_source_id": "legge-sbe-v3-1879-fulltext",
        "candidate_en_backup_page_url": LEGGE_SHEKING_1871_PART_2_ITEM_URL,
        "candidate_en_backup_source_id": "legge-sheking-1871-part-2-hocr",
    }


def load_shijing_verification_index(*, skip_fetch: bool) -> dict[str, dict[str, Any]]:
    chinese_catalog = parse_chinese_catalog(skip_fetch=skip_fetch)
    verification_entries = load_shijing_verification_ledger()
    verification_index = build_verification_index(verification_entries)
    validate_verification_coverage(
        {section_id_for_catalog_entry(entry) for entry in chinese_catalog},
        verification_index,
    )
    return verification_index


def verification_annotation(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "verification_status": entry["verification_status"],
        "verification_decision": entry.get("decision", entry.get("verification_decision")),
        "chinese_source_status": entry["chinese_source_status"],
        "english_source_status": entry["english_source_status"],
        "source_volume": entry["source_volume"],
        "source_page_or_anchor": entry["source_page_or_anchor"],
        "raw_source_path": entry["raw_source_path"],
        "processed_translation_path": entry["processed_translation_path"],
        "reviewer_note": entry["reviewer_note"],
        "extraction_method": entry["extraction_method"],
        "remaining_warnings": entry["remaining_warnings"],
        "alignment_status": entry["alignment_status"],
        "alignment_granularity": entry["alignment_granularity"],
    }


def fetch_legge_ocr_sources(*, skip_fetch: bool) -> dict[str, str]:
    return {
        "part-1": fetch_cached_text(
            LEGGE_SHEKING_1871_PART_1_OCR_URL,
            REPO_ROOT / LEGGE_SHEKING_1871_OCR_RAW_PATHS["part-1"],
            skip_fetch=skip_fetch,
        ),
        "part-2": fetch_cached_text(
            LEGGE_SHEKING_1871_PART_2_OCR_URL,
            REPO_ROOT / LEGGE_SHEKING_1871_OCR_RAW_PATHS["part-2"],
            skip_fetch=skip_fetch,
        ),
    }


def fetch_legge_hocr_sources(*, skip_fetch: bool) -> dict[str, str]:
    return {
        "part-1": fetch_cached_text(
            LEGGE_SHEKING_1871_PART_1_HOCR_URL,
            REPO_ROOT / LEGGE_SHEKING_1871_HOCR_RAW_PATHS["part-1"],
            skip_fetch=skip_fetch,
        ),
        "part-2": fetch_cached_text(
            LEGGE_SHEKING_1871_PART_2_HOCR_URL,
            REPO_ROOT / LEGGE_SHEKING_1871_HOCR_RAW_PATHS["part-2"],
            skip_fetch=skip_fetch,
        ),
    }


def fetch_sbe_page_titles(*, skip_fetch: bool) -> list[str]:
    raw_catalog = fetch_cached_text(SBE_ALLPAGES_URL, SBE_CATALOG_PATH, skip_fetch=skip_fetch)
    payload = json.loads(raw_catalog)
    return sorted(page["title"] for page in payload["query"]["allpages"] if "/Ode " in page["title"])


def parse_chinese_catalog(*, skip_fetch: bool) -> list[dict[str, Any]]:
    raw_text = fetch_cached_text(page_to_raw_url(ZH_INDEX_URL), ZH_INDEX_RAW_PATH, skip_fetch=skip_fetch)
    entries: list[dict[str, Any]] = []
    major_division = ""
    collection = ""
    subdivision = ""
    subdivision_counts: dict[tuple[str, str], int] = {}
    sort_key = 0
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        major_match = re.fullmatch(r"==\s*([^=]+?)\s*==", line)
        if major_match:
            major_label = clean_wikitext(major_match.group(1)).strip()
            if major_label in {"周頌", "魯頌", "商頌"}:
                major_division = "頌"
                collection = major_label
                subdivision = major_label
            else:
                major_division = major_label
                collection = major_label
            continue
        subdivision_match = re.search(r"'''([^']+)'''", line)
        if subdivision_match:
            subdivision = clean_wikitext(subdivision_match.group(1)).strip()
            continue
        if not line.startswith("#"):
            continue
        link_match = re.search(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]", line)
        if not link_match:
            continue
        target = link_match.group(1)
        label = clean_wikitext(link_match.group(2) or target.split("/")[-1]).strip()
        if target.startswith("/"):
            page_title = f"詩經{target}"
        elif target.startswith("詩經/"):
            page_title = target
        else:
            page_title = f"詩經/{target}"
        sort_key += 1
        key = (major_division, subdivision)
        subdivision_counts[key] = subdivision_counts.get(key, 0) + 1
        entries.append(
            {
                "sort_key": sort_key,
                "major_division": major_division,
                "collection": collection,
                "subdivision": subdivision,
                "label": label,
                "page_title": page_title,
                "page_url": url_for_page("https://zh.wikisource.org/wiki", page_title),
                "local_index": subdivision_counts[key],
                "canonical_ref": f"詩經·{major_division}·{subdivision}·{subdivision_counts[key]:03d}",
                "zh_section_heading": f"{major_division}‧{subdivision}‧{label}",
            }
        )
    return entries


def map_sbe_page_title(title: str, chinese_catalog: list[dict[str, Any]]) -> dict[str, Any]:
    guofeng_books = []
    xiaoya = []
    daya = []
    zhousong = []
    lusong = []
    shangsong = []
    current_subdivision = None
    current_book: list[dict[str, Any]] = []
    for poem in chinese_catalog:
        if poem["major_division"] == "國風":
            if poem["subdivision"] != current_subdivision:
                if current_book:
                    guofeng_books.append(current_book)
                current_book = []
                current_subdivision = poem["subdivision"]
            current_book.append(poem)
        elif poem["major_division"] == "小雅":
            xiaoya.append(poem)
        elif poem["major_division"] == "大雅":
            daya.append(poem)
        elif poem["collection"] == "周頌":
            zhousong.append(poem)
        elif poem["collection"] == "魯頌":
            lusong.append(poem)
        elif poem["collection"] == "商頌":
            shangsong.append(poem)
    if current_book:
        guofeng_books.append(current_book)

    states_match = re.search(r"Lessons from the States/Book (\d+)/Ode (\d+)", title)
    if states_match:
        book_index = int(states_match.group(1)) - 1
        ode_index = int(states_match.group(2)) - 1
        return guofeng_books[book_index][ode_index]

    xiaoya_match = re.search(r"The Minor Odes of the Kingdom/Decade (\d+)/Ode (\d+)", title)
    if xiaoya_match:
        absolute_index = (int(xiaoya_match.group(1)) - 1) * 10 + int(xiaoya_match.group(2)) - 1
        return xiaoya[absolute_index]

    daya_match = re.search(r"The Major Odes of the Kingdom/Decade (\d+)/Ode (\d+)", title)
    if daya_match:
        absolute_index = (int(daya_match.group(1)) - 1) * 10 + int(daya_match.group(2)) - 1
        return daya[absolute_index]

    zhousong_match = re.search(
        r"Odes of the Temple and the Altar/The Sacrificial Odes of Kâu/Decade (\d+)/Ode (\d+)",
        title,
    )
    if zhousong_match:
        absolute_index = (int(zhousong_match.group(1)) - 1) * 10 + int(zhousong_match.group(2)) - 1
        return zhousong[absolute_index]

    lusong_match = re.search(r"Odes of the Temple and the Altar/The Praise Odes of Lû/Ode (\d+)", title)
    if lusong_match:
        return lusong[int(lusong_match.group(1)) - 1]

    shangsong_match = re.search(
        r"Odes of the Temple and the Altar/The Sacrificial Odes of Shang/Ode (\d+)",
        title,
    )
    if shangsong_match:
        return shangsong[int(shangsong_match.group(1)) - 1]

    raise ValueError(f"Could not map SBE page title: {title}")


def build_section_seed(poem: dict[str, Any], *, en_page_title: str, english_witness: str) -> dict[str, Any]:
    witness_meta = shijing_witness_metadata(english_witness)
    if poem["sort_key"] == 1 and english_witness == "standalone_sheking":
        return dict(SECTION_CATALOG[0])
    if english_witness == "legge_hocr":
        witness = legge_ocr_witness_for_entry(poem)
        return {
            "section_id": section_id_for_catalog_entry(poem),
            "label": poem["label"],
            "canonical_ref": poem["canonical_ref"],
            "sort_key": poem["sort_key"],
            "major_division": poem["major_division"],
            "subdivision": poem["subdivision"],
            "poem_number": poem["local_index"],
            "legge_section_alias": poem["label"],
            "zh_page_url": poem["page_url"],
            "zh_section_heading": poem["zh_section_heading"],
            "en_page_url": witness["candidate_en_backup_page_url"],
            "en_page_title": en_page_title,
            "target_source_suffix": HOCR_TARGET_SOURCE_SUFFIX,
            "english_witness": english_witness,
            **witness_meta,
            **witness,
            "force_poem_alignment": True,
            "reviewed_ocr_notes": (
                "Poem-level fallback from generalized Legge 1871 Internet Archive hOCR extraction; "
                "translation lines are parsed conservatively from OCR layout, so stanza-level exact "
                "alignment is only retained when a safe block match is available."
            ),
        }
    if english_witness == "legge_ocr_reviewed":
        witness = legge_ocr_witness_for_entry(poem)
        reviewed = REVIEWED_LEGGE_OCR_POEM_BLOCKS[poem["sort_key"]]
        return {
            "section_id": section_id_for_catalog_entry(poem),
            "label": poem["label"],
            "canonical_ref": poem["canonical_ref"],
            "sort_key": poem["sort_key"],
            "major_division": poem["major_division"],
            "subdivision": poem["subdivision"],
            "poem_number": poem["local_index"],
            "legge_section_alias": reviewed["legge_section_alias"],
            "zh_page_url": poem["page_url"],
            "zh_section_heading": poem["zh_section_heading"],
            "en_page_url": witness["candidate_en_backup_page_url"],
            "en_page_title": en_page_title,
            "target_source_suffix": OCR_TARGET_SOURCE_SUFFIX,
            "english_witness": english_witness,
            **witness_meta,
            "candidate_en_page_url": witness["candidate_en_page_url"],
            "candidate_en_text_url": witness["candidate_en_text_url"],
            "candidate_en_ocr_url": witness["candidate_en_ocr_url"],
            "candidate_en_raw_path": witness["candidate_en_raw_path"],
            "candidate_en_source_id": witness["candidate_en_source_id"],
            "candidate_en_backup_page_url": witness["candidate_en_backup_page_url"],
            "candidate_en_backup_source_id": witness["candidate_en_backup_source_id"],
            "reviewed_english_blocks": reviewed["english_blocks"],
            "force_poem_alignment": True,
            "review_note": reviewed.get("review_note"),
            "reviewed_ocr_notes": (
                "Poem-level fallback from reviewed Legge 1871 Internet Archive OCR extraction; "
                "stanza breaks are preserved in the cleaned translation text, but the alignment stays "
                "at poem scope until stanza-level OCR cleanup is safer."
            ),
        }
    section_id = (
        f"{MAJOR_DIVISION_CODES[poem['major_division']]}-"
        f"{SUBDIVISION_CODES[poem['subdivision']]}-"
        f"{poem['local_index']:03d}"
    )
    target_suffix = STANDALONE_TARGET_SOURCE_SUFFIX if english_witness == "standalone_sheking" else SBE_TARGET_SOURCE_SUFFIX
    en_page_url = (
        "https://en.wikisource.org/wiki/Guan_ju"
        if english_witness == "standalone_sheking"
        else url_for_page("https://en.wikisource.org/wiki", en_page_title)
    )
    return {
        "section_id": section_id,
        "label": poem["label"],
        "canonical_ref": poem["canonical_ref"],
        "sort_key": poem["sort_key"],
        "major_division": poem["major_division"],
        "subdivision": poem["subdivision"],
        "poem_number": poem["local_index"],
        "legge_section_alias": poem["label"],
        "zh_page_url": poem["page_url"],
        "zh_section_heading": poem["zh_section_heading"],
        "en_page_url": en_page_url,
        "en_page_title": en_page_title,
        "target_source_suffix": target_suffix,
        "english_witness": english_witness,
        **witness_meta,
    }


def build_section_catalog(
    *,
    skip_fetch: bool,
    verification_index: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    chinese_catalog = parse_chinese_catalog(skip_fetch=skip_fetch)
    mapped_sections = []
    seen_sort_keys = set()
    first_section = dict(SECTION_CATALOG[0])
    if verification_index is None or verification_entry_is_exportable(verification_index[first_section["section_id"]]):
        mapped_sections.append(first_section)
    seen_sort_keys.add(1)
    for page_title in fetch_sbe_page_titles(skip_fetch=skip_fetch):
        poem = map_sbe_page_title(page_title, chinese_catalog)
        if poem["sort_key"] in seen_sort_keys:
            continue
        section_seed = build_section_seed(poem, en_page_title=page_title, english_witness="sbe_shih")
        if verification_index is not None and not verification_entry_is_exportable(
            verification_index[section_seed["section_id"]]
        ):
            seen_sort_keys.add(poem["sort_key"])
            continue
        mapped_sections.append(section_seed)
        seen_sort_keys.add(poem["sort_key"])
    for poem in chinese_catalog:
        if (
            poem["sort_key"] in seen_sort_keys
            or poem["sort_key"] in TITLE_ONLY_SORT_KEYS
            or poem["sort_key"] in EXTRACTION_FAILED_METADATA_ONLY_SORT_KEYS
        ):
            continue
        english_witness = "legge_ocr_reviewed" if poem["sort_key"] in REVIEWED_LEGGE_OCR_POEM_BLOCKS else "legge_hocr"
        section_seed = build_section_seed(
            poem,
            en_page_title="James Legge, The She King (1871 hOCR fallback)",
            english_witness=english_witness,
        )
        if verification_index is not None and not verification_entry_is_exportable(verification_index[section_seed["section_id"]]):
            seen_sort_keys.add(poem["sort_key"])
            continue
        mapped_sections.append(section_seed)
        seen_sort_keys.add(poem["sort_key"])
    mapped_sections.sort(key=lambda section: section["sort_key"])
    return mapped_sections


def build_canonical_section_inventory(
    complete_sections: list[dict[str, Any]],
    *,
    skip_fetch: bool,
    verification_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    chinese_catalog = parse_chinese_catalog(skip_fetch=skip_fetch)
    complete_by_sort_key = {section["sort_key"]: section for section in complete_sections}
    inventory: list[dict[str, Any]] = []
    for entry in chinese_catalog:
        section_id = complete_by_sort_key.get(entry["sort_key"], {}).get("section_id", section_id_for_catalog_entry(entry))
        verification = verification_index[section_id]
        zh_page_url = url_for_page("https://zh.wikisource.org/wiki", entry["page_title"])
        if entry["sort_key"] in TITLE_ONLY_SORT_KEYS:
            inventory.append(
                {
                    "global_sort_key": entry["sort_key"],
                    "major_division": entry["major_division"],
                    "subdivision": entry["subdivision"],
                    "local_poem_number": entry["local_index"],
                    "title": entry["label"],
                    "canonical_ref": entry["canonical_ref"],
                    "section_id": section_id,
                    "zh_page_url": zh_page_url,
                    "status": "missing_chinese_source",
                    "coverage_status": "title_only_lost_text",
                    "english_witness_type": "not_applicable",
                    "english_witness_status": "not_applicable",
                    "source_witness_type": "not_applicable",
                    "needs_human_text_review": False,
                    **verification_annotation(verification),
                }
            )
            continue
        if entry["sort_key"] in complete_by_sort_key:
            complete_section = complete_by_sort_key[entry["sort_key"]]
            inventory.append(
                {
                    "global_sort_key": entry["sort_key"],
                    "major_division": entry["major_division"],
                    "subdivision": entry["subdivision"],
                    "local_poem_number": entry["local_index"],
                    "title": entry["label"],
                    "canonical_ref": entry["canonical_ref"],
                    "section_id": section_id,
                    "zh_page_url": zh_page_url,
                    "en_page_url": complete_section["en_page_url"],
                    "english_witness": complete_section["english_witness"],
                    "status": "complete",
                    "coverage_status": "complete",
                    "english_witness_type": complete_section["english_witness_type"],
                    "english_witness_status": complete_section["english_witness_status"],
                    "source_witness_type": complete_section["source_witness_type"],
                    "needs_human_text_review": complete_section["needs_human_text_review"],
                    **verification_annotation(verification),
                }
            )
            continue
        english_witness = "legge_ocr_failed" if entry["sort_key"] in EXTRACTION_FAILED_METADATA_ONLY_SORT_KEYS else "legge_hocr"
        witness_meta = shijing_witness_metadata(english_witness)
        coverage_status = (
            "public_domain_translation_witness_not_safely_extractable"
            if verification["decision"] == "do_not_export_until_repaired"
            else "public_domain_text_witness_available"
        )
        inventory.append(
            {
                "global_sort_key": entry["sort_key"],
                "major_division": entry["major_division"],
                "subdivision": entry["subdivision"],
                "local_poem_number": entry["local_index"],
                "title": entry["label"],
                "canonical_ref": entry["canonical_ref"],
                "section_id": section_id,
                "zh_page_url": zh_page_url,
                **legge_ocr_witness_for_entry(entry),
                "english_witness": english_witness,
                "status": "needs_text_repair",
                "coverage_status": coverage_status,
                "english_witness_type": witness_meta["english_witness_type"],
                "english_witness_status": witness_meta["english_witness_status"],
                "source_witness_type": witness_meta["source_witness_type"],
                "needs_human_text_review": True,
                "notes": (
                    "Legge witness located, but this poem is non-exportable until the English text is verified against source "
                    "and cleaned of OCR/layout contamination."
                ),
                **verification_annotation(verification),
            }
        )
    return inventory


def extract_poem_markup(raw_text: str) -> str:
    onlyinclude_match = re.search(r"<onlyinclude>(.*)</onlyinclude>", raw_text, flags=re.S)
    working = onlyinclude_match.group(1) if onlyinclude_match else raw_text
    poem_match = re.search(r"<poem[^>]*>(.*?)</poem>", working, flags=re.S)
    if not poem_match:
        raise ValueError("Could not find <poem> block in raw page.")
    return poem_match.group(1)


def clean_poem_blocks(poem_markup: str) -> list[str]:
    blocks: list[list[str]] = []
    current_block: list[str] = []
    for raw_line in poem_markup.splitlines():
        line = raw_line.strip()
        if line.startswith(":"):
            line = line[1:].strip()
        cleaned = clean_wikitext(line).strip()
        if not cleaned:
            if current_block:
                blocks.append(current_block)
                current_block = []
            continue
        current_block.append(cleaned)
    if current_block:
        blocks.append(current_block)
    return ["\n".join(block) for block in blocks]


def extract_named_wikitext_section(raw_text: str, heading: str) -> str:
    lines = raw_text.splitlines()
    heading_regex = re.compile(rf"^(=+)\s*{re.escape(heading)}\s*\1\s*$")
    start_index = None
    heading_level = None
    for index, line in enumerate(lines):
        match = heading_regex.match(line.strip())
        if match:
            start_index = index + 1
            heading_level = len(match.group(1))
            break
    if start_index is None:
        return raw_text
    section_lines: list[str] = []
    for line in lines[start_index:]:
        stripped = line.strip()
        heading_match = re.match(r"^(=+)\s*[^=].*?\s*\1\s*$", stripped)
        if heading_match and heading_level is not None and len(heading_match.group(1)) <= heading_level:
            break
        section_lines.append(line)
    return "\n".join(section_lines)


def extract_chinese_poem_blocks(raw_text: str, section: dict[str, Any]) -> list[str]:
    section_text = extract_named_wikitext_section(raw_text, section["zh_section_heading"])
    if "<poem" in section_text:
        try:
            return clean_poem_blocks(extract_poem_markup(section_text))
        except ValueError:
            pass
    blocks: list[list[str]] = []
    current_block: list[str] = []
    for raw_line in section_text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith(":"):
            cleaned = clean_wikitext(stripped.lstrip(":").strip()).strip()
            if not cleaned:
                if current_block:
                    blocks.append(current_block)
                    current_block = []
                continue
            if cleaned.startswith("《") and cleaned.endswith("句。"):
                continue
            current_block.append(cleaned)
        elif not stripped and current_block:
            blocks.append(current_block)
            current_block = []
    if current_block:
        blocks.append(current_block)
    cleaned_blocks = ["\n".join(block) for block in blocks if block]
    if not cleaned_blocks:
        fallback_lines = []
        for raw_line in section_text.splitlines():
            cleaned = clean_wikitext(raw_line.strip().lstrip(":")).strip()
            if cleaned and re.search(r"[\u3400-\u9fff]", cleaned):
                fallback_lines.append(cleaned)
        if fallback_lines:
            return ["\n".join(fallback_lines)]
        raise ValueError(f"Could not extract Chinese stanza blocks for {section['section_id']}")
    return cleaned_blocks


def normalize_english_line(line: str) -> str:
    normalized = html.unescape(line)
    normalized = normalized.replace("\xa0", " ")
    normalized = re.sub(r"\[\s*\d+\s*\]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def normalize_transliteration_spacing(text: str) -> str:
    tokens = text.split()
    if not tokens:
        return ""
    combined: list[str] = []
    current = tokens[0]
    for token in tokens[1:]:
        if len(current) <= 2 and len(token) <= 2 and re.search(r"[A-Za-zÀ-ÿ]", current) and re.search(r"[A-Za-zÀ-ÿ]", token):
            current += token
            continue
        combined.append(current)
        current = token
    combined.append(current)
    return " ".join(combined)


HOCR_NS = {"x": "http://www.w3.org/1999/xhtml"}
PART1_BOOK_START_PAGES = {
    "周南": 203,
    "召南": 222,
    "邶風": 240,
    "鄘風": 275,
    "衛風": 293,
    "王風": 312,
    "鄭風": 326,
    "齊風": 352,
    "魏風": 365,
    "唐風": 376,
    "秦風": 392,
    "陳風": 407,
    "檜風": 417,
    "曹風": 422,
    "豳風": 428,
}
PART2_BOOK_START_PAGES = {
    "鹿鳴之什": 9,
    "南有嘉魚之什": 32,
    "鴻雁之什": 42,
    "節南山之什": 62,
    "谷風之什": 94,
    "甫田之什": 124,
    "魚藻之什": 150,
    "都人士之什": 173,
    "文王之什": 191,
    "生民之什": 229,
    "蕩之什": 269,
    "清廟之什": 333,
    "臣工之什": 346,
    "閔予小子之什": 360,
    "魯頌": 375,
    "商頌": 395,
}
PART2_BOOK_START_SEQUENCE = [9, 32, 42, 62, 94, 124, 150, 173, 191, 229, 269, 333, 346, 360, 375, 395]
PART2_BOOK_COUNTS = [10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 11, 10, 10, 11, 4, 5]
PART1_LINE_OVERRIDES: dict[tuple[str, int], tuple[int, int]] = {
    ("周南", 1): (203, 4),
    ("周南", 5): (210, 4),
    ("周南", 9): (218, 4),
    ("召南", 2): (224, 4),
    ("邶風", 8): (253, 15),
    ("衛風", 3): (296, 4),
    ("齊風", 1): (352, 4),
    ("魏風", 3): (367, 4),
    ("魏風", 7): (373, 1),
    ("秦風", 1): (392, 2),
    ("陳風", 9): (415, 52),
    ("曹風", 4): (426, 12),
    ("豳風", 2): (435, 1),
}
PART2_LINE_OVERRIDES: dict[tuple[str, int], tuple[int, int]] = {}
TITLE_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "my",
    "your",
    "their",
    "his",
    "her",
    "our",
    "i",
    "we",
    "you",
    "they",
    "is",
    "are",
    "was",
    "were",
    "be",
    "not",
    "but",
    "have",
    "has",
    "had",
    "will",
    "shall",
    "all",
    "there",
    "those",
    "these",
    "this",
    "that",
    "what",
    "how",
    "who",
    "whom",
    "where",
    "when",
    "why",
    "which",
}
TITLE_LINE_RE = re.compile(r"^(?:ODE\s+)?([A-Za-z0-9IVXLCDM ]{1,8})[\.:]\s+(.+)$", re.I)
ROMAN_VALUE = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def parse_hocr_bbox(title: str) -> tuple[int, int, int, int]:
    match = re.search(r"bbox\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", title)
    if not match:
        return (0, 0, 0, 0)
    return tuple(int(match.group(index)) for index in range(1, 5))


def roman_to_int(token: str) -> int | None:
    if not token:
        return None
    total = 0
    previous = 0
    for char in reversed(token):
        value = ROMAN_VALUE.get(char)
        if value is None:
            return None
        if value < previous:
            total -= value
        else:
            total += value
            previous = value
    return total


def parse_hocr_numeral(token: str) -> int | None:
    normalized = re.sub(r"[^A-Za-z0-9]", "", token).upper()
    if not normalized:
        return None
    if normalized.isdigit():
        return int(normalized)
    normalized = normalized.replace("J", "I").replace("Y", "V")
    explicit_fixes = {
        "L": "I",
        "H": "III",
        "HI": "III",
        "HN": "III",
        "IY": "IV",
        "VN": "VII",
        "VNI": "VII",
        "VIL": "VII",
        "VIIL": "VIII",
    }
    normalized = explicit_fixes.get(normalized, normalized)
    if normalized.endswith("L") and set(normalized) <= {"V", "I", "L"}:
        normalized = normalized.replace("L", "I")
    return roman_to_int(normalized)


def adjust_hocr_number(number: int | None, token: str, expected_count: int) -> int | None:
    if number is None:
        return None
    compact = re.sub(r"[^A-Za-z0-9]", "", token).upper()
    if compact in {"L", "I"}:
        return 1
    if "VN" in compact:
        return 7
    if number > expected_count and number - 10 >= 1:
        return number - 10
    if number == 50:
        return 1
    return number if 1 <= number <= expected_count else None


def looks_like_hocr_title(text: str) -> bool:
    if text.startswith(("Bk. ", "BOOK ", "PART ", "THE SHE KING", "THE BOOK OF POETRY")):
        return False
    match = TITLE_LINE_RE.match(text)
    if not match:
        return False
    rest = match.group(2).strip()
    if any(character in rest for character in [",", ";", "?", "!", "—", "[", "]"]):
        return False
    tokens = [token for token in re.split(r"\s+", re.sub(r"[^A-Za-z'‘’`-]+", " ", rest.replace("^", " "))) if token]
    if not tokens or len(tokens) > 7 or len(" ".join(tokens)) > 45:
        return False
    stopword_count = sum(1 for token in tokens if token.lower() in TITLE_STOPWORDS)
    return stopword_count <= 1


@functools.lru_cache(maxsize=2)
def load_hocr_pages(part: str) -> dict[int, list[dict[str, Any]]]:
    path = REPO_ROOT / LEGGE_SHEKING_1871_HOCR_RAW_PATHS[part]
    pages: dict[int, list[dict[str, Any]]] = {}
    current_page: int | None = None
    current_lines: list[dict[str, Any]] = []
    for event, elem in ET.iterparse(path, events=("start", "end")):
        if event == "start" and elem.tag.endswith("div") and elem.attrib.get("class") == "ocr_page":
            if current_page is not None:
                pages[current_page] = current_lines
            current_page = int(elem.attrib["id"].split("_")[-1])
            current_lines = []
            continue
        if event != "end" or not elem.tag.endswith("span") or elem.attrib.get("class") != "ocr_line":
            continue
        title = elem.attrib.get("title", "")
        fsize_match = re.search(r"x_fsize\s+([0-9.]+)", title)
        fsize = float(fsize_match.group(1)) if fsize_match else 0.0
        words = ["".join(word.itertext()) for word in elem.findall('.//x:span[@class="ocrx_word"]', HOCR_NS)]
        text = normalize_english_line(" ".join(words))
        if text:
            x0, y0, x1, y1 = parse_hocr_bbox(title)
            current_lines.append(
                {
                    "text": text,
                    "fsize": fsize,
                    "bbox": (x0, y0, x1, y1),
                    "has_latin": bool(re.search(r"[A-Za-z]", text)),
                    "has_chinese": bool(re.search(r"[\u3400-\u9fff]", text)),
                }
            )
        elem.clear()
    if current_page is not None:
        pages[current_page] = current_lines
    return pages


def iter_hocr_title_candidates(part: str) -> list[dict[str, Any]]:
    pages = load_hocr_pages(part)
    candidates: list[dict[str, Any]] = []
    for page_number, lines in sorted(pages.items()):
        for line_index, line in enumerate(lines):
            if not 8.5 <= line["fsize"] <= 14.5:
                continue
            if not looks_like_hocr_title(line["text"]):
                continue
            following = lines[line_index + 1 : line_index + 10]
            if not any(candidate["fsize"] >= 18 for candidate in following):
                continue
            match = TITLE_LINE_RE.match(line["text"])
            if match is None:
                continue
            candidates.append(
                {
                    "page": page_number,
                    "line_index": line_index,
                    "raw_number": parse_hocr_numeral(match.group(1)),
                    "number_token": match.group(1),
                    "title": normalize_transliteration_spacing(match.group(2).strip()),
                }
            )
    return candidates


def hocr_book_starts(part: str) -> dict[str, int]:
    return PART1_BOOK_START_PAGES if part == "part-1" else PART2_BOOK_START_PAGES


def hocr_line_overrides(part: str) -> dict[tuple[str, int], tuple[int, int]]:
    return PART1_LINE_OVERRIDES if part == "part-1" else PART2_LINE_OVERRIDES


@functools.lru_cache(maxsize=1)
def compute_hocr_section_map() -> dict[int, dict[str, Any]]:
    chinese_catalog = parse_chinese_catalog(skip_fetch=True)
    section_map: dict[int, dict[str, Any]] = {}
    book_starts = hocr_book_starts("part-1")
    ordered_books = list(book_starts.items())
    candidates = iter_hocr_title_candidates("part-1")
    overrides = hocr_line_overrides("part-1")
    for book_index, (subdivision, start_page) in enumerate(ordered_books):
        end_page = ordered_books[book_index + 1][1] if book_index + 1 < len(ordered_books) else 9999
        subdivision_entries = [entry for entry in chinese_catalog if entry["subdivision"] == subdivision]
        book_entries = [entry for entry in subdivision_entries if entry["sort_key"] not in TITLE_ONLY_SORT_KEYS]
        if not subdivision_entries or not book_entries:
            continue
        expected_count = max(entry["local_index"] for entry in subdivision_entries)
        candidate_map: dict[int, dict[str, Any]] = {}
        for candidate in candidates:
            if not start_page <= candidate["page"] < end_page:
                continue
            number = adjust_hocr_number(candidate["raw_number"], candidate["number_token"], expected_count)
            if number is None or number in candidate_map:
                continue
            candidate_map[number] = {**candidate, "number": number}
        selected: list[dict[str, Any]] = []
        for entry in book_entries:
            poem_number = entry["local_index"]
            override = overrides.get((subdivision, poem_number))
            if override is not None:
                page_number, line_index = override
                candidate = {
                    "page": page_number,
                    "line_index": line_index,
                    "number": poem_number,
                    "title": entry["label"],
                }
            else:
                candidate = candidate_map.get(poem_number)
            if candidate is None:
                raise ValueError(f"Could not derive hOCR boundary for {subdivision} ode {poem_number}")
            selected.append({**candidate, "sort_key": entry["sort_key"], "subdivision": subdivision})
        for item_index, item in enumerate(selected):
            next_item = selected[item_index + 1] if item_index + 1 < len(selected) else {"page": end_page, "line_index": 0}
            section_map[item["sort_key"]] = {
                "part": "part-1",
                "start_page": item["page"],
                "start_line_index": item["line_index"],
                "end_page": next_item["page"],
                "end_line_index": next_item["line_index"],
                "legge_section_alias": item["title"] or item["subdivision"],
            }

    part2_entries = [entry for entry in chinese_catalog if entry["major_division"] != "國風"]
    part2_candidates = iter_hocr_title_candidates("part-2")
    cursor = 0
    ordered_positions: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for book_index, start_page in enumerate(PART2_BOOK_START_SEQUENCE):
        end_page = PART2_BOOK_START_SEQUENCE[book_index + 1] if book_index + 1 < len(PART2_BOOK_START_SEQUENCE) else 9999
        book_count = PART2_BOOK_COUNTS[book_index]
        book_entries = part2_entries[cursor : cursor + book_count]
        cursor += book_count
        candidate_map: dict[int, dict[str, Any]] = {}
        for candidate in part2_candidates:
            if not start_page <= candidate["page"] < end_page:
                continue
            number = adjust_hocr_number(candidate["raw_number"], candidate["number_token"], book_count)
            if number is None or number in candidate_map:
                continue
            candidate_map[number] = {**candidate, "number": number}
        for position, entry in enumerate(book_entries, start=1):
            candidate = candidate_map.get(position)
            if candidate is None and entry["sort_key"] in TITLE_ONLY_SORT_KEYS:
                continue
            if candidate is None:
                candidate = interpolate_hocr_position(
                    position,
                    known_positions=candidate_map,
                    start_page=start_page,
                    end_page=end_page,
                    book_count=book_count,
                )
            ordered_positions.append((entry, candidate))
    for item_index, (entry, item) in enumerate(ordered_positions):
        if entry["sort_key"] in TITLE_ONLY_SORT_KEYS:
            continue
        next_item = ordered_positions[item_index + 1][1] if item_index + 1 < len(ordered_positions) else {"page": 9999, "line_index": 0}
        section_map[entry["sort_key"]] = {
            "part": "part-2",
            "start_page": item["page"],
            "start_line_index": item["line_index"],
            "end_page": next_item["page"],
            "end_line_index": next_item["line_index"],
            "legge_section_alias": item["title"] or entry["label"],
        }
    return section_map


def line_in_hocr_range(
    page_number: int,
    line_index: int,
    *,
    start_page: int,
    start_line_index: int,
    end_page: int,
    end_line_index: int,
) -> bool:
    if page_number < start_page or page_number > end_page:
        return False
    if page_number == start_page and line_index < start_line_index:
        return False
    if page_number == end_page and line_index >= end_line_index:
        return False
    return page_number < end_page or end_line_index > 0


def looks_like_commentary_line(text: str) -> bool:
    lower = text.lower()
    commentary_markers = (
        "ode ",
        "st. ",
        "bk. ",
        "book ",
        "narrative.",
        "the title",
        "choo",
        "maou",
        "tso-",
        "preface",
    )
    return any(marker in lower for marker in commentary_markers) or (len(text.split()) > 12 and "," in text)


def looks_like_hocr_verse_line(text: str, fsize: float) -> bool:
    if not 8.0 <= fsize <= 14.5:
        return False
    if text.startswith(("BOOK ", "Bk. ", "PART ", "THE SHE KING")):
        return False
    letters = re.sub(r"[^A-Za-z]", "", text)
    if len(letters) < 5:
        return False
    tokens = re.findall(r"[A-Za-z]+", text)
    if len(tokens) < 2 or max(len(token) for token in tokens) < 3:
        return False
    vowel_tokens = sum(1 for token in tokens if re.search(r"[AEIOUYaeiouy]", token))
    if vowel_tokens / len(tokens) < 0.5:
        return False
    if len(letters) / max(len(text), 1) < 0.45:
        return False
    return not looks_like_commentary_line(text)


def interpolate_hocr_position(
    position: int,
    *,
    known_positions: dict[int, dict[str, Any]],
    start_page: int,
    end_page: int,
    book_count: int,
) -> dict[str, Any]:
    lower_positions = [index for index in known_positions if index < position]
    upper_positions = [index for index in known_positions if index > position]
    lower = max(lower_positions) if lower_positions else None
    upper = min(upper_positions) if upper_positions else None
    if lower is not None and upper is not None:
        lower_item = known_positions[lower]
        upper_item = known_positions[upper]
        span = upper - lower
        offset = position - lower
        page = round(lower_item["page"] + (upper_item["page"] - lower_item["page"]) * (offset / span))
        if page == lower_item["page"] == upper_item["page"]:
            line_index = round(lower_item["line_index"] + (upper_item["line_index"] - lower_item["line_index"]) * (offset / span))
        else:
            line_index = offset
        return {"page": page, "line_index": max(0, line_index), "title": ""}
    if upper is not None:
        upper_item = known_positions[upper]
        page = round(start_page + (upper_item["page"] - start_page) * (position / upper))
        return {"page": page, "line_index": position, "title": ""}
    if lower is not None:
        lower_item = known_positions[lower]
        remaining_slots = book_count + 1 - lower
        page = round(lower_item["page"] + (end_page - lower_item["page"]) * ((position - lower) / remaining_slots))
        return {"page": page, "line_index": position, "title": ""}
    return {"page": start_page, "line_index": position, "title": ""}


def extract_hocr_poem_blocks(section: dict[str, Any]) -> tuple[list[str], str]:
    hocr_section = compute_hocr_section_map()[section["sort_key"]]
    pages = load_hocr_pages(hocr_section["part"])
    verse_lines: list[str] = []
    current_block: list[str] = []
    title_seen = False
    for page_number in range(hocr_section["start_page"], hocr_section["end_page"] + 1):
        for line_index, line in enumerate(pages.get(page_number, [])):
            if not line_in_hocr_range(
                page_number,
                line_index,
                start_page=hocr_section["start_page"],
                start_line_index=hocr_section["start_line_index"],
                end_page=hocr_section["end_page"],
                end_line_index=hocr_section["end_line_index"],
            ):
                continue
            text = normalize_english_line(line["text"])
            if not text:
                continue
            if not title_seen:
                title_seen = True
                continue
            if line["has_chinese"]:
                continue
            if not line["has_latin"]:
                continue
            if not looks_like_hocr_verse_line(text, line["fsize"]):
                continue
            if re.match(r"^\d+\s+", text) and current_block:
                verse_lines.append("\n".join(current_block))
                current_block = []
            current_block.append(text)
    if current_block:
        verse_lines.append("\n".join(current_block))
    cleaned = [block for block in verse_lines if block.strip()]
    if not cleaned:
        fallback_lines: list[str] = []
        title_seen = False
        for page_number in range(hocr_section["start_page"], hocr_section["end_page"] + 1):
            for line_index, line in enumerate(pages.get(page_number, [])):
                if not line_in_hocr_range(
                    page_number,
                    line_index,
                    start_page=hocr_section["start_page"],
                    start_line_index=hocr_section["start_line_index"],
                    end_page=hocr_section["end_page"],
                    end_line_index=hocr_section["end_line_index"],
                ):
                    continue
                text = normalize_english_line(line["text"])
                if not text:
                    continue
                if not title_seen:
                    title_seen = True
                    continue
                if line["has_latin"] and 6.0 <= line["fsize"] <= 16.0 and not text.startswith(("BOOK ", "Bk. ", "PART ")):
                    fallback_lines.append(text)
        cleaned = ["\n".join(fallback_lines)] if fallback_lines else [section["label"]]
    return cleaned, hocr_section["legge_section_alias"]


def extract_rendered_text_lines(rendered_html: str) -> list[str]:
    stripped = re.sub(r"<style.*?</style>", " ", rendered_html, flags=re.S)
    stripped = re.sub(r"<sup.*?</sup>", " ", stripped, flags=re.S)
    stripped = re.sub(r"<br ?/?>", "\n", stripped)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    lines = [normalize_english_line(line) for line in stripped.splitlines()]
    return [line for line in lines if line]


def extract_sbe_poem_blocks(rendered_html: str) -> list[str]:
    extractor = BlockCenterExtractor()
    extractor.feed(rendered_html)
    if not extractor.blocks:
        raise ValueError("Could not find a rendered Shijing poem block.")
    best_block = max(extractor.blocks, key=lambda paragraphs: sum(len(paragraph.splitlines()) for paragraph in paragraphs))
    return [paragraph for paragraph in best_block if paragraph]


def extract_english_poem_blocks(
    section: dict[str, Any],
    *,
    raw_text: str,
    rendered_html: str | None,
) -> tuple[list[str], str, str | None, str | None]:
    if section["english_witness"] == "standalone_sheking":
        return extract_english_poem_blocks_from_raw(raw_text), section["legge_section_alias"], section.get("pinyin_alias"), None
    if section["english_witness"] == "legge_hocr":
        blocks, legge_title = extract_hocr_poem_blocks(section)
        return blocks, legge_title, section.get("pinyin_alias"), None
    if section["english_witness"] == "legge_ocr_reviewed":
        return list(section["reviewed_english_blocks"]), section["legge_section_alias"], section.get("pinyin_alias"), None
    if rendered_html is None:
        raise ValueError(f"Missing rendered HTML for SBE witness {section['section_id']}")
    lines = extract_rendered_text_lines(rendered_html)
    heading_line = next((line for line in lines if line.startswith("Ode ")), "")
    title_match = re.match(r"^Ode\s+\d+(?:,\s*([^\.]+))?\.\s*(.*?)\.\s*$", heading_line)
    selection_text = title_match.group(1).strip() if title_match and title_match.group(1) else None
    legge_title = normalize_transliteration_spacing(title_match.group(2).strip()) if title_match else section["label"]
    pinyin_match = next(
        (
            re.match(rf"^(.+?)\s*\(\s*{re.escape(section['label'])}\s*\)\s+corresponds to", line)
            for line in lines
            if f"({section['label']})" in line or f"( {section['label']} )" in line
        ),
        None,
    )
    pinyin_alias = pinyin_match.group(1).strip() if pinyin_match else None
    return extract_sbe_poem_blocks(rendered_html), legge_title, pinyin_alias, selection_text


def extract_english_poem_blocks_from_raw(raw_text: str) -> list[str]:
    poem_matches = re.findall(r"<poem[^>]*>(.*?)</poem>", raw_text, flags=re.S)
    for poem_markup in poem_matches:
        blocks = clean_poem_blocks(poem_markup)
        if blocks:
            return blocks
    raise ValueError("Could not find an English <poem> block with content.")


def poem_lines(blocks: list[str]) -> list[str]:
    return [line for block in blocks for line in block.splitlines() if line.strip()]


def chunk_lines(lines: list[str], chunk_size: int) -> list[str]:
    return ["\n".join(lines[index : index + chunk_size]) for index in range(0, len(lines), chunk_size)]


def parse_stanza_selection(selection_text: str | None) -> list[int] | None:
    if not selection_text or "Stanza" not in selection_text:
        return None
    stanza_text = re.sub(r"^Stanzas?\s+", "", selection_text).strip()
    stanza_text = stanza_text.replace(" and ", ", ")
    stanza_text = stanza_text.replace(";", ",")
    selected: list[int] = []
    for fragment in [piece.strip() for piece in stanza_text.split(",") if piece.strip()]:
        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", fragment)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            selected.extend(range(start, end + 1))
            continue
        number_match = re.fullmatch(r"(\d+)", fragment)
        if number_match:
            selected.append(int(number_match.group(1)))
    return selected or None


def select_chinese_excerpt(chinese_blocks: list[str], stanza_selection: list[int] | None) -> list[str]:
    if stanza_selection is None:
        return chinese_blocks
    max_index = max(stanza_selection)
    if max_index > len(chinese_blocks):
        return chinese_blocks
    return [chinese_blocks[index - 1] for index in stanza_selection]


def build_segments_and_alignments(
    section: dict[str, Any],
    chinese_source_id: str,
    english_source_id: str,
    chinese_blocks: list[str],
    english_blocks: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int, str, str]:
    force_poem_alignment = bool(section.get("force_poem_alignment"))
    if force_poem_alignment:
        segment_type = "poem"
        chinese_segments_text = ["\n\n".join(chinese_blocks)]
        english_segments_text = ["\n\n".join(english_blocks)]
        section_note = section["reviewed_ocr_notes"]
    elif len(chinese_blocks) == len(english_blocks):
        segment_type = "stanza"
        chinese_segments_text = chinese_blocks
        english_segments_text = english_blocks
        section_note = "Aligned stanza by stanza from matching Chinese and English poem blocks."
    elif len(english_blocks) > len(chinese_blocks):
        chinese_lines = poem_lines(chinese_blocks)
        chunk_size = len(chinese_lines) // len(english_blocks) if english_blocks else 0
        if chunk_size and len(chinese_lines) % len(english_blocks) == 0 and chunk_size <= 8:
            segment_type = "stanza"
            chinese_segments_text = chunk_lines(chinese_lines, chunk_size)
            english_segments_text = english_blocks
            section_note = (
                f"Aligned at stanza level by splitting the Chinese text into {chunk_size}-line units to match "
                "Legge's printed stanza blocks."
            )
        else:
            segment_type = "poem"
            chinese_segments_text = ["\n\n".join(chinese_blocks)]
            english_segments_text = ["\n\n".join(english_blocks)]
            section_note = "Fell back to poem-level alignment because Chinese and English stanza counts did not match cleanly."
    else:
        segment_type = "poem"
        chinese_segments_text = ["\n\n".join(chinese_blocks)]
        english_segments_text = ["\n\n".join(english_blocks)]
        section_note = "Fell back to poem-level alignment because Chinese and English stanza counts did not match cleanly."

    chinese_segments: list[dict[str, Any]] = []
    english_segments: list[dict[str, Any]] = []
    alignments: list[dict[str, Any]] = []

    for order, (zh_text, en_text) in enumerate(zip(chinese_segments_text, english_segments_text), start=1):
        chinese_segment_id = f"{WORK_ID}__{section['section_id']}__{order:03d}__{SOURCE_SUFFIX}"
        english_segment_id = f"{WORK_ID}__{section['section_id']}__{order:03d}__{section['target_source_suffix']}"
        canonical_ref = f"{section['canonical_ref']}.{order}"
        confidence = 0.99 if segment_type == "stanza" else 0.95
        chinese_segments.append(
            {
                "segment_id": chinese_segment_id,
                "work_id": WORK_ID,
                "section_id": section["section_id"],
                "source_id": chinese_source_id,
                "segment_type": segment_type,
                "segment_order": order,
                "canonical_ref": canonical_ref,
                "text_original": zh_text,
                "text_normalized": zh_text,
                "notes": f"{section['label']} Chinese {segment_type} {order}.",
            }
        )
        english_segments.append(
            {
                "segment_id": english_segment_id,
                "work_id": WORK_ID,
                "section_id": section["section_id"],
                "source_id": english_source_id,
                "segment_type": segment_type,
                "segment_order": order,
                "canonical_ref": f"{section['legge_section_alias']}.{order}",
                "text_original": en_text,
                "text_normalized": en_text,
                "notes": f"{section['legge_section_alias']} English {segment_type} {order}.",
            }
        )
        alignments.append(
            {
                "alignment_id": (
                    f"{WORK_ID}__{section['section_id']}__{order:03d}__{SOURCE_SUFFIX}__{section['target_source_suffix']}"
                ),
                "work_id": WORK_ID,
                "section_id": section["section_id"],
                "source_id": chinese_source_id,
                "target_source_id": english_source_id,
                "alignment_type": "exact_or_near_exact",
                "confidence": confidence,
                "chinese_segment_ids": [chinese_segment_id],
                "translation_segment_ids": [english_segment_id],
                "alignment_granularity": segment_type,
                "section_unit": "poem",
                "segment_type": segment_type,
                "is_coarse_alignment": segment_type == "poem" and max(len(chinese_blocks), len(english_blocks)) > 1,
                "coarse_alignment_reason": (
                    "Whole-poem fallback because Chinese and English stanza structures do not align safely."
                    if segment_type == "poem" and max(len(chinese_blocks), len(english_blocks)) > 1
                    else None
                ),
                "source_segment_count": 1,
                "target_segment_count": 1,
                "notes": f"{segment_type.title()}-level Shijing alignment for {section['label']} block {order}.",
            }
        )

    alignments.append(
        {
            "alignment_id": (
                f"{WORK_ID}__{section['section_id']}__section-group__{SOURCE_SUFFIX}__{section['target_source_suffix']}"
            ),
            "work_id": WORK_ID,
            "section_id": section["section_id"],
            "source_id": chinese_source_id,
            "target_source_id": english_source_id,
            "alignment_type": "section_group",
            "confidence": 1.0,
            "chinese_segment_ids": [segment["segment_id"] for segment in chinese_segments],
            "translation_segment_ids": [segment["segment_id"] for segment in english_segments],
            "alignment_granularity": "section_group",
            "section_unit": "poem",
            "segment_type": segment_type,
            "is_coarse_alignment": False,
            "coarse_alignment_reason": None,
            "source_segment_count": len(chinese_segments),
            "target_segment_count": len(english_segments),
            "notes": section_note,
        }
    )
    return chinese_segments, english_segments, alignments, len(chinese_segments), segment_type, section_note


def build_sources(section: dict[str, Any], paths: dict[str, Path]) -> list[dict[str, Any]]:
    chinese_source_id, english_source_id = source_ids(section)
    witness_meta = shijing_witness_metadata(section.get("english_witness"))
    english_notes = (
        "Processed segmentation preserves the stanza blocks printed on Legge's standalone She King page."
        if section["english_witness"] == "standalone_sheking"
        else (
            "Reviewed section-level cleanup preserves the shared Legge 1871 Internet Archive OCR raw witness while "
            "keeping the exported alignment at poem scope until stanza-level OCR cleanup is safer."
            if section["english_witness"] == "legge_ocr_reviewed"
            else (
                "Generalized extraction preserves the shared Legge 1871 Internet Archive hOCR/raw witnesses and only "
                "retains stanza-level exact alignment when the OCR-derived stanza blocks match the Chinese segmentation safely."
                if section["english_witness"] == "legge_hocr"
                else (
                    "Untouched raw capture preserves the transcluded English Wikisource page, while segmentation uses cached "
                    "rendered HTML because the raw wikitext is only a <pages> transclusion."
                )
            )
        )
    )
    if section.get("stanza_selection"):
        english_notes += f" This witness is excerpted and only covers stanza selection {section['stanza_selection']}."
    return [
        {
            "source_id": chinese_source_id,
            "work_id": WORK_ID,
            "section_id": section["section_id"],
            "language_code": "zh-Hant",
            "source_kind": "wikisource",
            "citation": f"{title_from_url(section['zh_page_url'])}, Chinese Wikisource, accessed {ACCESS_DATE}.",
            "source_url": section["zh_page_url"],
            "raw_path": str(paths["zh_raw"].relative_to(REPO_ROOT)),
            "processed_path": str(paths["zh_segments"].relative_to(REPO_ROOT)),
            "rights_status": "public_domain",
            "author_or_translator_ids": ["shijing-anthologists"],
            "notes": (
                "Untouched raw capture comes from the page's action=raw export; processed segmentation keeps the poem text "
                "separate from translation and extracts subsection headings when multiple poems share a Chinese page."
            ),
            "witness_type": "zh_wikisource_page",
            "text_review_status": section.get("chinese_source_status", "verified_transcribed_text"),
            "needs_human_text_review": False,
        },
        {
            "source_id": english_source_id,
            "work_id": WORK_ID,
            "section_id": section["section_id"],
            "language_code": "en",
            "source_kind": "translation",
            "citation": (
                f"James Legge, The She King, '{section['legge_section_alias']}', English Wikisource, accessed {ACCESS_DATE}."
                if section["english_witness"] == "standalone_sheking"
                else (
                    (
                        f"James Legge, The She King, '{section['legge_section_alias']}', Chinese Classics, Vol. IV "
                        f"(1871), Internet Archive {'hOCR' if section['english_witness'] == 'legge_hocr' else 'OCR'} witness, "
                        f"accessed {LEGGE_SHEKING_1871_OCR_ACCESS_DATE}."
                    )
                    if section["english_witness"] in {"legge_ocr_reviewed", "legge_hocr"}
                    else (
                        f"James Legge, The Shih, Sacred Books of the East, Vol. III, '{section['legge_section_alias']}', "
                        f"English Wikisource, accessed {ACCESS_DATE}."
                    )
                )
            ),
            "source_url": section["en_page_url"],
            "raw_path": str(paths["en_raw"].relative_to(REPO_ROOT)),
            "processed_path": str(paths["en_segments"].relative_to(REPO_ROOT)),
            "rights_status": "public_domain",
            "author_or_translator_ids": ["james-legge"],
            "notes": (
                english_notes
                + (
                    " This OCR-derived extraction still needs human text review before it should be treated as a clean verified transcription."
                    if section.get("verification_status") not in {"verified_transcribed_text", "human_verified_ocr", "human_verified_fulltext"}
                    else ""
                )
            ),
            "witness_type": witness_meta["english_witness_type"],
            "text_review_status": section.get("verification_status", witness_meta["english_witness_status"]),
            "needs_human_text_review": bool(section.get("needs_human_text_review", witness_meta["needs_human_text_review"])),
        },
    ]


def write_section_files(section: dict[str, Any], *, skip_fetch: bool) -> dict[str, Any]:
    paths = section_paths(section)
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    zh_raw = fetch_cached_text(page_to_raw_url(section["zh_page_url"]), paths["zh_raw"], skip_fetch=skip_fetch)
    resolved_zh_page_url, zh_raw = resolve_redirect_raw(section["zh_page_url"], zh_raw)
    section["zh_page_url"] = resolved_zh_page_url
    paths["zh_raw"].write_text(zh_raw, encoding="utf-8")

    if section["english_witness"] == "legge_hocr":
        en_raw = fetch_cached_text(section["candidate_en_hocr_url"], paths["en_raw"], skip_fetch=skip_fetch)
    elif section["english_witness"] == "legge_ocr_reviewed":
        en_raw = fetch_cached_text(section["candidate_en_ocr_url"], paths["en_raw"], skip_fetch=skip_fetch)
    else:
        en_raw = fetch_cached_text(page_to_raw_url(section["en_page_url"]), paths["en_raw"], skip_fetch=skip_fetch)
        paths["en_raw"].write_text(en_raw, encoding="utf-8")

    rendered_html = None
    if section["english_witness"] == "sbe_shih":
        rendered_html = fetch_rendered_html(section["en_page_title"], paths["en_rendered"], skip_fetch=skip_fetch)

    chinese_source_id, english_source_id = source_ids(section)
    chinese_blocks = extract_chinese_poem_blocks(zh_raw, section)
    english_blocks, legge_title, pinyin_alias, selection_text = extract_english_poem_blocks(
        section,
        raw_text=en_raw,
        rendered_html=rendered_html,
    )
    stanza_selection = parse_stanza_selection(selection_text)
    chinese_blocks = select_chinese_excerpt(chinese_blocks, stanza_selection)
    chinese_segments, english_segments, alignments, exact_alignment_count, segment_type, alignment_note = (
        build_segments_and_alignments(
            section,
            chinese_source_id,
            english_source_id,
            chinese_blocks,
            english_blocks,
        )
    )

    paths["zh_base"].write_text(
        "\n\n".join(segment["text_original"] for segment in chinese_segments) + "\n",
        encoding="utf-8",
    )
    paths["en_text"].write_text(
        "\n\n".join(segment["text_original"] for segment in english_segments) + "\n",
        encoding="utf-8",
    )
    write_jsonl(paths["zh_segments"], chinese_segments)
    write_jsonl(paths["en_segments"], english_segments)
    write_jsonl(paths["alignments"], alignments)

    enriched_section = {
        **section,
        **shijing_witness_metadata(section.get("english_witness")),
        "work_id": WORK_ID,
        "status": "complete",
        "coverage_status": "complete",
        "alignment_status": "complete",
        "tmx_status": "complete",
        "section_unit": "poem",
        "segment_type": segment_type,
        "expected_exact_alignment_count": exact_alignment_count,
        "source_ids": {
            "source_id": chinese_source_id,
            "target_source_id": english_source_id,
        },
        "legge_section_alias": legge_title,
        "pinyin_alias": pinyin_alias or section.get("pinyin_alias"),
        "stanza_selection": selection_text,
        "notes": alignment_note,
    }
    return {
        "section": enriched_section,
        "sources": build_sources(enriched_section, paths),
    }


def remove_metadata_only_section_artifacts(manifest_sections: list[dict[str, Any]], *, skip_fetch: bool) -> None:
    for section in manifest_sections:
        if section.get("tmx_status") == "complete":
            continue
        base_name = f"{WORK_ID}__{section['section_id']}"
        for directory in (CHINESE_DIR, TRANSLATION_DIR, ALIGNMENT_DIR):
            for path in directory.glob(f"{base_name}*"):
                if path.is_file():
                    path.unlink()
        for path in section_export_paths(section["section_id"], WORK_ID).values():
            if path.exists():
                path.unlink()


def bootstrap_corpus(skip_fetch: bool = False) -> dict[str, Any]:
    verification_index = load_shijing_verification_index(skip_fetch=skip_fetch)
    processed_sections: list[dict[str, Any]] = []
    all_sources: list[dict[str, Any]] = []
    romanization_aliases: list[dict[str, Any]] = [
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "alias": "Shijing",
            "romanization_system": "pinyin",
        },
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "alias": "Shi Jing",
            "romanization_system": "pinyin",
        },
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "alias": "Classic of Poetry",
            "romanization_system": "english-title",
        },
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "alias": "Book of Poetry",
            "romanization_system": "english-title",
        },
    ]
    ingestion_log: list[dict[str, Any]] = []
    total_exact_alignments = 0

    if not skip_fetch or any((REPO_ROOT / path).exists() for path in LEGGE_SHEKING_1871_OCR_RAW_PATHS.values()):
        fetch_legge_ocr_sources(skip_fetch=skip_fetch)
    if not skip_fetch or any((REPO_ROOT / path).exists() for path in LEGGE_SHEKING_1871_HOCR_RAW_PATHS.values()):
        fetch_legge_hocr_sources(skip_fetch=skip_fetch)

    for section_seed in build_section_catalog(skip_fetch=skip_fetch, verification_index=verification_index):
        verification = verification_index[section_seed["section_id"]]
        result = write_section_files(
            {
                **section_seed,
                **verification_annotation(verification),
                "needs_human_text_review": False,
                "review_note": section_seed.get("review_note") or verification["reviewer_note"],
            },
            skip_fetch=skip_fetch,
        )
        section = result["section"]
        processed_sections.append(section)
        all_sources.extend(result["sources"])
        total_exact_alignments += section["expected_exact_alignment_count"]
        romanization_aliases.append(
            {
                "entity_type": "section",
                "entity_id": section["section_id"],
                "alias": section["legge_section_alias"],
                "romanization_system": "Legge-title",
            }
        )
        if section.get("pinyin_alias"):
            romanization_aliases.append(
                {
                    "entity_type": "section",
                    "entity_id": section["section_id"],
                    "alias": section["pinyin_alias"],
                    "romanization_system": "pinyin",
                }
            )
        ingestion_log.append(
            {
                "run_id": f"bootstrap-{section['section_id']}-{ACCESS_DATE.replace('-', '')}",
                "work_id": WORK_ID,
                "section_id": section["section_id"],
                "status": "complete",
                "source_ids": [section["source_ids"]["source_id"], section["source_ids"]["target_source_id"]],
                "notes": (
                    f"Bootstrap Shijing generation for {section['label']} with "
                    f"{section['expected_exact_alignment_count']} exact {section['segment_type']} alignments."
                ),
            }
        )

    processed_sections.sort(key=lambda section: section["sort_key"])
    processed_section_map = {section["section_id"]: section for section in processed_sections}
    canonical_inventory = build_canonical_section_inventory(
        processed_sections,
        skip_fetch=skip_fetch,
        verification_index=verification_index,
    )
    manifest_sections: list[dict[str, Any]] = []
    missing_chinese_source_count = 0
    needs_alignment_count = 0
    for inventory_item in canonical_inventory:
        complete_section = processed_section_map.get(inventory_item["section_id"])
        base_section = {
            "section_id": inventory_item["section_id"],
            "work_id": WORK_ID,
            "parent_section_id": None,
            "label": inventory_item["title"],
            "canonical_ref": inventory_item["canonical_ref"],
            "sort_key": inventory_item["global_sort_key"],
            "major_division": inventory_item["major_division"],
            "subdivision": inventory_item["subdivision"],
            "poem_number": inventory_item["local_poem_number"],
            "section_unit": "poem",
            "zh_page_url": inventory_item["zh_page_url"],
            "english_witness_type": inventory_item["english_witness_type"],
            "english_witness_status": inventory_item["english_witness_status"],
            "source_witness_type": inventory_item["source_witness_type"],
            "needs_human_text_review": inventory_item["needs_human_text_review"],
            **verification_annotation(inventory_item),
        }
        if complete_section is not None:
            manifest_sections.append(
                {
                    **complete_section,
                    **base_section,
                    "status": "complete",
                    "coverage_status": "complete",
                    "alignment_status": inventory_item["alignment_status"] or "complete",
                    "tmx_status": "complete",
                }
            )
            continue
        if inventory_item["status"] == "missing_chinese_source":
            missing_chinese_source_count += 1
            manifest_sections.append(
                {
                    **base_section,
                    "status": "missing_chinese_source",
                    "coverage_status": "title_only_lost_text",
                    "alignment_status": "metadata_only",
                    "tmx_status": "metadata_only",
                    "expected_exact_alignment_count": 0,
                    "notes": (
                        "Canonical Shijing index entry represented for structural completeness only. "
                        "Chinese Wikisource marks this title as 有其義而亡其辭, so no poem text is available to align."
                    ),
                }
            )
            continue
        needs_alignment_count += 1
        manifest_sections.append(
            {
                **base_section,
                "status": inventory_item["status"],
                "coverage_status": inventory_item["coverage_status"],
                "alignment_status": inventory_item["alignment_status"] or "needs_text_repair",
                "tmx_status": "not_exportable",
                "expected_exact_alignment_count": 0,
                "en_page_url": inventory_item["candidate_en_page_url"],
                "candidate_en_source_id": inventory_item["candidate_en_source_id"],
                "candidate_en_text_url": inventory_item["candidate_en_text_url"],
                "candidate_en_ocr_url": inventory_item["candidate_en_ocr_url"],
                "candidate_en_raw_path": inventory_item["candidate_en_raw_path"],
                "candidate_en_access_date": LEGGE_SHEKING_1871_OCR_ACCESS_DATE,
                "candidate_en_backup_page_url": inventory_item["candidate_en_backup_page_url"],
                "candidate_en_backup_source_id": inventory_item["candidate_en_backup_source_id"],
                "notes": inventory_item["notes"],
            }
        )

    inventory_payload = {
        "work_id": WORK_ID,
        "title": "Canonical Shijing poem inventory",
        "count_basis": {
            "canonical_index_entry_count": len(canonical_inventory),
            "extant_poem_count": len(canonical_inventory) - missing_chinese_source_count,
            "title_only_missing_text_count": missing_chinese_source_count,
            "basis_note": (
                "Derived from the ordered Chinese Wikisource 詩經 index. The index enumerates 311 canonical entries; "
                "six of them are title-only Xiaoya entries marked 有其義而亡其辭."
            ),
        },
        "poems": canonical_inventory,
    }
    write_json(INVENTORY_PATH, inventory_payload)

    manifest = {
        "work_id": WORK_ID,
        "work_status": "inventory_complete",
        "source_pair_defaults": {
            "source_id": SOURCE_SUFFIX,
            "target_source_id": SBE_TARGET_SOURCE_SUFFIX,
            "source_language": "zh-Hant",
            "target_language": "en",
        },
        "summary": {
            "section_count": len(manifest_sections),
            "canonical_entry_count": len(canonical_inventory),
            "extant_poem_count": len(canonical_inventory) - missing_chinese_source_count,
            "missing_chinese_source_sections": missing_chinese_source_count,
            "complete_sections": len(processed_sections),
            "metadata_only_sections": len(manifest_sections) - len(processed_sections),
            "sections_needing_alignment": needs_alignment_count,
            "sections_needing_qc": needs_alignment_count,
            "exact_alignment_count": total_exact_alignments,
            "source_count": len(all_sources),
        },
        "ingestion_policy": build_ingestion_policy(),
        "romanization_aliases": romanization_aliases,
        "ingestion_log": ingestion_log,
        "sources": all_sources,
        "sections": manifest_sections,
    }
    write_json(MANIFEST_PATH, manifest)
    remove_metadata_only_section_artifacts(manifest_sections, skip_fetch=skip_fetch)
    return manifest["summary"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap raw captures, processed files, and metadata for the Shijing corpus.")
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Reuse local raw captures instead of downloading them again.",
    )
    args = parser.parse_args()

    summary = bootstrap_corpus(skip_fetch=args.skip_fetch)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
