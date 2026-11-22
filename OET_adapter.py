#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OET_adapter.py

A simple Tkinter GUI program to export customised versions of the
Open English Translation (OET) of the Bible from the ESFM source files in
https://github.com/Freely-Given-org/OpenEnglishTranslation--OET

Only uses the Python standard library (Python 3.11+ for tomllib).

Settings files (kept in the same folder as this program):
    globalSettings.toml     Source repository settings and remembered ("global") export answers
    XXX.export.toml         Named export settings sets

Output goes into exportedFiles/XXX/ (with ESFM/, USFM/, VPL/ subfolders only if
more than one file type is exported).
"""
import csv
import json
import re
import shutil
import subprocess
import tempfile
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog


PROGRAM_NAME = 'OET Adapter'
PROGRAM_VERSION = '0.2.0'

APP_FOLDER = Path(__file__).resolve().parent
GLOBAL_SETTINGS_PATH = APP_FOLDER / 'globalSettings.toml'
EXPORT_SETTINGS_SUFFIX = '.export.toml'
EXPORTED_FILES_FOLDER = APP_FOLDER / 'exportedFiles'

GITHUB_OWNER_REPO = 'Freely-Given-org/OpenEnglishTranslation--OET'
GITHUB_URL = f'https://github.com/{GITHUB_OWNER_REPO}'
GITHUB_CLONE_URL = f'{GITHUB_URL}.git'
GITHUB_BRANCH = 'main'
RAW_BASE_URL = f'https://raw.githubusercontent.com/{GITHUB_OWNER_REPO}/{GITHUB_BRANCH}/'
API_CONTENTS_URL = f'https://api.github.com/repos/{GITHUB_OWNER_REPO}/contents/'
REPO_FOLDER_NAME = 'OpenEnglishTranslation--OET'
PARALLEL_REPO_PATH = APP_FOLDER.parent / REPO_FOLDER_NAME
USER_AGENT = f'OET_adapter/{PROGRAM_VERSION}'

# Where the ESFM source files live in the OET repo
RV_FOLDER = 'translatedTexts/ReadersVersion'
LV_OT_FOLDER = 'derivedTexts/auto_edited_OT_ESFM'
LV_NT_FOLDER = 'derivedTexts/auto_edited_VLT_ESFM'
LV_DC_FOLDER = 'derivedTexts/auto_edited_DC_ESFM'
WORD_TABLE_FOLDER = RV_FOLDER # All the word tables are in here
NAMES_TABLE_PATH = f'{RV_FOLDER}/OET-RV_names_table.tsv'


# ---------------------------------------------------------------------------
# Book codes and orders (BOS book codes, as used in the OET ESFM filenames)
# ---------------------------------------------------------------------------

FRONT_BOOKS = ['FRT', 'INT']
BACK_BOOKS = ['XXA', 'XXB', 'XXC', 'XXD', 'XXE', 'XXF', 'XXG', 'CNC', 'GLS', 'GLO', 'TDX', 'NDX', 'OTH', 'BAK']
OT_BOOKS_TRADITIONAL = ['GEN', 'EXO', 'LEV', 'NUM', 'DEU', 'JOS', 'JDG', 'RUT', 'SA1', 'SA2', 'KI1', 'KI2',
                        'CH1', 'CH2', 'EZR', 'NEH', 'EST', 'JOB', 'PSA', 'PRO', 'ECC', 'SNG', 'ISA', 'JER',
                        'LAM', 'EZE', 'DAN', 'HOS', 'JOL', 'AMO', 'OBA', 'JNA', 'MIC', 'NAH', 'HAB', 'ZEP',
                        'HAG', 'ZEC', 'MAL']
DC_BOOKS_TRADITIONAL = ['TOB', 'JDT', 'ESG', 'ESA', 'WIS', 'SIR', 'BAR', 'LJE', 'DAG', 'DNG', 'PAZ', 'SUS',
                        'BEL', 'MA1', 'MA2', 'MA3', 'MA4', 'GES', 'ES1', 'LES', 'ES2', 'MAN', 'PS2', 'PSS',
                        'ODE', 'LAO']
NT_BOOKS_TRADITIONAL = ['MAT', 'MRK', 'LUK', 'JHN', 'ACT', 'ROM', 'CO1', 'CO2', 'GAL', 'EPH', 'PHP', 'COL',
                        'TH1', 'TH2', 'TI1', 'TI2', 'TIT', 'PHM', 'HEB', 'JAM', 'PE1', 'PE2', 'JN1', 'JN2',
                        'JN3', 'JDE', 'REV']
# OET-RV order (from OpenBibleData createPages/settings.py)
OT_BOOKS_OET = ['GEN', 'EXO', 'LEV', 'NUM', 'DEU', 'JOB', 'JOS', 'JDG', 'RUT', 'SA1', 'SA2', 'PSA', 'AMO',
                'HOS', 'KI1', 'KI2', 'CH1', 'CH2', 'PRO', 'ECC', 'SNG', 'JOL', 'MIC', 'ISA', 'ZEP', 'HAB',
                'JER', 'LAM', 'JNA', 'NAH', 'OBA', 'DAN', 'EZE', 'EZR', 'EST', 'NEH', 'HAG', 'ZEC', 'MAL']
DC_BOOKS_OET = ['PS2', 'WIS', 'TOB', 'MAN', 'BAR', 'LJE', 'DNG', 'DAG', 'SUS', 'PAZ', 'BEL', 'GES', 'ES1',
                'LES', 'ES2', 'ESG', 'ESA', 'JDT', 'MA3', 'SIR', 'MA1', 'MA2', 'MA4', 'PSS', 'ODE']
NT_BOOKS_OET = ['JHN', 'MRK', 'MAT', 'LUK', 'ACT', 'JAM', 'GAL', 'TH1', 'TH2', 'CO1', 'CO2', 'ROM', 'COL',
                'LAO', # Laodiceans goes after Colossians in the OET order (but it's in the DC section)
                'PHM', 'EPH', 'PHP', 'TI1', 'TIT', 'PE1', 'PE2', 'TI2', 'HEB', 'JDE', 'JN1', 'JN2', 'JN3', 'REV']

TRADITIONAL_ORDER = FRONT_BOOKS + OT_BOOKS_TRADITIONAL + DC_BOOKS_TRADITIONAL + NT_BOOKS_TRADITIONAL + BACK_BOOKS
OET_RV_ORDER = FRONT_BOOKS + OT_BOOKS_OET + DC_BOOKS_OET + NT_BOOKS_OET + BACK_BOOKS

# BOS code -> USFM book abbreviation (only where they differ)
BOS_TO_USFM = {'SA1': '1SA', 'SA2': '2SA', 'KI1': '1KI', 'KI2': '2KI', 'CH1': '1CH', 'CH2': '2CH',
               'EZE': 'EZK', 'JNA': 'JON', 'NAH': 'NAM', 'JAM': 'JAS', 'JDE': 'JUD',
               'CO1': '1CO', 'CO2': '2CO', 'TH1': '1TH', 'TH2': '2TH', 'TI1': '1TI', 'TI2': '2TI',
               'PE1': '1PE', 'PE2': '2PE', 'JN1': '1JN', 'JN2': '2JN', 'JN3': '3JN',
               'MA1': '1MA', 'MA2': '2MA', 'MA3': '3MA', 'MA4': '4MA', 'GES': '1ES', 'LES': '2ES',
               'ES1': '1ES', 'ES2': '2ES', 'ESA': 'ADE', 'PAZ': 'S3Y', 'DNG': 'DAG', 'ODE': 'ODA',
               'GLS': 'GLO'}


def book_section(BBB):
    """ Returns 'FRT', 'OT', 'DC', 'NT' or 'BAK'. """
    if BBB in FRONT_BOOKS: return 'FRT'
    if BBB in BACK_BOOKS: return 'BAK'
    if BBB in OT_BOOKS_TRADITIONAL: return 'OT'
    if BBB in NT_BOOKS_TRADITIONAL: return 'NT'
    return 'DC' # including LAO and anything unknown


# Standard USFM (Paratext) two-character book numbers, keyed by USFM book abbreviation
USFM_BOOK_NUMBERS = {
    'GEN': '01', 'EXO': '02', 'LEV': '03', 'NUM': '04', 'DEU': '05', 'JOS': '06', 'JDG': '07', 'RUT': '08',
    '1SA': '09', '2SA': '10', '1KI': '11', '2KI': '12', '1CH': '13', '2CH': '14', 'EZR': '15', 'NEH': '16',
    'EST': '17', 'JOB': '18', 'PSA': '19', 'PRO': '20', 'ECC': '21', 'SNG': '22', 'ISA': '23', 'JER': '24',
    'LAM': '25', 'EZK': '26', 'DAN': '27', 'HOS': '28', 'JOL': '29', 'AMO': '30', 'OBA': '31', 'JON': '32',
    'MIC': '33', 'NAM': '34', 'HAB': '35', 'ZEP': '36', 'HAG': '37', 'ZEC': '38', 'MAL': '39',
    'MAT': '41', 'MRK': '42', 'LUK': '43', 'JHN': '44', 'ACT': '45', 'ROM': '46', '1CO': '47', '2CO': '48',
    'GAL': '49', 'EPH': '50', 'PHP': '51', 'COL': '52', '1TH': '53', '2TH': '54', '1TI': '55', '2TI': '56',
    'TIT': '57', 'PHM': '58', 'HEB': '59', 'JAS': '60', '1PE': '61', '2PE': '62', '1JN': '63', '2JN': '64',
    '3JN': '65', 'JUD': '66', 'REV': '67',
    'TOB': '68', 'JDT': '69', 'ESG': '70', 'WIS': '71', 'SIR': '72', 'BAR': '73', 'LJE': '74', 'S3Y': '75',
    'SUS': '76', 'BEL': '77', '1MA': '78', '2MA': '79', '3MA': '80', '4MA': '81', '1ES': '82', '2ES': '83',
    'MAN': '84', 'PS2': '85', 'ODA': '86', 'PSS': '87', 'JSA': '88', 'JDB': '89', 'TBS': '90', 'SST': '91',
    'DNT': '92', 'BLT': '93', 'XXA': '94', 'XXB': '95', 'XXC': '96', 'XXD': '97', 'XXE': '98', 'XXF': '99',
    'FRT': 'A0', 'BAK': 'A1', 'OTH': 'A2', '3ES': 'A3', 'EZA': 'A4', '5EZ': 'A5', '6EZ': 'A6', 'INT': 'A7',
    'CNC': 'A8', 'GLO': 'A9', 'TDX': 'B0', 'NDX': 'B1', 'DAG': 'B2', 'PS3': 'B3', '2BA': 'B4', 'LBA': 'B5',
    'JUB': 'B6', 'ENO': 'B7', '1MQ': 'B8', '2MQ': 'B9', '3MQ': 'C0', 'REP': 'C1', '4BA': 'C2', 'LAO': 'C3',
}


def usfm_code(BBB, text=''):
    """ Get the uppercase USFM book abbreviation, preferably from the \\id line. """
    match = re.match(r'\\id ([0-9A-Za-z]{3})\b', text)
    if match:
        return match.group(1).upper()
    return BOS_TO_USFM.get(BBB, BBB)


# ---------------------------------------------------------------------------
# Minimal TOML writing (tomllib can only read)
# ---------------------------------------------------------------------------

def toml_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple)):
        return '[' + ', '.join(toml_value(v) for v in value) + ']'
    return json.dumps(str(value), ensure_ascii=False) # JSON strings are valid TOML basic strings


def write_toml(path, data, header=''):
    """ Writes a dict with simple values and (one level of) sub-tables. """
    lines = [f'# {line}' for line in header.split('\n')] if header else []
    for key, value in data.items():
        if not isinstance(value, dict):
            lines.append(f'{key} = {toml_value(value)}')
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f'\n[{key}]')
            for subkey, subvalue in value.items():
                lines.append(f'{subkey} = {toml_value(subvalue)}')
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8')


def read_toml(path):
    try:
        with open(path, 'rb') as tomlFile:
            return tomllib.load(tomlFile)
    except FileNotFoundError:
        return {}


# ---------------------------------------------------------------------------
# Export settings questions
# ---------------------------------------------------------------------------

ALL_SECTIONS = ['FRT', 'OT', 'DC', 'NT', 'BAK']
ALL_FORMATS = ['ESFM', 'USFM', 'VPL']


def rv_included(answers):
    return answers.get('version', 'RV') in ('RV', 'BOTH')


class Question:
    def __init__(self, key, label, prompt, kind, options, default, applies=lambda answers: True):
        self.key, self.label, self.prompt, self.kind = key, label, prompt, kind
        self.options, self.default, self.applies = options, default, applies # options are (value, text) pairs

    def answer_text(self, value):
        texts = dict(self.options)
        if self.kind == 'check':
            return 'ALL' if set(value) == {v for v, _t in self.options} \
                else ', '.join(texts.get(v, v) for v in value)
        return texts.get(value, str(value))


QUESTIONS = [
    Question('version', 'Version(s)', 'Which OET version(s) do you want to export?', 'radio',
             [('RV', 'OET-RV (Readers’ Version)'), ('LV', 'OET-LV (Literal Version)'), ('BOTH', 'Both RV and LV')],
             'RV'),
    Question('sections', 'Books', 'Which parts of the Bible do you want to export?', 'check',
             [('FRT', 'Front matter'), ('OT', 'Old Testament'), ('DC', 'Deuterocanon / Apocrypha'),
              ('NT', 'New Testament'), ('BAK', 'Back matter')],
             list(ALL_SECTIONS)),
    Question('book_order', 'Book order', 'Which book order do you want?', 'radio',
             [('OET-RV', 'OET-RV book order'), ('traditional', 'Traditional book order')],
             'OET-RV', applies=rv_included),
    Question('divine_name', 'Divine name', 'How should the divine name be shown in the OET-RV?', 'radio',
             [('Yahweh', 'Leave ‘Yahweh’'), ('LORD', 'Change to ‘the LORD’ (with ‘ORD’ in small caps)')],
             'Yahweh', applies=rv_included),
    Question('names', 'Names', 'Which names should be used in the OET-RV?', 'radio',
             [('RV', 'Use the OET-RV names'), ('traditional', 'Change back to traditional names only')],
             'RV', applies=rv_included),
    Question('word_numbers', 'Word numbers', 'Do you want the ESFM word numbers included?', 'radio',
             [('remove', 'Remove word numbers (and the WORDTABLE line)'),
              ('keep', 'Include word numbers (ESFM export only)')],
             'remove'),
    Question('formats', 'File types', 'Which file types do you want to export?', 'check',
             [('ESFM', 'ESFM files'), ('USFM', 'USFM files'), ('VPL', 'VPL (verse-per-line) files')],
             ['USFM'], applies=lambda answers: answers.get('word_numbers') == 'remove'),
]
QUESTIONS_BY_KEY = {q.key: q for q in QUESTIONS}


def effective_answers(answers):
    """ Fill in the implied answers for questions that weren't applicable. """
    result = {q.key: answers.get(q.key, q.default) for q in QUESTIONS}
    if not rv_included(result):
        result['book_order'] = 'traditional'
        result['divine_name'] = 'Yahweh'
        result['names'] = 'RV'
    if result['word_numbers'] == 'keep':
        result['formats'] = ['ESFM']
    result['sections'] = [s for s in ALL_SECTIONS if s in result['sections']]
    result['formats'] = [f for f in ALL_FORMATS if f in result['formats']]
    return result


