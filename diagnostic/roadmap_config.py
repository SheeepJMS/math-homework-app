# Competition Roadmap config: contest catalog and paths (diagnostic-only).
# Used by GET /diagnostic/api/roadmap. Do not touch homework website.

from datetime import datetime

# Path identifiers
PATH_CANADA = 'CANADA'
PATH_AMC = 'AMC'

# AIME qualification thresholds (configurable): min score on AMC10/AMC12 to recommend AIME.
# Values are approximate; adjust per your scoring scheme (e.g. AMC10 top ~2.5%, AMC12 top ~5%).
AIME_AMC10_THRESHOLD = 100   # or use percentile later
AIME_AMC12_THRESHOLD = 90

# Contest catalog: contest_key -> config for mapping papers and building paths.
# match_keywords: list of substrings to match against DiagCompetition.name / DiagExam.title (case-insensitive).
# grade_min/max: inclusive. None means no bound.
# months: list of month numbers (1-12) when contest typically runs.
# sequence_order: order in path (lower = earlier step).
CONTEST_CATALOG = [
    # Canada path (Waterloo etc.) — list more specific matches first (e.g. Gauss 8 before Gauss 7)
    {'contest_key': 'Gauss8', 'display_name': 'Gauss 8', 'path': PATH_CANADA,
     'grade_min': 5, 'grade_max': 8, 'months': [5], 'sequence_order': 2,
     'match_keywords': ['gauss 8', 'gauss8']},
    {'contest_key': 'Gauss7', 'display_name': 'Gauss 7', 'path': PATH_CANADA,
     'grade_min': 4, 'grade_max': 7, 'months': [5], 'sequence_order': 1,
     'match_keywords': ['gauss 7', 'gauss7', 'gauss']},
    {'contest_key': 'Pascal', 'display_name': 'Pascal', 'path': PATH_CANADA,
     'grade_min': 6, 'grade_max': 9, 'months': [2], 'sequence_order': 3,
     'match_keywords': ['pascal']},
    {'contest_key': 'Cayley', 'display_name': 'Cayley', 'path': PATH_CANADA,
     'grade_min': 7, 'grade_max': 10, 'months': [2], 'sequence_order': 4,
     'match_keywords': ['cayley']},
    {'contest_key': 'Fermat', 'display_name': 'Fermat', 'path': PATH_CANADA,
     'grade_min': 8, 'grade_max': 11, 'months': [2], 'sequence_order': 5,
     'match_keywords': ['fermat']},
    {'contest_key': 'Euclid', 'display_name': 'Euclid', 'path': PATH_CANADA,
     'grade_min': 9, 'grade_max': 12, 'months': [4], 'sequence_order': 6,
     'match_keywords': ['euclid']},
    {'contest_key': 'FGH', 'display_name': 'Fryer / Galois / Hypatia', 'path': PATH_CANADA,
     'grade_min': 6, 'grade_max': 12, 'months': [4], 'sequence_order': None,
     'match_keywords': ['fryer', 'galois', 'hypatia', 'fgh']},
    {'contest_key': 'CSMC', 'display_name': 'CSMC', 'path': PATH_CANADA,
     'grade_min': 9, 'grade_max': 12, 'months': [], 'sequence_order': None,
     'match_keywords': ['csmc']},
    {'contest_key': 'CIMC', 'display_name': 'CIMC', 'path': PATH_CANADA,
     'grade_min': None, 'grade_max': None, 'months': [4, 5], 'sequence_order': None,
     'match_keywords': ['cimc']},
    {'contest_key': 'CTMC', 'display_name': 'CTMC', 'path': PATH_CANADA,
     'grade_min': None, 'grade_max': None, 'months': [], 'sequence_order': None,
     'match_keywords': ['ctmc']},
    # AMC path
    {'contest_key': 'AMC8', 'display_name': 'AMC 8', 'path': PATH_AMC,
     'grade_min': 3, 'grade_max': 8, 'months': [1], 'sequence_order': 1,
     'match_keywords': ['amc 8', 'amc8', 'amc 8']},
    {'contest_key': 'AMC10', 'display_name': 'AMC 10', 'path': PATH_AMC,
     'grade_min': 7, 'grade_max': 10, 'months': [11], 'sequence_order': 2,
     'match_keywords': ['amc 10', 'amc10']},
    {'contest_key': 'AMC12', 'display_name': 'AMC 12', 'path': PATH_AMC,
     'grade_min': 9, 'grade_max': 12, 'months': [11], 'sequence_order': 3,
     'match_keywords': ['amc 12', 'amc12']},
    {'contest_key': 'AIME', 'display_name': 'AIME', 'path': PATH_AMC,
     'grade_min': None, 'grade_max': None, 'months': [2, 3], 'sequence_order': 4,
     'match_keywords': ['aime']},
]

# Ordered sequence for each path (contest_keys only; used for current_stage / next_target).
CANADA_SEQUENCE = ['Gauss7', 'Gauss8', 'Pascal', 'Cayley', 'Fermat', 'Euclid']
AMC_SEQUENCE = ['AMC8', 'AMC10', 'AMC12', 'AIME']


def get_catalog_by_key():
    """Return dict contest_key -> config."""
    return {c['contest_key']: c for c in CONTEST_CATALOG}


def get_sequence_for_path(path):
    if path == PATH_CANADA:
        return CANADA_SEQUENCE
    if path == PATH_AMC:
        return AMC_SEQUENCE
    return []


def infer_contest_key(competition_name, exam_title):
    """Map competition name + exam title to contest_key using match_keywords. Returns first match or None."""
    text = ' '.join([str(competition_name or ''), str(exam_title or '')]).lower()
    for c in CONTEST_CATALOG:
        for kw in c.get('match_keywords', []):
            if kw.lower() in text:
                return c['contest_key']
    return None


def grade_eligible(contest_key, grade):
    """True if grade is within contest's grade range. If grade is None, treat as eligible (generic)."""
    if grade is None:
        return True
    catalog = get_catalog_by_key()
    c = catalog.get(contest_key)
    if not c:
        return False
    gmin, gmax = c.get('grade_min'), c.get('grade_max')
    if gmin is not None and grade < gmin:
        return False
    if gmax is not None and grade > gmax:
        return False
    return True


def months_near(contest_key, as_of_date, within_months=3):
    """True if contest's typical month is within next `within_months` months from as_of_date."""
    catalog = get_catalog_by_key()
    c = catalog.get(contest_key)
    if not c or not c.get('months'):
        return False
    now_m = as_of_date.month
    for m in c['months']:
        # simple: same month or next few months
        delta = (m - now_m) if m >= now_m else (m + 12 - now_m)
        if 0 <= delta <= within_months:
            return True
    return False
