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
    14: {
        "legge_section_alias": "Ts'aou ch'ung",
        "review_note": (
            "Recovered three stanza blocks by checking the Legge hOCR witness across the page break at part-1 "
            "page 225 lines 12-23 and page 226 lines 3-11."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Yaou-yaou went the grass-insects,",
                    "And the hoppers sprang about.",
                    "While I do not see my lord,",
                    "My sorrowful heart is agitated.",
                    "Let me have seen him,",
                    "Let me have met him,",
                    "And my heart will then be stilled.",
                ]
            ),
            "\n".join(
                [
                    "I ascended that hill in the south,",
                    "And gathered the turtle-foot ferns.",
                    "While I do not see my lord,",
                    "My sorrowful heart is very sad.",
                    "Let me have seen him,",
                    "Let me have met him,",
                    "And my heart will then be pleased.",
                ]
            ),
            "\n".join(
                [
                    "I ascended that hill in the south,",
                    "And gathered the thorn-ferns.",
                    "While I do not see my lord,",
                    "My sorrowful heart is wounded with grief.",
                    "Let me have seen him,",
                    "Let me have met him,",
                    "And my heart will then be at peace.",
                ]
            ),
        ],
    },
    16: {
        "legge_section_alias": "Kan t'ang",
        "review_note": (
            "Recovered the three verse stanzas from part-1 hOCR page 228 lines 11-19 and excluded the following "
            "Xing Lu carry-over at page 229 lines 3-4."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "[This] umbrageous sweet pear-tree",
                    "Clip it not, hew it not down.",
                    "Under it the chief of Shaou lodged.",
                ]
            ),
            "\n".join(
                [
                    "[This] umbrageous sweet pear-tree",
                    "Clip it not, break not a twig of it.",
                    "Under it the chief of Shaou rested.",
                ]
            ),
            "\n".join(
                [
                    "[This] umbrageous sweet pear-tree",
                    "Clip it not, bend not a twig of it.",
                    "Under it the chief of Shaou halted.",
                ]
            ),
        ],
    },
    18: {
        "legge_section_alias": "Kaou yang",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR page 230 lines 14-21 and page 231 lines 5-8, "
            "skipping the commentary and running header between them."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "[Those] lamb-skins and sheep-skins,",
                    "With their five braidings of white silk!",
                    "They have retired from the court to take their meal;",
                    "Easy are they and self-possessed.",
                ]
            ),
            "\n".join(
                [
                    "[Those] lamb-skins and sheep-skins,",
                    "With their five seams wrought with white silk!",
                    "Easy are they and self-possessed;",
                    "They have retired from the court to take their meal.",
                ]
            ),
            "\n".join(
                [
                    "The seams of [those] lamb-skins and sheep-skins,",
                    "The five joinings wrought with white silk!",
                    "Easy are they and self-possessed;",
                    "They have retired to take their meal from the court.",
                ]
            ),
        ],
    },
    19: {
        "legge_section_alias": "Yin k'e luy",
        "review_note": (
            "Recovered the three verse stanzas from part-1 hOCR page 231 lines 14-22 and page 232 lines 7-15 "
            "after removing the intervening commentary block."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Grandly rolls the thunder,",
                    "On the south of the southern hill !",
                    "How was it he went away from this,",
                    "Not daring to take a little rest?",
                    "My noble lord !",
                    "May he return ! May he return !",
                ]
            ),
            "\n".join(
                [
                    "Grandly rolls the thunder,",
                    "About the sides of the southern hill !",
                    "How was it he went away from this,",
                    "Not daring to take a little rest?",
                    "My noble lord !",
                    "May he return ! May he return !",
                ]
            ),
            "\n".join(
                [
                    "Grandly rolls the thunder,",
                    "At the foot of the southern hill !",
                    "How was it he went away from this,",
                    "Not remaining a little at rest?",
                    "My noble lord !",
                    "May he return ! May he return !",
                ]
            ),
        ],
    },
    20: {
        "legge_section_alias": "P'eaou yew mei",
        "review_note": (
            "Recovered the three verse stanzas from part-1 hOCR page 232 lines 20-27 and page 233 lines 5-8, "
            "excluding the Ode 8 commentary that interrupts the page break."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Dropping are the fruits from the plum-tree;",
                    "There are [but] seven [tenths] of them left !",
                    "For the gentlemen who seek me,",
                    "This is the fortunate time !",
                ]
            ),
            "\n".join(
                [
                    "Dropping are the fruits from the plum-tree ;",
                    "There are [but] three [tenths] of them left !",
                    "For the gentlemen who seek me,",
                    "Now is the time.",
                ]
            ),
            "\n".join(
                [
                    "Dropt are the fruits from the plum-tree ;",
                    "In my shallow basket I have collected them.",
                    "Would the gentlemen who seek me",
                    "[Only] speak about it !",
                ]
            ),
        ],
    },
    21: {
        "legge_section_alias": "Seaou sing",
        "review_note": (
            "Recovered the two verse stanzas from part-1 hOCR page 233 lines 14-18 and page 234 lines 9-13 "
            "after excluding the preceding Plum-tree commentary."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Small are those starlets,",
                    "Three or five of them in the east.",
                    "Swiftly by night we go ;",
                    "In the early dawn we are with the prince.",
                    "Our lot is not like hers.",
                ]
            ),
            "\n".join(
                [
                    "Small are those starlets,",
                    "And there are Orion and the Pleiades.",
                    "Swiftly by night we go,",
                    "Carrying our coverlets and sheets.",
                    "Our lot is not as hers.",
                ]
            ),
        ],
    },
    22: {
        "legge_section_alias": "Keang yew sze",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR page 234 lines 17-21 and page 235 lines 7-16, "
            "skipping the intervening Seaou Sing commentary."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "The Keang has its branches, led from it and returning to it.",
                    "Our lady, when she was married,",
                    "Would not employ us.",
                    "She would not employ us;",
                    "But afterwards she repented.",
                ]
            ),
            "\n".join(
                [
                    "The Keang has its islets.",
                    "Our lady, when she was married,",
                    "Would not let us be with her.",
                    "She would not let us be with her;",
                    "But afterwards she repressed [such feelings].",
                ]
            ),
            "\n".join(
                [
                    "The Keang has the T'o.",
                    "Our lady, when she was married,",
                    "Would not come near us.",
                    "She would not come near us;",
                    "But she blew that feeling away, and sang.",
                ]
            ),
        ],
    },
    23: {
        "legge_section_alias": "Yay yew szekeun",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR page 236 lines 10-20 and excluded the Ho pe nung "
            "carry-over on the following page."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "In the wild there is a dead antelope,",
                    "And it is wrapped up with the white grass.",
                    "There is a young lady with thoughts natural to the spring,",
                    "And a fine gentleman would lead her astray.",
                ]
            ),
            "\n".join(
                [
                    "In the forest there are the scrubby oaks ;",
                    "In the wild there is a dead deer,",
                    "And it is bound round with the white grass.",
                    "There is a young lady like a gem.",
                ]
            ),
            "\n".join(
                [
                    "[She says], Slowly, gently, gently;",
                    "Do not move my handkerchief;",
                    "Do not make my dog bark.",
                ]
            ),
        ],
    },
    24: {
        "legge_section_alias": "Ho pe nung",
        "review_note": (
            "Recovered the first two stanzas from part-1 hOCR page 237 lines 3-10 and the closing stanza from "
            "page 238 lines 59-62 after skipping the Tsow-yu page header and commentary."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "How great is that luxuriance,",
                    "Those flowers of the sparrow-plum!",
                    "Are they not expressive of reverence and harmony, —",
                    "The carriages of the king's daughter?",
                ]
            ),
            "\n".join(
                [
                    "How great is that luxuriance,",
                    "The flowers like those of the peach-tree or the plum!",
                    "[See] the grand-daughter of the tranquillizing king,",
                    "And the son of the reverent marquis!",
                ]
            ),
            "\n".join(
                [
                    "What are used in angling?",
                    "Silk threads formed into lines.",
                    "The son of the reverent marquis,",
                    "And the grand-daughter of the tranquillizing king!",
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
    27: {
        "legge_section_alias": "Lull e.",
        "review_note": (
            "Recovered the four stanza blocks from part-1 hOCR page 243 lines 6-13 and page 244 lines 6-13 "
            "after excluding the intervening note block."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Green is the upper robe,",
                    "Green with a yellow lining!",
                    "The sorrow of my heart, —",
                    "How can it cease?",
                ]
            ),
            "\n".join(
                [
                    "Green is the upper robe;",
                    "Green the upper, and yellow the lower garment!",
                    "The sorrow of my heart, —",
                    "How can it be forgotten?",
                ]
            ),
            "\n".join(
                [
                    "[Dyed] green has been the silk; —",
                    "It was you who did it.",
                    "[But] I think of the ancients,",
                    "That I may be kept from doing wrong.",
                ]
            ),
            "\n".join(
                [
                    "Linen, fine or coarse,",
                    "Is cold when worn in the wind.",
                    "I think of the ancients,",
                    "And find what is in my heart.",
                ]
            ),
        ],
    },
    28: {
        "legge_section_alias": "Yen-yen.",
        "review_note": (
            "Recovered the first three stanzas from part-1 hOCR page 244 lines 16-19 and page 245 lines 15-28, "
            "plus the closing stanza from page 246 lines 6-11, after excluding the interleaved commentary."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "The swallows go flying about,",
                    "With their wings unevenly displayed.",
                    "The lady was returning to her native state,",
                    "And I escorted her far into the country.",
                    "I looked till I could no longer see her,",
                    "And my tears fell down like rain.",
                ]
            ),
            "\n".join(
                [
                    "The swallows go flying about,",
                    "Now up, now down.",
                    "The lady was returning to her native state,",
                    "And far did I accompany her.",
                    "I looked till I could no longer see her,",
                    "And long I stood and wept.",
                ]
            ),
            "\n".join(
                [
                    "The swallows go flying about;",
                    "From below, from above, comes their twittering.",
                    "The lady was returning to her native state,",
                    "And far did I escort her to the south.",
                    "I looked till I could no longer see her,",
                    "And great was the grief of my heart.",
                ]
            ),
            "\n".join(
                [
                    "Lovingly confiding was the lady Chung;",
                    "Truly deep was her feeling.",
                    "Both gentle was she and docile,",
                    "Virtuously careful of her person.",
                    "In thinking of our deceased lord,",
                    "She stimulated worthless me.",
                ]
            ),
        ],
    },
    30: {
        "legge_section_alias": "Chung fung.",
        "review_note": (
            "Recovered the four stanza blocks from part-1 hOCR page 248 lines 13-16 and page 249 lines 11-22 "
            "after excluding the commentary between pages."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "The wind blows and is fierce.",
                    "He looks at me and smiles,",
                    "With scornful words and dissolute, — the smile of pride.",
                    "To the centre of my heart I am grieved.",
                ]
            ),
            "\n".join(
                [
                    "The wind blows, with clouds of dust.",
                    "Kindly he seems to be willing to come to me;",
                    "[But] he neither goes nor comes.",
                    "Long, long, do I think of him.",
                ]
            ),
            "\n".join(
                [
                    "The wind blew, and the sky was cloudy;",
                    "Before a day elapses, it is cloudy again.",
                    "I awake, and cannot sleep;",
                    "I think of him, and gasp.",
                ]
            ),
            "\n".join(
                [
                    "All cloudy is the darkness,",
                    "And the thunder keeps muttering.",
                    "I awake and cannot sleep;",
                    "I think of him, and my breast is full of pain.",
                ]
            ),
        ],
    },
    31: {
        "legge_section_alias": "Keih koo.",
        "review_note": (
            "Recovered the five stanza blocks from part-1 hOCR page 250 lines 8-17 and page 251 lines 17-28 "
            "after excluding the preceding 終風 commentary."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Hear the roll of our drums!",
                    "See how we leap about, using our weapons!",
                    "Those do the fieldwork in the State, or fortify Tsou,",
                    "While we alone march to the south.",
                ]
            ),
            "\n".join(
                [
                    "We followed Sun Tsze-chung,",
                    "Peace having been made with Ch'in and Sung;",
                    "[But] he did not lead us back,",
                    "And our sorrowful hearts are very sad.",
                ]
            ),
            "\n".join(
                [
                    "Here we stay; here we stop;",
                    "Here we lose our horses;",
                    "And we seek for them,",
                    "Among the trees of the forest.",
                ]
            ),
            "\n".join(
                [
                    "For life or for death, however separated,",
                    "To our wives we pledged our word.",
                    "We held their hands; —",
                    "We were to grow old together with them.",
                ]
            ),
            "\n".join(
                [
                    "Alas for our separation!",
                    "We have no prospect of life.",
                    "Alas for our stipulation!",
                    "We cannot make it good.",
                ]
            ),
        ],
    },
    32: {
        "legge_section_alias": "ICae fung.",
        "review_note": (
            "Recovered the four stanza blocks from part-1 hOCR page 252 lines 16-23 and page 253 lines 6-13 "
            "after excluding the trailing 擊鼓 commentary."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "The genial wind from the south",
                    "Blows on the heart of that jujube tree,",
                    "Till that heart looks tender and beautiful.",
                    "What toil and pain did our mother endure!",
                ]
            ),
            "\n".join(
                [
                    "The genial wind from the south",
                    "Blows on the branches of that jujube tree,",
                    "Our mother is wise and good;",
                    "But among us there is none good.",
                ]
            ),
            "\n".join(
                [
                    "There is the cool spring",
                    "Below the city of Tseun.",
                    "We are seven sons,",
                    "And our mother is full of pain and suffering.",
                ]
            ),
            "\n".join(
                [
                    "The beautiful yellow birds",
                    "Give forth their pleasant notes.",
                    "We are seven sons,",
                    "And cannot compose our mother's heart.",
                ]
            ),
        ],
    },
    33: {
        "legge_section_alias": "雄雉",
        "review_note": (
            "Recovered the four stanza blocks from part-1 hOCR page 253 lines 17-20 and page 254 lines 14-25 "
            "after excluding the 凱風 commentary carried over at the page break."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "The male pheasant flies away,",
                    "Lazily moving his wings.",
                    "The man of my heart! —",
                    "He has brought on us this separation.",
                ]
            ),
            "\n".join(
                [
                    "The pheasant has flown away,",
                    "But from below, from above, comes his voice.",
                    "Ah! the princely man! —",
                    "He afflicts my heart.",
                ]
            ),
            "\n".join(
                [
                    "Look at that sun and moon!",
                    "Long, long do I think.",
                    "The way is distant;",
                    "How can he come to me?",
                ]
            ),
            "\n".join(
                [
                    "All ye princely men,",
                    "Know ye not his virtuous conduct?",
                    "He hates none; he covets nothing; —",
                    "What does he which is not good?",
                ]
            ),
        ],
    },
    34: {
        "legge_section_alias": "aou-y ew-koo-y eh •",
        "review_note": (
            "Recovered the four stanza blocks from part-1 hOCR page 255 lines 8-15 and page 256 lines 7-14 "
            "after excluding the introductory note block between stanzas 2 and 3."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "The gourd has [still] its bitter leaves,",
                    "And the crossing at the ford is deep.",
                    "If deep, I will go through with my clothes on;",
                    "If shallow, I will do so, holding them up.",
                ]
            ),
            "\n".join(
                [
                    "The ford is full to overflowing;",
                    "There is the note of the female pheasant.",
                    "The full ford will not wet the axle of my carriage;",
                    "It is the pheasant calling for her mate.",
                ]
            ),
            "\n".join(
                [
                    "The wild goose, with its harmonious notes,",
                    "At sunrise, with the earliest dawn,",
                    "By the gentleman, who wishes to bring home his bride,",
                    "[Is presented] before the ice is melted.",
                ]
            ),
            "\n".join(
                [
                    "The boatman keeps beckoning;",
                    "And others cross with him, but I do not.",
                    "Others cross with him, but I do not; —",
                    "I am waiting for my friend.",
                ]
            ),
        ],
    },
    36: {
        "legge_section_alias": "Shih Wei.",
        "review_note": "Recovered the two stanza blocks from part-1 hOCR page 261 lines 8-15.",
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Reduced! Reduced!",
                    "Why not return?",
                    "If it were not for your sake, O prince,",
                    "How should we be thus exposed to the dew?",
                ]
            ),
            "\n".join(
                [
                    "Reduced! reduced!",
                    "Why not return?",
                    "If it were not for your person, O prince,",
                    "How should we be here in the mire?",
                ]
            ),
        ],
    },
    37: {
        "legge_section_alias": "Maou-Vewt",
        "review_note": (
            "Recovered the four stanza blocks from part-1 hOCR page 261 lines 19-22 and page 262 lines 21-32 "
            "after excluding the intervening note block."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "The dolichos on that high and sloping mound; —",
                    "How wide apart are [now] its joints!",
                    "O ye uncles,",
                    "Why have ye delayed these many days?",
                ]
            ),
            "\n".join(
                [
                    "Why do they rest without stirring?",
                    "It must be they expect allies.",
                    "Why do they prolong the time?",
                    "There must be a reason for their conduct.",
                ]
            ),
            "\n".join(
                [
                    "Our fox-furs are frayed and worn.",
                    "Came our carriages not eastwards?",
                    "O ye uncles,",
                    "You do not sympathize with us.",
                ]
            ),
            "\n".join(
                [
                    "Fragments, and a remnant,",
                    "Children of dispersion [are we]!",
                    "O ye uncles,",
                    "Notwithstanding your full robes, your ears are stopped.",
                ]
            ),
        ],
    },
    38: {
        "legge_section_alias": "Keen he.",
        "review_note": (
            "Recovered the four stanza blocks from part-1 hOCR page 263 lines 8-15 and page 264 lines 3-12 "
            "after excluding the 旄丘 commentary."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Easy and indifferent! easy and indifferent!",
                    "I am ready to perform in all dances,",
                    "Then when the sun is in the meridian,",
                    "There in that conspicuous place.",
                ]
            ),
            "\n".join(
                [
                    "With my large figure,",
                    "I dance in the ducal courtyard.",
                    "I am strong [also] as a tiger;",
                    "The reins are in my grasp like ribbons.",
                ]
            ),
            "\n".join(
                [
                    "In my left hand I grasp a flute;",
                    "In my right I hold a pheasant's feather.",
                    "I am red as if I were rouged;",
                    "The duke gives me a cup [of spirits].",
                ]
            ),
            "\n".join(
                [
                    "The hazel grows on the hills,",
                    "And the liquorice in the marshes.",
                    "Of whom are my thoughts?",
                    "Of the fine men of the west.",
                    "O those fine men!",
                    "Those men of the west!",
                ]
            ),
        ],
    },
    39: {
        "legge_section_alias": "Ts‘euen shwuy.",
        "review_note": (
            "Recovered the four stanza blocks from part-1 hOCR page 265 lines 12-23 and page 266 lines 9-20 "
            "after merging the split closing stanza around the page break."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "How the water bubbles up from that spring,",
                    "And flows away to the K'e!",
                    "My heart is in Wei;",
                    "There is not a day I do not think of it.",
                    "Admirable are those, my cousins;",
                    "I will take counsel with them.",
                ]
            ),
            "\n".join(
                [
                    "When I came forth, I lodged in Tse,",
                    "And we drank the cup of convoy at Ne.",
                    "When a young lady goes to be married,",
                    "She leaves her parents and brothers;",
                    "[But] I would ask for my aunts,",
                    "And then for my elder sister.",
                ]
            ),
            "\n".join(
                [
                    "I will go forth and lodge in Kan,",
                    "And we will drink the cup of convoy at Yen.",
                    "I will grease the axle and fix the pin,",
                    "And the returning chariot will proceed.",
                    "Quickly shall we arrive in Wei; —",
                    "But would not this be wrong?",
                ]
            ),
            "\n".join(
                [
                    "I think of the Fei-ts'euen,",
                    "I am ever sighing about it.",
                    "I think of Seu and Ts'aou,",
                    "Long, long, my heart dwells with them.",
                    "Let me drive forth and travel there,",
                    "To dissipate my sorrow.",
                ]
            ),
        ],
    },
    41: {
        "legge_section_alias": "Pihfung.",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR page 269 lines 10-21 and page 270 lines 4-9."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Cold blows the north wind;",
                    "Thick falls the snow.",
                    "Ye who love and regard me,",
                    "Let us join hands and go together.",
                    "Is it a time for delay?",
                    "The urgency is extreme!",
                ]
            ),
            "\n".join(
                [
                    "The north wind whistles;",
                    "The snow falls and drifts about.",
                    "Ye who love and regard me,",
                    "Let us join hands, and go away for ever.",
                    "Is it a time for delay?",
                    "The urgency is extreme!",
                ]
            ),
            "\n".join(
                [
                    "Nothing red is seen but foxes,",
                    "Nothing black but crows.",
                    "Ye who love and regard me,",
                    "Let us join hands, and go together in our carriages.",
                    "Is it a time for delay?",
                    "The urgency is extreme!",
                ]
            ),
        ],
    },
    43: {
        "legge_section_alias": "Sin-fae.",
        "review_note": "Recovered the three stanza blocks from part-1 hOCR page 272 lines 9-20.",
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Fresh and bright is the New Tower,",
                    "On the waters of the Ho, wide and deep.",
                    "A pleasant, genial mate she sought,",
                    "And has got this vicious bloated mass!",
                ]
            ),
            "\n".join(
                [
                    "Lofty is the New Tower,",
                    "On the waters of the Ho, flowing still.",
                    "A pleasant, genial mate she sought,",
                    "And has got this vicious bloated mass!",
                ]
            ),
            "\n".join(
                [
                    "It was a fish net that was set,",
                    "And a goose has fallen into it.",
                    "A pleasant, genial mate she sought,",
                    "And she has got this hunchback.",
                ]
            ),
        ],
    },
    46: {
        "legge_section_alias": "Ts 'eang yew tsze.",
        "review_note": "Recovered the three stanza blocks from part-1 hOCR pages 276-277 lines 17-22 and 277:8-19.",
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "The tribulus grows on the wall,",
                    "And cannot be brushed away.",
                    "The story of the inner chamber",
                    "Cannot be told.",
                    "What would have to be told",
                    "Would be the vilest of recitals.",
                ]
            ),
            "\n".join(
                [
                    "The tribulus grows on the wall,",
                    "And cannot be removed.",
                    "The story of the inner chamber",
                    "Cannot be particularly related.",
                    "What might be particularly related",
                    "Would be a long story.",
                ]
            ),
            "\n".join(
                [
                    "The tribulus grows on the wall,",
                    "And cannot be bound together and taken away.",
                    "The story of the inner chamber",
                    "Cannot be recited.",
                    "What might be recited",
                    "Would be the most disgraceful of things.",
                ]
            ),
        ],
    },
    48: {
        "legge_section_alias": "Sang-chung •",
        "review_note": "Recovered the three stanza blocks from part-1 hOCR pages 280-282 lines 13-19, 281:12-18, and 282:5-7.",
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "I am going to gather the dodder,",
                    "In the fields of Mei.",
                    "But of whom are my thoughts?",
                    "Of that beauty, the eldest of the Keang.",
                    "She made an appointment with me in Sang-chung;",
                    "She will meet me in Shang-kung;",
                    "She will accompany me to K'e-shang.",
                ]
            ),
            "\n".join(
                [
                    "I am going to gather the wheat,",
                    "In the north of Mei.",
                    "But of whom are my thoughts?",
                    "Of that beauty, the eldest of the Yih.",
                    "She made an appointment with me in Sang-chung;",
                    "She will meet me in Shang-kung;",
                    "She will accompany me to K'e-shang.",
                ]
            ),
            "\n".join(
                [
                    "I am going to gather the mustard plant,",
                    "In the east of Mei.",
                    "But of whom are my thoughts?",
                    "Of that beauty, the eldest of the Yung.",
                    "She made an appointment with me in Sang-chung;",
                    "She will meet me in Shang-kung;",
                    "She will accompany me to K'e-shang.",
                ]
            ),
        ],
    },
    49: {
        "legge_section_alias": "Shun che pun-pun.",
        "review_note": "Recovered the two stanza blocks from part-1 hOCR page 282 lines 13-20.",
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Boldly faithful in their pairings are quails;",
                    "Vigorously so are magpies.",
                    "This man is all vicious,",
                    "And I consider him my brother!",
                ]
            ),
            "\n".join(
                [
                    "Vigorously faithful in their pairings are magpies;",
                    "Boldly so are quails.",
                    "This woman is all vicious,",
                    "And I regard her as marchioness!",
                ]
            ),
        ],
    },
    51: {
        "legge_section_alias": "Te tung.",
        "review_note": "Recovered the three stanza blocks from part-1 hOCR pages 285-286 lines 13-16 and 286:7-14.",
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "There is a rainbow in the east,",
                    "And no one dares to point to it.",
                    "When a girl goes away from her home,",
                    "She separates from her parents and brothers.",
                ]
            ),
            "\n".join(
                [
                    "In the morning a rainbow rises in the west,",
                    "And only during the morning is there rain.",
                    "When a girl goes away from her home,",
                    "She separates from her brothers and parents.",
                ]
            ),
            "\n".join(
                [
                    "This person",
                    "Has her heart only on being married.",
                    "Greatly is she untrue to herself,",
                    "And does not recognize the law of her lot.",
                ]
            ),
        ],
    },
    53: {
        "legge_section_alias": "Kan maou.",
        "review_note": "Recovered the three stanza blocks from part-1 hOCR pages 287-288 lines 6-11 and 288:27-38.",
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Conspicuously rise the staffs with their ox-tails,",
                    "In the distant suburbs of Tseun,",
                    "Ornamented with the white silk bands;",
                    "There are four carriages with their good horses;",
                    "That admirable gentleman, —",
                    "What will he give them for this?",
                ]
            ),
            "\n".join(
                [
                    "Conspicuously rise the staffs with their falcon-banners,",
                    "In the nearer suburbs of Tseun,",
                    "Ornamented with the white silk ribbons;",
                    "There are five carriages with their good horses.",
                    "That admirable gentleman, —",
                    "What will he give them for this?",
                ]
            ),
            "\n".join(
                [
                    "Conspicuously rise the staffs with their feathered streamers,",
                    "At the walls of Tseun,",
                    "Bound with the white silk cords.",
                    "There are six carriages with their good horses;",
                    "That admirable gentleman, —",
                    "What will he tell them for this?",
                ]
            ),
        ],
    },
    54: {
        "legge_section_alias": "Tsae chle.",
        "review_note": "Recovered the four stanza blocks from part-1 hOCR pages 289-291 lines 12-17, 290:8-21, and 291:3-10.",
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "I would have galloped my horses and whipt them,",
                    "Returning to condole with the marquis of Wei.",
                    "I would have urged them all the long way,",
                    "Till I arrived at Tsaou.",
                    "A great officer has gone, over the hills and through the rivers;",
                    "But my heart is full of sorrow.",
                ]
            ),
            "\n".join(
                [
                    "You disapproved of my proposal,",
                    "And I cannot return to Wei;",
                    "But I regard you as in the wrong,",
                    "And cannot forget my purpose.",
                    "You disapproved of my purpose,",
                    "And I cannot return across the streams;",
                    "But I regard you as in the wrong,",
                    "And cannot shut out my thoughts.",
                ]
            ),
            "\n".join(
                [
                    "I will ascend that mound with the steep side,",
                    "And gather the mother-of-pearl lilies.",
                    "I might, as a woman, have many thoughts,",
                    "But every one of them was practicable.",
                    "The people of Heu blame me,",
                    "But they are all childish and hasty in their conclusions.",
                ]
            ),
            "\n".join(
                [
                    "I would have gone through the country,",
                    "Amidst the wheat so luxuriant.",
                    "I would have carried the case before the great State.",
                    "On whom should I have relied? Who would come to the help of Wei?",
                    "Ye great officers and gentlemen,",
                    "Do not condemn me.",
                    "The hundred plans you think of",
                    "Are not equal to the course I was going to take.",
                ]
            ),
        ],
    },
    55: {
        "legge_section_alias": "Ke aou",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR pages 290-291 after removing running-title "
            "fragments and rejoining page-break lines."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Look at those recesses in the banks of the K'e,",
                    "With their green bamboos, so fresh and luxuriant!",
                    "There is our elegant and accomplished prince, —",
                    "As from the knife and the file,",
                    "As from the chisel and the polisher!",
                    "How grave is he and dignified!",
                    "How commanding and distinguished!",
                    "Never can he be forgotten!",
                ]
            ),
            "\n".join(
                [
                    "Look at those recesses in the banks of the K'e,",
                    "With their green bamboos, so strong and luxuriant!",
                    "There is our elegant and accomplished prince, —",
                    "With his ear-stoppers of beautiful pebbles,",
                    "And his cap glittering as with stars between the seams!",
                    "How grave is he and dignified!",
                    "How commanding and distinguished!",
                    "Our elegant and accomplished prince —",
                    "Never can he be forgotten!",
                ]
            ),
            "\n".join(
                [
                    "Look at those recesses in the banks of the K'e,",
                    "With their green bamboos, so dense together!",
                    "There is our elegant and accomplished prince, —",
                    "Pure as gold or as tin,",
                    "Soft and rich as a sceptre of jade!",
                    "How magnanimous is he and gentle!",
                    "There he is in his chariot with its two high sides!",
                    "Skilful is he at quips and jokes,",
                    "But how does he keep from rudeness in them!",
                ]
            ),
        ],
    },
    56: {
        "legge_section_alias": "Kaou pan",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR pages 295-297 by rejoining the stanza blocks "
            "split across the section boundary with 碩人."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "He has reared his hut by the stream in the valley,",
                    "That large man, so much at his ease.",
                    "Alone he sleeps, and wakes, and talks.",
                    "He swears he will never forget his true joy.",
                ]
            ),
            "\n".join(
                [
                    "He has reared his hut in the bend of the mound,",
                    "That large man, with such an air of indifference.",
                    "Alone, he sleeps and wakes, and sings.",
                    "He swears he will never pass from this spot.",
                ]
            ),
            "\n".join(
                [
                    "He has reared his hut on the level height,",
                    "That large man, so self-collected.",
                    "Alone, he sleeps and wakes, and sleeps again.",
                    "He swears he will never tell of his delight.",
                ]
            ),
        ],
    },
    57: {
        "legge_section_alias": "Shih jin",
        "review_note": (
            "Recovered the four stanza blocks from part-1 hOCR pages 297-301 after trimming the preceding 考槃 "
            "carry-over lines and preserving only the 碩人 verse text."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Large was she and tall,",
                    "In her embroidered robe, with a single garment over it: —",
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
                    "Her forehead cicada-like; her eyebrows like the silkworm moth;",
                    "What dimples, as she artfully smiled!",
                    "How beautiful were her clear black eyes!",
                    "O beautiful woman, so large and tall!",
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
    59: {
        "legge_section_alias": "Chuh kan",
        "review_note": (
            "Recovered the four stanza blocks from part-1 hOCR pages 303-304 after rejoining the final stanza "
            "lines split across the page break."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "With your long and tapering bamboo rods,",
                    "You angle in the K'e.",
                    "Do I not think of you?",
                    "But I am far away, and cannot get to you.",
                ]
            ),
            "\n".join(
                [
                    "The Ts'euen-yuen is on the left,",
                    "And the waters of the K'e are on the right.",
                    "But when a young lady goes away,",
                    "She leaves her brothers and parents.",
                ]
            ),
            "\n".join(
                [
                    "The waters of the K'e are on the right,",
                    "And the Ts'euen-yuen is on the left.",
                    "How shine the white teeth through the artful smiles!",
                    "How the girdle gems move to the measured steps!",
                ]
            ),
            "\n".join(
                [
                    "The waters of the K'e flow smoothly:",
                    "There are the oars of cedar",
                    "And the boats of pine.",
                    "Might I but go there in my carriage and ramble,",
                    "To dissipate my sorrow!",
                ]
            ),
        ],
    },
    61: {
        "legge_section_alias": "Ho kwang",
        "review_note": (
            "Recovered the two stanza blocks from part-1 hOCR pages 305-306 after removing page-head lines."
        ),
        "force_poem_alignment": False,
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
    62: {
        "legge_section_alias": "Pih he",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR pages 306-307 after removing page-head debris "
            "and preserving only the verse translation."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "Our chief's qualities are gentle and kind,",
                    "And his cap is well fitted by the seam.",
                    "He is to the king's service,",
                    "And I can find no means to cherish my hair.",
                ]
            ),
            "\n".join(
                [
                    "How can I get the herb for forgetfulness?",
                    "I would plant it on the north of my hall.",
                    "Would it then make me forget?",
                    "My heart is wounded with sadness.",
                ]
            ),
            "\n".join(
                [
                    "How is my chief so to be remembered,",
                    "While there is no year in which I see him?",
                    "How is my chief so to be remembered,",
                    "While there is no day in which I see him?",
                ]
            ),
        ],
    },
    63: {
        "legge_section_alias": "Yew hoo",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR pages 308-309 by rejoining the stanza that "
            "continues across the page boundary."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "There is a fox, solitary and suspicious,",
                    "At that deep ford of the K'e.",
                    "My heart is sad; —",
                    "That man has no lower garment.",
                ]
            ),
            "\n".join(
                [
                    "There is a fox, solitary and suspicious,",
                    "At that deep ford of the K'e.",
                    "My heart is sad; —",
                    "That man has no girdle.",
                ]
            ),
            "\n".join(
                [
                    "There is a fox, solitary and suspicious,",
                    "By the side there of the K'e.",
                    "My heart is sad; —",
                    "That man has no clothes.",
                ]
            ),
        ],
    },
    66: {
        "legge_section_alias": "Keun tsze yu yih",
        "review_note": (
            "Recovered the two stanza blocks from part-1 hOCR pages 314-315 after removing the intervening "
            "running-title line."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "My husband is away on service,",
                    "Not knowing the day of his return.",
                    "When the sheep and oxen come down from the hill,",
                    "How can I not think of him?",
                ]
            ),
            "\n".join(
                [
                    "My husband is away on service,",
                    "Not knowing the day of his return.",
                    "When the fowls roost in the evening,",
                    "How can I not think of him?",
                ]
            ),
        ],
    },
    67: {
        "legge_section_alias": "Keun tsze yang yang",
        "review_note": "Recovered the two stanza blocks from part-1 hOCR page 315 after removing page furniture.",
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "My husband is complacent and self-satisfied,",
                    "Moving about with his left hand occupied.",
                    "Complacent and self-satisfied is my husband,",
                    "And right is his heart.",
                ]
            ),
            "\n".join(
                [
                    "My husband is complacent and self-satisfied,",
                    "Moving about with his left hand occupied.",
                    "Complacent and self-satisfied is my husband,",
                    "And happy is his heart.",
                ]
            ),
        ],
    },
    68: {
        "legge_section_alias": "Yang che shwuy",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR pages 316-318 after trimming the trailing "
            "stanza that belongs to the following poem 中谷有蓷."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "The torrent carries bundles of thorns;",
                    "That person will not come to me.",
                    "He will not come to me,",
                    "And I languish, and am grieved.",
                ]
            ),
            "\n".join(
                [
                    "The torrent carries bundles of briers;",
                    "That person will not collect me.",
                    "He will not collect me,",
                    "And I languish, and am grieved.",
                ]
            ),
            "\n".join(
                [
                    "The torrent carries bundles of faggots;",
                    "That person will not comfort me.",
                    "He will not comfort me,",
                    "And I languish, and am grieved.",
                ]
            ),
        ],
    },
    70: {
        "legge_section_alias": "T'hoo yuen",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR pages 319-320 after removing catchword debris "
            "and preserving the verse blocks only."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "There is the hare! that which leads it is the snare.",
                    "When my king has no proper business,",
                    "Why should he reduce us all to such extremity?",
                    "He who called us to it, — from him shall come no good.",
                ]
            ),
            "\n".join(
                [
                    "There is the hare! in the midst of the snare.",
                    "When my king has no proper business,",
                    "Why should he reduce us all to such extremity?",
                    "He who called us to it, — from him shall come no blessing.",
                ]
            ),
            "\n".join(
                [
                    "There is the hare! on the side of the snare.",
                    "When my king has no proper business,",
                    "Why should he reduce us all to such extremity?",
                    "He who called us to it, — from him shall come no end.",
                ]
            ),
        ],
    },
    71: {
        "legge_section_alias": "Ko leih",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR pages 321-322 after removing running-title "
            "fragments and preserving only the poem translation."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "The dolichos grows luxuriant",
                    "On the branches of the jujube trees.",
                    "My brothers are all in a distant quarter,",
                    "And none of them will have me any more.",
                    "People of whom I ask, all say,",
                    "They are dead or gone away.",
                    "How can it be otherwise than that my heart should ache?",
                ]
            ),
            "\n".join(
                [
                    "The dolichos grows luxuriant",
                    "On the branches of the thorn trees.",
                    "My brothers are all in a distant quarter,",
                    "And there is no one of them in whom I can confide.",
                    "People of whom I ask, all say,",
                    "They are dead or gone away.",
                    "How can it be otherwise than that my heart should be grieved?",
                ]
            ),
            "\n".join(
                [
                    "The dolichos grows luxuriant",
                    "On the branches of the sour plum trees.",
                    "My brothers are all in a distant quarter,",
                    "And none of them will attend to me.",
                    "People of whom I ask, all say,",
                    "They are dead or gone away.",
                    "How can it be otherwise than that I should sigh?",
                ]
            ),
        ],
    },
    72: {
        "legge_section_alias": "Tsae koh",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR pages 322-323 after trimming page-head debris "
            "and preserving the verse lines only."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "One day gone by, when absent from you,",
                    "Seems like three months.",
                    "I gather and dress the dolichos; —",
                    "When shall I see you again?",
                ]
            ),
            "\n".join(
                [
                    "One day gone by, when absent from you,",
                    "Seems like three autumns.",
                    "I gather and dress the mugwort; —",
                    "When shall I see you again?",
                ]
            ),
            "\n".join(
                [
                    "One day gone by, when absent from you,",
                    "Seems like three years.",
                    "I gather and dress the lespedeza; —",
                    "When shall I see you again?",
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
                    "Although I do not go to you,",
                    "Why do you not continue your messages to me?",
                ]
            ),
            "\n".join(
                [
                    "O you with the blue strings to your girdle-gems,",
                    "Long, long do I think of you.",
                    "Although I do not go to you,",
                    "Why do you not come to me?",
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
    127: {
        "legge_section_alias": "Sze feeh",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR pages 393-394 after removing the running page header "
            "and keeping only the verse lines."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "His four iron-black horses are in very fine condition;",
                    "The six reins are in the hand of the charioteer.",
                    "The ruler's favourites",
                    "Follow him to the chase.",
                ]
            ),
            "\n".join(
                [
                    "The male animals of the season are made to present themselves,",
                    "The males in season, of very large size.",
                    "The ruler says, 'To the left of them;'",
                    "Then he lets go his arrows and hits.",
                ]
            ),
            "\n".join(
                [
                    "He rambles in the northern park;",
                    "His four horses display their training.",
                    "Light carriages, with bells at the horses' bits,",
                    "Convey the long and short-mouthed dogs.",
                ]
            ),
        ],
    },
    128: {
        "legge_section_alias": "Seaou jung",
        "review_note": (
            "Recovered the full poem block from part-1 hOCR pages 395-397 after restoring the omitted opening carriage "
            "line and retaining poem-level alignment because the witness prints the poem as one continuous block."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "[There is] his short war carriage; —",
                    "With the ridge-like end of its pole, elegantly bound in five",
                    "places;",
                    "With its slip rings and side straps;",
                    "And the traces attached by gilt rings to the masked transverse;",
                    "With its beautiful mat of tiger's skin, and its long naves;",
                    "With its piebalds, and horses with white left feet.",
                    "When I think of my husband [thus],",
                    "Looking bland and soft as a piece of jade;",
                    "Living there in his plank house;",
                    "It sends confusion into all the corners of my heart.",
                    "His mail-covered team moves in great harmony;",
                    "There are the trident spears with their gilt ends;",
                    "And the beautiful feather-figured shield;",
                    "With the tiger-skin bow-case, and the carved metal ornaments",
                    "on its front.",
                    "The two bows are placed in the case,",
                    "Bound with string to their bamboo frames.",
                    "I think of my husband,",
                    "When I lie down and rise up.",
                    "Tranquil and serene is the good man,",
                    "With his virtuous fame spread far and near.",
                ]
            ),
        ],
    },
    130: {
        "legge_section_alias": "Chung-nan",
        "review_note": (
            "Recovered the two stanza blocks from part-1 hOCR pages 399-400 after discarding the interleaved commentary "
            "line and preserving only the verse text."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "What are there on Chung-nan?",
                    "There are white firs and plum trees.",
                    "Our prince has arrived at it,",
                    "Wearing an embroidered robe over his fox-fur,",
                    "And with his countenance rouged as with vermilion.",
                    "May he prove a ruler indeed!",
                ]
            ),
            "\n".join(
                [
                    "What are there on Chung-nan?",
                    "There are nooks and open glades.",
                    "Our prince has arrived at it,",
                    "With the symbol of distinction embroidered on his lower skirt,",
                    "And the gems at his girdle emitting their tinkling.",
                    "May long life and an endless name be his?",
                ]
            ),
        ],
    },
    143: {
        "legge_section_alias": "Yueh chLuh",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR page 414 after correcting OCR slips and excluding the "
            "following poem title."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "The moon comes forth in her brightness;",
                    "How lovely is that beautiful lady!",
                    "O to have my deep longings for her relieved!",
                    "How anxious is my toiled heart!",
                ]
            ),
            "\n".join(
                [
                    "The moon comes forth in her splendour;",
                    "How attractive is that beautiful lady!",
                    "O to have my anxieties about her relieved!",
                    "How agitated is my toiled heart!",
                ]
            ),
            "\n".join(
                [
                    "The moon comes forth and shines;",
                    "How brilliant is that beautiful lady!",
                    "O to have the chains of my mind relaxed!",
                    "How miserable is my toiled heart!",
                ]
            ),
        ],
    },
    145: {
        "legge_section_alias": "Tsih jp'o",
        "review_note": (
            "Recovered the three stanza blocks from part-1 hOCR pages 415-416 after restoring the closing pillow line "
            "that the automatic verse-line heuristic had dropped."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "By the shores of that marsh,",
                    "There are rushes and lotus plants.",
                    "There is the beautiful lady; —",
                    "I am tortured for her, but what avails it ?",
                    "Waking or sleeping, I do nothing;",
                    "From my eyes and nose the water streams.",
                ]
            ),
            "\n".join(
                [
                    "By the shores of that marsh,",
                    "There are rushes and the valerian.",
                    "There is the beautiful lady,",
                    "Tall and large, and elegant.",
                    "Waking or sleeping, I do nothing;",
                    "My inmost heart is full of grief.",
                ]
            ),
            "\n".join(
                [
                    "By the shores of that marsh,",
                    "There are rushes and lotus flowers.",
                    "There is that beautiful lady,",
                    "Tall and large, and majestic.",
                    "Waking or sleeping, I do nothing;",
                    "On my side, on my back, with my face on the pillow, I lie.",
                ]
            ),
        ],
    },
    155: {
        "legge_section_alias": "鴟鴞",
        "review_note": (
            "Recovered the four stanza blocks from part-1 hOCR pages 435-437 after restoring the split opening and "
            "third-stanza closing lines from the witness."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "\n".join(
                [
                    "O owl, O owl,",
                    "You have taken my young ones; —",
                    "Do not [also] destroy my nest.",
                    "With love and with toil",
                    "I nourished them. — I am to",
                    "be pitied.",
                ]
            ),
            "\n".join(
                [
                    "Before the sky was dark with rain,",
                    "I gathered the roots of the mulberry tree,",
                    "And bound round and round my window and door.",
                    "Now ye people below,",
                    "Dare any of you despise my house?",
                ]
            ),
            "\n".join(
                [
                    "With my claws I tore and held.",
                    "Through the rushes which I gathered,",
                    "And all the materials I collected,",
                    "My mouth was all sore; —",
                    "I said to myself, 'I have not yet got my house complete.'",
                ]
            ),
            "\n".join(
                [
                    "My wings are all-injured;",
                    "My tail is all-broken;",
                    "My house is in a perilous condition;",
                    "It is tossed about in the wind and rain: —",
                    "I can but cry out with this note of alarm.",
                ]
            ),
        ],
    },
    157: {
        "legge_section_alias": "P:〇 f〇〇",
        "review_note": (
            "Recovered the five stanza blocks from part-1 hOCR pages 440-442 after restoring the duke-of-Chow lines "
            "that the automatic verse-line heuristic had dropped; kept poem-level alignment because the stanza "
            "structures do not match cleanly."
        ),
        "english_blocks": [
            "\n".join(
                [
                    "We broke our axes,",
                    "And we splintered our hatchets;",
                    "But the object of the duke of Chow, in marching to the east,",
                    "Was to put the four States to rights.",
                    "His compassion for us people",
                    "Is very great.",
                ]
            ),
            "\n".join(
                [
                    "We broke our axes,",
                    "And splintered our chisels;",
                    "But the object of the duke of Chow, in marching to the east,",
                    "Was to reform the four States.",
                    "His compassion for us people",
                    "Is very admirable.",
                ]
            ),
            "\n".join(
                [
                    "We broke our axes;",
                    "And splintered our clubs.",
                    "But the object of the duke of Chow, in marching to the east,",
                    "Was to save the alliance of the four States.",
                    "His compassion for us people",
                    "Is very excellent.",
                ]
            ),
            "\n".join(
                [
                    "In hewing the wood for an axe-handle, how do you proceed?",
                    "Without another axe it cannot be done.",
                    "In taking a wife, how do you proceed?",
                    "Without a go-between it cannot be done.",
                ]
            ),
            "\n".join(
                [
                    "In hewing an axe-handle, in hewing an axe-handle,",
                    "The pattern is not far off.",
                    "I see the lady,",
                    "And forthwith the vessels are arranged in rows.",
                ]
            ),
        ],
    },
}