def settings_name(answers):
    """ Makes a name like RVLV_ALLBks_RVOrder_LORD_TradNames_NoWordNums_ALLFormats """
    a = effective_answers(answers)
    parts = [{'RV': 'RV', 'LV': 'LV', 'BOTH': 'RVLV'}[a['version']]]
    if a['sections'] == ALL_SECTIONS:
        parts.append('ALLBks')
    else:
        parts.append(''.join({'FRT': 'Front', 'BAK': 'Back'}.get(s, s) for s in a['sections']) + 'Bks')
    if rv_included(a):
        parts.append('RVOrder' if a['book_order'] == 'OET-RV' else 'TradOrder')
        parts.append(a['divine_name'])
        parts.append('RVNames' if a['names'] == 'RV' else 'TradNames')
    parts.append('WordNums' if a['word_numbers'] == 'keep' else 'NoWordNums')
    parts.append('ALLFormats' if a['formats'] == ALL_FORMATS else ''.join(a['formats']))
    return '_'.join(parts)


# ---------------------------------------------------------------------------
# Source files: either a local clone of the OET repo, or temporary downloads
# ---------------------------------------------------------------------------

class Source:
    def __init__(self, mode, repo_path=None, log=print):
        self.mode, self.log = mode, log
        self.repo_path = Path(repo_path) if repo_path else None
        self.temp_dir = None
        self.dir_cache = {}

    def describe(self):
        if self.mode == 'local':
            return str(self.repo_path)
        return 'Temporary downloads from GitHub (as needed)'

    def _temp_path(self):
        if self.temp_dir is None:
            self.temp_dir = tempfile.TemporaryDirectory(prefix='OET_adapter_')
        return Path(self.temp_dir.name)

    def list_dir(self, rel_folder):
        """ Returns a list of filenames in the given repo folder. """
        if rel_folder in self.dir_cache:
            return self.dir_cache[rel_folder]
        if self.mode == 'local':
            folder = self.repo_path / rel_folder
            names = sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []
        else:
            self.log(f'Listing {rel_folder}/ on GitHub…')
            request = urllib.request.Request(f'{API_CONTENTS_URL}{rel_folder}?ref={GITHUB_BRANCH}',
                                             headers={'User-Agent': USER_AGENT})
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    names = sorted(entry['name'] for entry in json.load(response) if entry['type'] == 'file')
            except urllib.error.HTTPError as err:
                if err.code == 404:
                    names = []
                else:
                    raise
        self.dir_cache[rel_folder] = names
        return names

    def get_path(self, rel_path):
        """ Returns a local Path for the repo file (downloading it first if necessary). """
        if self.mode == 'local':
            return self.repo_path / rel_path
        local_path = self._temp_path() / rel_path
        if not local_path.exists():
            self.log(f'  Downloading {rel_path}…')
            local_path.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(RAW_BASE_URL + rel_path, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(request, timeout=300) as response, open(local_path, 'wb') as outFile:
                shutil.copyfileobj(response, outFile)
        return local_path

    def read_text(self, rel_path):
        return self.get_path(rel_path).read_text(encoding='utf-8')


def find_book_files(source, VV):
    """ Returns a dict of BOS book code -> repo-relative ESFM path for OET-RV or OET-LV. """
    folders = [RV_FOLDER] if VV == 'RV' else [LV_OT_FOLDER, LV_NT_FOLDER, LV_DC_FOLDER]
    books = {}
    for folder in folders:
        for name in source.list_dir(folder):
            match = re.fullmatch(rf'OET-{VV}_([0-9A-Z]{{3}})\.ESFM', name)
            if match:
                books.setdefault(match.group(1), f'{folder}/{name}')
    return books


# ---------------------------------------------------------------------------
# Text conversions
# ---------------------------------------------------------------------------

WORD_NUMBER_REGEX = re.compile(r'¦[0-9]+')
APOSTROPHES = "'’"
NAME_CHARS = r"[^\W_][\w'’\-]*"  # A name token (letters, digits, apostrophes, hyphens)

# Character markers (opened and closed) -- used to decide whether we need \+nd nesting
CHARACTER_MARKERS = {'add', 'nd', 'wj', 'bk', 'k', 'qs', 'qac', 'sc', 'em', 'it', 'bd', 'bdit', 'no', 'tl',
                     'sup', 'untr', 'w', 'pn', 'png', 'addpn', 'ior', 'iqt', 'jmp', 'qt', 'ord', 'sls', 'rq',
                     'dc', 'sig', 'lit', 'rb', 'wg', 'wh', 'wa', 'ca', 'va', 'vp', 'fig'}
NOTE_MARKERS = {'f', 'fe', 'ef', 'x', 'ex'}
MARKER_REGEX = re.compile(r'\\(\+?)([a-z]+[0-9]*)(\*?)')


def marker_stack(prefix):
    """ Returns the list of character/note markers still open at the end of prefix. """
    stack = []
    for match in MARKER_REGEX.finditer(prefix):
        marker, closing = match.group(2), match.group(3)
        if marker in CHARACTER_MARKERS or marker in NOTE_MARKERS:
            if closing:
                if marker in stack: # pop back to the matching opener
                    while stack and stack.pop() != marker:
                        pass
            else:
                stack.append(marker)
    return stack


def remove_word_numbers(text):
    """ Remove ESFM word numbers and the \\rem WORDTABLE line. """
    text = re.sub(r'^\\rem WORDTABLE .*\n', '', text, flags=re.MULTILINE)
    return WORD_NUMBER_REGEX.sub('', text)


# --- Yahweh -> the LORD -----------------------------------------------------

YAHWEH_REGEX = re.compile(r"(?<![\w\-])Yahweh((?:['’]s)?)((?:¦[0-9]+)?)(?![\w\-])")
SKIP_LINE_MARKERS_FOR_LORD = ('\\id', '\\ide', '\\usfm', '\\rem', '\\h ', '\\toc', '\\mt', '\\i', '\\periph')


def clean_for_context(text):
    """ Remove notes, verse numbers, markers and word numbers so we can examine the words. """
    text = re.sub(r'\\(f|fe|ef|x|ex) .*?\\\1\*', ' ', text)
    text = re.sub(r'\\[vc] \S+', ' ', text)
    text = re.sub(r'\\\+?[a-z]+[0-9]*\*?', ' ', WORD_NUMBER_REGEX.sub('', text))
    return re.sub(r'\s+', ' ', text)


SENTENCE_END_CHARS = ('.', '?', '!')
OPENING_CHARS = ' ≈“‘"('


def change_yahweh_to_lord(text, BBB):
    """
    Change 'Yahweh' to 'the \\nd Lord\\nd*' (USFM \\nd renders as L + small-caps ORD).

    Heuristics:
        'The' at the start of a sentence (including after a previous line that ended a sentence),
        no article for vocatives
            (after 'O'/'Oh', ', Yahweh,', or a sentence-initial 'Yahweh,' not followed by 'the'),
        skips book introductions, footnotes and cross-references, quoted mentions like ‘Yahweh’,
            and hyphenated compound names.
    """
    if BBB in FRONT_BOOKS or BBB in BACK_BOOKS:
        return text
    newLines = []
    previousEndedSentence = True
    for line in text.split('\n'):
        if line.startswith(SKIP_LINE_MARKERS_FOR_LORD):
            newLines.append(line)
            continue
        marker = re.match(r'\\([a-z]+[0-9]*)', line)
        isHeading = bool(marker and (marker.group(1) in ('c', 'd', 'r', 'sp', 'cl', 'b')
                                     or marker.group(1).startswith(('s', 'm')))
                         and marker.group(1) not in ('m', 'mi')) # (\m is a paragraph)
        if isHeading:
            previousEndedSentence = True
        if 'Yahweh' not in line:
            newLines.append(line)
            cleanLine = clean_for_context(line).rstrip(' ”’")')
            if cleanLine.strip() and not isHeading:
                previousEndedSentence = cleanLine.endswith(SENTENCE_END_CHARS + (':',))
            continue
        result, pos = '', 0
        for match in YAHWEH_REGEX.finditer(line):
            prefix, after = line[:match.start()], line[match.end():]
            result += line[pos:match.start()]
            pos = match.end()
            stack = marker_stack(prefix)
            if any(m in NOTE_MARKERS for m in stack) \
            or (prefix.endswith('‘') and after.startswith('’')): # a mention, not a use
                result += match.group(0)
                continue
            possessive, wordNumber = match.group(1), match.group(2)
            # Are we directly inside a \nd field?
            ndOpen = bool(re.search(r'\\\+?nd $', prefix) and re.match(r'\\\+?nd\*', after))
            cleanPrefix = clean_for_context(prefix).rstrip()
            cleanAfter = clean_for_context(after).lstrip()
            strippedPrefix = cleanPrefix.strip(OPENING_CHARS)
            sentenceInitial = (not strippedPrefix and previousEndedSentence) \
                              or (strippedPrefix and (cleanPrefix.rstrip(OPENING_CHARS).endswith(SENTENCE_END_CHARS)
                                                      or cleanPrefix.endswith(('“', '‘'))))
            vocative = bool(re.search(r'\b(O|Oh|oh|Ah|ah)$', cleanPrefix)) \
                       or (cleanPrefix.endswith(',') and cleanAfter.startswith((',', '.', '!', '?', ';', '—', '–'))) \
                       or (bool(sentenceInitial) and not possessive and cleanAfter.startswith(',')
                           and not re.match(r',\s*the\b', cleanAfter))
            article = '' if vocative else ('The ' if sentenceInitial else 'the ')
            plus = '+' if [m for m in stack if not (ndOpen and m == 'nd')] else ''
            if ndOpen: # Replace the whole \nd Yahweh\nd* field
                opener = re.search(r'\\\+?nd $', prefix).group(0)
                closer = re.match(r'\\\+?nd\*', after).group(0)
                result = result[:-len(opener)]
                pos += len(closer)
            result += f'{article}\\{plus}nd Lord{possessive}{wordNumber}\\{plus}nd*'
        result += line[pos:]
        newLines.append(result)
        cleanLine = clean_for_context(line).rstrip(' ”’")')
        if cleanLine.strip():
            previousEndedSentence = cleanLine.endswith(SENTENCE_END_CHARS + (':',))
        if isHeading:
            previousEndedSentence = True
    return '\n'.join(newLines)


# --- OET-RV names -> traditional names ---------------------------------------

def normalise_apostrophes(name):
    return name.replace('’', "'")


class NamesTable:
    """ Loads OET-RV_names_table.tsv and works out which RV names map unambiguously. """

    def __init__(self, tsv_text):
        allTrads = {} # (segment, RVName) -> set of TraditionalNames (including identical ones)
        self.anyTrads = {} # RVName -> set of traditional names (any segment)
        for row in csv.DictReader(tsv_text.splitlines(), delimiter='\t'):
            rvName = normalise_apostrophes((row.get('RVName') or '').strip())
            trad = normalise_apostrophes((row.get('TraditionalName') or '').strip())
            segment = (row.get('Segment') or '').strip()
            if not rvName or not trad:
                continue
            allTrads.setdefault((segment, rvName), set()).add(trad)
            self.anyTrads.setdefault(rvName, set()).add(trad)
        self.unambiguous = {} # segment -> {RVName: TraditionalName}
        for (segment, rvName), trads in allTrads.items():
            if len(trads) == 1:
                trad = next(iter(trads))
                if trad != rvName:
                    self.unambiguous.setdefault(segment, {})[rvName] = trad
        # For front/back matter, use names that are unambiguous in all segments
        combined = {}
        for rvName, trads in self.anyTrads.items():
            if len(trads) == 1 and next(iter(trads)) != rvName:
                combined[rvName] = next(iter(trads))
        self.unambiguous['ALL'] = combined

    def lookup(self, segment):
        return self.unambiguous.get(segment, {})


EXPLANATION_REGEX = re.compile(r' ?\\(\+?)add !(.*?)\\\1add\*(\))?')
NOT_A_NAME_REGEX = re.compile(r"^(Grk|Heb|Hebrew|Greek|Lat|Latin|Aram|Aramaic|LXX|Syr|Syriac|or|i\.e|e\.g)\b")
PRECEDING_NAME_REGEX = re.compile(rf"(?<![\w'’\-])({NAME_CHARS})((?:¦[0-9]+)?)((?:\\\+?[a-z]+[0-9]*\*)*)\s*$")
NAME_TOKEN_REGEX = re.compile(rf"(?<![\w'’\-\\¦])({NAME_CHARS})")


def explanation_traditional_name(content):
    """ Gets the traditional name out of an \\add !(…) explanation (or None). """
    content = WORD_NUMBER_REGEX.sub('', content).strip().removeprefix('(').removesuffix(')').strip()
    first = content.split(';')[0].strip()
    if not first or NOT_A_NAME_REGEX.match(first) or not first[0].isupper():
        return None
    return normalise_apostrophes(first)


def split_possessive(token):
    """ Returns (base, suffix) e.g. ("Ya'akov", "'s"). """
    for suffix in ("'s", "’s", "'", "’"):
        if token.endswith(suffix) and len(token) > len(suffix):
            return token[:-len(suffix)], suffix
    return token, ''


def change_to_traditional_names(text, BBB, namesTable):
    """
    Change OET-RV names back to traditional names.

    1/ Where the text has an explanation like `Yeshua \\add !(Jesus; Grk. Yesus)\\add*`,
        the whole thing becomes `Jesus`, and that choice is reused for later bare 'Yeshua' in the book.
    2/ Other names are changed using OET-RV_names_table.tsv but only where the table
        gives one unambiguous traditional name (for that OT/NT/DC segment).
    3/ Forms like `Havah/Eve` become `Eve`.
    All other \\add !(…) explanations are removed.
    """
    section = book_section(BBB)
    segment = section if section in ('OT', 'NT', 'DC') else 'ALL'
    tableMap = namesTable.lookup(segment)
    multiwordNames = sorted((n for n in tableMap if ' ' in n), key=len, reverse=True)
    multiwordRegex = re.compile(r"(?<![\w'’\-])(" + '|'.join(re.escape(n) for n in multiwordNames)
                                + r")(?![\w'’\-])") if multiwordNames else None

    # Pass 1: find the first explained traditional name for each RV name in this book
    #   (so we can use it for any occurrences before the first explanation)
    contextMap = {}
    for line in text.split('\n'):
        if line.startswith('\\rem'):
            continue
        for match in EXPLANATION_REGEX.finditer(line):
            trad = explanation_traditional_name(match.group(2))
            preceding = PRECEDING_NAME_REGEX.search(WORD_NUMBER_REGEX.sub('', line[:match.start()]))
            if trad and preceding and preceding.group(1)[0].isupper():
                rvBase, _ = split_possessive(normalise_apostrophes(preceding.group(1)))
                tradBase, _ = split_possessive(trad)
                contextMap.setdefault(rvBase, tradBase)

    def replace_token(token, currentMap):
        """ Returns the traditional form of the name token (or None if no change). """
        normToken = normalise_apostrophes(token)
        for candidate, suffix in ((normToken, ''), split_possessive(normToken)):
            if candidate in currentMap:
                return currentMap[candidate] + suffix
            if candidate in tableMap:
                return tableMap[candidate] + suffix
        return None

    def bare_names_pass(segmentText, currentMap):
        """ Replace bare names in a piece of text which contains no explanations. """
        if '\\x ' in segmentText: # Don't change book abbreviations in cross-references
            parts = re.split(r'(\\x .*?\\x\*)', segmentText)
            return ''.join(part if part.startswith('\\x ') else bare_names_pass(part, currentMap) for part in parts)
        if multiwordRegex:
            segmentText = multiwordRegex.sub(lambda m: tableMap[normalise_apostrophes(m.group(1))], segmentText)
        result, pos = '', 0
        for match in NAME_TOKEN_REGEX.finditer(segmentText):
            token = match.group(1)
            if not token[0].isupper() or match.start() < pos: # (could be the 2nd part of 'Havah/Eve')
                continue
            result += segmentText[pos:match.start()]
            pos = match.end()
            # Handle 'Havah/Eve' style
            slashMatch = re.match(rf"/({NAME_CHARS})", segmentText[pos:])
            if slashMatch:
                rvBase, _ = split_possessive(normalise_apostrophes(token))
                other = normalise_apostrophes(slashMatch.group(1))
                otherBase, _ = split_possessive(other)
                if otherBase in namesTable.anyTrads.get(rvBase, ()) or otherBase == currentMap.get(rvBase):
                    result += slashMatch.group(1)
                    pos += slashMatch.end()
                    continue
            replacement = replace_token(token, currentMap)
            result += replacement if replacement else token
        return result + segmentText[pos:]

    # Pass 2: make the changes
    currentMap = dict(contextMap)
    newLines = []
    for line in text.split('\n'):
        if line.startswith(('\\rem', '\\id', '\\ide', '\\usfm')):
            newLines.append(line)
            continue
        result, pos = '', 0
        for match in EXPLANATION_REGEX.finditer(line):
            before = line[pos:match.start()]
            trad = explanation_traditional_name(match.group(2))
            preceding = PRECEDING_NAME_REGEX.search(before)
            if trad and preceding and preceding.group(1)[0].isupper():
                rvToken = preceding.group(1)
                rvBase, _ = split_possessive(normalise_apostrophes(rvToken))
                tradBase, _ = split_possessive(trad)
                currentMap[rvBase] = tradBase
                result += bare_names_pass(before[:preceding.start()], currentMap)
                result += trad + preceding.group(2) + preceding.group(3)
            else:
                result += bare_names_pass(before, currentMap)
            pos = match.end()
        result += bare_names_pass(line[pos:], currentMap)
        newLines.append(result)
    return '\n'.join(newLines)


# --- 'Adapted' OET -----------------------------------------------------------

# Parts of the text that must stay unchanged: figures, URLs, filenames
ADAPTED_PROTECT_REGEX = re.compile(r'(\\fig .*?\\fig\*|\S*(?:https?://|www\.)\S*'
                                   r'|\S+\.(?:tsv|png|jpe?g|svg|ESFM|USFM|SFM|usfm|md|txt|json)\b)')
ADAPTED_FULL_NAME_REGEX = re.compile(r'(?<![\w\-/.])(?<!Adapted )Open English Translation')
ADAPTED_OET_REGEX = re.compile(r'(?<![\w\-/.])(?<!Adapted )(OET(?:-[A-Z]{2})?)(?![\w\-])(?!\.\w)')


def add_adapted(text):
    """
    Precede every 'Open English Translation' and 'OET' (incl. OET-RV, OET-LV) with 'Adapted '
        (but not in figures, URLs, filenames, or the \\rem WORDTABLE line).
    """
    newLines = []
    for line in text.split('\n'):
        if ('OET' not in line and 'Open English Translation' not in line) or line.startswith('\\rem WORDTABLE'):
            newLines.append(line)
            continue
        parts = ADAPTED_PROTECT_REGEX.split(line)
        for index in range(0, len(parts), 2): # The odd-numbered parts are the protected ones
            parts[index] = ADAPTED_OET_REGEX.sub(r'Adapted \1',
                                                 ADAPTED_FULL_NAME_REGEX.sub('Adapted Open English Translation', parts[index]))
        newLines.append(''.join(parts))
    return '\n'.join(newLines)


# --- ESFM -> USFM and USFM -> VPL --------------------------------------------

ADD_PREFIX_CHARS = '?+¿=<>≡&*@#%^≈!'


def esfm_to_usfm(text, VV, code):
    """
    Convert ESFM (with word numbers already removed) to plain USFM.
    Based on convert_OET-LV-RV_ESFM_to_USFM.py in the OET repo.
    """
    text = re.sub(r'^\\rem (ESFM|WORDTABLE) .*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\\id [0-9A-Za-z]{3}', f'\\\\id {code}', text) # USFM abbreviations are uppercase
    text = WORD_NUMBER_REGEX.sub('', text)
    if VV == 'LV': # Our LV ESFM has no paragraph marker after \c lines
        text = re.sub(r'^\\c ([0-9]{1,3})\n\\v ', r'\\c \1\n\\nb\n\\v ', text, flags=re.MULTILINE)
        text = text.replace('\\add ¿\\add*', '') # Remove those added hyphens
    text = re.sub(r'\\(\+?)add [' + re.escape(ADD_PREFIX_CHARS) + ']{1,2}', r'\\\1add ', text)
    text = text.replace('\\untr ', '').replace('\\untr*', '')
    if VV == 'RV':
        text = re.sub(r'\\z[a-z0-9]+\*', '', text) # Psalm/Song thematic colouring markers
        text = re.sub(r'\\z[a-z0-9]+ ', '', text)
        text = (text.replace("'", '’') # Convert apostrophes
                    .replace('\\q1 ≈', '\\q1 ').replace('\\q2 ≈', '\\q2 ') # Remove 'parallelism' marker
                    .replace(' ⇔', ' ')) # Remove "verse text swapped in order" marker
        newLines = []
        for line in text.split('\n'):
            if line.startswith('\\rem /'): # our additional section headings, etc.
                continue
            if line == '\\ie':
                newLines.append('\\rem NOTE: This USFM file was exported from the ESFM source file with some loss of features, so don’t edit this derived file.')
            newLines.append(line)
        text = '\n'.join(newLines)
    return text


VPL_SKIP_MARKERS = {'id', 'ide', 'usfm', 'rem', 'h', 'sts', 'periph', 'mr', 'sr', 'r', 'sp', 'cl', 'cp', 'cd',
                    'lit', 'b', 'ie', 'restore', 'esb', 'esbe', 'cat', 'qa'}


def clean_vpl_text(text, VV):
    text = re.sub(r'\\(f|fe|ef|x|ex) .*?\\\1\*', '', text) # Remove notes and cross-references
    text = re.sub(r'\\fig .*?\\fig\*', '', text)
    text = re.sub(r"\\\+?nd Lord((?:['’]s)?)\\\+?nd\*", r'LORD\1', text)
    text = re.sub(r'\|[^\\]*(?=\\\+?w\*)', '', text) # \w word|attributes\w*
    text = re.sub(r'\\\+?[a-z]+[0-9]*\*', '', text) # All remaining closing markers
    text = re.sub(r'\\\+?[a-z]+[0-9]* ?', '', text) # and opening markers
    if VV == 'LV':
        text = text.replace('_', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def usfm_to_vpl(usfmText, code, VV):
    """ Returns VPL lines like 'GEN 1:1<tab>text' (Psalm titles go in verse 0). """
    entries, current, chapter = [], None, '0'

    def flush():
        if current and clean_vpl_text(current[1], VV):
            entries.append(f'{current[0]}\t{clean_vpl_text(current[1], VV)}')

    for line in usfmText.split('\n'):
        match = re.match(r'\\([a-z]+[0-9]*)\s?(.*)', line)
        if not match:
            if current:
                current[1] += ' ' + line
            continue
        marker, rest = match.groups()
        if marker == 'c':
            flush()
            current, chapter = None, rest.split()[0] if rest.split() else chapter
        elif marker == 'v':
            flush()
            verseMatch = re.match(r'(\S+)\s*(.*)', rest)
            current = [f'{code} {chapter}:{verseMatch.group(1)}', verseMatch.group(2)] if verseMatch else None
        elif marker == 'd':
            flush()
            current = [f'{code} {chapter}:0', rest]
        elif marker in VPL_SKIP_MARKERS or marker.startswith(('i', 's', 'mt', 'ms', 'toc')):
            continue # headings, introductions, etc.
        elif current:
            current[1] += ' ' + rest
    flush()
    return entries


# ---------------------------------------------------------------------------
# The export itself
# ---------------------------------------------------------------------------

def run_export(source, answers, log, keep_gui_alive=lambda: None):
    """ Export the books according to the answers. Returns the output folder Path. """
    a = effective_answers(answers)
    name = settings_name(a)
    assert name
    outputFolder = EXPORTED_FILES_FOLDER / name
    if outputFolder.exists():
        shutil.rmtree(outputFolder)
    outputFolder.mkdir(parents=True)
    formats = a['formats']
    useSubfolders = len(formats) > 1
    formatFolders = {}
    for fmt in formats:
        formatFolders[fmt] = outputFolder / fmt if useSubfolders else outputFolder
        formatFolders[fmt].mkdir(exist_ok=True)

    namesTable = None
    if rv_included(a) and a['names'] == 'traditional':
        log('Loading OET-RV names table…')
        namesTable = NamesTable(source.read_text(NAMES_TABLE_PATH))

    order = OET_RV_ORDER if a['book_order'] == 'OET-RV' else TRADITIONAL_ORDER
    versions = {'RV': ['RV'], 'LV': ['LV'], 'BOTH': ['RV', 'LV']}[a['version']]
    wordTablesNeeded = set()
    totalFiles = 0
    for VV in versions:
        log(f'\nExporting OET-{VV}…')
        available = find_book_files(source, VV)
        books = [BBB for BBB in order if BBB in available and book_section(BBB) in a['sections']]
        books += sorted(BBB for BBB in available # any books not in our order lists go at the end
                        if BBB not in order and book_section(BBB) in a['sections'])
        width = max(2, len(str(len(books))))
        esfmCount = vplCount = 0 # ESFM and VPL files are numbered in the chosen book order
        for BBB in books:
            keep_gui_alive()
            text = source.read_text(available[BBB])
            code = usfm_code(BBB, text)
            prefix = f'{USFM_BOOK_NUMBERS.get(code, "ZZ")}_' # Standard USFM book number (USFM files)
            if VV == 'RV' and namesTable:
                text = change_to_traditional_names(text, BBB, namesTable)
            if VV == 'RV' and a['divine_name'] == 'LORD':
                text = change_yahweh_to_lord(text, BBB)
            text = add_adapted(text)
            if a['word_numbers'] == 'keep':
                for tableName in re.findall(r'^\\rem WORDTABLE (\S+)', text, flags=re.MULTILINE):
                    wordTablesNeeded.add(tableName)
            else:
                text = remove_word_numbers(text)
            written = []
            if 'ESFM' in formats:
                esfmCount += 1
                (formatFolders['ESFM'] / f'{esfmCount:0{width}}_OET-{VV}_{BBB}.ESFM').write_text(text, encoding='utf-8')
                written.append('ESFM')
            if 'USFM' in formats or 'VPL' in formats:
                usfmText = esfm_to_usfm(text, VV, code)
                if 'USFM' in formats:
                    (formatFolders['USFM'] / f'{prefix}OET-{VV}_{code}.USFM').write_text(usfmText, encoding='utf-8')
                    written.append('USFM')
                if 'VPL' in formats:
                    vplLines = usfm_to_vpl(usfmText, code, VV)
                    if vplLines:
                        vplCount += 1
                        (formatFolders['VPL'] / f'{vplCount:0{width}}_OET-{VV}_{code}.vpl').write_text(
                            '\n'.join(vplLines) + '\n', encoding='utf-8')
                        written.append('VPL')
            totalFiles += len(written)
            log(f'  {BBB} ({code}): {", ".join(written) if written else "nothing (no verses)"}')
    for tableName in sorted(wordTablesNeeded):
        keep_gui_alive()
        log(f'Copying word table {tableName}…')
        try:
            shutil.copyfile(source.get_path(f'{WORD_TABLE_FOLDER}/{tableName}'), formatFolders['ESFM'] / tableName)
        except (OSError, urllib.error.URLError) as err:
            log(f'  WARNING: Unable to copy {tableName}: {err}')
    log(f'\nWrote {totalFiles:,} files to {outputFolder}')
    return outputFolder


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class ChoiceDialog(tk.Toplevel):
    """ A modal dialog with radio-button choices (and an optional 'remember' checkbox). """

    def __init__(self, parent, title, message, options, default=None, remember_text=None):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.result = None
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=message, wraplength=480, justify='left').pack(anchor='w', pady=(0, 10))
        self.choice = tk.StringVar(value=default if default is not None else options[0][0])
        for value, text in options:
            ttk.Radiobutton(frame, text=text, value=value, variable=self.choice).pack(anchor='w', pady=2)
        self.remember = tk.BooleanVar(value=True)
        if remember_text:
            ttk.Checkbutton(frame, text=remember_text, variable=self.remember).pack(anchor='w', pady=(10, 0))
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=(15, 0))
        ttk.Button(buttons, text='Cancel', command=self.destroy).pack(side='right')
        ttk.Button(buttons, text='OK', command=self.ok).pack(side='right', padx=5)
        self.bind('<Return>', lambda _e: self.ok())
        self.bind('<Escape>', lambda _e: self.destroy())
        self.wait_visibility()
        self.grab_set()
        self.wait_window()

    def ok(self):
        self.result = (self.choice.get(), self.remember.get())
        self.destroy()


