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

CHANGELOG:
  2026-11-24 Added LICENSE and README.md files to the outputs, plus a program version check
"""
import csv
import datetime
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog


PROGRAM_NAME = 'OET Adapter'
PROGRAM_VERSION = '0.5.1'

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
ADAPTER_URL = 'https://github.com/Freely-Given-org/OpenEnglishTranslation_adapter'
ADAPTER_CLONE_URL = f'{ADAPTER_URL}.git'
ADAPTER_RAW_URL = 'https://raw.githubusercontent.com/Freely-Given-org/OpenEnglishTranslation_adapter/main/OET_adapter.py'
GIT_ENV = {**os.environ, 'GIT_TERMINAL_PROMPT': '0'} # Never let git wait for a password
OET_FORMATS_URL = 'https://OpenEnglishTranslation.Bible/Resources/Formats/'

# Where the ESFM source files live in the OET repo
RV_FOLDER = 'translatedTexts/ReadersVersion'
LV_OT_FOLDER = 'derivedTexts/auto_edited_OT_ESFM'
LV_NT_FOLDER = 'derivedTexts/auto_edited_VLT_ESFM'
LV_DC_FOLDER = 'derivedTexts/auto_edited_DC_ESFM'
WORD_TABLE_FOLDER = RV_FOLDER # All the word tables are in here
NAMES_TABLE_PATH = f'{RV_FOLDER}/OET-RV_names_table.tsv'
# Each text folder has its own LICENSE and README.md (with the copyright and upstream source attributions)
# (All the LICENSE files are the same: the OET text is all CC BY-SA 4.0)
TEXT_FOLDER_LABELS = {RV_FOLDER: 'OET-RV (Readers’ Version)',
                      LV_OT_FOLDER: 'OET-LV (Literal Version) Hebrew Scriptures',
                      LV_NT_FOLDER: 'OET-LV (Literal Version) Messianic Update',
                      LV_DC_FOLDER: 'OET-LV (Literal Version) deuterocanonical books'}


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
ALL_PARTS = ['intros', 'headings', 'footnotes', 'xrefs']
ALL_FORMATS = ['ESFM', 'USFM', 'VPL']


def rv_included(answers):
    return answers.get('version', 'RV') in ('RV', 'BOTH')


def esfm_exported(answers):
    return answers.get('word_numbers', 'remove') == 'keep' or 'ESFM' in answers.get('formats', ['USFM'])


class Question:
    def __init__(self, key, label, prompt, kind, options, default, applies=lambda answers: True, allow_none=False):
        self.key, self.label, self.prompt, self.kind = key, label, prompt, kind
        self.options, self.default, self.applies = options, default, applies # options are (value, text) pairs
        self.allow_none = allow_none # For 'check' questions: can nothing be selected?

    def answer_text(self, value):
        texts = dict(self.options)
        if self.kind == 'check':
            if not value:
                return 'None'
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
    Question('parts', 'Included parts', 'Which of these parts do you want included?', 'check',
             [('intros', 'Book introductions'), ('headings', 'Section headings'), ('footnotes', 'Footnotes'),
              ('xrefs', 'Cross-references')],
             list(ALL_PARTS), allow_none=True),
    Question('spelling', 'Spelling', 'Which spelling do you want?', 'radio',
             [('UK', 'Remain in British spelling'), ('US', 'Change to American spelling and terminology')],
             'UK'),
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
    Question('esfm_markers', 'ESFM markers', 'Which formatting markers should the ESFM files keep?', 'radio',
             [('all', 'Leave the additional formatting markers'),
              ('essential', 'Just keep the essential ones (simplified like the USFM files)')],
             'all', applies=esfm_exported),
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
    result['parts'] = [p for p in ALL_PARTS if p in result['parts']]
    result['formats'] = [f for f in ALL_FORMATS if f in result['formats']]
    if 'ESFM' not in result['formats']:
        result['esfm_markers'] = 'all'
    return result


PART_ABBREVIATIONS = {'intros': 'Intros', 'headings': 'Hdgs', 'footnotes': 'FNs', 'xrefs': 'XRefs'}


def settings_name(answers):
    """ Makes a name like RVLV_ALLBks_RVOrder_NoFNs_UK_LORD_TradNames_NoWordNums_ALLFormats_Simple """
    a = effective_answers(answers)
    parts = [{'RV': 'RV', 'LV': 'LV', 'BOTH': 'RVLV'}[a['version']]]
    if a['sections'] == ALL_SECTIONS:
        parts.append('ALLBks')
    else:
        parts.append(''.join({'FRT': 'Front', 'BAK': 'Back'}.get(s, s) for s in a['sections']) + 'Bks')
    if rv_included(a):
        parts.append('RVOrder' if a['book_order'] == 'OET-RV' else 'TradOrder')
    excluded = [p for p in ALL_PARTS if p not in a['parts']]
    parts.append('No' + ''.join(PART_ABBREVIATIONS[p] for p in excluded) if excluded else 'ALLParts')
    parts.append(a['spelling'])
    if rv_included(a):
        parts.append(a['divine_name'])
        parts.append('RVNames' if a['names'] == 'RV' else 'TradNames')
    parts.append('WordNums' if a['word_numbers'] == 'keep' else 'NoWordNums')
    parts.append('ALLFormats' if a['formats'] == ALL_FORMATS else ''.join(a['formats']))
    if 'ESFM' in a['formats']:
        parts.append('Simple' if a['esfm_markers'] == 'essential' else 'AllMarkers')
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


# --- Optional parts: book introductions, section headings, footnotes, cross-references ---

INTRO_LINE_REGEX = re.compile(r'\\i(?!de?\b)[a-z]*[0-9]*\b') # \ip, \is1, \io1, \iot, \ie, etc. (but not \id or \ide)
HEADING_LINE_REGEX = re.compile(r'\\(s[0-9]?|ms[0-9]?|mr|sr|r)\b|\\rem /(s[0-9]?|ms[0-9]?|r)\b')
FOOTNOTE_REGEX = re.compile(r'\\(f|fe|ef) .*?\\\1\*')
XREF_REGEX = re.compile(r'\\(x|ex) .*?\\\1\*')


def remove_parts(text, BBB, includedParts):
    """
    Remove book introductions (not in front/back matter books), section headings
        (including parallel passage references and the OET-RV's extra `\\rem /s1` headings),
        footnotes and/or cross-references, unless they're in includedParts.
    """
    removeIntros = 'intros' not in includedParts and BBB not in FRONT_BOOKS and BBB not in BACK_BOOKS
    removeHeadings = 'headings' not in includedParts
    newLines = []
    for line in text.split('\n'):
        if (removeIntros and INTRO_LINE_REGEX.match(line)) or (removeHeadings and HEADING_LINE_REGEX.match(line)):
            continue
        newLines.append(line)
    text = '\n'.join(newLines)
    if 'footnotes' not in includedParts:
        text = FOOTNOTE_REGEX.sub('', text)
    if 'xrefs' not in includedParts:
        text = XREF_REGEX.sub('', text)
    return text


# --- British -> American spelling and terminology ----------------------------

def _build_american_spellings():
    """ Returns a dict of lowercase British word -> American word. """
    words = {}
    # -our -> -or (with prefixes and suffixes)
    for stem in ('ardour armour behaviour candour clamour colour demeanour misdemeanour endeavour enamour favour '
                 'fervour flavour harbour honour humour labour neighbour odour parlour rancour rigour rumour '
                 'saviour savour splendour tumour valour vapour vigour').split():
        for prefix in ('', 'dis', 'un', 'multi'):
            for suffix in ('', 's', 'ed', 'ing', 'er', 'ers', 'able', 'ably', 'ite', 'ites', 'itism', 'y',
                           'ful', 'fully', 'less', 'hood', 'hoods', 'ably'):
                words[prefix + stem + suffix] = prefix + stem.replace('our', 'or') + suffix
    # -ise -> -ize
    for stem in ('agonis apologis authoris baptis capitalis catechis characteris christianis civilis colonis '
                 'computeris criticis digitis disorganis dramatis emphasis energis epitomis evangelis familiaris '
                 'fantasis fertilis finalis formalis generalis harmonis hellenis hospitalis hypnotis idealis idolis '
                 'immortalis internalis itemis jeopardis judais legalis legitimis liberalis localis materialis '
                 'maximis memoris mesmeris minimis mobilis modernis monopolis moralis nationalis naturalis '
                 'neutralis normalis optimis organis ostracis parenthesis patronis penalis personalis plagiaris '
                 'pluralis polaris popularis pressuris prioritis privatis proselytis publicis pulveris rationalis '
                 'realis recognis reorganis revitalis romanis sanitis satiris scandalis scrutinis secularis '
                 'sensitis socialis solemnis specialis stabilis standardis sterilis stigmatis subsidis summaris '
                 'symbolis sympathis synthesis terroris theoris trivialis tyrannis unauthoris unorganis urbanis '
                 'utilis vandalis vaporis verbalis victimis visualis vocalis westernis').split():
        for suffix in ('e', 'es', 'ed', 'ing', 'er', 'ers', 'ation', 'ations', 'able'):
            words[stem + suffix] = stem[:-1] + 'z' + suffix
    # -yse -> -yze
    for stem, suffixes in (('paralys', ('e', 'es', 'ed', 'ing')), ('analys', ('e', 'ed', 'ing', 'er', 'ers')),
                           ('catalys', ('e', 'ed', 'ing'))):
        for suffix in suffixes:
            words[stem + suffix] = stem[:-1] + 'z' + suffix
    # -re -> -er
    for word in ('metre centimetre millimetre kilometre litre millilitre centre theatre sceptre sepulchre mitre '
                 'ochre fibre sabre sombre meagre lustre spectre calibre').split():
        american = word[:-2] + 'er'
        words[word], words[word + 's'] = american, american + 's'
    words.update({'centred': 'centered', 'centring': 'centering', 'manoeuvre': 'maneuver',
                  'manoeuvres': 'maneuvers', 'manoeuvred': 'maneuvered', 'manoeuvring': 'maneuvering'})
    # Doubled l -> single l (unstressed final syllable)
    for stem in ('barrel bevel cancel channel counsel cudgel dial duel enamel equal fuel funnel gravel grovel '
                 'jewel kennel label level libel marshal marvel model panel pedal pencil quarrel refuel revel '
                 'rival shovel signal snivel spiral stencil tassel total travel tunnel unravel').split():
        for suffix in ('ed', 'ing', 'er', 'ers', 'or', 'ors', 'ous', 'ously'):
            words[stem + 'l' + suffix] = stem + suffix
    # Other spellings
    for pair in ('grey gray, greys grays, greyer grayer, greyish grayish, greying graying, greyness grayness, '
                 'greyed grayed, plough plow, ploughs plows, ploughed plowed, ploughing plowing, '
                 'ploughman plowman, ploughmen plowmen, ploughshare plowshare, ploughshares plowshares, '
                 'judgement judgment, judgements judgments, acknowledgement acknowledgment, '
                 'acknowledgements acknowledgments, towards toward, amongst among, whilst while, '
                 'learnt learned, dreamt dreamed, spoilt spoiled, burnt burned, axe ax, practise practice, practises practices, '
                 'practised practiced, practising practicing, fulfil fulfill, fulfils fulfills, '
                 'fulfilment fulfillment, fulfilments fulfillments, enrol enroll, enrols enrolls, '
                 'enrolment enrollment, instil instill, instils instills, distil distill, distils distills, '
                 'skilful skillful, skilfully skillfully, unskilful unskillful, wilful willful, wilfully willfully, '
                 'storey story, storeys stories, haemorrhage hemorrhage, haemorrhages hemorrhages, '
                 'haemorrhaging hemorrhaging, defence defense, defences defenses, defenceless defenseless, '
                 'offence offense, offences offenses, licence license, licences licenses, pretence pretense, '
                 'pretences pretenses, mould mold, moulds molds, moulded molded, moulding molding, '
                 'mouldings moldings, mouldy moldy, moulder molder, moulders molders, smoulder smolder, '
                 'smoulders smolders, smouldered smoldered, smouldering smoldering, moult molt, moulted molted, '
                 'jewellery jewelry, woollen woolen, woollens woolens, sceptic skeptic, sceptics skeptics, '
                 'sceptical skeptical, scepticism skepticism, enquire inquire, enquires inquires, '
                 'enquired inquired, enquiring inquiring, enquiry inquiry, enquiries inquiries, '
                 'programme program, programmes programs, cheque check, cheques checks, aluminium aluminum, '
                 'mediaeval medieval, encyclopaedia encyclopedia, foetus fetus, foetuses fetuses, '
                 'diarrhoea diarrhea, anaemia anemia, anaemic anemic, oedema edema, faeces feces, '
                 'oesophagus esophagus, ageing aging, gaol jail, gaols jails, gaoler jailer, gaolers jailers, '
                 'kerb curb, aeroplane airplane, aeroplanes airplanes').split(', '):
        british, american = pair.split()
        words[british] = american
    # American terminology
    for pair in ('rubbish garbage, corn grain, tonne metric_ton, tonnes metric_tons, biscuit wafer, '
                 'biscuits wafers, fortnight two_weeks, fortnights two_weeks').split(', '):
        british, american = pair.split()
        words[british] = american.replace('_', ' ')
    return words


AMERICAN_SPELLINGS = _build_american_spellings()
SPELLING_WORD_REGEX = re.compile(r'(?<![\\+])(?<![^\W_])[^\W\d_]+') # A run of letters (not a marker; LV uses _ between words)
SPELLING_PROTECT_REGEX = re.compile(r'(\|[^\\]*|\S*(?:https?://|www\.)\S*'
                                    r'|\S+\.(?:tsv|png|jpe?g|svg|ESFM|USFM|SFM|usfm|md|txt|json)\b)')
SPELLING_SKIP_LINE_MARKERS = ('\\id ', '\\ide ', '\\usfm ', '\\rem ESFM', '\\rem WORDTABLE')
# 'burnt offering(s)' and 'burnt sacrifice(s)' stay as they are
#   (allowing for word numbers, markers, and the LV's _ and ÷ word joiners)
BURNT_KEEP_REGEX = re.compile(r'(?:¦[0-9]+)?(?:[\s_÷]|\\\+?[a-z]+[0-9]*\*?|[?+=<>≡&@*#%^$≈])*(?:offering|sacrifice)',
                              re.IGNORECASE)


def match_case(original, replacement):
    if len(original) > 1 and original.isupper():
        return replacement.upper()
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def americanise(text):
    """ Change British spelling and terminology to American (not in figures, URLs, filenames or attributes). """
    def replace_word(match):
        word = match.group(0)
        if word.lower() == 'burnt' and BURNT_KEEP_REGEX.match(match.string, match.end()):
            return word
        american = AMERICAN_SPELLINGS.get(word.lower())
        return match_case(word, american) if american else word

    newLines = []
    for line in text.split('\n'):
        if line.startswith(SPELLING_SKIP_LINE_MARKERS):
            newLines.append(line)
            continue
        parts = SPELLING_PROTECT_REGEX.split(line)
        for index in range(0, len(parts), 2): # The odd-numbered parts are the protected ones
            part = SPELLING_WORD_REGEX.sub(replace_word, parts[index])
            # 'spelt' is also a type of wheat, so only change it where it's about spelling
            part = re.sub(r"\b([Ss])pelt(?=\s+(?:as\b|‘|'|\())", r'\1pelled', part)
            parts[index] = part
        newLines.append(''.join(parts))
    return '\n'.join(newLines)


def is_usa_edition(answers):
    """
    True if the only text change is American spelling, and both RV and LV ESFM files are exported
        with their word numbers. (The book selection and book order don't count as text changes.)
    Then the export is a 'USA edition' rather than an 'Adapted' OET.
    """
    a = effective_answers(answers)
    return a['spelling'] == 'US' and a['version'] == 'BOTH' and a['word_numbers'] == 'keep' \
        and a['parts'] == ALL_PARTS and a['divine_name'] == 'Yahweh' and a['names'] == 'RV' \
        and a['esfm_markers'] == 'all'


USA_EDITION_SPELLING_LINE = '\\li1 This USA edition has been created by changing some spelling and vocabulary from the British edition.'


def mark_usa_edition(text, BBB, VV, usaEdition):
    """
    For American spelling exports:
        LV \\id lines get ' USA edition' appended,
        RV \\id lines get 'USA edition ' before the version number (only for a USA edition),
        FRT gets '\\mt3 USA edition' before the first \\pc line, and its \\li1 line about
            British spelling is replaced.
    """
    lines = text.split('\n')
    if lines[0].startswith('\\id '):
        if VV == 'LV':
            lines[0] = lines[0].rstrip() + ' USA edition'
        elif usaEdition:
            lines[0] = re.sub(r'(?<!\S)(v[0-9]+(?:\.[0-9]+)*)\s*$', r'USA edition \1', lines[0].rstrip())
    if BBB == 'FRT':
        lines = [USA_EDITION_SPELLING_LINE if line.startswith('\\li1 ') and 'British spelling' in line else line
                 for line in lines]
        for index, line in enumerate(lines):
            if line.startswith('\\pc ') or line == '\\pc':
                lines.insert(index, '\\mt3 USA edition')
                break
    return '\n'.join(lines)


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

ADD_REMOVE_CHARS = '+=<>≡&@*#%^$≈' # \add fields starting with one of these (optionally with ?) lose their markers
ADD_REMOVE_REGEX = re.compile(r'\\(\+?)add \??[' + re.escape(ADD_REMOVE_CHARS) + r']\??(.*?)\\\1add\*')
ADD_NAME_REGEX = re.compile(r'\\(\+?)add !')
ADD_NAME_FIELD_REGEX = re.compile(r' ?\\(\+?)add !.*?\\\1add\*')
PARALLELISM_CHARS = ('≈', '⇔') # Psalm parallelism and 'verse text reordered' markers


def simplify_markers(text, VV, traditionalNames):
    """
    Keep only the essential formatting markers (as needed for USFM):
        \\add fields starting with [+=<>≡&@*#%^$≈] (optionally with ?) are replaced by their text,
        \\add ! (name explanation) fields become straight \\add fields, or are deleted if changing
            back to traditional names,
        straight \\add fields stay (with any ? removed),
        Psalm parallelism (≈) and reordering (⇔) markers are removed.
    """
    if VV == 'LV':
        text = text.replace('\\add ¿\\add*', '') # Remove those added hyphens
    while True: # (repeat for any nested \+add fields)
        newText = ADD_REMOVE_REGEX.sub(r'\2', text)
        if newText == text:
            break
        text = newText
    if VV == 'RV' and traditionalNames:
        text = ADD_NAME_FIELD_REGEX.sub('', text)
    text = ADD_NAME_REGEX.sub(r'\\\1add ', text)
    text = re.sub(r'\\(\+?)add \?', r'\\\1add ', text)
    for char in PARALLELISM_CHARS:
        text = text.replace(char, '')
    return text


def esfm_to_usfm(text, VV, code, traditionalNames):
    """
    Convert ESFM (with word numbers already removed) to plain USFM.
    Based on convert_OET-LV-RV_ESFM_to_USFM.py in the OET repo.
    """
    text = re.sub(r'^\\rem (ESFM|WORDTABLE) .*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\\id [0-9A-Za-z]{3}', f'\\\\id {code}', text) # USFM abbreviations are uppercase
    text = WORD_NUMBER_REGEX.sub('', text)
    if VV == 'LV': # Our LV ESFM has no paragraph marker after \c lines
        text = re.sub(r'^\\c ([0-9]{1,3})\n\\v ', r'\\c \1\n\\nb\n\\v ', text, flags=re.MULTILINE)
    text = simplify_markers(text, VV, traditionalNames)
    text = text.replace('\\untr ', '').replace('\\untr*', '')
    if VV == 'RV':
        text = re.sub(r'\\z[a-z0-9]+\*', '', text) # Psalm/Song thematic colouring markers
        text = re.sub(r'\\z[a-z0-9]+ ', '', text)
        text = text.replace("'", '’') # Convert apostrophes
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
    for char in PARALLELISM_CHARS:
        text = text.replace(char, '')
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

def markdown_section(markdown, heading_regex):
    """ Returns the body of the first '## ' section whose heading matches (or ''). """
    match = re.search(rf'^## (?:{heading_regex})[ \t]*\n(.*?)(?=^## |\Z)', markdown, flags=re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ''


def absolute_links(markdown, folder):
    """ Make relative Markdown links (from a README in the given repo folder) point to GitHub. """
    def fix(match):
        target = match.group(1)
        if re.match(r'[a-z]+:|#', target, flags=re.IGNORECASE):
            return match.group(0)
        return f']({GITHUB_URL}/blob/{GITHUB_BRANCH}/{posixpath.normpath(f"{folder}/{target}")})'
    return re.sub(r'\]\(([^)\s]+)\)', fix, markdown)


def source_description(source):
    """ Describes where the OET files came from (with the git commit if we can get it). """
    if source.mode != 'local':
        return f'downloaded from the `{GITHUB_BRANCH}` branch of the [OET repository]({GITHUB_URL})'
    try:
        result = subprocess.run(['git', '-C', str(source.repo_path), 'log', '-1', '--format=%H %cs'],
                                capture_output=True, text=True, timeout=30)
        commit, date = result.stdout.split()
        when = datetime.date.fromisoformat(date)
        return f'the [OET repository]({GITHUB_URL}) at commit [`{commit[:10]}`]({GITHUB_URL}/commit/{commit}) ' \
               f'({when.day} {when:%B %Y})'
    except (OSError, ValueError, subprocess.SubprocessError):
        return f'a local copy of the [OET repository]({GITHUB_URL})'


def make_readme(source, a, name, usaEdition, exported, folders, wordTables):
    """ Returns the text of the README.md for an export folder.
        exported is a dict of VV -> list of BOS book codes. """
    versionNames = ' and '.join(f'OET-{VV}' for VV in exported)
    title = f'Open English Translation ({versionNames}) USA edition' if usaEdition \
        else f'Adapted Open English Translation ({versionNames})'
    today = datetime.date.today()
    lines = [f'# {title}', '',
             f'These Bible files were exported on {today.day} {today:%B %Y} by [{PROGRAM_NAME}]({ADAPTER_URL}) v{PROGRAM_VERSION} '
             f'from {source_description(source)}.',
             f'Export settings name: `{name}`', '',
             'The _Open English Translation_ (OET) is a free, open-licensed modern-English Bible translation. '
             'It has two versions that were designed to be read together: the _Readers’ Version_ (OET-RV) '
             'and the very literal _Literal Version_ (OET-LV). Read it online at [OET.Bible](https://OET.Bible).', '']

    # Contents
    lines += ['## Contents', '']
    useSubfolders = len(a['formats']) > 1
    for VV, books in exported.items():
        lines.append(f'- OET-{VV}: {len(books)} books ({", ".join(books)})' if books else f'- OET-{VV}: no books')
    formatDescriptions = {
        'ESFM': f'ESFM files (`.ESFM`): [ESFM]({OET_FORMATS_URL}) is the OET’s extended USFM format. '
                'Filenames start with the book’s position in the chosen book order.',
        'USFM': 'USFM files (`.USFM`): standard [USFM](https://ubsicap.github.io/usfm/) for Paratext and other Bible software. '
                'Filenames start with the standard Paratext book number.',
        'VPL': 'VPL files (`.vpl`): one verse per line, like `GEN 1:1<tab>verse text`, with no formatting. '
               'Filenames start with the book’s position in the chosen book order.'}
    for fmt in a['formats']:
        lines.append(f'- {"`" + fmt + "/` folder: " if useSubfolders else ""}{formatDescriptions[fmt]}')
    if wordTables:
        lines.append(f'- Word tables ({", ".join(f"`{t}`" for t in wordTables)}) '
                     'that the ESFM word numbers (like `¦123`) refer to.')
    lines.append('- `LICENSE`: the full licence text.')
    lines.append('')

    # Settings
    lines += ['## Export settings', '', '| Setting | Choice |', '| --- | --- |']
    for q in QUESTIONS:
        if q.applies(a):
            lines.append(f'| {q.label} | {q.answer_text(a[q.key])} |')
    lines.append('')

    # Changes (required by the CC BY-SA licence)
    changes = []
    if len(exported) == 1:
        changes.append(f'Only the OET-{next(iter(exported))} is included '
                       '(the OET-RV and OET-LV were designed to be used together).')
    if a['sections'] != ALL_SECTIONS:
        changes.append('Only some books are included (see above).')
    if rv_included(a) and a['book_order'] == 'traditional':
        changes.append('The books are numbered in the traditional order (rather than the OET-RV order).')
    removedParts = [QUESTIONS_BY_KEY['parts'].answer_text([p]).lower() for p in ALL_PARTS if p not in a['parts']]
    if removedParts:
        changes.append(f'These parts were removed: {", ".join(removedParts)}.')
    if a['spelling'] == 'US':
        changes.append('British spelling was changed to American spelling (e.g., honour → honor, realise → realize), '
                       'and a few words to American terms (e.g., rubbish → garbage, corn → grain).')
        changes.append('‘USA edition’ was added to the `\\id` lines and to the front matter.')
    if rv_included(a) and a['divine_name'] == 'LORD':
        changes.append('In the OET-RV, ‘Yahweh’ was changed to ‘the LORD’.')
    if rv_included(a) and a['names'] == 'traditional':
        changes.append('In the OET-RV, names were changed back to their traditional forms (e.g., Yeshua → Jesus).')
    if a['word_numbers'] == 'remove':
        changes.append('The ESFM word numbers and `\\rem WORDTABLE` lines were removed.')
    if 'ESFM' in a['formats'] and a['esfm_markers'] == 'essential':
        changes.append('In the ESFM files, the additional OET formatting markers were removed '
                       '(like the USFM files).')
    convertedFormats = [fmt for fmt in ('USFM', 'VPL') if fmt in a['formats']]
    if convertedFormats:
        changes.append(f'The {" and ".join(convertedFormats)} files were converted from ESFM, '
                       'and the OET’s extra formatting markers were removed.')
    if not usaEdition:
        changes.append('‘Open English Translation’ and ‘OET’ were changed to ‘Adapted Open English Translation’ '
                       'and ‘Adapted OET’, as requested in the OET licence notes.')
    lines += ['## Changes from the original OET', '']
    lines += [f'- {change}' for change in changes] if changes else ['- None']
    lines.append('')

    # Licence and attribution (from each text folder's README)
    copyrights, sourceSections = {}, []
    for folder in folders:
        folderReadme = source.read_text(f'{folder}/README.md')
        for match in re.finditer(r'^Copyright .*$', folderReadme, flags=re.MULTILINE):
            copyright = absolute_links(match.group(0).replace('(c)', '©').rstrip(), folder)
            key = re.sub(r'\s*\(.*$|\.$', '', copyright) # e.g. 'Copyright © 2010-2026 Robert Hunt'
            if len(copyright) > len(copyrights.get(key, '')): # Keep the fullest one
                copyrights[key] = copyright
        section = markdown_section(folderReadme, r'Sources(?: and attribution)?')
        if section:
            sourceSections += [f'### {TEXT_FOLDER_LABELS[folder]}', '', absolute_links(section, folder), '']
    attributionName = title if usaEdition else f'Adapted from the Open English Translation ({versionNames})'
    lines += ['## Licence', '', *copyrights.values(), '',
              'The OET text is licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.en) '
              '(Creative Commons Attribution-ShareAlike 4.0 International). The full licence text is in `LICENSE`.', '',
              'You can copy, share and adapt these files, but you must give credit (keep this attribution), '
              'say what you changed, and share anything you make from them under the same licence.', '',
              'Please attribute this text as:', '',
              f'> _{attributionName}_, © Robert Hunt, [OET.Bible](https://OET.Bible), CC BY-SA 4.0', '']
    if not usaEdition:
        lines += ['The OET copyright holder also requests that changed versions of the OET text '
                  '(including using the OET-RV or OET-LV alone) aren’t called the _Open English Translation_, '
                  'but something like _Adapted from the Open English Translation_.', '']
    if sourceSections:
        lines += ['## Sources and attribution', '',
                  'Please also keep these attributions for the sources that the OET is built on.', '']
        lines += sourceSections
    return '\n'.join(lines).rstrip() + '\n'


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
    usaEdition = is_usa_edition(a) # If so, no 'Adapted' changes
    if usaEdition:
        log('This is a USA edition (only the spelling is changed), so OET isn’t being renamed to ‘Adapted OET’.')
    wordTablesNeeded = set()
    foldersUsed = [] # Source text folders (for the LICENSE and README attributions)
    exported = {VV: [] for VV in versions} # VV -> list of exported book codes
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
            traditionalNames = VV == 'RV' and namesTable is not None
            text = remove_parts(text, BBB, a['parts'])
            if traditionalNames:
                text = change_to_traditional_names(text, BBB, namesTable)
            if VV == 'RV' and a['divine_name'] == 'LORD':
                text = change_yahweh_to_lord(text, BBB)
            if a['spelling'] == 'US':
                text = americanise(text)
                text = mark_usa_edition(text, BBB, VV, usaEdition)
            if not usaEdition:
                text = add_adapted(text)
            if a['word_numbers'] == 'keep':
                for tableName in re.findall(r'^\\rem WORDTABLE (\S+)', text, flags=re.MULTILINE):
                    wordTablesNeeded.add(tableName)
            else:
                text = remove_word_numbers(text)
            written = []
            if 'ESFM' in formats:
                esfmText = simplify_markers(text, VV, traditionalNames) if a['esfm_markers'] == 'essential' else text
                esfmCount += 1
                (formatFolders['ESFM'] / f'{esfmCount:0{width}}_OET-{VV}_{BBB}.ESFM').write_text(esfmText, encoding='utf-8')
                written.append('ESFM')
            if 'USFM' in formats or 'VPL' in formats:
                usfmText = esfm_to_usfm(text, VV, code, traditionalNames)
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
            if written:
                exported[VV].append(code)
                sourceFolder = available[BBB].rsplit('/', 1)[0]
                if sourceFolder not in foldersUsed:
                    foldersUsed.append(sourceFolder)
            log(f'  {BBB} ({code}): {", ".join(written) if written else "nothing (no verses)"}')
    for tableName in sorted(wordTablesNeeded):
        keep_gui_alive()
        log(f'Copying word table {tableName}…')
        try:
            shutil.copyfile(source.get_path(f'{WORD_TABLE_FOLDER}/{tableName}'), formatFolders['ESFM'] / tableName)
        except (OSError, urllib.error.URLError) as err:
            log(f'  WARNING: Unable to copy {tableName}: {err}')
    if wordTablesNeeded and WORD_TABLE_FOLDER not in foldersUsed:
        foldersUsed.append(WORD_TABLE_FOLDER)
    foldersUsed = sorted(foldersUsed, key=list(TEXT_FOLDER_LABELS).index) or [RV_FOLDER] # For LICENSE and README
    log('')
    shutil.copyfile(source.get_path(f'{foldersUsed[0]}/LICENSE'), outputFolder / 'LICENSE')
    log('Copied LICENSE')
    readmeText = make_readme(source, a, name, usaEdition, exported, foldersUsed, sorted(wordTablesNeeded))
    (outputFolder / 'README.md').write_text(readmeText, encoding='utf-8')
    log('Wrote README.md')
    log(f'\nWrote {totalFiles:,} files to {outputFolder}')
    return outputFolder


# ---------------------------------------------------------------------------
# Checking for a newer version of this program
# ---------------------------------------------------------------------------

def version_tuple(version):
    return tuple(int(n) for n in re.findall(r'[0-9]+', version))


def latest_program_version():
    """ Returns the PROGRAM_VERSION of the program on GitHub (or None if we can't get it). """
    try:
        request = urllib.request.Request(ADAPTER_RAW_URL, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(request, timeout=10) as response:
            match = re.search(r"^PROGRAM_VERSION = '([^']+)'", response.read().decode('utf-8'), flags=re.MULTILINE)
        return match.group(1) if match else None
    except (OSError, ValueError):
        return None


def git_output(*args):
    """ Runs git in the program folder and returns its output (or None if it failed). """
    try:
        result = subprocess.run(['git', '-C', str(APP_FOLDER), *args], capture_output=True, text=True,
                                timeout=20, env=GIT_ENV)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def program_git_status():
    """ If this program is in a git clone, returns (newerOnGitHub, currentBranch), otherwise None.
        newerOnGitHub is None if we couldn't contact GitHub. """
    if not (APP_FOLDER / '.git').exists() or git_output('rev-parse', '--git-dir') is None:
        return None
    branch = git_output('rev-parse', '--abbrev-ref', 'HEAD')
    remote = git_output('ls-remote', ADAPTER_CLONE_URL, 'refs/heads/main') # Anonymous HTTPS, so no password needed
    if not remote:
        return None, branch
    remoteCommit = remote.split()[0]
    # If GitHub's latest commit is already in our history, we're up to date (or ahead)
    upToDate = git_output('merge-base', '--is-ancestor', remoteCommit, 'HEAD') is not None
    return not upToDate, branch


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
                ttk.Checkbutton(self.body, text=text, variable=self.var[value],
                                command=self.update_next_text).pack(anchor='w', pady=2)
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
            if validate and not values and not QUESTIONS_BY_KEY[step].allow_none:
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
        root.minsize(760, 720)
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

    def run_command(self, args, cwd=None, env=None):
        """ Runs a command showing its output in the log. Returns True on success. """
        self.log('$ ' + ' '.join(str(a) for a in args))
        try:
            process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding='utf-8', errors='replace', env=env)
        except FileNotFoundError:
            self.log(f'ERROR: Unable to run {args[0]} (is it installed?)')
            return False
        for line in process.stdout:
            self.log('  ' + line.rstrip())
        return process.wait() == 0

    # --- Startup ---

    def startup(self):
        if self.check_for_newer_program(): # Restarting
            return
        self.setup_source()
        self.offer_saved_settings()

    def check_for_newer_program(self):
        """ Tell the user if there's a newer version of this program on GitHub (and offer to update a git clone).
            Returns True if the program is restarting. """
        self.log(f'Checking for a newer version of {PROGRAM_NAME}…')
        latestVersion = latest_program_version()
        gitStatus = program_git_status()
        if gitStatus is not None: # It's a git clone, so check commits (not just the version number)
            newer, branch = gitStatus
        else:
            newer = latestVersion is not None and version_tuple(latestVersion) > version_tuple(PROGRAM_VERSION)
        if newer is None or (gitStatus is None and latestVersion is None):
            self.log('  Unable to check GitHub (are you offline?)')
            return False
        if not newer:
            self.log(f'  You have the latest version (v{PROGRAM_VERSION}).')
            return False
        what = f'Version {latestVersion}' \
            if latestVersion and version_tuple(latestVersion) > version_tuple(PROGRAM_VERSION) else 'A newer copy'
        message = f'{what} of {PROGRAM_NAME} is available on GitHub (you have v{PROGRAM_VERSION}).'
        self.log(f'  {message}')
        if gitStatus is None:
            messagebox.showinfo('Newer version available', f'{message}\n\nYou can download it from\n{ADAPTER_URL}',
                                parent=self.root)
            return False
        if branch != 'main':
            messagebox.showinfo('Newer version available', f'{message}\n\nThis copy is on the ‘{branch}’ branch, '
                                f'so it can’t be updated automatically. Use git to update it from {ADAPTER_URL}',
                                parent=self.root)
            return False
        if not messagebox.askyesno('Newer version available',
                                   f'{message}\n\nDo you want to update it now (with git pull)?', parent=self.root):
            return False
        if not self.run_command(['git', 'pull', '--ff-only', ADAPTER_CLONE_URL, 'main'], cwd=APP_FOLDER, env=GIT_ENV):
            messagebox.showwarning('Update failed', f'Unable to update {PROGRAM_NAME} (see the log).\n\n'
                                   f'You can update it yourself by running ‘git pull’ in\n{APP_FOLDER}',
                                   parent=self.root)
            return False
        if messagebox.askyesno('Updated', f'{PROGRAM_NAME} has been updated. Restart it now?', parent=self.root):
            subprocess.Popen([sys.executable, str(Path(__file__).resolve())], cwd=APP_FOLDER)
            self.root.destroy()
            return True
        self.log('  The update will be used the next time you start the program.')
        return False

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