AUTO_REVIEWED_LEGGE_OCR_OVERRIDES: dict[int, dict[str, Any]] = {
    77: {
        "line_replacements": {
            "Are^ there indeed none feasting?": "Are there indeed none feasting?",
        },
    },
    78: {
        "line_replacements": {
            "The reins are in his ^rasp like ribbons,": "The reins are in his grasp like ribbons,",
            "And with bared arms he seizes a ti^er,": "And with bared arms he seizes a tiger,",
            "O Shuh7 try not such sport again ;": "O Shuh, try not such sport again;",
            "Shun has gone hunting,": "Shuh has gone hunting,",
            "Shull has gone hunting.": "Shuh has gone hunting.",
            "His two insides have tlieir heads in a line,": "His two insides have their heads in a line,",
        },
    },
    76: {
        "line_replacements": {
            "0 Chung": "O Chung",
            "m}r": "my",
        },
    },
    79: {
        "line_replacements": {
            "The men of Tscing are in P^ang;": "The men of Ts'ing are in P'ang;",
            "The men of Ts4ing are in Seaou;": "The men of Ts'ing are in Seaou;",
            "Cho'v": "Chow",
        },
    },
    80: {
        "line_replacements": {
            "His lambs fur": "His lamb's fur",
            "\\vill": "will",
            "Ho'v": "How",
        },
    },
    88: {
        "line_replacements": {
            "0 Sir": "O Sir",
        },
    },
    89: {
        "keep_blocks": [0, 1],
        "review_note": (
            "Reviewed the part-1 hOCR witness directly and trimmed the following 風雨 carry-over blocks so only 東門之墠 "
            "remains in the exportable text."
        ),
    },
    93: {
        "line_replacements": {
            "Wliere": "Where",
            "tliey": "they",
            "silk7": "silk,",
            "coiifure": "coiffure",
        },
    },
    96: {
        "line_replacements": {
            "The court is full •": "The court is full.",
            "Bat it was not the east that was bright; —": "But it was not the east that was bright; —",
        },
        "review_note": (
            "Reviewed the part-1 hOCR witness directly, corrected the one obvious court-line OCR slip in the middle "
            "stanza, and restored the stanza-1 closing full stop after checking the public-domain transcription."
        ),
    },
    101: {
        "line_replacements": {
            "Ts(e": "Ts'e",
            "Ts4e": "Ts'e",
        },
    },
    104: {
        "line_replacements": {
            "Tsce": "Ts'e",
            "Ts4e": "Ts'e",
        },
        "review_note": "Reviewed the part-1 hOCR witness directly and dropped the trailing subdivision heading after the final verse stanza.",
    },
    113: {
        "drop_lines": ["rul 'ds"],
        "review_note": "Reviewed the part-1 hOCR witness directly and removed the stray non-verse OCR fragment between the opening and later stanzas.",
    },
    114: {
        "line_replacements": {
            "Let us fii^st think of the griefs that may arise;": "Let us first think of the griefs that may arise;",
        },
        "review_note": "Reviewed the part-1 hOCR witness directly and corrected the single obvious OCR corruption in the closing stanza.",
    },
    110: {
        "line_replacements": {
            "My brother is saying, (Alas! my younger brother, abroad on": "My brother is saying, Alas! my younger brother, abroad on",
        },
    },
    111: {
        "line_replacements": {
            "4I": "I",
            "Come, says one to another, I will return with you.": "Come, says one to another, I will return with you.",
        },
    },
    116: {
        "line_replacements": {
            "princel}r": "princely",
        },
        "review_note": "Reviewed the part-1 hOCR witness directly and removed the trailing ODES OF T‘ANG heading after the final stanza.",
    },
    105: {
        "line_replacements": {
            "AVith its screen of bamboos woven in squares, and its vermilion-": "With its screen of bamboos woven in squares, and its vermilion-",
            "And the daughter of Ts^ started on it in the evening.": "And the daughter of Ts'e started on it in the evening.",
            "And the daughter of Tsce is delighted and complacent.": "And the daughter of Ts'e is delighted and complacent.",
            "And the daughter of Ts4e moves on with unconcern.": "And the daughter of Ts'e moves on with unconcern.",
            "And the daughter of Ts^e moves on with unconcern.": "And the daughter of Ts'e moves on with unconcern.",
            "And the daughter of Ts^e proceeds at her ease,": "And the daughter of Ts'e proceeds at her ease.",
        },
    },
    117: {
        "review_note": (
            "Reviewed the part-1 hOCR witness directly, restored the opening pepper-plant refrain, and split the two "
            "verified stanzas for stanza-level export."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "The clusters of the pepper plant,\n"
            "Large and luxuriant, would fill a pint.\n"
            "That hero there\n"
            "Is large and peerless.\n"
            "O the pepper plant!\n"
            "How its shoots extend!",
            "The clusters of the pepper plant,\n"
            "Large and luxuriant, would fill both your hands.\n"
            "That hero there\n"
            "Is large and generous.\n"
            "O the pepper plant!\n"
            "How its shoots extend!",
        ],
    },
    126: {
        "line_replacements": {
            "He has many carriages, giving forth their lin-Un\\": "He has many carriages, giving forth their lin-lin.",
        },
    },
    133: {
        "line_replacements": {
            "I will prepare my bufFcoat and sharp weapons,": "I will prepare my buff-coat and sharp weapons,",
        },
    },
    134: {
        "line_replacements": {
            "I escorted my mother^ nephew,": "I escorted my mother's nephew,",
            "I escorted my mothers nephew ;": "I escorted my mother's nephew;",
        },
    },
    136: {
        "line_replacements": {
            "Yuen-k(ew": "Yuen-k'ew",
        },
    },
    137: {
        "line_replacements": {
            "Yuen-k^ew": "Yuen-k'ew",
            "You give me a stalk of the pepper plant •": "You give me a stalk of the pepper plant.",
        },
        "review_note": (
            "Reviewed the part-1 hOCR witness directly and restored the closing full stop in the final line after "
            "checking the public-domain transcription."
        ),
    },
    142: {
        "line_replacements": {
            "On the embankment are magpies5 nests ;": "On the embankment are magpies' nests;",
        },
        "drop_lines": ["; B C. 691 — 647), who believed slan-"],
    },
    146: {
        "line_replacements": {
            "In your lamb^ fur you saunter about;": "In your lamb's fur you saunter about;",
            "In your fox?s fur you hold your court.": "In your fox's fur you hold your court.",
            "In your lamVs fur you wander aimlessly about;": "In your lamb's fur you wander aimlessly about;",
            "In your fox^ fur you appear in your ball.": "In your fox's fur you appear in your hall.",
        },
    },
    148: {
        "keep_blocks": [0, 1, 2],
        "review_note": (
            "Reviewed the part-1 hOCR witness directly and trimmed the following 匪風 carry-over blocks so only 隰有萇楚 "
            "remains in the exportable text."
        ),
    },
    152: {
        "drop_lines": ["IV. Hea ts^euen. ,"],
        "review_note": "Reviewed the part-1 hOCR witness directly and removed the following 下泉 title from the final stanza block.",
    },
    161: {
        "english_blocks": [
            "With pleased sounds the deer call to one another,\n"
            "Eating the celery of the fields.\n"
            "I have here admirable guests;\n"
            "The lutes are struck, and the organ is blown for them; --\n"
            "The organ is blown till its tongues are all moving.\n"
            "The baskets of offerings also are presented to them.\n"
            "The men love me,\n"
            "And will show me the perfect path.",
            "With pleased sounds the deer call to one another,\n"
            "Eating the southernwood of the fields.\n"
            "I have here admirable guests,\n"
            "Whose virtuous fame is grandly brilliant.\n"
            "They show the people not to be mean;\n"
            "The officers have in them a pattern and model.\n"
            "I have good wine,\n"
            "Which my admirable guests drink, enjoying themselves.",
            "With pleased sounds the deer call to one another,\n"
            "Eating the salsola of the fields.\n"
            "I have here admirable guests,\n"
            "To feast and make glad their hearts.\n"
            "The pleasant sound of their lutes,\n"
            "The reverence of their deportment,\n"
            "The excellence of their virtuous fame,\n"
            "Make the people imitate them.\n"
            "They have good wine,\n"
            "By which they entertain their admirable guests,\n"
            "To feast and make glad their hearts.",
        ],
        "review_note": (
            "Reviewed the part-2 hOCR witness directly and restored the truncated final stanza after checking the "
            "public-domain CTI transcription for 小雅·鹿鳴 (AnoShih 2.1.161)."
        ),
    },
    163: {
        "english_blocks": [
            "Brilliant are the flowers,\n"
            "On those level heights and the low grounds.\n"
            "Complete and alert is the messenger, with his suite,\n"
            "Ever anxious lest he should not succeed.",
            "My horses are young;\n"
            "The six reins look as if they were moistened.\n"
            "I gallop them, and urge them on,\n"
            "Everywhere pushing my inquiries.",
            "My horses are piebald;\n"
            "The six reins are like silk.\n"
            "I gallop them, and urge them on,\n"
            "Everywhere seeking information and counsel.",
            "My horses are white and black-maned;\n"
            "The six reins look glossy.\n"
            "I gallop them and urge them on,\n"
            "Everywhere seeking information and advice.",
            "My horses are grey;\n"
            "The six reins are well in hand.\n"
            "I gallop them and urge them on,\n"
            "Everywhere seeking information and suggestions.",
        ],
        "review_note": (
            "Reviewed the part-2 hOCR witness directly and corrected the closing OCR damage in the final stanza after "
            "checking the public-domain CTI transcription for 小雅·皇皇者華 (AnoShih 2.1.163)."
        ),
    },
    164: {
        "english_blocks": [
            "The flowers of the cherry tree --\n"
            "Are they not gorgeously displayed?\n"
            "Of all the men in the world\n"
            "There are none equal to brothers.",
            "On the dreaded occasions of death and burial,\n"
            "It is brothers who greatly sympathize.\n"
            "When fugitives are collected on the heights and low grounds,\n"
            "They are brothers who will seek one another out.",
            "There is the wagtail on the level height; --\n"
            "When brothers are in urgent difficulties,\n"
            "Friends, though they may be good,\n"
            "Will only heave long sighs.",
            "Brothers may quarrel inside the walls,\n"
            "But they will oppose insult from without,\n"
            "When friends, however good they may be,\n"
            "Will not afford help.",
            "When death and disorder are past,\n"
            "And there are tranquillity and rest;\n"
            "Although they have brothers,\n"
            "Some reckon them not equal to friends.",
            "Your dishes may be set in array,\n"
            "And you may drink to satiety;\n"
            "But it is when your brothers are all present,\n"
            "That you are harmonious and happy, with child-like joy.",
            "Loving union with wife and children\n"
            "Is like the music of lutes;\n"
            "But it is the accord of brothers\n"
            "Which makes the harmony and happiness lasting.",
            "For the ordering of your family,\n"
            "For your joy in your wife and children,\n"
            "Examine this and study it; --\n"
            "Will you not find that it is truly so?",
        ],
        "review_note": (
            "Reviewed the part-2 hOCR witness directly, corrected the obvious OCR corruption in stanza 2, and restored "
            "the missing closing line in stanza 8 after checking the public-domain CTI transcription for 小雅·常棣 "
            "(AnoShih 2.1.164)."
        ),
    },
    179: {
        "review_note": (
            "Recovered the four stanza blocks for 蓼蕭 from the public-domain witness after the reviewed hOCR export "
            "collapsed the final stanza break and left an obvious OCR slip in the opening dew line."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "How long grows the southernwood,\n"
            "With the dew lying on it so bright!\n"
            "Now that I see my noble men,\n"
            "My heart is entirely satisfied.\n"
            "As we feast, we laugh and talk; --\n"
            "It is right they should have fame and prosperity!",
            "How long grows the southernwood,\n"
            "With the dew lying on it so abundantly!\n"
            "Now that I see my noble men,\n"
            "I appreciate their favour and their brightness.\n"
            "Their virtue is without taint of error; --\n"
            "May they live long, and not be forgotten!",
            "How high is the southernwood,\n"
            "All wet with the fallen dew!\n"
            "Now that I see my noble men,\n"
            "Grandly we feast, delighted and complacent.\n"
            "May their relations with their brothers be right!\n"
            "May they be happy in their excellent virtue to old age!",
            "How high is the southernwood,\n"
            "With the dew lying on it so richly!\n"
            "I have seen my noble men,\n"
            "With the ends of their reins hanging down,\n"
            "With the bells tinkling on their cross-boards and bits.\n"
            "May all happiness gather upon them.",
        ],
    },
    192: {
        "review_note": (
            "Recovered the four stanza blocks for 白駒 from the public-domain witness after the reviewed hOCR export "
            "picked up a trailing subdivision heading."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "Let the brilliant white colt\n"
            "Feed on the young growth of my vegetable garden.\n"
            "Tether it by the foot, tie it by the collar,\n"
            "To prolong this morning.\n"
            "So may its owner of whom I think\n"
            "Spend his time here at his ease!",
            "Let the brilliant white colt\n"
            "Feed on the bean sprouts of my vegetable garden.\n"
            "Tether it by the foot, tie it by the collar,\n"
            "To prolong this evening.\n"
            "So may its owner of whom I think\n"
            "Be here, an admired guest!",
            "If you with the brilliant white colt\n"
            "Would brightly come to me,\n"
            "You should be a duke, you should be a marquis,\n"
            "Enjoying yourself without end.\n"
            "Be on your guard against idly wandering;\n"
            "Deal vigorously with your thoughts of retirement.",
            "The brilliant white colt\n"
            "Is there in that empty valley,\n"
            "With a bundle of fresh grass.\n"
            "Its owner is like a gem.\n"
            "Do not make the news of you rare as gold and gems, --\n"
            "Indulging your purpose to abandon me.",
        ],
    },
    222: {
        "review_note": (
            "Recovered the four stanza blocks for 鴛鴦 from the public-domain witness after the reviewed hOCR export "
            "dropped the opening stanza and ran into the following KUI BIAN heading."
        ),
        "force_poem_alignment": False,
        "english_blocks": [
            "The Yellow ducks fly about,\n"
            "And are taken with hand-nets and spread-nets.\n"
            "May our sovereign live for ten thousand years,\n"
            "Enjoying the happiness and wealth which are his due!",
            "The Yellow ducks are on the dam,\n"
            "With their left wings gathered up.\n"
            "May our sovereign live for ten thousand years,\n"
            "Enjoying the happiness and wealth which are his due!",
            "The teams of steeds are in the stable,\n"
            "Fed with forage and grain.\n"
            "May our sovereign live for ten thousand years,\n"
            "Sustained in his happiness and wealth!",
            "The teams of steeds are in the stable,\n"
            "Fed with grain and forage.\n"
            "May our sovereign live for ten thousand years,\n"
            "In the comfort of his happiness and wealth!",
        ],
    },
    120: {
        "line_replacements": {
            "LamVs fur and leopard^ cuffs,": "Lamb's fur and leopard's cuffs,",
            "Yon use us with cruel unkindness.": "You use us with cruel unkindness.",
        },
        "review_note": "Reviewed the part-1 hOCR witness directly and corrected the obvious OCR damage in the repeated opening lines.",
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


def build_section_seed(
    poem: dict[str, Any],
    *,
    en_page_title: str,
    english_witness: str,
    verification_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        reviewed = REVIEWED_LEGGE_OCR_POEM_BLOCKS.get(poem["sort_key"])
        if reviewed is None:
            reviewed = build_auto_reviewed_hocr_entry(poem, verification_entry)
        translation_ref_label = reviewed.get("translation_ref_label") or poem["label"]
        return {
            "section_id": section_id_for_catalog_entry(poem),
            "label": poem["label"],
            "canonical_ref": poem["canonical_ref"],
            "sort_key": poem["sort_key"],
            "major_division": poem["major_division"],
            "subdivision": poem["subdivision"],
            "poem_number": poem["local_index"],
            "legge_section_alias": translation_ref_label,
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
            "force_poem_alignment": reviewed.get("force_poem_alignment", True),
            "review_note": reviewed.get("review_note"),
            "reviewed_ocr_notes": (
                "Reviewed Legge 1871 Internet Archive OCR extraction with stanza boundaries preserved for exact alignment."
                if not reviewed.get("force_poem_alignment", True)
                else (
                    "Poem-level fallback from reviewed Legge 1871 Internet Archive OCR extraction; "
                    "stanza breaks are preserved in the cleaned translation text, but the alignment stays "
                    "at poem scope until stanza-level OCR cleanup is safer."
                )
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
        verification_entry = verification_index[section_id_for_catalog_entry(poem)] if verification_index is not None else None
        english_witness = (
            "legge_ocr_reviewed"
            if (
                poem["sort_key"] in REVIEWED_LEGGE_OCR_POEM_BLOCKS
                or (verification_entry and verification_entry.get("verification_status") == "human_verified_ocr")
            )
            else "legge_hocr"
        )
        section_seed = build_section_seed(
            poem,
            en_page_title="James Legge, The She King (1871 hOCR fallback)",
            english_witness=english_witness,
            verification_entry=verification_entry,
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
    glossary_block_re = re.compile(r"^[\u3400-\u9fff]{1,8}[：:].+")
    glossary_marker_tokens = ("《", "》", "「", "」", "『", "』", "註", "注")

    def is_glossary_block(block: str) -> bool:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or not all(glossary_block_re.match(line) for line in lines):
            return False
        if any(token in block for token in glossary_marker_tokens):
            return True
        prefixes = {re.split(r"[：:]", line, maxsplit=1)[0] for line in lines}
        return len(lines) >= 2 and len(prefixes) > 1

    filtered_blocks = [
        block
        for block in cleaned_blocks
        if not is_glossary_block(block)
    ]
    cleaned_blocks = filtered_blocks or cleaned_blocks
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


def sanitize_reviewed_hocr_line(text: str) -> str:
    cleaned = normalize_english_line(text)
    cleaned = re.sub(r"^\d+[.)]?\s*", "", cleaned)
    cleaned = re.sub(r"^[cC4]+\s*(?=[A-Z])", "", cleaned)
    cleaned = re.sub(r"^0(?=\s+[A-Z])", "O", cleaned)
    cleaned = re.sub(r"^1(?=\s+[a-z])", "I", cleaned)
    cleaned = re.sub(r"([!?])\d+$", r"\1", cleaned)
    cleaned = cleaned.replace("；", ";").replace("，", ",")
    cleaned = cleaned.replace("[", "").replace("]", "")
    cleaned = (
        cleaned.replace("‘", "'")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
    )
    cleaned = cleaned.replace("/", "")
    cleaned = cleaned.rstrip("*•")
    return cleaned.strip(" \"'“”‘’")


def build_auto_reviewed_hocr_entry(
    poem: dict[str, Any],
    verification_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    blocks, legge_alias = extract_hocr_poem_blocks(poem)
    override = AUTO_REVIEWED_LEGGE_OCR_OVERRIDES.get(poem["sort_key"], {})
    ocr_part = "part-1" if poem["major_division"] == "國風" else "part-2"
    keep_blocks = override.get("keep_blocks")
    if keep_blocks:
        blocks = [blocks[index] for index in keep_blocks if index < len(blocks)]
    cleaned_blocks: list[str] = []
    override_blocks = override.get("english_blocks")
    if override_blocks:
        for block in override_blocks:
            cleaned_lines = [sanitize_reviewed_hocr_line(line) for line in str(block).splitlines()]
            cleaned_lines = [line for line in cleaned_lines if line]
            if cleaned_lines:
                cleaned_blocks.append("\n".join(cleaned_lines))
    else:
        drop_lines = set(override.get("drop_lines", []))
        line_replacements = override.get("line_replacements", {})
        for block in blocks:
            cleaned_lines = []
            for line in block.splitlines():
                cleaned = sanitize_reviewed_hocr_line(line)
                for before, after in line_replacements.items():
                    cleaned = cleaned.replace(before, after)
                if not cleaned or cleaned in drop_lines:
                    continue
                if re.match(r"^(?:ODES OF|PART I\.|FART I\.)", cleaned):
                    continue
                cleaned_lines.append(cleaned)
            if cleaned_lines:
                cleaned_blocks.append("\n".join(cleaned_lines))
    if not cleaned_blocks:
        cleaned_blocks = [poem["label"]]
    return {
        "legge_section_alias": legge_alias,
        "translation_ref_label": poem["label"],
        "review_note": (
            override.get("review_note")
            or f"Reviewed the {ocr_part} hOCR witness directly and kept only the verse lines needed for export."
        ),
        "force_poem_alignment": override.get(
            "force_poem_alignment",
            (verification_entry or {}).get("alignment_granularity") != "stanza",
        ),
        "english_blocks": cleaned_blocks,
    }


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