class ExportWizard(tk.Toplevel):
    """ Asks the export settings questions one after the other, with Back/Next/Cancel. """

    def __init__(self, parent, global_defaults):
        super().__init__(parent)
        self.title('Export settings')
        self.transient(parent)
        self.minsize(520, 300)
        self.global_defaults = dict(global_defaults)
        self.answers = {}
        self.remember = {q.key: (q.key in global_defaults) for q in QUESTIONS}
        self.skip_mode = 'no'
        self.result = None # (answers, remember dict, skip_mode) when finished
        self.history = []
        self.asked = set() # Questions actually shown to the user

        self.body = ttk.Frame(self, padding=15)
        self.body.pack(fill='both', expand=True)
        buttons = ttk.Frame(self, padding=(15, 0, 15, 15))
        buttons.pack(fill='x')
        ttk.Button(buttons, text='Cancel', command=self.destroy).pack(side='right')
        self.next_button = ttk.Button(buttons, text='Next >', command=self.next)
        self.next_button.pack(side='right', padx=5)
        self.back_button = ttk.Button(buttons, text='< Back', command=self.back)
        self.back_button.pack(side='right')
        self.bind('<Escape>', lambda _e: self.destroy())

        self.steps = (['skip'] if global_defaults else []) + [q.key for q in QUESTIONS]
        self.current = None
        self.show(self.next_step(-1))
        self.wait_visibility()
        self.grab_set()
        self.wait_window()

    def is_needed(self, step):
        if step == 'skip':
            return True
        question = QUESTIONS_BY_KEY[step]
        if not question.applies({**self.global_defaults, **self.answers}):
            return False
        if self.skip_mode in ('yes', 'yes_delete') and step in self.global_defaults:
            self.answers[step] = self.global_defaults[step]
            return False
        return True

    def next_step(self, index):
        for nextIndex in range(index + 1, len(self.steps)):
            if self.is_needed(self.steps[nextIndex]):
                return nextIndex
        return None

    def show(self, index):
        for child in self.body.winfo_children():
            child.destroy()
        self.current = index
        step = self.steps[index]
        self.back_button.state(['!disabled'] if self.history else ['disabled'])
        self.build_page(step)
        self.update_next_text()

    def build_page(self, step):
        if step == 'skip':
            ttk.Label(self.body, text='Some export questions have saved global answers.\n'
                                      'Skip the questions that have global settings?',
                      wraplength=480, justify='left').pack(anchor='w', pady=(0, 10))
            saved = '\n'.join(f'    {QUESTIONS_BY_KEY[k].label}: {QUESTIONS_BY_KEY[k].answer_text(v)}'
                              for k, v in self.global_defaults.items() if k in QUESTIONS_BY_KEY)
            ttk.Label(self.body, text=saved, justify='left').pack(anchor='w', pady=(0, 10))
            self.var = tk.StringVar(value=self.skip_mode)
            for value, text in (('no', 'No (ask every question, with the saved answers preselected)'),
                                ('yes', 'Yes (skip questions with preselected global settings)'),
                                ('yes_delete', 'Yes, and then delete all global export settings')):
                ttk.Radiobutton(self.body, text=text, value=value, variable=self.var,
                                command=self.update_next_text).pack(anchor='w', pady=2)
            return
        question = QUESTIONS_BY_KEY[step]
        ttk.Label(self.body, text=question.prompt, wraplength=480, justify='left',
                  font=('TkDefaultFont', 11, 'bold')).pack(anchor='w', pady=(0, 10))
        current = self.answers.get(step, self.global_defaults.get(step, question.default))
        if question.kind == 'radio':
            self.var = tk.StringVar(value=current)
            for value, text in question.options:
                default = ' [default]' if value == question.default else ''
                ttk.Radiobutton(self.body, text=text + default, value=value, variable=self.var,
                                command=self.update_next_text).pack(anchor='w', pady=2)
        else:
            self.var = {}
            for value, text in question.options:
                self.var[value] = tk.BooleanVar(value=value in current)
                ttk.Checkbutton(self.body, text=text, variable=self.var[value]).pack(anchor='w', pady=2)
            ttk.Label(self.body, text='Default: ' + question.answer_text(question.default),
                      foreground='grey').pack(anchor='w', pady=(4, 0))
        self.remember_var = tk.BooleanVar(value=self.remember[step])
        ttk.Checkbutton(self.body, text='Save this answer as a global setting (don’t ask again)',
                        variable=self.remember_var).pack(anchor='w', pady=(15, 0))

    def next_step_preview(self, index):
        """ Like next_step() but without side effects, using the currently selected value. """
        saved = dict(self.answers), self.skip_mode
        try:
            self.capture(validate=False)
            return self.next_step(index)
        finally:
            self.answers, self.skip_mode = saved

    def update_next_text(self):
        self.next_button.config(text='Finish' if self.next_step_preview(self.current) is None else 'Next >')

    def capture(self, validate=True):
        """ Store the value(s) from the current page. Returns False if invalid. """
        if self.current is None or not hasattr(self, 'var'):
            return True
        step = self.steps[self.current]
        if step == 'skip':
            self.skip_mode = self.var.get()
            return True
        if isinstance(self.var, dict):
            values = [v for v, _t in QUESTIONS_BY_KEY[step].options if self.var[v].get()]
            if validate and not values:
                messagebox.showwarning('Export settings', 'Please select at least one option.', parent=self)
                return False
            self.answers[step] = values
        else:
            self.answers[step] = self.var.get()
        if validate:
            self.remember[step] = self.remember_var.get()
            self.asked.add(step)
        return True

    def next(self):
        if not self.capture():
            return
        # Forget answers that we'll redetermine (e.g., after going back)
        for step in self.steps[self.current + 1:]:
            self.answers.pop(step, None)
            self.asked.discard(step)
        nextIndex = self.next_step(self.current)
        if nextIndex is None:
            self.result = (dict(self.answers), {k: self.remember[k] for k in self.asked}, self.skip_mode)
            self.destroy()
            return
        self.history.append(self.current)
        self.show(nextIndex)

    def back(self):
        if self.history:
            self.capture(validate=False)
            self.show(self.history.pop())


class OETAdapterApp:
    def __init__(self, root):
        self.root = root
        root.title(f'{PROGRAM_NAME} v{PROGRAM_VERSION}')
        root.minsize(760, 560)
        self.global_settings = read_toml(GLOBAL_SETTINGS_PATH)
        self.source = None
        self.answers = None
        self.answer_name = None

        main = ttk.Frame(root, padding=10)
        main.pack(fill='both', expand=True)

        sourceFrame = ttk.LabelFrame(main, text='OET source files', padding=8)
        sourceFrame.pack(fill='x')
        self.source_label = ttk.Label(sourceFrame, text='(not set up yet)')
        self.source_label.grid(row=0, column=0, sticky='w')
        self.refresh_label = ttk.Label(sourceFrame, text='')
        self.refresh_label.grid(row=1, column=0, sticky='w')
        ttk.Button(sourceFrame, text='Change…', command=lambda: self.setup_source(force=True)) \
            .grid(row=0, column=1, rowspan=2, sticky='e')
        sourceFrame.columnconfigure(0, weight=1)

        settingsFrame = ttk.LabelFrame(main, text='Export settings', padding=8)
        settingsFrame.pack(fill='x', pady=10)
        self.settings_name_label = ttk.Label(settingsFrame, text='No export settings selected yet',
                                             font=('TkDefaultFont', 10, 'bold'))
        self.settings_name_label.grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 6))
        self.answer_labels = {}
        for row, question in enumerate(QUESTIONS, start=1):
            ttk.Label(settingsFrame, text=question.label + ':').grid(row=row, column=0, sticky='w', padx=(0, 10))
            self.answer_labels[question.key] = ttk.Label(settingsFrame, text='—')
            self.answer_labels[question.key].grid(row=row, column=1, sticky='w')
            self.answer_labels[question.key + '_global'] = ttk.Label(settingsFrame, text='', foreground='grey')
            self.answer_labels[question.key + '_global'].grid(row=row, column=2, sticky='w', padx=(10, 0))

        buttons = ttk.Frame(main)
        buttons.pack(fill='x')
        ttk.Button(buttons, text='New export settings…', command=self.new_settings).pack(side='left')
        ttk.Button(buttons, text='Load saved settings…', command=self.load_settings).pack(side='left', padx=5)
        ttk.Button(buttons, text='Quit', command=root.destroy).pack(side='right')
        # Centred in the space between the settings buttons and Quit (so it stands out)
        self.run_button = ttk.Button(buttons, text='Run export', command=self.run, state='disabled')
        self.run_button.pack(side='left', expand=True)

        logFrame = ttk.LabelFrame(main, text='Log', padding=4)
        logFrame.pack(fill='both', expand=True, pady=(10, 0))
        self.log_text = tk.Text(logFrame, height=14, wrap='word', state='disabled')
        scrollbar = ttk.Scrollbar(logFrame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.log_text.pack(side='left', fill='both', expand=True)

        self.update_answer_display()
        root.after(100, self.startup)

    # --- Utilities ---

    def log(self, message):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', message + '\n')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')
        self.root.update()

    def save_global_settings(self):
        write_toml(GLOBAL_SETTINGS_PATH, self.global_settings,
                   header=f'Global settings for {PROGRAM_NAME} (written by the program)')

    def run_command(self, args, cwd=None):
        """ Runs a command showing its output in the log. Returns True on success. """
        self.log('$ ' + ' '.join(str(a) for a in args))
        try:
            process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding='utf-8', errors='replace')
        except FileNotFoundError:
            self.log(f'ERROR: Unable to run {args[0]} (is it installed?)')
            return False
        for line in process.stdout:
            self.log('  ' + line.rstrip())
        return process.wait() == 0

    # --- Startup ---

    def startup(self):
        self.setup_source()
        self.offer_saved_settings()

    def setup_source(self, force=False):
        """ Decide where the OET files come from (stored in the global settings). """
        settings = self.global_settings.setdefault('source', {})
        mode, repoPath = settings.get('mode'), settings.get('repo_path')
        if not force and mode == 'temp':
            pass
        elif not force and mode == 'local' and repoPath and (Path(repoPath) / '.git').is_dir():
            pass
        else:
            if (PARALLEL_REPO_PATH / '.git').is_dir() and not force:
                mode, repoPath = 'local', str(PARALLEL_REPO_PATH)
            else:
                found = (PARALLEL_REPO_PATH / '.git').is_dir()
                options = []
                if found:
                    options.append(('parallel', f'Use the existing repo at {PARALLEL_REPO_PATH}'))
                else:
                    options.append(('clone_parallel', f'Download (git clone) the repo into {PARALLEL_REPO_PATH}'))
                options += [('clone_elsewhere', 'Download (git clone) the repo somewhere else…'),
                            ('existing', 'Use an existing copy of the repo somewhere else…'),
                            ('temp', 'Just temporarily download the files as needed for each export')]
                dialog = ChoiceDialog(self.root, 'OET source files',
                                      f'Where should the OET files come from?\n({GITHUB_URL})',
                                      options, default=options[0][0])
                if dialog.result is None:
                    if not mode:
                        self.log('No source chosen: using temporary downloads for now.')
                        self.source = Source('temp', log=self.log)
                        self.update_source_display()
                    return
                choice = dialog.result[0]
                if choice == 'parallel':
                    mode, repoPath = 'local', str(PARALLEL_REPO_PATH)
                elif choice == 'temp':
                    mode, repoPath = 'temp', ''
                elif choice == 'existing':
                    folder = filedialog.askdirectory(parent=self.root, title='Select the OET repo folder',
                                                     initialdir=str(APP_FOLDER.parent))
                    if not folder:
                        return
                    if not (Path(folder) / 'translatedTexts').is_dir():
                        messagebox.showerror('OET source files', f'{folder} doesn’t look like the OET repo.')
                        return
                    mode, repoPath = 'local', folder
                else: # clone
                    if choice == 'clone_parallel':
                        target = PARALLEL_REPO_PATH
                    else:
                        folder = filedialog.askdirectory(parent=self.root, initialdir=str(APP_FOLDER.parent),
                                                         title='Select the folder to put the OET repo in')
                        if not folder:
                            return
                        target = Path(folder) / REPO_FOLDER_NAME
                    if target.exists():
                        messagebox.showerror('OET source files', f'{target} already exists.')
                        return
                    self.log(f'Cloning {GITHUB_CLONE_URL} into {target} (this may take a while)…')
                    if not self.run_command(['git', 'clone', '--progress', GITHUB_CLONE_URL, str(target)]):
                        messagebox.showerror('OET source files', 'git clone failed (see the log).')
                        return
                    mode, repoPath = 'local', str(target)
            settings['mode'], settings['repo_path'] = mode, repoPath or ''
            if mode == 'local':
                answer = messagebox.askyesno('OET source files',
                                             f'Using the OET repo at\n{repoPath}\n\n'
                                             'Should it be refreshed (git pull) before each export?')
                settings['refresh_before_export'] = answer
            self.save_global_settings()
        self.source = Source(mode, repoPath, log=self.log)
        self.update_source_display()

    def update_source_display(self):
        settings = self.global_settings.get('source', {})
        self.source_label.config(text='Source: ' + self.source.describe())
        if self.source.mode == 'local':
            refresh = settings.get('refresh_before_export', False)
            self.refresh_label.config(text=f'Refresh (git pull) before export: {"Yes" if refresh else "No"}')
        else:
            self.refresh_label.config(text='')

    def offer_saved_settings(self):
        savedFiles = sorted(APP_FOLDER.glob('*' + EXPORT_SETTINGS_SUFFIX))
        if not savedFiles:
            self.new_settings()
            return
        options = [(str(p), p.name.removesuffix(EXPORT_SETTINGS_SUFFIX)) for p in savedFiles]
        options.append(('new', 'Create new export settings…'))
        dialog = ChoiceDialog(self.root, 'Export settings', 'Re-use some existing export settings?',
                              options, default=options[0][0])
        if dialog.result is None:
            return
        if dialog.result[0] == 'new':
            self.new_settings()
        else:
            self.load_settings_file(Path(dialog.result[0]))

    # --- Export settings ---

    def update_answer_display(self):
        globalDefaults = self.global_settings.get('export_defaults', {})
        effective = effective_answers(self.answers) if self.answers else None
        for question in QUESTIONS:
            if effective:
                text = question.answer_text(effective[question.key])
                if not question.applies(effective):
                    text += '  (implied)'
            else:
                text = '—'
            self.answer_labels[question.key].config(text=text)
            self.answer_labels[question.key + '_global'].config(
                text='(global setting)' if question.key in globalDefaults else '')
        self.settings_name_label.config(text=f'{self.answer_name}' if self.answers
                                        else 'No export settings selected yet')
        self.run_button.config(state='normal' if self.answers else 'disabled')

    def new_settings(self):
        globalDefaults = dict(self.global_settings.get('export_defaults', {}))
        wizard = ExportWizard(self.root, globalDefaults)
        if wizard.result is None:
            self.log('Export settings cancelled.')
            return
        answers, remember, skipMode = wizard.result
        answers = effective_answers({**globalDefaults, **answers})
        # Update the global export settings
        if skipMode == 'yes_delete':
            globalDefaults = {}
        for key, rememberIt in remember.items(): # only the questions that were actually asked
            if rememberIt:
                globalDefaults[key] = answers[key]
            else:
                globalDefaults.pop(key, None)
        self.global_settings['export_defaults'] = globalDefaults
        self.save_global_settings()
        # Save the named settings set
        self.answers, self.answer_name = answers, settings_name(answers)
        path = APP_FOLDER / (self.answer_name + EXPORT_SETTINGS_SUFFIX)
        write_toml(path, {'name': self.answer_name, **answers},
                   header=f'{PROGRAM_NAME} export settings')
        self.log(f'Saved export settings to {path.name}')
        self.update_answer_display()

    def load_settings(self):
        filename = filedialog.askopenfilename(parent=self.root, initialdir=str(APP_FOLDER),
                                              title='Load export settings',
                                              filetypes=[('Export settings', '*' + EXPORT_SETTINGS_SUFFIX)])
        if filename:
            self.load_settings_file(Path(filename))

    def load_settings_file(self, path):
        data = read_toml(path)
        self.answers = effective_answers({k: v for k, v in data.items() if k in QUESTIONS_BY_KEY})
        self.answer_name = settings_name(self.answers)
        self.log(f'Loaded export settings from {path.name}')
        self.update_answer_display()

    # --- Run ---

    def run(self):
        if not self.answers:
            return
        if self.source is None:
            self.setup_source()
            if self.source is None:
                return
        outputFolder = EXPORTED_FILES_FOLDER / self.answer_name
        if outputFolder.exists() and not messagebox.askyesno(
                'Run export', f'{outputFolder} already exists.\nReplace its contents?'):
            return
        self.run_button.config(state='disabled')
        try:
            if self.source.mode == 'local' and self.global_settings.get('source', {}).get('refresh_before_export'):
                self.log(f'Refreshing {self.source.repo_path}…')
                if not self.run_command(['git', 'pull', '--ff-only'], cwd=self.source.repo_path):
                    if not messagebox.askyesno('Run export', 'git pull failed (see the log).\n'
                                                             'Continue with the existing files?'):
                        return
                self.source.dir_cache.clear()
            self.log(f'Running export {self.answer_name}…')
            outputFolder = run_export(self.source, self.answers, self.log, keep_gui_alive=self.root.update)
            messagebox.showinfo('Run export', f'Export finished.\n\nFiles are in\n{outputFolder}')
        except Exception as err: # Show any problem to the user rather than crashing
            self.log(f'ERROR: {type(err).__name__}: {err}')
            messagebox.showerror('Run export', f'Export failed:\n{err}')
        finally:
            self.run_button.config(state='normal')


def main():
    root = tk.Tk()
    OETAdapterApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
