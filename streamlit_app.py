import streamlit as st
import pandas as pd
import io
import os
import re
import json
import requests as _requests
from datetime import date, timedelta
import base64
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from docx import Document

# WINGS 자동화 (로컬 실행 시에만 활성화; 클라우드 배포에서는 ImportError로 비활성화)
try:
    from wings_scraper import download_wings_excel as _wings_fetch
    _WINGS_AUTO = True
except ImportError:
    _WINGS_AUTO = False


# ---------------------------------------------------------------------------
# Persistent storage via GitHub API
# ---------------------------------------------------------------------------
_GITHUB_REPO = 'PMM-YB/Star-Truck-Korea-Database-Systemization'
_DATA_FILE = 'code_data.json'


def _get_github_token():
    """Get GitHub token from Streamlit secrets."""
    try:
        return st.secrets.get('GITHUB_TOKEN', '')
    except Exception:
        return ''


@st.cache_resource(ttl=60)
def _load_persistent_data():
    """Load persistent code data from GitHub repo (cached 60s)."""
    token = _get_github_token()
    if not token:
        return None
    try:
        headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
        resp = _requests.get(
            f'https://api.github.com/repos/{_GITHUB_REPO}/contents/{_DATA_FILE}',
            headers=headers, timeout=10
        )
        if resp.status_code == 200:
            import base64 as _b64
            content = _b64.b64decode(resp.json()['content']).decode('utf-8')
            return json.loads(content)
    except Exception:
        pass
    return None


def _save_persistent_data(data: dict):
    """Save code data to GitHub repo."""
    token = _get_github_token()
    if not token:
        return False
    try:
        headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
        url = f'https://api.github.com/repos/{_GITHUB_REPO}/contents/{_DATA_FILE}'
        # Get current file SHA
        resp = _requests.get(url, headers=headers, timeout=10)
        sha = resp.json().get('sha', '') if resp.status_code == 200 else ''
        # Encode content
        import base64 as _b64
        content_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        payload = {
            'message': 'Update code data (auto-save)',
            'content': _b64.b64encode(content_bytes).decode(),
        }
        if sha:
            payload['sha'] = sha
        resp = _requests.put(url, headers=headers, json=payload, timeout=15)
        if resp.status_code in (200, 201):
            _load_persistent_data.clear()  # Clear cache so next load gets fresh data
            return True
    except Exception:
        pass
    return False


def _collect_current_data() -> dict:
    """Collect current session state into a persistable dict."""
    return {
        'allcode_added': sorted(st.session_state.get('_allcode_added', set())),
        'allcode_removed': sorted(st.session_state.get('_allcode_removed', set())),
        'allcode_custom_desc': dict(st.session_state.get('_allcode_custom_desc', {})),
        'mand_codes': sorted(st.session_state.get('_mand_codes_set', set())),
        'mand_custom_desc': dict(st.session_state.get('_mand_custom_desc', {})),
        'except_codes': sorted(st.session_state.get('_except_codes_set', set())),
        'except_custom_desc': dict(st.session_state.get('_except_custom_desc', {})),
    }


def _apply_persistent_data(data: dict):
    """Apply loaded persistent data to session state (only on first load)."""
    if data is None:
        return
    if st.session_state.get('_persistent_loaded'):
        return
    st.session_state['_persistent_loaded'] = True
    if 'allcode_added' in data:
        st.session_state['_allcode_added'] = set(data['allcode_added'])
    if 'allcode_removed' in data:
        st.session_state['_allcode_removed'] = set(data['allcode_removed'])
    if 'allcode_custom_desc' in data:
        st.session_state['_allcode_custom_desc'] = dict(data['allcode_custom_desc'])
    if 'mand_codes' in data:
        st.session_state['_mand_codes_set'] = set(data['mand_codes'])
    if 'mand_custom_desc' in data:
        st.session_state['_mand_custom_desc'] = dict(data['mand_custom_desc'])
    if 'except_codes' in data:
        st.session_state['_except_codes_set'] = set(data['except_codes'])
    if 'except_custom_desc' in data:
        st.session_state['_except_custom_desc'] = dict(data['except_custom_desc'])


def _auto_save():
    """Save current state to GitHub (call after any code change)."""
    data = _collect_current_data()
    _save_persistent_data(data)


# ---------------------------------------------------------------------------
# Option code descriptions (SAM / WINGS codes → human-readable description)
# ---------------------------------------------------------------------------
OPTION_CODE_MAP = {
    # A
    "A0A": "Two position sensors, on rear axle",
    "A0B": "Axle, wheel mounting track, narrow",
    "A0C": "Axle, wheel mounting track, wide",
    "A0D": "2nd tandem rear axle, disengageable and liftable",
    "A0H": "Protective plate for HAD high-pressure lines",
    "A0K": "2nd generation steered leading axle/trailing axle",
    "A1A": "Front axle with air suspension",
    "A1C": "Front axle 7.5 t",
    "A1D": "Front axle 8.0 t",
    "A1E": "Front axle 9.0 t",
    "A1F": "Front axle 9.5 t",
    "A1G": "Front axle 7.1 t",
    "A1H": "Hydraulic Auxiliary Drive (HAD)",
    "A1J": "Front axle 4.4 t",
    "A1K": "Front axle 5.3 t",
    "A1L": "Front axle 6.1 t",
    "A1M": "Front axle 4.1 t",
    "A1O": "Front axle, 6.0 t",
    "A1P": "Front axle 4.7 t",
    "A1Q": "Front axle 8.5 t",
    "A1R": "Front axle 3.2 t",
    "A1U": "Front axle 10.0 t",
    "A1V": "Cranked front axle, higher ground clearance",
    "A1W": "Differential lock, front axle",
    "A1X": "Straight front axle, increased ground clearance",
    "A1Y": "Front axle, straight version",
    "A1Z": "Front axle, offset version",
    "A2A": "Rear axle, crown wheel 325, hypoid, 7.2 t",
    "A2B": "Rear axle, crown wheel 325, hypoid, 6.2 t",
    "A2C": "Rear axle, crown wheel 325, hypoid, 8.1 t",
    "A2E": "Rear axle, crown wheel 440, hypoid, 13.0 t",
    "A2F": "Rear axle, crown wheel 233, planetary, 13.4 t",
    "A2G": "Rear axle, crown wheel 300, planetary, 13.4 t",
    "A2H": "Rear axle, crown wheel 300, planetary, 16.0 t",
    "A2I": "Rear axle, crown wheel 485, hypoid, 13.0 t",
    "A2J": "Rear axle, crown wheel 390, hypoid, 10.0 t",
    "A2K": "Rear axle, crown wheel 410, hypoid, 10.8 t",
    "A2L": "Rear axle, crown wheel 390, hypoid, 11.0 t",
    "A2M": "Rear axle, crown wheel 368, hypoid, 7.7 t",
    "A2O": "Rear axle, ring gear 390, hypoid, 9.5 t, single",
    "A2P": "Rear axle, crown wheel 390, hypoid, 9.2 t",
    "A2Q": "Rear axle, crown wheel 325, hypoid, 8.3 t",
    "A2R": "Rear axle, crown wheel 325, hypoid, 6.4 t",
    "A2S": "Rear axle, electrical, 2-gear, 11.5t",
    "A2T": "Rear axle, crown wheel 325, hypoid, 5.3 t",
    "A2V": "Rear axle, ring gear 390, hypoid, 7.7 t, single",
    "A2W": "Rear axle, 440 crown wheel, high drive, 13.0 t",
    "A2X": "Rear axle with active lubrication, controlled",
    "A2Y": "Rear axle, narrow version",
    "A2Z": "Differential lock, rear axle",
    "A3D": "Rear axle with active lubrication, uncontrolled",
    "A3E": "Rear axle, crown wheel 390, hypoid, NFD, 10.0 t",
    "A3F": "Rear axle, crown wheel 457, hypoid, 13.0 t",
    "A3G": "Rear axle, electrical, 4-gear, 13.0t",
    "A4A": "Leading axle, 7.5 t, de-loadable, liftable",
    "A4B": "Leading axle, 7.5 t, steered, de-loadable",
    "A4D": "Leading axle, 7.1 t, friction-steered, liftable",
    "A4E": "Leading axle, 10 t, liftable,unsteered, twin tyres",
    "A4F": "Trailing axle BR2/T-5.0L/S17.5",
    "A4H": "Leading axle, 4.3 t, de-loadable, liftable",
    "A4I": "Trail. axle 5.3 t, steered, de-loadable, liftable",
    "A4J": "Trail. axle 6.1 t, steered, de-loadable, liftable",
    "A4K": "Trail. axle 10 t, de-loadable, liftable,twin tyres",
    "A4L": "Trailing axle, 10 t, de-loadable, twin tyres",
    "A4M": "Trail. axle 10 t, steel-sprung,liftable,twin tyres",
    "A4P": "Trailing axle, 8.5 t, liftable, twin tyres",
    "A4Q": "Trailing axle, 9 t, steered, de-loadable, liftable",
    "A4R": "Trailing axle, 9 t, steered, de-loadable",
    "A4S": "Trailing axle, 9 t, de-loadable, liftable",
    "A4T": "Trailing axle, 8 t, steered, de-loadable, liftable",
    "A4U": "Trailing axle, 8 t, steered, de-loadable",
    "A4V": "Trailing axle, 8 t, de-loadable, liftable",
    "A4W": "Trailing axle, 7.5 t, de-loadable",
    "A4X": "Trailing axle, 7.5 t, steered, de-loadable",
    "A4Y": "Trail. axle, 7.5 t, steered, de-loadable, liftable",
    "A4Z": "Trailing axle, 7.5 t, de-loadable, liftable",
    "A5A": "Axle ratio i = 2.278",
    "A5B": "Axle ratio i = 2.533",
    "A5C": "Axle ratio i = 2.733",
    "A5D": "Axle ratio i = 2.846",
    "A5E": "Axle ratio i = 2.929",
    "A5F": "Axle ratio i = 2.923",
    "A5G": "Axle ratio i = 2.412",
    "A5H": "Axle ratio i = 2.611",
    "A5I": "Axle ratio i = 3.077",
    "A5J": "Axle ratio i = 3.154",
    "A5K": "Axle ratio i = 3.308",
    "A5L": "Axle ratio i = 3.417",
    "A5M": "Axle ratio i = 3.431",
    "A5N": "Axle ratio i = 3.583",
    "A5P": "Axle ratio i = 3.714",
    "A5Q": "Axle ratio i = 3.727",
    "A5R": "Axle ratio i = 3.909",
    "A5S": "Axle ratio i = 3.636",
    "A5V": "Axle ratio i = 4.100",
    "A5W": "Axle ratio i = 4.143",
    "A5X": "Axle ratio i = 4.300",
    "A5Y": "Axle ratio i = 4.333",
    "A5Z": "Axle ratio i = 4.556",
    "A6A": "Axle ratio i = 4.571",
    "A6B": "Axle ratio i = 4.778",
    "A6C": "Axle ratio i = 4.833",
    "A6D": "Axle ratio i = 4.750",
    "A6E": "Axle ratio i = 4.875",
    "A6G": "Axle ratio i = 5.125",
    "A6H": "Axle ratio i = 5.143",
    "A6I": "Axle ratio i = 5.222",
    "A6J": "Axle ratio i = 5.333",
    "A6K": "Axle ratio i = 5.849",
    "A6L": "Axle ratio i = 5.857",
    "A6M": "Axle ratio i = 5.875",
    "A6N": "Axle ratio i = 5.250",
    "A6P": "Axle ratio i = 5.714",
    "A6Q": "Axle ratio i = 6.000",
    "A6R": "Axle ratio i = 6.824",
    "A6S": "Axle ratio i = 6.857",
    "A6T": "Axle ratio i = 6.143",
    "A6Y": "Axle ratio i = 2.643",
    "A6Z": "Axle ratio i = 3.231",
    "A9Y": "Deletion, rear axle (CKD)",
    "A9Z": "Deletion, front axle (CKD)",
    "ABC": "Test code logic, alpha-alpha-alpha",
    "AZZ": "Front axles 1 and 2 Distance 2000 mm",
    # B
    "B0A": "Pipe fracture protection, for braking system",
    "B0C": "Control code, protective ring for ABS sensor",
    "B0D": "Linkage adjustment+lubricat. nipple, on drum brake",
    "B1A": "Electronic braking system with ABS",
    "B1B": "Electronic braking system with ABS and ASR",
    "B1C": "Electronic air-processing unit, low",
    "B1D": "Electronic air-processing unit, medium",
    "B1E": "Electronic air-processing unit, high",
    "B1F": "Heating, electronic air-processing unit",
    "B1G": "Pressure control system, 10 bar",
    "B1H": "Electr. compressed air supply and control, centre",
    "B1I": "Electr. compressed air supply and control, upper",
    "B1U": "Global ABS+ASR",
    "B1V": "Holding brake at front axle",
    "B1X": "Frequent-stop brake",
    "B1Y": "ABS brakes",
    "B1Z": "ABS, disengageable",
    "B2A": "Disc brakes on front and rear axle",
    "B2B": "Drum brakes on front and rear axle",
    "B2C": "Disc brakes on fr. axle, drum brakes on rear axle",
    "B2D": "Cover plate for brake discs",
    "B2E": "Disc brakes with full protection",
    "B2F": "Deactivation of brake on 2nd axle, lifted",
    "B2G": "Disc brakes, with protection for rear tipper",
    "B2X": "Parking brake, electronic",
    "B2Z": "Parking brake, additional on front axle",
    "B3F": "Secondary oil retarder, 2nd generation",
    "B3G": "Permanent-magnet retarder",
    "B3H": "Water-type secondary retarder",
    "B3K": "Secondary oil retarder",
    "B3L": "Secondary oil retarder (Voith)",
    "B4A": "Condensation monitoring, for compressed air sys.",
    "B4K": "Compressed air tank, alumin, for braking sys. only",
    "B4L": "All compressed air tanks, aluminium",
    "B4M": "Air reservoir, steel",
    "B4Z": "Air reservoir, additional",
    "B5A": "Trailer brake, 2-line, brake connections, left",
    "B5B": "Trailer brake, 2-line",
    "B5C": "Independent trailer brake",
    "B5D": "Trailer Stability Control Assist (TSA)",
    "B5E": "Independent trailer brake, electronic",
    "B5F": "Trailer control, separate",
    "B5I": "Brake and electrical connections, high",
    "B5J": "Brake and electrical connections, low",
    "B5K": "Coupling heads self-locking, England standard",
    "B5L": "Trailer brake connection, rear, Duo-Matic+Standard",
    "B5M": "Trailer brake connection, front, Duo-Matic",
    "B5N": "Compressed air supply connection, front",
    "B5Q": "Brackets for coupling heads, with quick-release",
    "B5R": "Trailer brake, 3-line",
    "B9V": "Deletion, heating, compressed-air supply unit",
    "B9W": "Deletion, condensation monitoring f.comp.-air sys.",
    "B9X": "Omission of full protection at 1st+2nd front axle",
    "B9Y": "Deletion, trailer brake and socket",
    "B9Z": "Deletion of full disc brake guard, 2nd front axle",
    # C
    "C0A": "Frame overhang 750 mm",
    "C0B": "Frame overhang 800 mm",
    "C0D": "Frame overhang 900 mm",
    "C0E": "Frame overhang 950 mm",
    "C0F": "Frame overhang 1000 mm",
    "C0G": "Frame overhang 1050 mm",
    "C0J": "Frame overhang 1200 mm",
    "C0L": "Frame overhang 1300 mm",
    "C0M": "Frame overhang 1350 mm",
    "C0O": "Frame overhang 850 mm",
    "C0Q": "Frame overhang 1500 mm",
    "C0R": "Frame overhang 1550 mm",
    "C0S": "Frame overhang 1600 mm",
    "C0T": "Frame overhang 1650 mm",
    "C0W": "Frame overhang 1800 mm",
    "C0X": "Frame overhang 1850 mm",
    "C0Y": "Frame overhang 1900 mm",
    "C0Z": "Frame overhang 1950 mm",
    "C1B": "Wheelbase 2550 mm",
    "C1C": "Wheelbase 2650 mm",
    "C1D": "Wheelbase 3020 mm",
    "C1G": "Wheelbase 2990 mm",
    "C1H": "Wheelbase 3150 mm",
    "C1I": "Wheelbase 3200 mm",
    "C1J": "Wheelbase 3250 mm",
    "C1K": "Wheelbase 3300 mm",
    "C1L": "Wheelbase 3260 mm",
    "C1M": "Wheelbase 3320 mm",
    "C1N": "Wheelbase 3400 mm",
    "C1P": "Wheelbase 3450 mm",
    "C1Q": "Wheelbase 3550 mm",
    "C1R": "Wheelbase 3600 mm",
    "C1S": "Wheelbase 3560 mm",
    "C1T": "Wheelbase 3610 mm",
    "C1U": "Wheelbase 3620 mm",
    "C1W": "Wheelbase 3700 mm",
    "C1X": "Wheelbase 3750 mm",
    "C1Y": "Wheelbase 3850 mm",
    "C1Z": "Wheelbase 3900 mm",
    "C2A": "Wheelbase 3860 mm",
    "C2C": "Wheelbase 4000 mm",
    "C2E": "Wheelbase 4050 mm",
    "C2F": "Wheelbase 4160 mm",
    "C2G": "Wheelbase 4150 mm",
    "C2I": "Wheelbase 4200 mm",
    "C2J": "Wheelbase 4220 mm",
    "C2K": "Wheelbase 4250 mm",
    "C2L": "Wheelbase 4300 mm",
    "C2N": "Wheelbase 4500 mm",
    "C2O": "Wheelbase 4550 mm",
    "C2P": "Wheelbase 4600 mm",
    "C2Q": "Wheelbase 4760 mm",
    "C2R": "Wheelbase 4800 mm",
    "C2S": "Wheelbase 4820 mm",
    "C2T": "Wheelbase 4850 mm",
    "C2U": "Wheelbase 4900 mm",
    "C2V": "Wheelbase 4400 mm",
    "C2W": "Wheelbase 3100 mm",
    "C2Y": "Wheelbase 5150 mm",
    "C2Z": "Wheelbase 5750 mm",
    "C3A": "Wheelbase 5100 mm",
    "C3B": "Wheelbase 5200 mm",
    "C3D": "Wheelbase 5360 mm",
    "C3E": "Wheelbase 5400 mm",
    "C3F": "Wheelbase 5420 mm",
    "C3G": "Wheelbase 5450 mm",
    "C3H": "Wheelbase 5500 mm",
    "C3J": "Wheelbase 5700 mm",
    "C3K": "Wheelbase 5800 mm",
    "C3L": "Wheelbase 5960 mm",
    "C3M": "Wheelbase 6000 mm",
    "C3N": "Wheelbase 6050 mm",
    "C3O": "Wheelbase 4700 mm",
    "C3P": "Wheelbase 6100 mm",
    "C3Q": "Wheelbase 6260 mm",
    "C3R": "Wheelbase 6300 mm",
    "C3S": "Wheelbase 6350 mm",
    "C3T": "Wheelbase 6400 mm",
    "C3U": "Wheelbase 6600 mm",
    "C3V": "Wheelbase 6700 mm",
    "C3W": "Wheelbase 3050 mm",
    "C3X": "Wheelbase 7250 mm",
    "C4C": "Frame overhang 2100 mm",
    "C4E": "Frame overhang 2200 mm",
    "C4F": "Frame overhang 2250 mm",
    "C4I": "Frame overhang 2400 mm",
    "C4K": "Frame overhang 2500 mm",
    "C4L": "Frame overhang 2550 mm",
    "C4P": "Frame overhang 2700 mm",
    "C4R": "Frame overhang 2800 mm",
    "C4S": "Frame overhang 2850 mm",
    "C4V": "Frame overhang 3000 mm",
    "C4X": "Frame overhang 3100 mm",
    "C4Y": "Frame overhang 3150 mm",
    "C5A": "ADR chassis",
    "C5B": "Step plate above frame, partial cover",
    "C5C": "Step plate above frame, full cover",
    "C5D": "Step, behind cab, left",
    "C5E": "Pre-install., chassis for danger. goods transport",
    "C5F": "Chassis parts, for trailing axle lifting device",
    "C5G": "Mounting parts, for loading crane, front",
    "C5H": "Attachment fixtures, rigid",
    "C5I": "Mounting parts, for platform",
    "C5J": "Mounting parts, for tipper",
    "C5K": "Mounting parts, for concrete mixer",
    "C5L": "Steps, behind cab, right",
    "C5M": "Pre-installation, for bodies without subframe",
    "C5N": "Frame, for refuse-collection vehicle, rear loader",
    "C5O": "Preparation for special front-mounted equipment",
    "C5P": "Bolted frame",
    "C5R": "Springing, for reduced height",
    "C5S": "Axle/chassis parts, narrow vehicle",
    "C5T": "Reinforced frame",
    "C5U": "Road paver preparation",
    "C5V": "Frame front end, reinforced, for spec. attachments",
    "C5W": "Frame height, low, for all-wheel-drive vehicles",
    "C5X": "Pre-inst. for on-road tipper body, no subframe",
    "C5Y": "Frame height lowered by 25 mm",
    "C5Z": "Mounting parts, for platform with cargo liftgate",
    "C6A": "Steering ZF 8090",
    "C6B": "Steering ZF 8095",
    "C6C": "Steering, single-circuit",
    "C6D": "Steering ZF 8098",
    "C6E": "Steering wheel lock with mechanical vehicle key",
    "C6F": "Steering, Shibao",
    "C6G": "Steering, Servotwin",
    "C6H": "Steering, Servotwin, 4-axle and 9t FA, air",
    "C6I": "Power steering pump, controlled",
    "C6J": "Power steering pump, uncontrolled",
    "C6K": "Standard steering column",
    "C6L": "Power-assisted steering, reinforced, from 9 t",
    "C6M": "Stabiliser, reinforced, for RA",
    "C6P": "Power steering pump, electronically controlled",
    "C6Q": "Stabiliser, front axle",
    "C6R": "Shock absorber for firm-ride springs, from 16 t",
    "C6S": "Stabiliser, for extremely high loads, rear axle",
    "C6T": "Stabiliser, for extremely high loads, front axle",
    "C6U": "Extra anti-roll bar, rear/trailing axle",
    "C6V": "Stabiliser, 1st rear axle",
    "C6W": "Stabiliser, reinforced, 2nd rear axle",
    "C6X": "Stabiliser, reinforced, front axle",
    "C6Y": "Stabiliser, under frame, rear axle",
    "C6Z": "Stabiliser, reinforced, under frame, rear axle",
    "C7A": "Rear underride guard (ECE)",
    "C7B": "Rear underride guard, folding, for air-spr. tipper",
    "C7C": "R.underride gd,fold., steel tipper, test force 80%",
    "C7D": "Rear underride guard, pneumatic tipper, road paver",
    "C7E": "Front underride guard (ECE), steel",
    "C7F": "Front underride guard (ECE), aluminium",
    "C7G": "Protective device, side, behind rear axle",
    "C7H": "Protective device, side",
    "C7I": "Battery carrier cover, lockable",
    "C7J": "Battery carrier, batteries side by side",
    "C7K": "Battery carrier, batteries stacked",
    "C7L": "Battery and equipment carrier, right",
    "C7M": "Protective device, side, weight-optimised",
    "C7N": "Battery and equipment carrier, 80 mm lowered",
    "C7P": "Free space for swap bodies, low frame",
    "C7Q": "Free space for crane outrigger feet",
    "C7R": "Free space on frame, right",
    "C7S": "Free space on frame, left",
    "C7T": "Integral rear end",
    "C7U": "Clearance for swap bodies, 1120mm ground clearance",
    "C7W": "Omission of stabiliser, front axle",
    "C7Y": "Frame, non-assembled, stage I (CKD)",
    "C7Z": "Frame, non-assembled, stage II (CKD)",
    "C8A": "Aluminium wing, rear axle",
    "C8B": "Rear wing, 2550 mm vehicle width",
    "C8C": "Rear wing, 2500 mm vehicle width",
    "C8D": "Quarter-mudguards for fully integrated tipper",
    "C8E": "Half-mudguards for fully integrated tipper",
    "C8F": "Wing, for chassis transit",
    "C8G": "Wing, three-piece, without EC splash guard",
    "C8H": "Wing, 3-piece, with EC splash guard",
    "C8I": "Splash guard (EC), front",
    "C8J": "Splash guard, in wing",
    "C8L": "Wing, optimised for body",
    "C8M": "Mudguard centre piece, low",
    "C8P": "Omission of reinforced frame",
    "C8Q": "Centre mounting, reinforced",
    "C8R": "Wing, 1-piece, without EC splash guard",
    "C8S": "Deletion of extra anti-roll bar, rear/trail. axle",
    "C8T": "Deletion, wings for chassis transit",
    "C8U": "Vehicle level, lowered",
    "C8V": "Side fairings, for leading axle",
    "C8W": "Omission of underbody panelling, aerodynamic",
    "C8X": "Wing, 1-piece, with splash guard",
    "C8Y": "Aerodynamic underbody panelling",
    "C8Z": "Side skirts, aerodynamic",
    "C9A": "Mudguard centre part, high",
    "C9B": "Frame overhang 3300 mm",
    "C9C": "Omission of frame",
    "C9D": "Rear underride guard by BB, preserves N3G with V0V",
    "C9E": "Frame overhang, 3450 mm",
    "C9F": "Battery & equipm. carrier, wing bracket integrated",
    "C9G": "Omission, support angle for road dumper",
    "C9H": "Frame overhang 3600 mm",
    "C9I": "Frame overhang, 3900 mm",
    "C9J": "Deletion, stabiliser, rear axle",
    "C9K": "Frame overhang, retrofitted 3rd axle",
    "C9L": "Frame overhang, extended, 200 mm",
    "C9M": "Frame overhang extended, 400 mm, 2-axle vehicle",
    "C9N": "Frame overhang, extended, 300 mm",
    "C9O": "Deletion, steering system (CKD)",
    "C9P": "Frame overhang, extended, 600 mm",
    "C9Q": "Pre-installation, body width 2300 mm",
    "C9R": "Deletion, protection device, side",
    "C9S": "Deletion mounting parts, on frame",
    "C9T": "Pre-installation frame, for shackle attachment",
    "C9U": "Deletion, wings at 2nd front axle",
    "C9V": "Deletion, wings, rear",
    "C9W": "Deletion, splash guard (EC), front",
    "C9X": "Deletion, wing stays, rear",
    "C9Y": "Deletion, rear underride guard (ECE)",
    "C9Z": "Deletion, front underride guard (ECE)",
    "CGH": "Battery and equipment carrier, 100 mm lowered",
    "CLW": "Steering oil cooling",
    "CLX": "Servotwin, optimised, dual-circuit",
    "COY": "Steering column, Comfort Plus",
    "CRC": "Frame thickness 8 mm",
    "CRT": "Omission of 1st body mounting after cab",
    "CSJ": "Underbody panelling, ProCabin, standard",
    "CSK": "Underbody panelling, ProCabin, optimised",
    "CYZ": "Step, behind cab, left, not ECE-compliant",
    "CZC": "Kick-out behind rear axle mudguard",
    "CZD": "Omission of kick-out behind rear axle mudguard",
    "CZE": "Front mudguard, fender skirt, aerodynam. optimised",
    "CZG": "Wheel well, interior panelling",
    "CZH": "Front mudguard, fender skirt, standard",
    "CZN": "Deletion, aerodynamic side trim",
    "CZQ": "Wing, two-piece, without EC splash guard",
    "CZR": "Front underride guard (SASO)",
    "CZU": "Rear underride guard (ECE-R 58/3)",
    "CZW": "Step plate above frame, extended",
    "CZX": "Licence plate holder, with metric thread",
    "CZY": "Wing, for chassis transfer, not ECE-conform",
    # D
    "D0A": "Leather steering wheel",
    "D0S": "Compressed-air connection, in cab",
    "D1C": "Driver's suspension seat, comfort",
    "D1D": "Driver's suspension seat, ventilated",
    "D1P": "Co-driver's suspension seat, comfort",
    "D2M": "Co-driver's seat backrest, release mechanism",
    "D2N": "Driver's seat backrest, release mechanism",
    "D2W": "Armrests on both sides, co-driver's seat",
    "D2Y": "Seat belt monitor",
    "D3B": "Luxury bed, bottom",
    "D3E": "Stowage facility, padded",
    "D3I": "Bunk, bottom",
    "D3K": "Seat cover, Dinamica, black, driver's seat",
    "D3L": "Seat cover, Dinamica, black, co-driver's seat",
    "D3R": "Seat cover, leather, co-driver's seat",
    "D3S": "Seat cover, leather, driver's seat",
    "D4J": "Mattress, ExtraPremiumComfort, bottom",
    "D4Q": "Shaving mirror",
    "D4S": "Roller sunblind, 1-piece, electric, windscreen",
    "D4U": "Curtain, for rear wall window",
    "D4Y": "Sunblind, side, driver's side",
    "D4Z": "Sunblind, side, driver's and co-driver's side",
    "D5F": "LED ambient lighting, driving and living",
    "D5O": "StyleLine",
    "D5R": "TrendLine",
    "D5S": "Seat cover, prem. flat-weave fabric, driver's seat",
    "D5T": "Seat cover, prem. flat-weave fabr., passenger seat",
    "D5V": "Flooring, weight-optimised",
    "D5Y": "Rubber mats, driver's and co-driver's side",
    "D5Z": "Carpet, engine tunnel",
    "D6C": "Auxiliary air conditioning, electric",
    "D6F": "Air conditioning system",
    "D6G": "Automatic climate control",
    "D6I": "Residual engine heat utilisation",
    "D6M": "Auxiliary hot water heater, cab",
    "D6V": "Noise and heat insulation of cab",
    "D6Z": "Construction-site filter",
    "D7A": "Heat insulation, additional",
    "D7F": "Stowage flaps, above windscreen, one lockable",
    "D7G": "Stowage compartment lid, driver and co-driver side",
    "D7I": "Stowage trays for stowage compartments",
    "D7J": "Drawers, under bed",
    "D7K": "Drawer, under dash support",
    "D7R": "Stowage flaps, above windscreen",
    "D7V": "Table, on co-driver's side",
    "D8A": "Roof hatch/vent, roof",
    "D8M": "Sliding/tilting sunroof, electric, glass version",
    "D8X": "Seat base, low, 40 mm lower",
    "D9A": "Pre-installation luxury bed, top, wide",
    "DUP0": "Basetype",
    "D0B": "Home-Line interior design",
    "D0C": "Style-Line interior design",
    "D0D": "Wood/leather steering wheel",
    "D0E": "Steering wheel, diameter 500 mm",
    "D0J": "Leather steering wheel in genuine chrome look",
    "D0K": "Leather steering wheel in matt wood look",
    "D0L": "Smokers pack",
    "D0Q": "Grab handles in cab, on both B-pillars",
    "D0U": "Smoke detector, in cab",
    "D0V": "Rear-view mirror, in cab",
    "D0Y": "Cab interior fittings, loose, stage I (CKD)",
    "D0Z": "SoloStar Concept",
    "D1A": "Driver's fixed seat, standard",
    "D1B": "Driver's suspension seat, standard",
    "D1F": "Driver susp. seat standard w. fore/aft hor.damping",
    "D1G": "Driver's suspension seat, comfort, without heating",
    "D1H": "Co-dr. susp. seat standard w. fore/aft hor.damping",
    "D1I": "Co-driver's suspension seat, comfort, w/o heating",
    "D1J": "Co-driver's seat,static,head restraint,stowage",
    "D1K": "2 co-driver's seats,static,head restraints,stowage",
    "D1L": "3 co-driver's seats, static, head restraints",
    "D1M": "Rigid co-driver's seat, single",
    "D1N": "Fold-up co-driver's seat",
    "D1S": "Co-driver's suspension seat, standard",
    "D1T": "Co-driver's fixed seat, folding",
    "D1U": "Co-driver's fixed seat, standard",
    "D1V": "Double bench seat",
    "D1W": "Seat/bunk combination, 1 bunk",
    "D1X": "Seat/bunk combination, 2 bunks",
    "D1Z": "Centre seat, with 3-point seat belt",
    "D2A": "Cent.seat,static,3-pt.s.belt,head restr.,fold.rest",
    "D2B": "Driver's suspension seat, standard US variant",
    "D2C": "Co-driv.seat, static, head rest, stowage, US vers.",
    "D2F": "2-seater bench seat, co-driver, rigid",
    "D2G": "2-seat bench seat, co-driver, adjustable, w/ table",
    "D2K": "Massage function, for driver's seat",
    "D2L": "Massage function, for co-driver's seat",
    "D2O": "Seat belts, red",
    "D2P": "Seat belt, red, for centre seat",
    "D2Q": "Seat belt, red, for co-driver's seat",
    "D2T": "Comfort package, driver's seat",
    "D2U": "Comfort package, co-driver's seat",
    "D2V": "Armrests on both sides, driver's seat",
    "D2Z": "Seat belt, red, for driver's seat",
    "D3A": "Luxury bed, top, wide, with levelling control",
    "D3C": "Bed, bottom",
    "D3D": "Bed, top, narrow",
    "D3F": "Luxury bed, top, narrow",
    "D3G": "Luxury bed, bottom, weight-optimised",
    "D3H": "Bed, top, folding, 90 degrees",
    "D3J": "Luxury bed, bottom, extra wide, folding",
    "D3M": "Mattress, PremiumComfort, bottom",
    "D3N": "Mattress, PremiumComfort, top",
    "D3O": "Seat cov., Dinamica star, almond beige, dr.'s seat",
    "D3P": "Seat cov., Dinamica star, almond beige, c-dr. seat",
    "D3Q": "Seat cover, velour, driver's seat",
    "D3T": "Seat cover, velour, co-driver's seat, centre seat",
    "D3U": "Seat cover, flat-weave fabric and leather, outer",
    "D3V": "Seat cover, leather",
    "D3W": "Seat cover, Dinamica star, black",
    "D3X": "Seat cover, flat-weave fabric",
    "D3Y": "Seat cover, velour",
    "D3Z": "Seat cover, man-made leather",
    "D4A": "Standard cockpit",
    "D4B": "Classic cockpit",
    "D4C": "Comfort cockpit",
    "D4F": "Mattress topper for upper comfort bed top, wide",
    "D4H": "Comfort berth, bottom, not adjustable",
    "D4I": "Compact bunk, top, folding",
    "D4K": "CabLock",
    "D4L": "Power window, co-driver's door",
    "D4R": "Window lifters, manual, driver and co-driver door",
    "D4T": "Curtain, along side of bed(s)",
    "D4V": "Power window, driver's side",
    "D4W": "Power windows, all-round",
    "D4X": "Roller sunblind, 2-piece, electric, windscreen",
    "D5B": "Ambient lighting",
    "D5G": "Ambient lighting Extended",
    "D5M": "Cab interior decor, burred walnut, matt",
    "D5N": "Cab interior trim, wood, matt",
    "D5P": "Cab interior trim, chrome",
    "D5Q": "Cab interior decor spa silver",
    "D5U": "Floor surface, in TPO",
    "D5X": "Footwell inlay, ribbed mat, both sides",
    "D6A": "Seat belts, orange",
    "D6B": "Luxury bed, large, bottom",
    "D6H": "Auxiliary air-conditioning unit",
    "D6J": "Temperate display in Fahrenheit",
    "D6N": "Hot-water auxiliary heater, cab and engine",
    "D6P": "Auxiliary hot air heater, 2000 W",
    "D6R": "Switch, auxiliary heater, lower bunk",
    "D6W": "Air humidifier, cab",
    "D6X": "Activated charcoal filter",
    "D6Y": "Pollen filter",
    "D7C": "Stowage comp., under windscrn, central comp.w/ lid",
    "D7L": "Stowage facility, above windscreen, 1 compartment",
    "D7M": "Stowage facility, above windscreen, 2 compartments",
    "D7P": "Tray, low, on engine tunnel",
    "D7Q": "Stowage facility, high, on engine tunnel",
    "D7U": "Stowage facility, on engine tunnel",
    "D7W": "Stowage facility, behind basic box",
    "D7X": "Stowage flaps over windscr., w. valuables compart.",
    "D7Y": "Luggage rack, top, on rear wall",
    "D7Z": "Stowage net, on rear wall",
    "D8B": "Roof hatch, round, diameter 800 mm",
    "D8D": "DesignLine Value",
    "D8E": "DesignLine Premium",
    "D8F": "Driver's susp.seat,comf.,w/o belt adj.,w/o heating",
    "D8G": "Seat cover, Spacer fabric, leather-like on side",
    "D8H": "Driver's susp. seat, standard, horiz. suspension",
    "D8J": "2 co-driver comfort seats,static,head rest,stowage",
    "D8K": "Co-driver comfort seat,static,head rest,stowage",
    "D8L": "Tilting sunroof, electric, glass version",
    "D8N": "Tilting sunroof, electric",
    "D8Q": "Driver's suspen.seat, leather, ventilated, massage",
    "D8R": "Co-driv. suspen.seat, leather, ventilated, massage",
    "D8S": "Co-driver seat, w/o head restraint, fold. backrest",
    "D8Z": "Ctrl. panel, sliding/tilting sunroof, bottom bunk",
    "D9C": "Pre-installation luxury bed, top, narrow",
    "D9D": "Retrofit pre-installation for seat bench",
    "D9E": "Pre-installation for centre seat",
    "D9F": "Pre-installation air humidifier",
    "D9H": "Pre-inst. for centre seat, rear",
    "D9I": "Pre-inst. for deluxe bed with electrics, top, wide",
    "D9L": "Deletion, curtain, along side of bed(s)",
    "D9M": "Deletion, residual heat utilisation",
    "D9N": "Deletion, compressed-air connection, in cab",
    "D9O": "Deletion, stowage comp. lid, driver+co-driver side",
    "D9Q": "Deletion, bed, top",
    "D9R": "Deletion of hot-water auxiliary heater, cab",
    "D9T": "Omission of roof hatch/vent",
    "D9W": "Deletion, curtain, all-round",
    "D9X": "Deletion, bed, bottom",
    "D9Y": "Deletion, air conditioning system",
    "D9Z": "Deletion, co-driver's seat",
    "DXN": "Maximum noise insulation",
    "DXO": "Additional noise insulation",
    "DXP": "Standard noise insulation",
    "DZO": "Driver's seat, swivelling",
    "DZP": "Co-driver's seat, swivelling",
    "DZR": "Table, between driver's and co-driver's seat",
    "DZS": "Cabinet, on rear panel",
    "DZT": "Mattress, oscillating, bottom",
    "DZU": "Comfort bunk, bottom, with backrest adjustment",
    "DZX": "Mattress, Value, bottom",
    "DZZ": "Omission of mattress, bottom",
    # E
    "E1B": "Batteries 2 x 12 V/170 Ah, low-maintenance",
    "E1M": "Alternator, 28 V/150 A",
    "E1N": "Alternator 28 V/100 A",
    "E1U": "Alternator, controlled 24-30 V/150 A",
    "E1W": "AGM-Batteries, 2 x 12 V/170 Ah, maintenance-free",
    "E1Z": "AGM-Batteries, 2 x 12 V/220 Ah, maintenance-free",
    "E2J": "Automatic cutouts",
    "E3E": "Additional socket, 12 V/15 A, co-driver footwell",
    "E3L": "Socket, 24 V/15 A, co-driver footwell",
    "E3W": "PSM, 2nd generation",
    "E4C": "Additional functions, for body manufacturer",
    "E4D": "Body interface, behind cab",
    "E5A": "No. 1 switch, for non-MB body electrics",
    "E5B": "No. 2 switch, for non-MB body electrics",
    "E5C": "No. 3 switch, for non-MB body electrics",
    "E5K": "MirrorCam switch, on bed",
    "E6Z": "Reversing buzzer",
    "E7F": "Cable remote control for air suspension",
    "E8D": "USB-C connector, in side wall stowage comp., left",
    "E8E": "USB-C connector, in side wall stowage comp., right",
    "E9H": "Provision for fitting loading tailgate control",
    "E0C": "Battery sensor, KroSchu",
    "E0E": "Batteries from company Banner",
    "E0F": "Batteries from company Exide",
    "E0M": "Batteries from company Moura",
    "E0N": "Batteries from company Inci",
    "E0O": "Batteries from company Clarios",
    "E0R": "Battery/batteries, NATO",
    "E0U": "Battery cover, walk-on, w/o step plate",
    "E0V": "Highload parameter, level 1",
    "E0W": "Highload parameter, level 2",
    "E0Y": "Battery cover",
    "E0Z": "Battery cable, extended",
    "E1A": "Batteries 2 x 12 V/115 Ah, low-maintenance",
    "E1C": "Batteries 2 x 12 V/220 Ah, low-maintenance",
    "E1E": "Batteries, 2 x 12 V/100 Ah, maintenance-free",
    "E1F": "Batteries 2 x 12 V/140 Ah, low-maintenance",
    "E1G": "Batteries, 2 x 12 V/135 Ah, low-maintenance",
    "E1H": "Batteries, 2 x 12 V/165 Ah, low-maintenance",
    "E1I": "Batteries, 2 x 12 V/135 Ah, maintenance-free",
    "E1J": "Batteries, 2x 12 V/170Ah, maintenance-free",
    "E1K": "Batteries, 2x 12 V/220 Ah, maintenance-free",
    "E1P": "Alternator, 28 V/80 A",
    "E1X": "Batteries, 2x 12 V/170Ah, low-maintenance, high",
    "E1Y": "Batteries, 2x 12 V/220Ah, maintenance-free, high",
    "E2X": "230 V socket, front passenger footwell",
    "E3A": "Voltage transformer, 24 V/12 V, 10 A",
    "E3B": "Connection point 12V/15A, for auxiliary consumers",
    "E3D": "24 V/15 A socket, in side wall stowage space, left",
    "E3F": "Additional socket 12 V/15 A, firewall",
    "E3H": "Additional socket,24 V/15 A, in instrument support",
    "E3I": "Additional socket 24 V/15 A, firewall",
    "E3J": "Socket, 24 V/10 A, on battery carrier",
    "E3K": "Power socket",
    "E3M": "Socket, 24 V/15 A, behind seat",
    "E3Q": "Additional socket, 24 V/15 A, co-driver footwell",
    "E3R": "Power socket, 24 V/25 A, co-driver footwell",
    "E3S": "24 V/15 A socket, in sidewall stowage space, right",
    "E3T": "Socket, 12 V/15 A, co-driver footwell",
    "E3U": "Socket, 12 V/15 A, behind seat",
    "E3V": "12 V/15 A socket, in sidewall stowage space, right",
    "E3X": "Initial parameterisation of PSM, external",
    "E3Y": "PSM, body and trailer CAN, ISO 11992",
    "E3Z": "PSM, body CAN, ISO 11898 instead of 11992",
    "E4A": "Communications interface (KOM)",
    "E4B": "Interface, fleet management system FMS",
    "E4E": "Engine start/stop for bodybuilder, automatic",
    "E4I": "Mounting interface, US variant, RP 170",
    "E4S": "Shutdown, outgoing signals",
    "E4X": "Starting-off aid, with no time limit",
    "E4Y": "Starting-off aid, time limit 120 s",
    "E4Z": "Starting-off aid, time limit 90 s",
    "E5D": "Master switch, electrical auxiliary consumers",
    "E5E": "Battery master switch, single-pin",
    "E5F": "Emergency stop switch for bodybuilder in dashboard",
    "E5G": "Battery disconnect switch outside, on frame",
    "E5H": "Switch for night-time driving light",
    "E5I": "Second control folding door, co-driver's B-pillar",
    "E5J": "Battery master switch, mechanical, single-pin",
    "E5L": "Slot for 4 additional switches",
    "E5M": "Electromechanical main battery switch",
    "E5T": "ADR type class EX/II, incl. AT",
    "E5U": "ADR type class EX/III, incl. EX/II and AT",
    "E5V": "ADR type class FL, incl. EX/II, EX/III and AT",
    "E5W": "ADR type class OX, incl. AT",
    "E5X": "ADR type class AT",
    "E5Y": "ADR accessories, fire exting., in stowage compt",
    "E5Z": "ADR acces.,fire exting.,in stow.compt.+behind cab",
    "E6B": "Trailer socket, 12 V, 13-pin, adapter",
    "E6G": "Trailer socket, 12 V, 13-pin, frame-mounted, LED",
    "E6I": "Trailer socket, 24 V, 7-pin",
    "E6Y": "Reverse warning, comb. with hazard warning lights",
    "E7A": "Electrics, for refuse-collection veh., side loader",
    "E7B": "Preinstallation, elec./lights, for demount. bodies",
    "E7C": "Electrical system, automated refuse program",
    "E8B": "USB connection",
    "E8F": "USB-C connector, in stowage comp. above windshield",
    "E9C": "Pre-inst. cable harn., elec. compart./instr. panel",
    "E9D": "Pre-installation for twin-pole battery circuit breaker",
    "E9E": "Provision, ADR, without chassis shielding",
    "E9F": "Pre-installation, 2nd control unit, level control",
    "E9G": "Provision for fitting electrical devices",
    "E9I": "Pre-inst., switch, lift axle, semitr./trailer",
    "E9K": "Provision, 24-V radio, retrofit",
    "E9M": "Pre-installation for stealth light",
    "E9U": "Omission of interface, FMS Fleet Management System",
    "E9W": "Deletion of daytime running lamps",
    "E9X": "Deletion, voltage transformer, 24 V/12 V, 10 A",
    "E9Z": "Deletion, batteries (CKD)",
    # F
    "F0F": "Side module, N3 vehicle",
    "F0G": "Side module, N3G vehicle",
    "F0T": "Mercedes star, illuminated from behind",
    "F0Y": "Mirror cover, construction vehicle",
    "F1B": "M-cab ClassicSpace, 2.30 m, tunnel 170 mm",
    "F1D": "L-cab ClassicSpace, 2.30 m, tunnel 170 mm",
    "F1I": "L-cab StreamSpace, 2.50 m, level floor",
    "F1Q": "M-cab",
    "F1R": "L-cab",
    "F2A": "Floor variant, flat floor",
    "F2B": "Floor variant, tunnel 170 mm",
    "F2E": "Floor variant tunnel 170 mm, for stowage compart. left",
    "F2G": "Cab width 2.30 m",
    "F2H": "Cab width 2.50 m",
    "F2N": "Cab, 600 mm attachment height",
    "F2P": "Cab, 765 mm attachment height",
    "F2U": "ClassicSpace",
    "F2W": "StreamSpace",
    "F3B": "Cab mountings, comfort, steel-sprung",
    "F3C": "Cab mountings, comfort, air-sprung",
    "F3Y": "Cab tilting mechanism, electrohydraulic",
    "F4H": "Cab rear wall, without window",
    "F4I": "Cab rear wall, with window",
    "F4X": "Stowage compartment exterior flap, left",
    "F4Y": "Stowage compartment exterior flap, right",
    "F4Z": "Stowage locker, left, under cab",
    "F5L": "Sun visor, exterior, transparent",
    "F5Y": "A-pillar trim",
    "F6D": "Windscreen, tinted, with filter band",
    "F6I": "Front mirror, heated",
    "F6Q": "Air horn",
    "F6R": "Air horns, cab roof",
    "F6T": "MirrorCam",
    "F6V": "MirrorCam bracket, chrome, lower cover, cab colour",
    "F7B": "Bumper, with steel corners",
    "F7C": "Bumper centre section with towing eyes",
    "F7D": "Bumper centre section w. towing eyes, coupling jaw",
    "F7T": "Door extension",
    "F7X": "Cab entrance, left/right, rigid",
    "F7Y": "Cab entrance, left/right, movable",
    "F8B": "2 remote control keys",
    "F8E": "Locking system, with central locking",
    "F8F": "Extended central locking",
    "F8V": "Light sensor",
    "F8W": "Rain sensor",
    "F0A": "L-cab, low roof, 2.30 m, tunnel 170 mm",
    "F0B": "L-cab, low roof, 2.30 m, tunnel 320 mm",
    "F0C": "L-cab, low roof, 2.30 m, level floor",
    "F0D": "M-cab, low roof, 2.30 m, tunnel 170 mm",
    "F0E": "M-cab, low roof, 2.30 m, tunnel 320 mm",
    "F0H": "L-cab ClassicSpace, 2.50 m, tunnel 120 mm",
    "F0I": "L-cab StreamSpace, 2.50 m, tunnel 120 mm",
    "F0J": "L-cab BigSpace, 2.50 m, tunnel 120 mm",
    "F0K": "Roof hatch, swivel type",
    "F0M": "ExtraLine",
    "F0Q": "DirectVision cab, low",
    "F0R": "DirectVision cab, high",
    "F0S": "Cab, reinforced",
    "F0X": "Mirror cover, on-road vehicle",
    "F0Z": "Mirror glass, country-specific version",
    "F1A": "S-cab ClassicSpace, 2.30 m, tunnel 170 mm",
    "F1C": "M-cab CompactSpace, 2.30 m, tunnel 170 mm",
    "F1E": "L-cab StreamSpace, 2.30 m, tunnel 170 mm",
    "F1F": "L-cab StreamSpace, 2.30 m, level floor",
    "F1H": "L-cab BigSpace, 2.50 m, level floor",
    "F1J": "L-cab GigaSpace, 2.50 m, level floor",
    "F1K": "L-cab CompactSpace, 2.30 m, tunnel 170 mm",
    "F1L": "L-cab BigSpace, 2.50 m, tunnel 320 mm",
    "F1M": "L-cab ClassicSpace, 2.30 m, level floor",
    "F1N": "M-cab CompactSpace, 2.30 m, tunnel 320 mm",
    "F1O": "M-cab ClassicSpace, 2.30 m, tunnel 320 mm",
    "F1P": "S-cab",
    "F1S": "S-cab ClassicSpace, 2.30 m, tunnel 320 mm",
    "F1T": "L-cab ClassicSpace, 2.30 m, tunnel 320 mm",
    "F1U": "L-cab BigSpace, 2.30 m, tunnel",
    "F1V": "L-cab CompactSpace, 2.30 m, tunnel 320 mm",
    "F1W": "L-cab, StreamSpace, 2.30 m, tunnel 320 mm",
    "F1X": "S-cab ClassicSpace, 2.30 m, tunnel",
    "F1Y": "S-cab ClassicSpace, extended, 2.30 m, tunnel",
    "F1Z": "L-cab ClassicSpace, 2.30 m, tunnel",
    "F2C": "Floor variant, tunnel 320 mm",
    "F2F": "Floor variant, tunnel 120 mm",
    "F2L": "Cab, 420 mm ride height, car transporter",
    "F2M": "Cab, 420 mm attachment height",
    "F2O": "Cab, 250 mm attachment height",
    "F2Q": "Vehicle height at limit area 4m and higher",
    "F2S": "Low roof",
    "F2T": "CompactSpace",
    "F2X": "GigaSpace",
    "F2Y": "ClassicSpace Low Roof",
    "F2Z": "M-cab, Zetros, 2.30 m, level floor",
    "F3A": "Cab mountings, standard, steel-sprung",
    "F3E": "Cab mountings, rear, reinforced",
    "F3G": "Cab mountings, front, reinforced, crewcab",
    "F3H": "Cab mountings, rear, reinforced, crewcab",
    "F3I": "Hydraul. cab tilting mechanism, reinforced,crewcab",
    "F3J": "Cab mountings, reinforced",
    "F3K": "Cab mountings, front/rear, extra-reinforced",
    "F3R": "ProCabin-Giga, level floor",
    "F3T": "XT-cab",
    "F3V": "Pricing, cab tilting mechanism",
    "F3W": "Cab tilting mechanism, mechanical-hydraulic",
    "F3Z": "Hydraulic tilting mechanism oil, below -25 degrees",
    "F4D": "Body height above frame, from 2.65 m to 2.75 m",
    "F4E": "Body height above frame, over 2.75m to 3.05m",
    "F4G": "Cab side wall, closed, right",
    "F4K": "Rear wall window behind driver, sliding",
    "F4Q": "Cab, 420 mm attachment height, Direct Vision",
    "F4R": "Cab, 300 mm attachment height, Direct Vision",
    "F4S": "Cab, 660 mm attachment height, Direct Vision",
    "F4U": "A-pillar panel, aerodynamically optimised, painted",
    "F5A": "Air deflectors, adjustable",
    "F5C": "Air deflector without base covering, adjustable",
    "F5D": "Air deflectors, rigid",
    "F5E": "Air deflectors, rigid, with cab side deflectors",
    "F5F": "Air deflectors, body height above frame, up to 3 m",
    "F5G": "Air deflectors, body height above frame, above 3 m",
    "F5H": "Wind deflector over 4 m, movable, side deflectors",
    "F5I": "Cab side deflectors, without air deflectors",
    "F5J": "Vehicle height w.roof spoiler fitted up to 4060 mm",
    "F5N": "Wind deflector, extended cab side deflectors",
    "F5P": "Air defl., adj., cabside defl./extended adj.range.",
    "F5Q": "Movable wind deflect.>4m,side deflectors,long roof",
    "F5T": "Side window wind deflector, clear",
    "F5U": "Control code, cab side deflector, modified",
    "F5Z": "A-pillar trim, reduced dirt build-up",
    "F6A": "Windscreen, non-tinted",
    "F6B": "Windscreen, non-tinted, heated",
    "F6C": "Windscreen, tinted",
    "F6F": "Sidewall window",
    "F6G": "Windscreen, weight-optimised",
    "F6H": "Windscreen, tinted, heated",
    "F6J": "Main mirror, electric, driver's side",
    "F6K": "Mirror bracket, vehicle width up to 2.30 m",
    "F6L": "Main mirror, manoeuvring setting, co-driver's side",
    "F6M": "Main mirror heatable and electrically adjustable",
    "F6N": "Wide-angle mirror, heated",
    "F6O": "Kerb mirror",
    "F6S": "Mirror bracket, vehicle width up to 2.40 m",
    "F6U": "Front mirror, not heated",
    "F6Y": "Actros with S-/M-cab",
    "F7G": "Bumper, corners in robust plastic",
    "F7L": "ExtraLine basic",
    "F7N": "Door extension, cover, top step",
    "F7O": "ExtraLine ProCabin",
    "F7P": "Cab entry, step plates in aluminium",
    "F7S": "Entrance support, aluminium",
    "F7V": "Cab entrance, two-step",
    "F7W": "Cab entrance, single-step",
    "F7Z": "Step, with grab rail on roof",
    "F8A": "2 vehicle keys",
    "F8C": "1 multifunction key and 1 remote control key",
    "F8D": "2 vehicle keys, additional",
    "F8G": "2 mechanical vehicle keys, additional",
    "F8H": "2 remote control keys, additional",
    "F8I": "1 multifunction/1 remote control key, additional",
    "F8J": "Lock, mechanical, on folding door",
    "F8L": "Immobiliser, with transponder",
    "F8M": "Pre-installation for digital vehicle key",
    "F8X": "Rain/light sensor",
    "F8Z": "Alarm system, with interior monitoring",
    "F9A": "Pre-installation, cab parts, body width 2600 mm",
    "F9B": "L-cab prepared for crewcab",
    "F9C": "S-cab prepared for crewcab",
    "F9K": "Omission of wind deflectors",
    "F9L": "Cab, non-assembled, stage II (CKD)",
    "F9M": "Cab, non-assembled, stage III (CKD)",
    "F9O": "Deletion, 2 remote-control keys",
    "F9P": "Deletion of MirrorCam",
    "F9Q": "Omission of contour markings, cab",
    "F9R": "Omission of cab",
    "F9T": "Deletion of door extension",
    "F9U": "Deletion, standing area behind cab",
    "F9V": "Deletion, tilting hydraulics",
    "F9W": "Deletion, cab rear wall",
    "F9X": "Deletion, front mirror, heated",
    "F9Y": "Vehicle key, without transponder",
    "F9Z": "Deletion, sun visor, exterior",
    "FAW": "Cab version NCP",
    "FUZ": "Modular sun visor, outside",
    "FVU": "CompactSpace Plus",
    "FVX": "Floor variant, tunnel 60 mm",
    "FVY": "Floor variant, tunnel 350 mm",
    "FVZ": "Floor variant, tunnel 350 mm (Powerdome 470 mm)",
    "FWA": "ClassicSpace L-cab, 2.50 m, TH height 60 mm, DV",
    "FWC": "BigSpace L-cab, 2.50 m, TH 60 mm, DV",
    "FWD": "GigaSpace L-cab, 2.50 m, TH 60 mm, DV",
    "FWE": "ClassicSpace L-cab, 2.50 m, TH 120 mm, DV",
    "FWG": "BigSpace L-cab, 2.50 m, TH 120 mm, DV",
    "FWH": "GigaSpace L-cab, 2.50 m, TH 120 mm, DV",
    "FWI": "ClassicSpace L-cab, 2.50 m, TH 350 mm, DV",
    "FWK": "BigSpace L-cab, 2.50 m, TH 350 mm, DV",
    "FWL": "GigaSpace L-cab, 2.50 m, TH 350 mm, DV",
    "FWM": "CompactSpace+ L-cab, 2.50 m, TH 350 mm, DV",
    "FWN": "ClassicSpace L-cab, 2.50 m, PD 470 mm, DV",
    "FWP": "BigSpace L-cab, 2.50 m, PD 470 mm, DV",
    "FWQ": "GigaSpace L-cab, 2.50 m, PD 470 mm, DV",
    "FWR": "CompactSpace+ L-cab, 2.50 m, PD 470 mm, DV",
    "FWS": "ClassicSpace M-cab, 2.50 m, TH 350 mm, DV",
    "FWT": "CompactSpace+ M-cab, 2.50 m, TH 350 mm, DV",
    "FWU": "ClassicSpace M-cab, 2.50 m, PD 470 mm, DV",
    "FWV": "CompactSpace+ M-cab, 2.50 m, PD 470 mm, DV",
    "FWW": "BigSpace XT cab, 2.50 m, TH 60 mm, DV",
    "FWX": "GigaSpace Xtcab, 2.50 m, TH 60 mm, DV",
    "FWY": "BigSpace XT cab, 2.50 m, TH 120 mm, DV",
    "FWZ": "GigaSpace XT cab, 2.50 m, TH 120 mm, DV",
    "FZZ": "Vehicle width, 2550 mm",
    # G
    "G0A": "Powertrain, 44 t to 68 t",
    "G0K": "Drive program, economy/power",
    "G0R": "Transmission support arms, optimised for removal",
    "G2E": "Transmission G 281-12/14.93-1.0",
    "G2F": "Transmission G 330-12/11.63-0.77",
    "G5A": "Single-disc clutch",
    "G5B": "Double-disc clutch",
    "G5G": "Mercedes PowerShift 3",
    "G5L": "PowerShift Advanced",
    "G0B": "Powertrain, 44 t to 80 t",
    "G0C": "Powertrain, 44 t to 120 t",
    "G0D": "Powertrain, customer req. Greater than 120 t",
    "G0E": "Powertrain, 150 t",
    "G0F": "Powertrain, 44 t to 50 t",
    "G0G": "Powertrain, 44 t to 62 t",
    "G0I": "Fire-service driving program, Airport",
    "G0L": "Predictive Powertrain Control (e-Horizon)",
    "G0M": "Securing sleeve for propshaft",
    "G0N": "PPC extension - Interurban",
    "G0O": "Driving program ECO for automatic transmission",
    "G0P": "Drive program VIAB",
    "G0Q": "Transmission oil, below -20 degrees",
    "G0S": "Municipal driving program",
    "G0U": "Drive program economy",
    "G0V": "Drive program power",
    "G0W": "Drive program offroad",
    "G0X": "Fire-service driving program",
    "G0Y": "Drive program heavy",
    "G0Z": "Drive program fleet",
    "G1B": "Transmission G 70-6/5.94-0.74",
    "G1C": "Transmission G 71-6/9.20-1.0",
    "G1D": "Transmission G 90-6/6.70-0.73",
    "G1E": "Transmission G 140-8/9.30-0.79",
    "G1F": "Transmission G 141-9/14.57-1.0",
    "G1H": "Transmission G 230-16/14.2-0.83",
    "G1I": "Transmission G 231-16/17.0-1.0",
    "G1J": "Transmission G 260-16/11.7-0.69",
    "G1K": "Transmission Eaton FSO-4505-A",
    "G1L": "Transmission Eaton FSO-4505-HDA",
    "G1N": "Gearbox, G56, 6-speed",
    "G1O": "Transmission Eaton EA 6206-AMT",
    "G1P": "Transmission Eaton EA 6106-AMT",
    "G1Z": "Transmission 9S-1115 TD/12.73-1, ZF-ECOMID",
    "G2B": "Transmission G 211-12/14.93-1.0",
    "G2C": "Transmission G 230-12/11.7-0.78",
    "G2D": "Transmission G 280-16/11.7-0.69",
    "G2G": "Transmission G 291-12/16.462-1,0",
    "G2H": "Transmission G 340-12/12.793-0,78",
    "G3A": "Automatic transmission 5/3.49-0.75, Allison 3000 P",
    "G3B": "Automatic 5/3.49-0.75, retarder, Allison 3000 PR",
    "G3E": "Autom. transmission 6/4.59-0.65, Allison WT MD3500",
    "G3F": "Automatic 6/3.49-0.65, retarder, Allison 3000 PR",
    "G3G": "Automatic 6/3.49-0.65, retarder, Allison 3200 PR",
    "G3H": "Automatic transmission 6/3.49-0.65, Allison 3200 P",
    "G3I": "Automatic transmission 6/3.49-0.65, Allison 3000 P",
    "G3J": "Autom. transmission 6/3.49-0.65, Allison 3200 SPP",
    "G3K": "Auto. trans. 6/3.49-0.65,retard.,Allison 3200SP PR",
    "G3L": "Auto 6/3.49-0.65 Allison 3000RDS w/o retarder",
    "G3M": "Auto 6/3.49-0.65 Allison 3000RDS with retarder",
    "G3N": "Auto 6/3.49-0.65 Allison 3300RDS w/o retarder",
    "G3O": "Auto 6/3.49-0.65 Allison 3300RDS with retarder",
    "G3Q": "Auto 6/4.70-0.67Allison 4500SPP w/o retarder",
    "G3R": "Auto 6/4.70-0.67 Allison 4500 SP PR with retarder",
    "G3X": "Release, shift lock, for automatic transmission",
    "G3Y": "Turbo retarder clutch",
    "G4C": "Transfer case VG 1600-3W/1.42-1.04 permanent",
    "G4D": "Transfer case VG 2800-3W/1.45-1.04, permanent",
    "G4E": "Transfer case VG 3000-3W, 1.04, engageable",
    "G4H": "Transfer case VG 1000-3W/1.61-0.98 permanent",
    "G4I": "Transfer case VG 1000-3W/1.61-0.98, engageable",
    "G4Z": "Oil cooler, for transfer case",
    "G5D": "Optimised ZF clutch SFTP",
    "G5F": "Clutch, remote-controlled",
    "G5H": "Gearshift, manual",
    "G5J": "Gearshift, mechanical",
    "G5K": "Gearshift, hydraulic",
    "G5Y": "Tachograph calibration, digital, ex factory",
    "G5Z": "Tachograph calibration, modular, ex factory",
    "G7A": "Powertrain, 44 t to 90 t",
    "G7B": "Powertrain, 68 t to 74 t",
    "G9Y": "Omission of Predictive Powertrain Control",
    "G9Z": "Deletion, transmission (CKD)",
    "GPZ": "Efficiency optimized powertrain control parameters",
    # J
    "J1Z": "Speedometer, deletion, tachograph",
    "J2I": "Standard loudspeaker",
    "J2K": "Speaker, 2-way system",
    "J3Z": "Axle load measuring device",
    "J4X": "Belt warning w/ seat occup. detection, co-driver",
    "J5P": "Wireless charger for mobile phones",
    "J6E": "Multimedia Cockpit Interactive 2",
    "J7A": "Truck Data Center 8",
    "J7C": "Card Reader for Truck Data Center",
    "J8C": "Pre-fitted Card Reader for Truck Data Center",
    "J8U": "Pre-installation for Truck Data Center 8",
    "J9A": "Pre-installation for CB radio, 12 V, DIN slot",
    # K
    "K0T": "Main tank, left",
    "K1C": "Tank, 290 l, left, 650 x 565 x 950 mm, aluminium",
    "K1E": "Tank, 390 l, left, 650 x 565 x 1250 mm, aluminium",
    "K1Y": "Tank 330 l, left, 735 x 565 x 950 mm, aluminium",
    "K3T": "AdBlue tank, 25 l",
    "K3V": "AdBlue tank, 60 l, left",
    "K5M": "Tanks, lockable",
    "K5Q": "Fuel screen, tank filler neck",
    "K5R": "Protective plate for tank",
    "K5S": "Protective cap for AdBlue metering system",
    "K5Y": "Initial filling, additional 30 litres of fuel",
    "K7N": "Exhaust system, outlet to left, under 30 degrees",
    "K7R": "Exhaust pipe, straight, above second axle",
    "K7S": "Exhaust pipe, curved, above second axle",
    # L
    "L0A": "Illumination regulation, in acc. with UN-R 48.06",
    "L0Y": "Tail lamps wiring harness, extended",
    "L1C": "LED daytime running lamps",
    "L1D": "Automatic main/dipped beam and cornering light",
    "L1G": "LED main headlamps",
    "L1M": "LED fog lamps",
    "L1P": "LED tail lights",
    "L1Q": "Tail lights, construc. in metal holder with grille",
    "L1W": "LED turn signals in light signature",
    "L2H": "Side marker lamps, flashing",
    "L9D": "Pre-installation for additional indicator lights",
    # M
    "M0A": "Engine mounts, reinforced",
    "M0C": "Bottom shell to prevent swirling-up of dust",
    "M0Q": "Noise regulation acc. to UN-R 51.03, phase 2",
    "J0U": "Remote update of driving assistance map",
    "J1A": "Instrument cluster, 10.4 cm",
    "J1B": "Instrument cluster, 10.4 cm, with add. displays",
    "J1C": "Instrument cluster, 12.7 cm, with video function",
    "J1D": "Instrument cluster, display graphics capable, ecometer",
    "J1E": "Instrument cluster, 12.7 cm, with add. displays",
    "J1F": "MTCO tachograph, 7 days + 1 driver",
    "J1G": "Extended PSM control for multimedia cockpit",
    "J1H": "Instrument cluster, 12.7 cm",
    "J1K": "Tachograph, 1 day + 2 drivers, modular",
    "J1M": "Dig. tachograph, 2nd gen., version 2, ADR",
    "J1O": "Dig. tachograph, 2nd gen., working speed control",
    "J1P": "Tachograph, 1 day + 2 drivers, up to 140 km/h",
    "J1Q": "Tachograph, digital Brazil",
    "J1R": "Tachograph, digital, EC, rpm, ADR",
    "J1S": "Tachograph manufacturer VDO",
    "J1T": "Tachograph manufacturer Stoneridge",
    "J1V": "Tachograph, digital, China",
    "J1W": "Tachograph, digital, EC, rpm, without ADR",
    "J1X": "Parameterisation of working time when ignition off",
    "J1Y": "Speedometer, km/h and mph",
    "J2A": "CD radio",
    "J2B": "CD radio, Bluetooth",
    "J2C": "CD radio, Bluetooth, comfort",
    "J2D": "Radio/navigation system, Bluetooth, comfort",
    "J2E": "Radio with USB connector",
    "J2G": "Digital radio",
    "J2H": "Multimedia Radio Touch",
    "J2M": "Aux-in in side wall stowage space, right",
    "J2O": "Comfort telephony, wireless charging",
    "J2U": "Navigation system",
    "J2V": "Auto Shut-Off System",
    "J2W": "Pre-installation for tracking system",
    "J2X": "ERA-Glonass",
    "J2Y": "CB radio, 24 V",
    "J2Z": "CB radio, 12 V",
    "J3A": "FleetBoard inside, veh. computer, standard instal.",
    "J3C": "Fleetboard DispoPilot.mobile",
    "J3D": "Fleetboard vehicle computer with FB driver card",
    "J3E": "FleetBoard DispoPilot.guide",
    "J3F": "Mount for Fleetboard DispoPilot.guide",
    "J3G": "Mount for Fleetboard DispoPilot.mobile",
    "J3H": "On-Board Unit (OBU), fitting+activation ex factory",
    "J3I": "Special price for demo. vehs. w. DispoPilot.guide",
    "J3J": "FleetBoard veh. computer, new, w. DTCO driver card",
    "J3K": "FleetBoard contract version 07/11 or newer exists",
    "J3L": "Stock vehicle, no FleetBoard service contract",
    "J3M": "FleetBoard inside, onboard computer with price",
    "J3N": "Fleetboard Eco Support",
    "J3P": "FleetBoard control, model 1",
    "J3Q": "Fleetboard DispoPilot.guide 2",
    "J3R": "Truck Data Center 7 (FB Card)",
    "J3S": "Truck Data Center 6 (DTCO)",
    "J3T": "Truck Data Center 6 (FB Card)",
    "J3U": "Requirement: Fleetboard Manager app",
    "J3V": "Truck Data Center 7",
    "J3X": "FB vehicle computer (TP5) for safety function",
    "J3Y": "Communications interface for FB DriverCard",
    "J4A": "Maintenance system",
    "J4C": "Gross weight measuring device, acc. to EC",
    "J4D": "Gross weight calculation, acc. to EC",
    "J4K": "Fleetboard Ready",
    "J4N": "Fleetboard vehicle computer, preliminary stage",
    "J4O": "Mercedes-Benz Trucks Uptime Ready",
    "J4P": "FleetBoard Core Ready",
    "J4Q": "FleetBoard Compliance Ready",
    "J4R": "FleetBoard Analytics Ready",
    "J4S": "Fleetboard Charge Ready",
    "J4V": "Seat belt warning, driver's and co-driver's side",
    "J5Q": "Digital radio with USB interface and Bluetooth",
    "J5S": "Radio, with USB connection and Bluetooth",
    "J5T": "Radio, Bluetooth, comfort",
    "J6A": "Classic Cockpit",
    "J6B": "Multimedia Cockpit",
    "J6C": "Multimedia Cockpit, interactive",
    "J6D": "New Multimedia Cockpit",
    "J6W": "Reversing camera, towing vehicle end",
    "J6Y": "Remote Online",
    "J6Z": "Preinstallation Mercedes-Benz Truck App Portal",
    "J7B": "Truck Data Center 8 (FB Card)",
    "J7D": "Truck Data Center 8, base",
    "J7H": "GPRS1 Config Fragment G_SIM ModemTR",
    "J7I": "GPRS1 Config Fragment G_SIM ModemAM",
    "J7J": "GPRS1 Config Fragment G_SIM ModemAsia",
    "J7P": "Driving assistance map, Mid. East & Africa region",
    "J7R": "Driving assistance map, Japan region",
    "J7S": "Driving assistance map, Taiwan region",
    "J7T": "Driving assistance map, China region",
    "J7U": "Driving assistance map, North America region",
    "J7V": "Driving assistance map, Europe region",
    "J7W": "Driving assistance map, South America region",
    "J7X": "Driving assistance map, Oceania region",
    "J8F": "Pre-installation for digital tachograph, Taiwan",
    "J8G": "Remote Truck 3.0 App pre-installation",
    "J8H": "No reversing camera at rear of tractor vehicle",
    "J8K": "Omission nav. sys., traffic sign ass.+Rem. Online",
    "J8L": "Preinst. & display for up to 3 additional cameras",
    "J8M": "Pre-install.for Truck Data Center 8 (FB Card),base",
    "J8N": "Pre-installation for Truck Data Center 8, base",
    "J8P": "Omission: pre-install.&display for up to 4 cameras",
    "J8R": "Pre-install.for Truck Data Center 8 (FB Card)",
    "J8S": "Preinst. & display for up to 2 additional cameras",
    "J8T": "Preinstallation & display for an additional camera",
    "J8W": "Pre-installation for digital tachograph, China",
    "J8X": "Preinstallation Toll4Europe toll services",
    "J8Y": "Pre-installation for Truck Data Center 7",
    "J8Z": "Pre-install.for Truck Data Center 7 (FB Card)",
    "J9B": "Provision for fitting telematics",
    "J9C": "Pre-installation for Fleetboard for J3D",
    "J9D": "Provision for fitting toll tracking",
    "J9E": "Provision for fitting LSVA recorder",
    "J9F": "Provision for fitting 12 V radio, retrofit",
    "J9H": "Pre-installation for 12 V trunking",
    "J9I": "Provision for fitting telephone, fax",
    "J9J": "Pre-installation for reversing camera",
    "J9K": "Pre-installation, universal, for multimedia use",
    "J9L": "Pre-installation for FleetBoard for J3J",
    "J9M": "Pre-installation and display for reversing camera",
    "J9N": "Pre-installation for Truck Data Center 6 (DTCO)",
    "J9O": "Pre-install.for Truck Data Center 6 (FB Card)",
    "J9P": "Pre-installation and display for up to 4 cameras",
    "J9Q": "Deletion, provision for CB radio, 12 V, DIN slot",
    "J9R": "Preinstallation for digital tachograph, TCO Russia",
    "J9S": "ERA-Glonass pre-installation",
    "J9T": "Deletion, FB veh. comp., new, w. DTCO driver card",
    "J9U": "Deletion, speaker, 2-way system",
    "J9V": "Pre-installation, FleetBoard for safety function",
    "J9W": "Deletion of HMI Connect Mid",
    "J9X": "Omission Truck Data Center",
    "J9Y": "Deletion, radio",
    "J9Z": "Deletion, provision for fitting toll tracking",
    "M0U": "Noise encapsulation, special package",
    "M3D": "Eng. OM471, inline 6, 12.8 l, 375kW (510hp), 2500 Nm",
    "M3E": "Eng. OM471, inline 6, 12.8 l, 390kW (530hp), 2600 Nm",
    "M4X": "Engine version Euro VI, E",
    "M5B": "2. Engine generation OM471",
    "M5D": "3. Engine generation OM471",
    "M5U": "Exhaust brake, standard system",
    "M5V": "High Performance Engine Brake",
    "M6L": "Air compressor, 2-cylinder",
    "M6M": "Air compressor, 2-stage, for optimised consumption",
    "M7I": "Insect screen in front of cooling system",
    "M7T": "Water pump, governed",
    "M7U": "Cooling output for hot regions",
    "M8A": "Air intake from front",
    "M8B": "Air intake behind cab, mounted",
    "K0E": "Plastic tank, 120 l, left",
    "K0F": "Plastic tank, 130 l, fire service",
    "K0G": "Plastic tank, 180 l, left",
    "K0H": "Plastic tank, 125 l, on frame end",
    "K0I": "Plastic tank, 80 l, left",
    "K0J": "Plastic tank, 300 l, left, 735 x 565 x 950 mm",
    "K0K": "Plastic tank, 400 l, left, 735 x 700 x 990 mm",
    "K0L": "Plastic tank, 150 l, left, 500 x 310 x 1210 mm",
    "K0M": "Second plastic tank, 150 l, left, 500x310x1210mm",
    "K0N": "Tank, 480 l, left, 735 x 700 x 1000 mm, aluminium",
    "K0O": "Plastic tank, 75 l, left, 500 x 310 x 610 mm",
    "K0P": "Second plastic tank, 100 l, left",
    "K0Q": "Second plastic tank, 2 x 100 l, left",
    "K0R": "Two plastic tanks, 2x300 l, left, 735x635x950 mm",
    "K0S": "AdBlue tank, 75 l, right",
    "K0U": "Main tank, right",
    "K0V": "Second tank, left",
    "K0X": "US fuel tank, 200 L (50 gal), angular, alu",
    "K0Y": "US fuel tank, 303 L (80 gal), angular, alu",
    "K0Z": "Main tank, 200 l, angular, aluminium",
    "K1A": "Tank 410 l, left, 650 x 700 x 1070 mm, aluminium",
    "K1B": "Tank, 230 l, left, 650 x 565 x 750 mm, aluminium",
    "K1D": "Tank, 330 l, left, 650 x 565 x 1050 mm, aluminium",
    "K1F": "Tank, 500 l, left, 650 x 565 x 1600 mm, aluminium",
    "K1G": "Tank,660l+75l AdBlue,left,735x565x2200 alu.,step",
    "K1H": "Tank, 300 l + 75 l AdBlue, left, 650x700x1050 alu.",
    "K1J": "Tank, 330 l, left, 650 x 700 x 850 mm, aluminium",
    "K1K": "Tank, 390 l, left, 650 x 700 x 1000 mm, aluminium",
    "K1L": "Tank, 430 l, left, 650 x 700 x 1100 mm, aluminium",
    "K1M": "Tank, 510 l, left, 650 x 700 x 1300 mm, aluminium",
    "K1N": "Tank, 570 l, left, 650 x 700 x 1450 mm, aluminium",
    "K1O": "Tank 450 l, left, 650 x 700 x 1170 mm, aluminium",
    "K1P": "Tank, 630 l, left, 650 x 700 x 1600 mm, aluminium",
    "K1Q": "Tank,660l+75l AdBlue,left,650x700x2020 alu.,step",
    "K1R": "Tank,720l+75l AdBlue,left,650x700x2170 alu.,step",
    "K1S": "Tank 260 l, left, 735 x 565 x 750 mm, aluminium",
    "K1T": "Tank, 320 l, left, 735 x 700 x 750 mm, aluminium",
    "K1U": "Tank, 360 l, left, 735 x 700 x 850 mm, aluminium",
    "K1V": "Tank, 430 l, left, 735 x 700 x 1000 mm, aluminium",
    "K1W": "Tank, 480 l, left, 735 x 700 x 1100 mm, aluminium",
    "K1X": "Tank 510 l, left, 735 x 700 x 1170 mm, aluminium",
    "K1Z": "Tank, 300 l, left, 735 x 700 x 700 mm, alumin.",
    "K2A": "Tank,760l+90l AdBlue,left,735x700x2020 alu.,step",
    "K2B": "Tank,820l+90l AdBlue,left,735x700x2170 alu.,step",
    "K2C": "Tank 790l+120l AdBlue,left,735x700x2170,alu.,step",
    "K2D": "Tank 680l+120l AdBlue,left,650x700x2170,alu., step",
    "K2E": "Tank 300 l+25 l AdBlue, left, 650x700x900 mm, alu.",
    "K2J": "Tank,880l+90l AdBlue,left,735x700x2305 alu.,step",
    "K2K": "Tank, 490l, left, 735 x 700 x 1170mm, alu, step",
    "K2L": "Tank 410 l, left, 735 x 700 x 950 mm, aluminium",
    "K2M": "Tank 535 l,left, 735x700x1250 mm, alu, asymmetric",
    "K2P": "Tank 390l+130l hydr.oil, left, 650x700x1365mm, alu",
    "K2T": "Second tank, 230 l, left, 650 x 565 x 750 mm, alu.",
    "K2U": "Second tank, 290 l, left, 650 x 565 x 950 mm, alu.",
    "K2V": "Second tank, 330 l, left, 650 x 565 x 1050 mm,alu.",
    "K2W": "Second tank, 390 l, left, 650 x 565 x 1250 mm,alu.",
    "K2X": "Second tank, 500 l, left, 650 x 565 x 1600 mm,alu.",
    "K2Z": "Second tank, 290 l, left, 650 x 700 x 750 mm, alu.",
    "K3A": "Second tank, 330 l, left, 650 x 700 x 850 mm, alu.",
    "K3B": "Second tank, 390 l, left, 650 x 700 x 1000 mm,alu.",
    "K3C": "Second tank, 430 l, left, 650 x 700 x 1100 mm,alu.",
    "K3D": "Second tank, 510 l, left, 650 x 700 x 1300 mm,alu.",
    "K3E": "Second tank, 570 l, left, 650 x 700 x 1450 mm,alu.",
    "K3F": "Second tank, 630 l, left, 650 x 700 x 1600 mm,alu.",
    "K3I": "Second tank, 360 l, left, 735 x 700 x 850 mm,alu.",
    "K3J": "Second tank, 430 l, left, 735 x 700 x 1000 mm,alu.",
    "K3K": "Second tank, 480 l, left, 735 x 700 x 1100 mm,alu.",
    "K3M": "AdBlue tank, 90 l, left, under battery box",
    "K3O": "AdBlue tank, 75 l, left, under battery box",
    "K3P": "AdBlue tank, 40 l, right, between front axles",
    "K3Q": "AdBlue filler neck with demount. platform subframe",
    "K3R": "AdBlue tank, 8 l",
    "K3S": "AdBlue tank, 35 l",
    "K3U": "AdBlue tank 30 l, right",
    "K3W": "AdBlue tank, 75 l, left",
    "K3X": "AdBlue tank, 100 l, left",
    "K3Y": "AdBlue tank 40 l, right",
    "K3Z": "AdBlue tank, 60 l, right",
    "K4B": "Tank, 230 l, right, 650 x 565 x 750 mm, aluminium",
    "K4C": "Tank, 290 l, right, 650 x 565 x 950 mm, aluminium",
    "K4E": "Tank, 390 l, right, 650 x 565 x 1250 mm, aluminium",
    "K4F": "Tank, 500 l, right, 650 x 565 x 1600 mm, aluminium",
    "K4H": "Tank, 290 l, right, 650 x 700 x 750 mm, aluminium",
    "K4J": "Tank, 390 l, right, 650 x 700 x 1000 mm, aluminium",
    "K4K": "Tank, 430 l, right, 650 x 700 x 1100 mm, aluminium",
    "K4L": "Tank, 510 l, right, 650 x 700 x 1300 mm, aluminium",
    "K4N": "Tank, 630 l, right, 650 x 700 x 1600 mm, aluminium",
    "K4O": "Tank, 330 l, right, 735 x 565 x 950 mm, aluminium",
    "K4Q": "Tank, 300 l, right, 735 x 700 x 700 mm, alumin.",
    "K4T": "Tank, 540 l, right, 735 x 700 x 1250 mm, alumin.",
    "K4U": "Tank, 480 l, right, 735 x 700 x 1100 mm, aluminium",
    "K4V": "Tank, 430 l, right, 735 x 700 x 1000 mm, aluminium",
    "K4W": "Tank 260 l, right, 735 x 565 x 750 mm, aluminium",
    "K4Z": "Tank, 290 l, right, 650 x 565 x 950 mm, steel",
    "K5A": "Tank, 290 l, left, 650 x 565 x 950 mm, steel",
    "K5B": "Tank, 390 l, left, 650 x 565 x 1250 mm, steel",
    "K5C": "Tank, 390 l, right, 650 x 565 x 1250 mm, steel",
    "K5D": "Tank, 500 l, right, 650 x 565 x 1600 mm, steel",
    "K5E": "Second tank 290 l, right, 650x565x950 mm, steel",
    "K5G": "Second tank 390 l, left, 650x565x1250 mm, steel",
    "K5H": "Second tank 500 l, left, 650x565x1600 mm, steel",
    "K5I": "NGT tank system, 560 l",
    "K5J": "NGT tank system, 570 l",
    "K5K": "NGT tank system, 600 l",
    "K5N": "NGT tank system, 580 l, on left of frame",
    "K5O": "NGT tank system, 800 l",
    "K5T": "AdBlue tank, 12 l",
    "K5U": "Tank, raised",
    "K5V": "Shunting tank 20 l, tank system from bodybuilder",
    "K6A": "Second tank 300 l, right, 735 x 700 x 700 mm, alu",
    "K6B": "Second tank, 230 l, right, 650 x 565 x 750 mm,alu.",
    "K6C": "Second tank, 290 l, right, 650 x 565 x 950 mm,alu.",
    "K6D": "Second tank, 330 l, right,650 x 565 x 1050 mm,alu.",
    "K6E": "Second tank, 390 l, right,650 x 565 x 1250 mm,alu.",
    "K6F": "Second tank, 500 l, right,650 x 565 x 1600 mm,alu.",
    "K6H": "Second tank, 290 l, right, 650 x 700 x 750 mm,alu.",
    "K6I": "Second tank, 330 l, right, 650 x 700 x 850 mm,alu.",
    "K6J": "Second tank, 390 l, right,650 x 700 x 1000 mm,alu.",
    "K6K": "Second tank, 430 l, right,650 x 700 x 1100 mm,alu.",
    "K6L": "Second tank, 510 l, right,650 x 700 x 1300 mm,alu.",
    "K6M": "Second tank, 570 l, right,650 x 700 x 1450 mm,alu.",
    "K6N": "Second tank, 630 l, right,650 x 700 x 1600 mm,alu.",
    "K6O": "Second tank,540 l,right, 735x700x1250 mm,aluminium",
    "K6P": "Second tank 410 l, right, 735 x 700 x 950 mm, alu",
    "K6Q": "Second tank, 330 l, right, 735 x 565 x 950 mm,alu.",
    "K6R": "Second tank, 320 l, right, 735 x 700 x 750 mm,alu.",
    "K6S": "Second tank, 360 l, right, 735 x 700 x 850 mm,alu.",
    "K6T": "Second tank, 430 l, right,735 x 700 x 1000 mm,alu.",
    "K6U": "Second tank, 480 l, right,735 x 700 x 1100 mm,alu.",
    "K6V": "Second tank, 370 l, right,650 x 700 x 950 mm,alu.",
    "K6W": "Tank, 200 l hydr. oil, right, 650x565x750 mm, alu.",
    "K6X": "2nd tank 400 l, right, 735 x700 x 950mm,alu",
    "K6Y": "Tank, 200 l hydr. oil, left, 650x565x750 mm, alu.",
    "K7A": "Exhaust system, tailpipe vertical",
    "K7B": "Exhaust syst., outlet downwards, fans out to right",
    "K7C": "Exhaust system, tailpipe to left and outwards",
    "K7D": "Exhaust system, tailpipe to right and outwards",
    "K7E": "Exhaust system, tailpipe vertical, outlet variable",
    "K7F": "Exhaust system, offset, for large tyres",
    "K7G": "Exhaust system with connection for dumper heating",
    "K7H": "Exhaust system, fire service",
    "K7I": "Exhaust system, on frame, right, tailpipe inwards",
    "K7J": "Exhaust system, vertical, behind cab",
    "K7K": "Exhaust system, horizontal, behind cab",
    "K7L": "Exhaust system, tailpipe towards centre of road",
    "K7O": "Exhaust system, tailpipe vertical, extended 600 mm",
    "K7P": "Exhaust system, bracket two-piece",
    "K7Q": "Exhaust system, outlet downwards",
    "K7T": "Exhaust pipe, above wing, second axle",
    "K7U": "Exhaust system, outlet to right",
    "K7V": "Exhaust system, lowered 80 mm",
    "K7W": "Exhaust system, vertical tailpipe, pivoting outlet",
    "K7Y": "Prevention of DPF regeneration, below 54 km/h",
    "K7Z": "Prevention of DPF regeneration, below 35 km/h",
    "K8A": "On-Board Diagnosis, exhaust gas without NOx check",
    "K8B": "On-Board Diagnosis, exhaust gas with NOx check",
    "K8D": "Exhaust sys.,tailpipe to right/outwards,horizontal",
    "K8L": "2nd tank 510 l,right,735x700x1200mm,alu,heated",
    "K8O": "AdBlue tank, 40 l, left, between front axles",
    "K8P": "AdBlue tank, 25 l, left between front axles",
    "K8Q": "Tank 850l+120l AdBlue,left,735x700x2305,alu.,step",
    "K8R": "Tank,650l+85l AdBlue,left,735x565x2200 alu.,step",
    "K8S": "AdBlue tank, 85 l, left",
    "K9A": "Pre-installation, additional tank, at rear, cab",
    "K9Y": "Omission GATS box (CKD)",
    "K9Z": "Deletion, tanks, lockable",
    "M8D": "Air intake, above corner, integrated in cab",
    "M8Y": "Fuel pre-filter, chassis-mounted, additional",
    "M9V": "Deletion, guard plate, bumper",
    # N
    "N1G": "PTO MB, 123-10b, flange, low-speed",
    "N2E": "PTO MB 131-2c, pump",
    "N6P": "Provision for PTO, via external transfer case",
    "N6Z": "Transmission oil cooling",
    # O
    "O3C": "Safety Package",
    "O3D": "Safety Package, without roll control",
    "O3J": "Climate Package, with noise/heat insulation",
    "L0B": "Illumination regulation, in acc. with UN-R 48.08",
    "L1A": "Bi-xenon headlamps",
    "L1B": "Daytime driving lamps",
    "L1E": "LED package",
    "L1H": "Foglamps, halogen",
    "L1I": "Fog lamps, LED daytime running lamps",
    "L1K": "LED matrix headlamps",
    "L1L": "LED light strip",
    "L1N": "Fog lamps, LED day run. lamps, corner. light func.",
    "L1S": "Tail lamps for rear loader",
    "L1T": "Bracket for rear lights for transport purpose",
    "L1V": "Automatic low/high beam",
    "L1Y": "LED light package, front, w.white indicator lenses",
    "O3K": "Active Safety",
    "O8K": "Driving Package",
    "OWN": "Control code, reversing camera, right",
    "OWY": "Interior measures upgrade",
    "OYL": "Storage Package",
    "OYN": "Sight Package, with LED main headlamps",
    "OYP": "Comfort Package, with ExtraPremiumComfort mattress",
    "OYR": "Active safety pack Overseas plus",
    "OYW": "Grounder version",
    # P
    "P0S": "Space for control unit betw. driv. seat & door pocket",
    "P9A": "Tip control, in cab",
    "P9K": "Pre-installation, rear-end tipper, Korea",
    # Q
    "Q0Q": "Front spring, 2 x 10.0 t, 4-leaf",
    "Q1X": "Front spring, 2 x 8.0 t, 3-leaf",
    "Q1Y": "Front spring, 9.0 t, 4-leaf",
    "Q3A": "Rear spring, 2 x 13.0 t",
    "Q3B": "Rear springs, 2 x 13.0 t, for axle spacing 1450 mm",
    "Q8N": "End crossmember, 300 mm indented",
    # R
    "R2F": "Light-alloy wheels, 8.25 x 22.5, Speedline",
    "R2K": "Light-alloy wheels, 9.00 x 22.5, Speedline",
    "R2U": "Aluminium rims 11.75 x 22.5, front axle, Speedline",
    "R6M": "Aluminium whls, 11.75 x 22.5, FA, Speedline, ET135",
    # S
    "S1D": "Stability Control Assist (ESP)",
    "S1H": "Lane Keeping Assist",
    "S1I": "Proximity Control Assist",
    "S1L": "Attention Assist",
    "S2D": "Active Brake Assist 6",
    "S2H": "Active Sideguard Assist 2",
    "S2L": "Frontguard Assist",
    "S2N": "Active Brake Assist 6 Plus",
    "S2Q": "Sensor position, side radar, widened",
    "S3A": "Airbag, driver",
    "S5A": "Speed limiter, 90 km/h (56 mph), ECE",
    "S5Z": "Cruise control",
    "S8C": "Hazard warning triangle",
    "S8D": "Warning lamp",
    # T
    "T6D": "Weight variant 41.0 t (10.0/10.0/10.5/10.5)",
    # U
    "U2G": "Exhaust box",
    "U3S": "3rd-generation electronics architecture",
    # V
    "V0R": "No check for N3G conformity",
    "V0T": "Vehicle class N3G, off-road vehicle",
    "V0U": "Overhang angle, front, minimum 25 degrees",
    "V0W": "Breakover angle, minimum 25 degrees",
    "V0X": "Ground clearance under front axle, minimum 250 mm",
    "V0Y": "Ground clearance under rear axle, minimum 250 mm",
    "V0Z": "Ground clearance between axles, minimum 300 mm",
    "V1B": "Arocs",
    "V1W": "Standard",
    "V1Z": "Grounder",
    "V2J": "Arocs model generation 5",
    "V8A": "Chassis number FIN",
    "V8B": "Chassis number FIN with model year",
    "V8W": "Model year 6",
    "V8X": "Model year 7",
    "V9F": "Technical changes model year April",
    "V9G": "Technical changes model year October",
    # W
    "W4J": "Weight variant 28.0 t (9.0/10.0/10.0)",
    "W5Y": "Weight variant 33.0 t (9.0/13.0/13.0)",
    "W7G": "Weight variant 37.0 t (8.0/8.0/13.0/13.0)",
    "W8M": "Weight variant 44.0 t (9.0/9.0/13.0/13.0)",
    # X
    "X2A": "Model identification, acc. to weight variant",
    "X2C": "Model plate, Gulf States",
    "X2I": "Model plate, export",
    "X2V": "Inner/outer turning circle not as per ECE dir.",
    "X3W": "Powertrain warranty as per T and Cs 3yrs/450,000km",
    "X3Z": "Powertrain warranty as per T and Cs 3yrs/250,000km",
    "X4B": "Instrument/labels/documentation, Korean",
    # Y
    "Y1W": "Refrigerator, on engine tunnel",
    "Y1X": "Pull-out refrigerator, under bed",
    "Y3L": "Preservation for transport",
    "Y4A": "Telescopic jack, 12 t/19 t",
    "Y4H": "Holder for wheel chock",
    "Y4I": "1 wheel chock",
    "Y4J": "2 wheel chocks",
    "Y4Z": "Compressed-air gun, with hose",
    "Y6A": "Country-specific version",
    # Z
    "Z4O": "Tank cross-section, narrow",
    "Z4P": "Tank cross-section, wide",
    "Z4Q": "Tank cross-section, low",
    "Z5E": "OM 471",
    "Z5M": "PTO, single",
    "Z5S": "Power take-off, pump, under top edge of frame",
    "Z5U": "Power take-off, propshaft, under top edge of frame",
    "Z5X": "Left-hand drive",
    "Z5Y": "Vehicle, for right-side traffic",
    # D (additional)
    "D1Q": "Co-driver's suspension seat, ventilated",
    "D2J": "Seat version, Korea",
    "D4E": "Mattress topper for lower comfort bed",
    "D5E": "LED ambient lighting",
    "D5K": "2 LED reading lamps, gooseneck",
    "D7N": "Flexible shelving sys., f. stowage above windscreen",
    # E (additional)
    "E0D": "Battery sensor, Hella",
    "E0Q": "Batteries from company Enersys",
    "E1T": "Alternator, controlled 24-30 V/100 A",
    "E4W": "Starting-off aid, speed limit 30 km/h",
    "E6A": "Trailer socket, 24 V, 15-pin",
    "E6E": "Adapter, 15-pin to 2x7-pin socket",
    # F (additional)
    "FAV": "Cab version ProCabin",
    "FZY": "Vehicle width, 2500 mm",
    "F2V": "BigSpace",
    "F3P": "ProCabin-Stream, level floor",
    "F3Q": "ProCabin-Big, level floor",
    "F4T": "Top entrance, painted",
    "F4V": "A-pillar cladding, aerodynamically optimised",
    "F5B": "Air deflector, snap-in, with cab side deflectors",
    "F5K": "Air deflectors, loose",
    "F6E": "Windscreen, tinted, with filter band, heated",
    "F7A": "Bumper, with plastic corners",
    # G (additional)
    "G0T": "Predictive Powertrain Control",
    # H
    "H2J": "Fifth-wheel lead +950 mm",
    "H1J": "Fifth-wheel lead +1050 mm",
    "H1K": "Fifth-wheel lead +1100 mm",
    "H1L": "Fifth-wheel lead +1150 mm",
    "H1M": "Fifth-wheel lead +1200 mm",
    "H1N": "Fifth-wheel lead +1250 mm",
    "H1P": "Fifth-wheel lead +1300 mm",
    "H1Q": "Fifth-wheel lead +1350 mm",
    "H1V": "Fifth-wheel lead +250 mm",
    "H1W": "Fifth-wheel lead +300 mm",
    "H1X": "Fifth-wheel lead +350 mm",
    "H1Y": "Fifth-wheel lead +400 mm",
    "H1Z": "Fifth-wheel lead +450 mm",
    "H2A": "Fifth-wheel lead +500 mm",
    "H2B": "Fifth-wheel lead +550 mm",
    "H2C": "Fifth-wheel lead +600 mm",
    "H2D": "Fifth-wheel lead +650 mm",
    "H2E": "Fifth-wheel lead +700 mm",
    "H2F": "Fifth-wheel lead +750 mm",
    "H2G": "Fifth-wheel lead +800 mm",
    "H2H": "Fifth-wheel lead +850 mm",
    "H2I": "Fifth-wheel lead +900 mm",
    "H2K": "Fifth-wheel lead +1000 mm",
    "H8N": "Control unit, CLCS high",
    "H8R": "Rear underride guard, folding, for platform truck",
    "H8T": "Ground clearance, increased, for road vehicle",
    "H8U": "Front underride guard, not ECE-compliant",
    "H8V": "Rear underride guard, reinforced",
    "H8W": "Step plate above frame, not ECE compliant",
    "H8X": "Multi-battery carrier, batteries side by side",
    "H8Y": "Full mudguards, for fully integrated tipper",
    "H8Z": "Splash guard, front",
    # I — vehicle classification / factory control codes
    "I4D": "Wheel arrangement 6x2, trailing axle, twin tyres",
    "I4L": "Wheel arrangement 8x4/4",
    "I5F": "26.0-tonner",
    "I5G": "32.0-tonner",
    "I4I": "Wheel arrangement 6x4",
    "I6A": "Rigid chassis",
    "I6B": "Tipper chassis",
    "I6D": "Semitrailer tractor",
    "I6I": "Vehicle production plant Wörth",
    "I6K": "Heavy-duty model series, new generation from 18 t",
    "I6M": "Heavy-duty vehicles from 18 t, off-road",
    "I6N": "Heavy-duty vehicles from 18 t, on-road",
    "I6W": "Leaf suspension, rear axle",
    "I6X": "Air suspension, rear axle",
    "I0A": "Tyres, tubeless, size 9.5 R 17.5, front axle",
    "I0C": "Tyres, tubeless, size 10 R 17.5, front axle",
    "I0E": "Tyres, tubeless, 215/75 R 17.5, front/leading axle",
    "I0F": "Tyres, tubeless, 215/75 R 17.5, rear axle",
    "I0I": "Tyres, tubeless, size 235/75 R 17.5, front axle",
    "I0J": "Tyres, tubeless, size 235/75 R 17.5, rear axle",
    "I0K": "Tyres, tubeless, size 245/70 R 17.5, front axle",
    "I0S": "Tyres tubeless, 245/70 R 19.5, front axle",
    "I0U": "Tyres, tubeless, size 265/70 R 19.5, front axle",
    "I0W": "Tyres, tubeless, size 285/70 R 19.5, front axle",
    "I0Y": "Tyres, tubeless, size 305/70 R 19.5, front axle",
    "I1C": "Tyres, tubeless, size 10 R 22.5, front axle",
    "I1E": "Tyres tubeless, 11 R 22.5, front/lead./trail. axle",
    "I1F": "Tyres, tubeless, size 11 R 22.5, rear axle",
    "I1G": "Tyres tubeless, 12 R 22.5, front/lead./trail. axle",
    "I1H": "Tyres, tubeless, size 12 R 22.5, rear axle",
    "I1I": "Tyres, tubeless, size 13 R 22.5, VA/VLA/NLA",
    "I1J": "Tyres, tubeless, size 13 R 22.5, rear axle",
    "I1M": "Tyres tubeless, 275/70 R 22.5, fr./lead./trl. axle",
    "I1N": "Tyres, tubeless, size 275/70 R 22.5, rear axle",
    "I1P": "Tyres tubeless, 275/80 R 22.5, fr./lead./trl. axle",
    "I1T": "Tyres tubeless, 295/60 R 22.5, fr./lead./trl. axle",
    "I1U": "Tyres, tubeless, size 295/60 R 22.5, rear axle",
    "I1V": "Tyres tubeless, 295/80 R 22.5, fr./lead./trl. axle",
    "I1W": "Tyres, tubeless, size 295/80 R 22.5, rear axle",
    "I1X": "Tyres, tubeless, size 295/55 R 22.5, trailing axle",
    "I1Y": "Tyres, tubeless, size 295/55 R 22.5, rear axle",
    "I2A": "Tyres tubeless, 305/70 R 22.5, fr./lead./trl. axle",
    "I2B": "Tyres, tubeless, size 305/70 R 22.5, rear axle",
    "I2C": "Tyres tubeless, 315/60 R 22.5, fr./lead./trl. axle",
    "I2D": "Tyres, tubeless, size 315/60 R 22.5, rear axle",
    "I2E": "Tyres tubeless, 315/70 R 22.5, fr./lead./trl. axle",
    "I2F": "Tyres, tubeless, size 315/70 R 22.5, rear axle",
    "I2G": "Tyres tubeless, 315/80 R 22.5, fr./lead./trl. axle",
    "I2H": "Tyres, tubeless, size 315/80 R 22.5, rear axle",
    "I2I": "Tyres tubeless, 355/50 R 22.5, fr./lead./trl. axle",
    "I2M": "Tyres tubeless, 385/55 R 22.5, fr./lead./trl. axle",
    "I2N": "Tubeless tyres, 385/55 R 22.5 RA",
    "I2P": "Tyres tubeless, 385/65 R 22.5, fr./lead./trl. axle",
    "I2Q": "Tyres, tubeless, size 385/65 R 22.5, rear axle",
    "I2R": "Tyres, tubeless, size 365/70 R 22.5, front axle",
    "I2S": "Tyres, tubeless, size 445/50 R 22.5, front axle",
    "I2U": "Tyres, tubeless, size 315/45 R 22.5, rear axle",
    "I2V": "Tyres, tubeless, size 425/65 R 22.5, front axle",
    "I2Z": "Tyres, tubeless, size 495/45 R 22.5, rear axle",
    "I3D": "Tyres tubeless, 375/50 R 22.5, fr./lead./trl. axle",
    "I3J": "Tyre size 11.00 R 22.0, FA/leading axle/trail.axle",
    "I3K": "Tyre size 11.00 R 22.0, rear axle",
    "I4A": "Wheel arrangement 4x2",
    "I4B": "Wheel arrangement 4x4",
    "I4C": "Wheel arrangement 6x2, single-tyred trailing axle",
    "I4E": "Wheel arrangement 6x2/2, leading axle, 22.5 inch",
    "I4F": "Wheel arrangement 6x2/2, leading axle, 17.5 inch",
    "I4G": "Wheel arrangement 6x2/4, leading axle, 22.5 inch",
    "I4H": "Wheel arrangement 6x2/4, trailing axle",
    "I4J": "Wheel arrangement 6x6",
    "I4K": "Wheel arrangemt. 8x2/4, lead.ax/twin-tyre trail ax",
    "I4M": "Wheel arrangement 8x6/4",
    "I4N": "Wheel arrangement 8x8/4",
    "I4Q": "Wheel arrangement 8x2/4, single-tyred trail.axle",
    "I4R": "Wheel arrangement 8x4, single-tyred trailing axle",
    "I4T": "Wheel arrangement 8x4/4, leading axle",
    "I4U": "Wheel arrangement 8x4/4,single-tyred trailing axle",
    "I4V": "27.0-tonner",
    "I4Z": "8.0-tonner",
    "I5A": "18.0-tonner",
    "I5B": "19.0-tonner",
    "I5C": "20.0-tonner",
    "I5D": "22.0-tonner",
    "I5E": "25.0-tonner",
    "I5H": "33.0-tonner",
    "I5I": "40.0-tonner",
    "I5J": "41.0-tonner",
    "I5L": "24.0 tonner",
    "I5M": "21.0-tonner",
    "I5N": "10.0-tonner",
    "I5O": "Payload-optimised 12-tonner",
    "I5P": "6.5-tonner",
    "I5Q": "7.5-tonner",
    "I5R": "7.99-tonner",
    "I5S": "9.5-tonner",
    "I5T": "10.5-tonner",
    "I5U": "11.0-tonner",
    "I5V": "12.0-tonner",
    "I5W": "13.0-tonner",
    "I5X": "13.5-tonner",
    "I5Y": "15.0-tonner",
    "I5Z": "Chassis",
    "I6C": "Concrete-mixer chassis",
    "I6E": "Municipal vehicle chassis",
    "I6F": "Fire service chassis",
    "I6H": "Vehicle production plant Aksaray",
    "I6J": "Model series Econic",
    "I6L": "Light-duty model series, new generation up to 21 t",
    "I6O": "Light-duty vehicles up to 21 t",
    "I6P": "Vehicle production plant Sao Bernardo do Campo",
    "I6Q": "Axle production plant Sao Bernardo do Campo",
    "I6R": "Axle production plant Kassel",
    "I6S": "Axle production plant Gaggenau",
    "I6V": "Air suspension, rear axle, lowliner",
    "I6Y": "Air suspension, rear axle, car carrier",
    "I6Z": "Air suspension, rear axle, low frame",
    "I7G": "Tyre size 12.00 R 20, front axle",
    "I7H": "Tyre size 12.00 R 20, rear axle",
    "I7M": "Tyre size 14.00 R 20, front/trailing axle",
    "I7N": "Tyre size 14.00 R 20, rear axle",
    "I7T": "Tyre size 335/80 R 20, front axle",
    "I7V": "Tyre size 365/80 R20, front axle",
    "I7X": "Tyre size 365/85 R 20, front axle",
    "I7Y": "Tyre size 365/85 R 20, rear axle",
    "I8E": "Tyres 395/85 R20 FA",
    "I8F": "Tyres 395/85 R 20 RA",
    "I8K": "Cab BIW Aksaray production plant",
    "I8Y": "Model series Zetros Off-road",
    "I8Z": "Model series Zetros",
    "I9M": "9.0-tonner",
    "I9W": "Tyres, 325/95 R 24, front axle/leading axle",
    "I9X": "Tyres, size 325/95 R 24, rear axle",
    "I9Y": "Tyres, 12.00 R 24, front/leading/trailing axle",
    "I9Z": "Tyre size 12.00 R 24, rear axle",
    "IZD": "Chassis electrified",
    # J (additional)
    "J2J": "Sound system",
    "J7G": "GPRS1 Config Fragment G_SIM ModemEU",
    "J7Q": "Driving assistance map, South Korea region",
    "JD2J": "Seat version, Korea",
    "JDAP": "Seat base Standard",
    # K (additional)
    "K0W": "Second tank, right",
    "K1I": "Tank, 290 l, left, 650 x 700 x 750 mm, aluminium",
    "K6G": "Second tank, 220 l, right, 650 x 700 x 600 mm, aluminium",
    # L (additional)
    "L2G": "LED side turn signal lamps",
    "L3K": "1 LED work light, cab rear wall, top",
    "L6A": "Intelligent Light",
    # M (additional)
    "M4Y": "Certification according to ECE",
    "M6R": "Air compressor, two-stage, deactivatable",
    "M8L": "Cyclone filter for coarse dust",
    # O (additional)
    "OKS": "Cooling module, standard",
    "O0A": "Coolant service interval, long for non-SWR",
    "O1S": "Interior colour almond beige",
    "O1T": "Interior colour greige/anthracite",
    "O1Z": "Steering, indirect",
    "O2N": "Starter Melco 95P65",
    "O3R": "Actros L",
    "O5J": "Country-spec. contr. code FIN/VIN-corr. divergent",
    "O5Q": "Control code for A dimension, rear axle 435 mm",
    # Q (additional)
    "Q0W": "Fifth-wheel coupling ex factory",
    "Q3Z": "Lowered frame, with residual bellow pressure ctrl.",
    "Q4K": "Fifth wheel coupling height = 185 mm",
    "Q4X": "Fifth wheel coupling, manually lubricated",
    "Q5Q": "Fifth wheel coupling, standard, Jost JSK 37C",
    "Q5Y": "Drive-on ramp/coupling aid",
    "Q6D": "Mounting plate, 40 mm, 20 t",
    "Q6W": "5th-wheel bracket, w/ hole pattern, raised, H=50mm",
    # R (additional)
    "R2J": "Light-alloy wheels, 9.00x22.5, matt, Alcoa",
    "R2Y": "Alum. wheels 9.00 x 22.5, Dura-Bright, Alcoa",
    # S (additional)
    "S2E": "Active Drive Assist 3",
    # U (additional)
    "U1W": "AdBlue lines, water-heated",
    "U2K": "Control code, high PTO transmission oil level",
    "U2S": "Control code, exhaust box, left-hand outlet",
    "U2T": "Control code, exhaust box, rear outlet",
    "U2V": "Control code, catalytic converter kit 2",
    "U3L": "Control code, catalytic converter kit 5",
    "U3D": "Control code, CAN star points, classic",
    "U3F": "Control code, global AdBlue sensor (GMS DEF)",
    "U3H": "Control code, Tachometer Simulator Unit (TSU)",
    "U3I": "Control code, NFD standard",
    "U4U": "Control code, tail light bracket POS 3 HUF, 12 mm",
    "U4X": "Control code, crescent crossmember under trans.",
    # V (additional)
    "V0S": "Vehicle class N3",
    "V1A": "Actros",
    "V2B": "Actros model generation 5",
    # W (additional)
    "W4E": "Weight variant 28.0 t (8.0/10.0/10.0)",
    # Z (additional)
    "Z3Z": "Export code",
    "Z4R": "Tank cross-section, high",
    "Z5P": "Clutch supplier F&S",
    "Z5Q": "Clutch supplier LUK",
    "Z7N": "Text order",
    "Z7P": "Stamping, model plate, manual",
    "Z8M": "CTT vehicle, conversion at Molsheim plant",
    "Z8P": "CTT vehicle, conversion on assembly line",
    "Z8R": "CTT vehicle, conversion, at the Wörth site",
    "Z8U": "CTT vehicle",
    "Z9A": "Constructability request order, special control",
    # Special J-prefix codes (internal / option codes starting with J)
    "JC9B": "Frame overhang 3300 mm",
    "JCAL": "Extension of wheelbase (JCAL)",
    "JCKD": "Battery carrier relocated to dimension 3625 mm",
    "JCRP": "Reinforcement, plate crossmembers, rear axles",
    "JCUX": "Extension of wheelbase (JCUX)",
    "JCWV": "Wheelbase 5900 mm",
    "JCWW": "Extension of wheelbase (JCWW)",
    "JCXX": "Extension of wheelbase",
    "JF3C": "Cab mountings, comfort, air-sprung",
    "JK0U": "Main tank, right",
    "JK3V": "AdBlue tank, 60 l, left",
    "JK4E": "Tank, 390 l, right, 650 x 565 x 1250 mm, aluminium",
    "JK5Y": "Initial filling, additional 30 litres of fuel",
    "JK6H": "JK6H option",
    "JKUR": "AdBlue-Tank relocated to the right",
    "JKVY": "Tank moved to measure 3125 mm",
    "JR6M": "Aluminium whls, 11.75 x 22.5, FA, Speedline, ET135",
    "JQYY": "Vehicle operation without trailer",
    "JW7Y": "Weight variant 41.0 t (8.0/8.0/13.0/13.0)",
    "JZYI": "Control code, no EU/ECE conformity",
    "JZYN": "Control code, no CoC, national individual regist",
    "JZYU": "Control code, system approvals list not complete",
    # ── Additional codes from master list ──
    # E (missing)
    "E0G": "Batteries from company GS Yuasa",
    "E1D": "Batteries 2 x 12 V/225 Ah, low-maintenance",
    "E1L": "Alternator, 28 V/120 A",
    "E1Q": "Alternator, 28 V/100 A, 2nd",
    "E1R": "Alternator, 28 V/150 A, 2nd",
    "E1V": "Alternator, controlled 24-30 V/100 A, 2nd",
    "E2A": "Central electrics, in cab",
    "E2D": "Wiring harness, for cab transit",
    "E2E": "Wiring harness, loose, stage I (CKD)",
    "E2K": "Wiring harness, for body manufacturer, extended",
    "E2L": "Wiring harness, additional, for body manufacturer",
    "E2M": "Wiring, supplementary, for rear tipper",
    "E2O": "Supplementary wiring, for concrete mixer",
    "E2R": "Supplementary wiring, for refuse collection",
    "E2S": "Supplementary wiring, for loading crane",
    "E2U": "Supplementary wiring, for special bodies",
    "E3C": "Additional socket 24 V/15 A, in instrument panel",
    "E3G": "Socket, 12 V/15 A, in instrument panel",
    "E3O": "Socket, 230 V, in side wall stowage space, left",
    "E4F": "Interface module, for body manufacturer",
    "E4G": "Body CAN interface, extended",
    "E4K": "Interface, J1939, for body manufacturer",
    "E4L": "CAN interface, for body manufacturer, additional",
    "E4M": "Interface, extended, for body manufacturer",
    "E4N": "Body interface, frame-mounted",
    "E4P": "PSM auxiliary control unit",
    "E4Q": "PSM auxiliary control unit, 2nd",
    "E4R": "PSM auxiliary control unit, 3rd",
    "E5O": "Battery master switch, two-pin",
    "E5P": "Battery master switch, three-pin",
    "E5R": "ADR type class MEMU",
    "E5S": "ADR accessories, fire extinguisher, in cab",
    "E6C": "Trailer socket, 24 V, 15-pin, additional",
    "E6H": "Trailer socket, 24 V, 7-pin, additional",
    "E6L": "Trailer socket, 12 V, 7-pin",
    "E6N": "Trailer socket, 24 V, 15-pin, frame-mounted",
    "E6O": "Trailer socket, 24 V, 7-pin, frame-mounted",
    "E7M": "Electrical installation, for fire service vehicle",
    "E8A": "Inductive charging cradle, for mobile phone",
    "E8C": "USB-C connector, in dashboard",
    "E8G": "USB connection, in side wall stowage comp., left",
    "E8H": "USB connection, in side wall stowage comp., right",
    "E8K": "USB-C conn., in side wall stowage comp., additional",
    "E8L": "Wireless charging pad, in dashboard",
    "E8M": "USB-C connector, in rear wall stowage",
    "E8Q": "230 V socket, in side wall stowage space, left",
    "E8R": "230 V socket, in side wall stowage space, right",
    "E8S": "Voltage transformer, 24 V/230 V, 300 W",
    "E8T": "Voltage transformer, 24 V/230 V, 1000 W",
    "E8U": "Voltage transformer, 24 V/230 V, 1500 W",
    "E8V": "Voltage transformer, 24 V/230 V, 2000 W",
    "E8W": "Voltage transformer, 24 V/230 V, 3000 W",
    "E8X": "230 V connection, external",
    "E8Y": "Shore power connection, 230 V",
    "E8Z": "Pre-installation for shore power connection",
    "E9A": "Pre-installation, voltage transformer",
    "E9L": "Pre-installation, wiring harness, body manufacturer",
    # F (missing)
    "F0L": "L-cab BigSpace, 2.50 m, level floor",
    "F0N": "L-cab GigaSpace, 2.50 m, tunnel 120 mm",
    "F1G": "L-cab BigSpace, 2.30 m, level floor",
    "F2D": "Floor variant, level floor",
    "F2J": "Cab, 500 mm attachment height",
    "F2K": "Cab, 550 mm attachment height",
    "F2R": "Cab, 850 mm attachment height",
    "F3D": "Cab mountings, comfort, reinforced",
    "F3F": "Cab mountings, front, reinforced",
    "F3L": "Cab tilting mechanism, manually operated",
    "F3M": "Cab tilting mechanism, hydraulic",
    "F3N": "Cab tilting mechanism, electrohydraulic, reinforced",
    "F3O": "ProCabin-Classic, level floor",
    "F3U": "ProCabin-Giga, tunnel",
    "F4A": "Cab rear wall, insulated",
    "F4B": "Cab rear wall, with stowage",
    "F4C": "Body height above frame, up to 2.65 m",
    "F4F": "Cab side wall, closed, left",
    "F4L": "Rear wall window, fixed",
    "F4N": "Cab rear wall, with window, insulated",
    "F5M": "Sun visor, exterior, painted",
    "F5O": "Air deflectors, body height above frame, above 4 m",
    "F5R": "Air deflectors, cab side deflectors, extended",
    "F5V": "A-pillar trim, chrome",
    "F6P": "Mirror bracket, vehicle width up to 2.55 m",
    "F7E": "Bumper, steel, construction vehicle",
    "F7F": "Bumper, with integrated fog lamps",
    "F7H": "Bumper, short, construction vehicle",
    "F7I": "Bumper centre section, steel",
    "F7J": "Bumper, with towing eyes, steel corners",
    "F7K": "Bumper, fire service",
    "F7M": "Bumper, with fog lamp brackets",
    "F7Q": "Cab entrance, left/right, standard",
    "F7R": "Cab entrance, three-step",
    "F7U": "Cab entrance, aluminium steps",
    "F8K": "Central locking, remote control",
    # G (missing)
    "G0J": "Drive program, manual",
    "G2A": "Transmission G 211-12/11.7-0.78",
    "G3D": "Automatic transmission 5/3.49-0.75, Allison 3200 P",
    "G3P": "Auto 6/4.70-0.67 Allison 4500 SPP with retarder",
    "G4A": "Transfer case VG 2400-3W/1.69-1.04, permanent",
    "G4B": "Transfer case VG 2400-3W/1.69-1.04, engageable",
    "G4F": "Transfer case VG 2000-3W/1.45-1.04, engageable",
    "G4G": "Transfer case VG 2000-3W/1.45-1.04, permanent",
    "G4J": "Transfer case, oil cooler, reinforced",
    # H (missing)
    "H0A": "Trailer coupling, standard",
    "H0B": "Trailer coupling, adjustable height",
    "H0C": "Trailer coupling, low",
    "H0D": "Trailer coupling, with shock absorber",
    "H0G": "Towing device, front",
    "H0H": "Towing device, rear",
    "H0K": "Tow bar coupling",
    "H0L": "Tow bar, with adjustable coupling head",
    "H1B": "Fifth-wheel lead +150 mm",
    "H1F": "Fifth-wheel lead +0 mm",
    "H1G": "Fifth-wheel lead +50 mm",
    "H1S": "Fifth-wheel lead +1400 mm",
    "H3A": "Fifth wheel coupling, Jost JSK 37CZ",
    "H3B": "Fifth wheel coupling, Jost JSK 42",
    "H3C": "Fifth wheel coupling, SAF SK-S 36.20",
    "H3D": "Fifth wheel coupling, SAF SK-S 36.20 Plus",
    "H3E": "Fifth wheel coupling, Fontaine 6000 series",
    "H3F": "Fifth wheel coupling, Jost JSK 37E",
    "H3G": "Fifth wheel coupling, Jost JSK 50",
    "H3H": "Fifth wheel coupling, SAF SK-HD 38.42",
    "H3J": "Fifth wheel coupling, Ringfeder 4040",
    "H3K": "Fifth wheel coupling, SAF SK-S 36.20-1",
    "H3M": "Fifth wheel coupling, Fontaine 7000 series",
    "H3N": "Fifth wheel coupling, Jost JSK 37CW",
    "H3O": "Fifth wheel coupling, Ringfeder 5050",
    "H3P": "Fifth wheel coupling, Jost JSK 37DZ",
    "H4A": "Fifth wheel coupling plate, standard",
    "H4C": "Fifth wheel coupling plate, reinforced",
    "H4D": "Fifth wheel coupling plate, extended",
    "H4E": "Fifth wheel coupling plate, weight-optimised",
    "H4F": "Fifth wheel coupling plate, low",
    "H4G": "Fifth wheel coupling plate, with slider",
    "H4J": "Fifth wheel bracket, standard",
    "H4K": "Fifth wheel bracket, reinforced",
    "H4L": "Fifth wheel bracket, raised 50 mm",
    "H4M": "Fifth wheel bracket, raised 100 mm",
    "H4N": "Fifth wheel bracket, raised 150 mm",
    # J (missing)
    "JV3L": "Preservation for transport (J-variant)",
    # N (missing)
    "N0A": "PTO, on engine, front",
    "N0B": "PTO, on engine, rear",
    "N0C": "PTO, on transmission, side",
    "N0D": "PTO, on transmission, rear",
    "N0E": "PTO, on transfer case",
    "N0F": "PTO, on engine, belt-driven",
    "N0G": "PTO, compressed-air controlled",
    "N0H": "PTO, electrically controlled",
    "N1A": "PTO MB, 131-2c, flange",
    "N1B": "PTO MB, 123-10b, flange, high-speed",
    "N1C": "PTO MB, 131-2c, pump, reinforced",
    "N1D": "PTO MB, 131-10c, flange",
    "N1E": "PTO MB, 131-10c, pump",
    "N1F": "PTO MB, via clutch-dependent connection",
    "N1H": "PTO MB, on transfer case, rear",
    "N1I": "PTO MB, on engine, belt-driven",
    "N1J": "PTO MB, on transmission, flange, additional",
    "N1K": "PTO, on engine, hydraulic pump",
    "N1L": "PTO, on transmission, pump, additional",
    "N1M": "PTO, on engine, with compressor",
    # O (missing)
    "O0T": "Control code, Factory Control",
    # P (missing)
    "P0A": "Tow coupling, standard",
    "P0B": "Tow coupling, automatic",
    "P0C": "Tow coupling, with shock absorber",
    "P0D": "Tow coupling, adjustable height",
    "P0E": "Tow coupling, reinforced",
    "P0F": "Tow coupling, heavy-duty",
    "P0G": "Tow coupling, for tipper",
    "P0I": "Tow coupling, for concrete mixer",
    "P0K": "Tow coupling, for refuse collection",
    "P0L": "Tow coupling, low",
    "P0O": "Pintle hook coupling",
    "P0P": "Pintle hook coupling, automatic",
    "P0Q": "Pintle hook coupling, reinforced",
    "P0R": "Coupling jaw, standard",
    "P0T": "Coupling jaw, reinforced",
    "P0V": "Drawbar coupling, standard",
    "P0W": "Drawbar coupling, automatic",
    "P0X": "Drawbar coupling, reinforced",
    "P0Y": "Drawbar coupling, with shock absorber",
    "P0Z": "Drawbar coupling, heavy-duty",
    "P1A": "Tow bar, fixed",
    "P1B": "Tow bar, adjustable",
    "P1C": "Tow bar, removable",
    "P1E": "Tow bar, reinforced",
    "P1F": "Tow bar, heavy-duty",
    "P1G": "Tow bar, for tipper",
    "P1H": "Tow bar, for concrete mixer",
    "P1L": "Tow coupling, low position",
    "P1M": "Tow coupling, medium position",
    "P1N": "Tow coupling, high position",
    # Q (missing)
    "Q1A": "Front spring, 2 x 4.0 t, 2-leaf",
    "Q1B": "Front spring, 2 x 4.5 t, 2-leaf",
    "Q1C": "Front spring, 2 x 5.0 t, 2-leaf",
    "Q1D": "Front spring, 2 x 5.3 t, 2-leaf",
    "Q1E": "Front spring, 2 x 6.0 t, 3-leaf",
    "Q1F": "Front spring, 2 x 6.5 t, 3-leaf",
    "Q1G": "Front spring, 2 x 7.0 t, 3-leaf",
    "Q1H": "Front spring, 2 x 7.1 t, 3-leaf",
    "Q1I": "Front spring, 2 x 7.5 t, 3-leaf",
    "Q1J": "Front spring, 2 x 7.5 t, 4-leaf",
    "Q1K": "Front spring, 2 x 8.0 t, 4-leaf",
    "Q1L": "Front spring, 2 x 8.5 t, 4-leaf",
    "Q1M": "Front spring, 2 x 9.0 t, 3-leaf",
    "Q1N": "Front spring, 2 x 9.0 t, 4-leaf",
    "Q1O": "Front spring, 2 x 9.5 t, 4-leaf",
    "Q1P": "Front spring, 2 x 10.0 t, 3-leaf",
    "Q1Q": "Front spring, 2 x 4.7 t, 2-leaf",
    "Q1R": "Front spring, 2 x 3.2 t, 2-leaf",
    "Q1S": "Front spring, 2 x 6.1 t, 3-leaf",
    "Q1T": "Front spring, 2 x 4.4 t, 2-leaf",
    "Q1U": "Front spring, 2 x 4.1 t, 2-leaf",
    "Q1V": "Front spring, 2 x 5.5 t, 3-leaf",
    # R (missing)
    "R0A": "Steel wheels, standard",
    "R0C": "Steel wheels, reinforced",
    "R0D": "Steel wheels, weight-optimised",
    "R0E": "Light-alloy wheels, standard",
    # S (missing)
    "S2A": "Active Brake Assist 4",
    "S2B": "Active Brake Assist 5",
    "S2C": "Active Sideguard Assist",
    # V (missing)
    "V0A": "Vehicle class N1",
    "V0B": "Vehicle class N2",
    "V0C": "Vehicle class N3, road vehicle",
    "V0D": "Vehicle class N3, construction vehicle",
    "V0E": "Vehicle class N3G, road vehicle",
    "V0F": "Vehicle class N3G, construction vehicle",
    "V0G": "Vehicle class M3",
    "V0H": "Vehicle class, special vehicle",
    "V0J": "Vehicle class, fire service",
    "V0K": "Vehicle class, military",
    "V0L": "Vehicle class, municipal",
    "V0N": "Vehicle class, CKD",
    "V0P": "Vehicle class, export",
    "V0Q": "Vehicle class, right-hand drive",
    "V0V": "Overhang angle, rear, minimum 25 degrees",
    "V1C": "Antos",
    "V1D": "Econic",
    "V1E": "Zetros",
    "V1F": "Unimog",
    "V1G": "Atego",
    "V1H": "eActros",
    "V1J": "eEconic",
    "V1K": "GenH2",
    "V1L": "Actros F",
    "V1M": "Arocs model",
    "V1N": "Actros L model",
    "V1P": "Actros model",
    "V1Q": "Antos model",
    "V2A": "Actros model generation 4",
    "V2C": "Antos model generation 5",
    "V2D": "Econic model generation",
    "V2E": "Zetros model generation",
    "V2F": "Unimog model generation",
    "V2G": "Atego model generation",
    "V2H": "eActros model generation",
    "V2K": "GenH2 model generation",
    "V2L": "Actros F model generation",
    "V2M": "Arocs model generation",
    "V2N": "Actros L model generation",
    "V2P": "Actros model generation",
    "V2R": "Antos model generation",
    "V2S": "Vehicle generation, current",
    "V2T": "Vehicle generation, previous",
    "V2U": "Vehicle generation, next",
    "V2V": "Vehicle generation, special",
    "V2Y": "Vehicle platform, current",
    "V2Z": "Vehicle platform, previous",
    "V3A": "Engine OM 470, 7.7 l",
    "V3B": "Engine OM 471, 12.8 l",
    "V3C": "Engine OM 473, 15.6 l",
    "V3D": "Engine OM 936, 7.7 l",
    "V3E": "Engine OM 934, 5.1 l",
    "V3F": "Engine, electric drive",
    "V3G": "Engine, hydrogen fuel cell",
    "V3H": "Engine OM 460, 12.0 l",
    "V3I": "Engine OM 457, 12.0 l",
    "V3J": "Engine OM 926, 7.2 l",
    "V3K": "Engine OM 924, 4.8 l",
    "V3L": "Engine OM 501, 11.9 l",
    "V3M": "Engine OM 502, 15.9 l",
    "V3N": "Engine OM 906, 6.4 l",
    "V3P": "Engine OM 904, 4.2 l",
    "V3Q": "Engine, natural gas (CNG)",
    "V3R": "Engine, natural gas (LNG)",
    "V3S": "Engine, dual-fuel",
    "V3T": "Engine OM 470, 10.7 l",
    "V3V": "Engine OM 471, 12.8 l, 2nd gen",
    "V3W": "Engine OM 473, 15.6 l, 2nd gen",
    "V3X": "Engine OM 936, 7.7 l, 2nd gen",
    "V3Y": "Engine OM 934, 5.1 l, 2nd gen",
    "V3Z": "Engine variant, special",
    "V4A": "Emission standard Euro VI, A",
    "V4B": "Emission standard Euro VI, B",
    "V4C": "Emission standard Euro VI, C",
    "V4D": "Emission standard Euro VI, D",
    "V4E": "Emission standard Euro VI, E",
    "V4F": "Emission standard Euro V",
    "V4G": "Emission standard Euro IV",
    "V4H": "Emission standard Euro III",
    "V4I": "Emission standard, US EPA",
    "V4J": "Emission standard, China VI",
    "V4K": "Emission standard, Brazil P8",
    "V4L": "Emission standard, special",
    "V4M": "Emission standard Euro VI, step E",
    "V4N": "Emission standard, non-regulated",
    "V4P": "Emission standard, Stage V",
    "V4Q": "Emission standard Euro 5, Classic",
    "V4R": "Emission standard, ADR",
    "V4S": "Emission standard, Japan",
    "V4T": "Emission standard, Korea",
    "V4U": "Emission standard, India BS VI",
    "V4V": "Emission standard, Australia",
    "V4W": "Emission standard, Taiwan",
    "V4X": "Emission standard, Gulf region",
    "V4Y": "Emission standard, Africa",
    "V4Z": "Emission standard, variant",
    "V5A": "Power output, 175 kW (238 hp)",
    "V5B": "Power output, 210 kW (286 hp)",
    "V5C": "Power output, 235 kW (320 hp)",
    "V5D": "Power output, 260 kW (354 hp)",
    "V5E": "Power output, 290 kW (394 hp)",
    "V5F": "Power output, 315 kW (428 hp)",
    "V5G": "Power output, 350 kW (476 hp)",
    "V5I": "Power output, 375 kW (510 hp)",
    "V5K": "Power output, 390 kW (530 hp)",
    "V5P": "Power output, 460 kW (625 hp)",
    "V6A": "Country version, Germany",
    "V6B": "Country version, France",
    "V6C": "Country version, Italy",
    "V6D": "Country version, Spain",
    "V6E": "Country version, United Kingdom",
    "V6F": "Country version, Netherlands",
    "V6G": "Country version, Belgium",
    "V6H": "Country version, Austria",
    "V6I": "Country version, Switzerland",
    "V6J": "Country version, Scandinavia",
    "V6K": "Country version, Poland",
    "V6L": "Country version, Czech Republic",
    "V6M": "Country version, Hungary",
    "V6N": "Country version, Romania",
    "V6P": "Country version, Turkey",
    "V6R": "Country version, Russia",
    "V6S": "Country version, South Africa",
    "V6T": "Country version, Middle East",
    "V6U": "Country version, North Africa",
    "V6V": "Country version, Sub-Saharan Africa",
    "V6W": "Country version, Australia",
    "V6X": "Country version, New Zealand",
    "V6Y": "Country version, Japan",
    "V6Z": "Country version, South Korea",
    "V7A": "Country version, China",
    "V7B": "Country version, Taiwan",
    "V7C": "Country version, India",
    "V7D": "Country version, Indonesia",
    "V7E": "Country version, Thailand",
    "V7F": "Country version, Malaysia",
    "V7G": "Country version, Singapore",
    "V7J": "Country version, Brazil",
    "V7K": "Country version, Argentina",
    "V7L": "Country version, Chile",
    "V7M": "Country version, Colombia",
    "V7N": "Country version, Mexico",
    "V7P": "Country version, USA",
    "V7Q": "Country version, Canada",
    "V7R": "Country version, Gulf states",
    "V7S": "Country version, Saudi Arabia",
    "V7T": "Country version, UAE",
    "V7U": "Country version, Israel",
    "V7V": "Country version, Iran",
    "V7W": "Country version, Pakistan",
    "V7X": "Country version, Bangladesh",
    "V7Y": "Country version, Sri Lanka",
    "V7Z": "Country version, special",
    "V8C": "Chassis number FIN, special",
    "V8D": "VIN, 17-digit",
    "V8E": "VIN, vehicle identification",
    "V8F": "Model identification, standard",
    "V8G": "Model identification, special",
    "V8H": "Type plate, standard",
    "V8I": "Type plate, export",
    "V8J": "Type plate, special",
    "V8K": "Model year 1",
    "V8L": "Model year 2",
    "V8M": "Model year 3",
    "V8N": "Model year 4",
    "V8P": "Model year 5",
    "V8Q": "Model year 8",
    "V8R": "Model year 9",
    "V8S": "Model year 10",
    "V8T": "Model year 11",
    "V8U": "Model year 12",
    "V8V": "Model year 13",
    "V8Y": "Technical changes, model year, spring",
    "V8Z": "Technical changes, model year, autumn",
    "V9A": "Technical changes, version A",
    "V9B": "Technical changes, version B",
    "V9C": "Technical changes, version C",
    "V9D": "Technical changes, version D",
    "V9E": "Technical changes, version E",
    "V9H": "Technical changes, model year August",
    "V9I": "Technical changes, model year December",
    "V9J": "Technical changes, model year February",
    # Z (missing)
    "Z1A": "Cab paint, standard",
    "Z2A": "Cab paint, metallic",
    "Z2C": "Cab paint, special colour",
    "Z2D": "Cab paint, two-tone",
}

# ---------------------------------------------------------------------------
# Mandatory codes — must always be present; flagged red if found in mismatches
# ---------------------------------------------------------------------------
MANDATORY_CODES = {
    # (description, note, category)
    # All vehicle mandatory
    'D2Y': ('Seat belt monitor', '', 'all'),
    'E6Z': ('Reversing buzzer', '', 'all'),
    'J4X': ('Belt warning w/ seat occup. detection, co-driver', '', 'all'),
    'K7N': ('Exhaust system, outlet to left, under 30 degrees', 'Exhaust system', 'all'),
    'L0A': ('Illumination regulation, in acc. with UN-R 48.06', '', 'all'),
    'S1D': ('Stability Control Assist (ESP)', '', 'all'),
    'S1H': ('Lane Keeping Assist', '', 'all'),
    'S1W': ('Active Brake Assist 5', 'AEBS', 'all'),
    'S1P': ('Active Brake Assist', 'AEBS', 'all'),
    'S2D': ('Active Brake Assist 6', 'AEBS', 'all'),
    'S2N': ('Active Brake Assist 6 Plus', 'AEBS', 'all'),
    'S5A': ('Speed limiter, 90 km/h (56 mph), ECE', '', 'all'),
    'S8C': ('Hazard warning triangle', '', 'all'),
    'V8B': ('Chassis number FIN with model year', '', 'all'),
    'X4B': ('Instrument/labels/publications in Korean', '', 'all'),
    'Z5X': ('Left-hand drive', '', 'all'),
    # Tractor only (BM 963425, 964416, 963403, 964424)
    'D2J': ('Seat version, Korea', '', 'tractor'),
    # Rigid only (BM 964XXX)
    'C6H': ('Steering, Servotwin', 'From 4-axle construction truck (tipper)', 'rigid'),
    # Tipper only (BM 964230, 964214)
    'J9J': ('Pre-installation for reversing camera', 'Mandatory among reverse camera pre-install', 'tipper'),
    'J9P': ('Pre-installation and display for up to 4 cameras', 'Mandatory among reverse camera pre-install', 'tipper'),
    'E4W': ('Starting-off aid, speed limit 30 km/h', 'If there is a liftable axle', 'tipper'),
}

# Groups where only ONE code from the group needs to be present
MANDATORY_GROUPS = {
    'AEBS': {'S1W', 'S1P', 'S2D', 'S2N'},
}


def _mand_info(code: str):
    """Return (description, note, category) for a mandatory code."""
    val = MANDATORY_CODES.get(code)
    if val is None:
        return ('', '', 'all')
    if isinstance(val, tuple):
        desc = val[0] if len(val) > 0 else ''
        note = val[1] if len(val) > 1 else ''
        cat = val[2] if len(val) > 2 else 'all'
        return (desc, note, cat)
    # Legacy string format
    return (val, '', 'all')


def _lookup_code(code: str) -> str:
    """Return description for a code, stripping leading J for special codes."""
    code = code.strip()
    # Check if code was deleted from All Code List
    _removed = st.session_state.get('_allcode_removed', set())
    if code in _removed:
        return ""
    # Check custom descriptions first
    _custom = st.session_state.get('_allcode_custom_desc', {})
    if code in _custom:
        return _custom[code]
    if code in OPTION_CODE_MAP:
        return OPTION_CODE_MAP[code]
    # Try without leading J (e.g. JF3C -> F3C)
    if code.startswith("J") and len(code) > 1:
        stripped = code[1:]
        if stripped in _removed:
            return ""
        if stripped in _custom:
            return _custom[stripped] + " (J-variant)"
        if stripped in OPTION_CODE_MAP:
            return OPTION_CODE_MAP[stripped] + " (J-variant)"
    return ""


@st.dialog("Option Code Details", width="large")
def show_code_details(commission_no: str, sam_str: str, wings_str: str, except_str: str = "",
                      all_wings_str: str = "", all_sam_str: str = "", vehicle_row: dict = None):
    st.markdown("""<style>
    [data-testid="stDialog"] [data-testid="stMarkdownContainer"] { font-size: 17px; }
    [data-testid="stDialog"] h4 { font-size: 22px !important; }
    [data-testid="stDialog"] h5 { font-size: 20px !important; }
    [data-testid="stDialog"] .stTabs button p { font-size: 17px !important; }
    [data-testid="stDialog"] [data-testid="stDialogTitle"] { font-size: 28px !important; }
    </style>""", unsafe_allow_html=True)

    # ── Commission No. + vehicle info row ──
    hdr_col, dl_col = st.columns([5, 1])
    with hdr_col:
        st.markdown(f"<span style='font-size:19px'><b>Commission No.:</b>&nbsp; <code style='font-size:19px;color:#2a7ab5'>{commission_no}</code></span>", unsafe_allow_html=True)
    if vehicle_row:
        with dl_col:
            _row_df = pd.DataFrame([{k: v for k, v in vehicle_row.items() if not str(k).startswith('_')}])
            st.download_button(
                "📥 Excel",
                data=to_excel_bytes(_row_df),
                file_name=f"vehicle_{commission_no}.xlsx",
                key=f"dl_row_{commission_no}",
                use_container_width=True,
            )

    # Vehicle info block
    if vehicle_row:
        _vr = vehicle_row
        def _vget(key, *fallbacks):
            for k in (key, *fallbacks):
                v = str(_vr.get(k, "") or "").strip()
                if v and v not in ("nan", "NaT", "None"):
                    return v
            return "—"
        # Compute MY: production month >= 4 → next year's MY, else current year's MY
        _prod_date_str = _vget("Production date")
        try:
            _pd = pd.to_datetime(_prod_date_str, errors='coerce')
            _my = str((_pd.year - 2000 + 1) if _pd.month >= 4 else (_pd.year - 2000)) if _pd is not pd.NaT and not pd.isnull(_pd) else "—"
        except Exception:
            _my = "—"
        # Build SAM Model string: Vehicle + Current Model(SAM) + Type + Cab [+ PTO]
        _sam_parts = [_vget("Vehicle"), _vget("Current Model(SAM)"), _vget("Type"), _vget("Cab")]
        _pto_val = _vget("PTO", "Option")
        _sam_model = " ".join(p for p in _sam_parts if p and p != "—")
        _info_items = [
            ("MY",           _my),
            ("SAM Model",    _sam_model or "—"),
            ("Baumuster",    _vget("Baumuster")),
            ("PTO (O/X)",    _pto_val),
            ("Changeability",_vget("Changeability Date")),
        ]
        _cells = "".join(
            f"<div style='display:inline-block;margin:3px 6px 3px 0;padding:3px 10px;background:#f0f4fa;border-radius:5px;font-size:13px;'>"
            f"<span style='color:#888;font-weight:600'>{label}</span>&nbsp;"
            f"<span style='color:#1a2a4a;font-weight:700'>{val}</span></div>"
            for label, val in _info_items if val != "—"
        )
        st.markdown(f"<div style='margin:4px 0 8px 0'>{_cells}</div>", unsafe_allow_html=True)

    st.divider()

    _mand_set = st.session_state.get('_mand_codes_set', set(MANDATORY_CODES.keys()))
    _mand_desc = st.session_state.get('_mand_custom_desc', {})

    # Parse all codes for this vehicle (to check mandatory presence)
    all_wings = {c.strip() for c in str(all_wings_str).split(",") if c.strip() and c.strip() != "nan"}
    all_sam = {c.strip() for c in str(all_sam_str).split(",") if c.strip() and c.strip() != "nan"}

    def _render_code(code: str):
        """Render a code (non-mandatory only, mandatory codes are separated)."""
        raw = code.replace('🔴', '').strip()
        desc = _lookup_code(raw)
        return f"**`{raw}`** &nbsp; {desc}"

    # Filter out mandatory codes and Factory Control codes from SAM/WINGS only lists
    _PROD_PREFIXES = ('I', 'O', 'Z', 'U')
    _exc_set_global = st.session_state.get('_except_codes_set', set())
    def _is_factory_control(c):
        return c in _exc_set_global or (c and c[0] in _PROD_PREFIXES)

    sam_codes_raw = [c.strip() for c in str(sam_str).split(",") if c.strip() and c.strip() != "nan"]
    wings_codes_raw = [c.strip() for c in str(wings_str).split(",") if c.strip() and c.strip() != "nan"]
    sam_codes_clean = [c.replace('🔴', '').strip() for c in sam_codes_raw]
    wings_codes_clean = [c.replace('🔴', '').strip() for c in wings_codes_raw]
    sam_codes = [c for c in sam_codes_clean if c not in _mand_set and not _is_factory_control(c)]
    wings_codes = [c for c in wings_codes_clean if c not in _mand_set and not _is_factory_control(c)]
    except_codes_from_param = [c.strip() for c in str(except_str).split(",") if c.strip() and c.strip() != "nan"]
    # Merge: except_codes from param + any Factory Control codes found in SAM/WINGS only lists
    _fc_from_sam = [c for c in sam_codes_clean if _is_factory_control(c) and c not in _mand_set]
    _fc_from_wings = [c for c in wings_codes_clean if _is_factory_control(c) and c not in _mand_set]
    except_codes = sorted(set(except_codes_from_param + _fc_from_sam + _fc_from_wings))

    # ── Two-view tabs: Difference vs Full code list ──
    view_tab1, view_tab2 = st.tabs(["🔍 Difference Codes", "📋 Full Code List"])

    with view_tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Codes Only in SAM")
            if sam_codes:
                for code in sam_codes:
                    st.markdown(_render_code(code))
            else:
                st.info("None")
        with col2:
            st.markdown("#### Codes Only in WINGS")
            if wings_codes:
                for code in wings_codes:
                    st.markdown(_render_code(code))
            else:
                st.info("None")

        if except_codes:
            st.divider()
            st.markdown("#### Factory Control Codes (automatically created, just for reference)")
            _exc_in_sam = [c for c in except_codes if c in all_sam and c not in all_wings]
            _exc_in_wings = [c for c in except_codes if c in all_wings and c not in all_sam]
            _exc_in_both = [c for c in except_codes if c in all_sam and c in all_wings]
            ecol1, ecol2 = st.columns(2)
            with ecol1:
                st.markdown("**Only in SAM**")
                if _exc_in_sam:
                    for code in _exc_in_sam:
                        st.markdown(f"**`{code}`** &nbsp; {_lookup_code(code)}")
                else:
                    st.caption("None")
            with ecol2:
                st.markdown("**Only in WINGS**")
                if _exc_in_wings:
                    for code in _exc_in_wings:
                        st.markdown(f"**`{code}`** &nbsp; {_lookup_code(code)}")
                else:
                    st.caption("None")
            if _exc_in_both:
                st.markdown("**Matching**")
                _bc1, _bc2 = st.columns(2)
                for i, code in enumerate(_exc_in_both):
                    desc = _lookup_code(code)
                    if i % 2 == 0:
                        _bc1.markdown(f"**`{code}`** &nbsp; {desc}")
                    else:
                        _bc2.markdown(f"**`{code}`** &nbsp; {desc}")

    with view_tab2:
        _only_sam_set = set(sam_codes)
        _only_wings_set = set(wings_codes)
        _exc_set_view = set(except_codes)

        # Factory Control Code 판별: exception 목록 OR 첫 글자가 I/O/Z/U
        def _is_prod(c):
            return c in _exc_set_view or _is_factory_control(c)

        # except_codes를 SAM only / WINGS only로 분류
        _exc_only_sam = sorted(c for c in except_codes if c in all_sam and c not in all_wings)
        _exc_only_wings = sorted(c for c in except_codes if c in all_wings and c not in all_sam)

        # 모든 불일치/일치 코드를 하나로 합침 (Factory Control Code는 아래로)
        def _sort_prod_last(codes):
            normal = sorted(c for c in codes if not _is_prod(c))
            prod = sorted(c for c in codes if _is_prod(c))
            return normal + prod
        _all_only_sam = _sort_prod_last(set(list(_only_sam_set) + _exc_only_sam))
        _all_only_wings = _sort_prod_last(set(list(_only_wings_set) + _exc_only_wings))
        _all_common = _sort_prod_last(c for c in (all_sam & all_wings) if c not in _mand_set)

        _section_css = '''<style>
            .code-section { padding: 10px 14px; border-radius: 8px; margin-bottom: 8px; }
            .code-section.mismatch { background: #fef2f2; border-left: 4px solid #e74c3c; }
            .code-section.match { background: #f0fdf4; border-left: 4px solid #22c55e; }
            .code-section h5 { margin: 0 0 8px 0; font-size: 20px; }
            .code-row { display: flex; gap: 10px; padding: 3px 0; font-size: 16px; }
            .code-row .code-left, .code-row .code-right { flex: 1; }
            .code-tag { font-weight: bold; font-family: monospace; padding: 2px 6px; border-radius: 3px; font-size: 17px; }
            .code-tag.red { color: #e74c3c; background: #fde8e8; }
            .code-tag.green { color: #16a34a; background: #dcfce7; }
            .code-desc { color: #555; font-size: 15px; }
            .badge { font-size: 11px; padding: 2px 6px; border-radius: 3px; font-weight: bold; vertical-align: middle; margin-left: 5px; }
            .badge.mandatory { color: #fff; background: #e74c3c; }
            .badge.production { color: #fff; background: #f59e0b; }
        </style>'''
        st.markdown(_section_css, unsafe_allow_html=True)

        def _badge(code):
            """코드 뒤에 Mandatory / Factory Control 뱃지 추가"""
            if code in _mand_set:
                return '<span class="badge mandatory">Mandatory</span>'
            if _is_prod(code):
                return '<span class="badge production">Factory Control</span>'
            return ''

        # ── 섹션 1: 불일치 코드 (빨간색, 가장 중요) ──
        if _all_only_sam or _all_only_wings:
            _mis_html = '<div class="code-section mismatch">'
            _mis_count = len(_all_only_sam) + len(_all_only_wings)
            _mis_html += f'<h5>❌ Mismatch Codes ({_mis_count})</h5>'
            _mis_html += '<div class="code-row"><div class="code-left"><b>Only in SAM</b></div><div class="code-right"><b>Only in WINGS</b></div></div>'
            _max_mis = max(len(_all_only_sam), len(_all_only_wings))
            for i in range(_max_mis):
                _left = ''
                _right = ''
                if i < len(_all_only_sam):
                    c = _all_only_sam[i]
                    _left = f'<span class="code-tag red">{c}</span>{_badge(c)} <span class="code-desc">{_lookup_code(c)}</span>'
                if i < len(_all_only_wings):
                    c = _all_only_wings[i]
                    _right = f'<span class="code-tag red">{c}</span>{_badge(c)} <span class="code-desc">{_lookup_code(c)}</span>'
                _mis_html += f'<div class="code-row"><div class="code-left">{_left}</div><div class="code-right">{_right}</div></div>'
            _mis_html += '</div>'
            st.markdown(_mis_html, unsafe_allow_html=True)

        # ── 섹션 2: 일치 코드 (초록색, 평행 표시) ──
        if _all_common:
            _match_html = '<div class="code-section match">'
            _match_html += f'<h5>✅ Matching Codes ({len(_all_common)})</h5>'
            _match_html += '<div class="code-row"><div class="code-left"><b>SAM</b></div><div class="code-right"><b>WINGS</b></div></div>'
            for c in _all_common:
                desc = _lookup_code(c)
                b = _badge(c)
                _match_html += f'<div class="code-row"><div class="code-left"><span class="code-tag green">{c}</span>{b} <span class="code-desc">{desc}</span></div><div class="code-right"><span class="code-tag green">{c}</span>{b} <span class="code-desc">{desc}</span></div></div>'
            _match_html += '</div>'
            st.markdown(_match_html, unsafe_allow_html=True)

        if not (all_sam or all_wings):
            st.info("No codes to display.")

    # ── Mandatory Codes section ───────────────────────────────────────────────
    st.divider()
    st.markdown("#### Mandatory Codes")
    st.warning("⚠️ **Demo ver.** — Mandatory Codes list is under review and subject to change. Please verify before final use.")
    st.caption("These codes must be present in both SAM and WINGS. Status shows presence in this vehicle's option codes.")

    # Build a set of group codes that are satisfied by another code in the same group
    _group_satisfied = set()  # codes in a group where another member is present
    _group_active = {}        # code -> which code in the group is actually present
    for grp_name, grp_codes in MANDATORY_GROUPS.items():
        present_in_vehicle = [c for c in grp_codes if c in all_wings or c in all_sam]
        if present_in_vehicle:
            for c in grp_codes:
                if c not in present_in_vehicle:
                    _group_satisfied.add(c)
                    _group_active[c] = present_in_vehicle[0]

    def _mand_badge(code):
        # If this code is in a group and another member is present → N/A
        if code in _group_satisfied:
            active = _group_active.get(code, '?')
            return f":gray[— N/A ({active} applied)]"
        in_w = code in all_wings
        in_s = code in all_sam
        if in_w and in_s:
            return ":green[✅ Both]"
        elif in_w:
            return ":orange[⚠️ WINGS only]"
        elif in_s:
            return ":orange[⚠️ SAM only]"
        return ":red[❌ Missing]"

    def _render_mand_line(code):
        desc, note, _ = _mand_info(code)
        # Custom description overrides
        custom = _mand_desc.get(code)
        if custom:
            desc = custom
        badge = _mand_badge(code)
        line = f"**`{code}`** &nbsp; {desc} &nbsp; {badge}"
        if note:
            line += f"  \n&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;*{note}*"
        return line

    sorted_mand = sorted(_mand_set)
    # Categorize
    _cat_all = [c for c in sorted_mand if _mand_info(c)[2] == 'all']
    _cat_tractor = [c for c in sorted_mand if _mand_info(c)[2] == 'tractor']
    _cat_rigid = [c for c in sorted_mand if _mand_info(c)[2] == 'rigid']
    _cat_tipper = [c for c in sorted_mand if _mand_info(c)[2] == 'tipper']
    _cat_other = [c for c in sorted_mand if c not in set(_cat_all + _cat_tractor + _cat_rigid + _cat_tipper)]

    def _render_category(label, codes):
        if not codes:
            return
        st.markdown(f"**{label}**")
        mc1, mc2 = st.columns(2)
        for i, code in enumerate(codes):
            if i % 2 == 0:
                mc1.markdown(_render_mand_line(code))
            else:
                mc2.markdown(_render_mand_line(code))

    _render_category("All Vehicle Mandatory", _cat_all)
    _render_category("Tractor Only (BM 963425, 964416, 963403, 964424)", _cat_tractor)
    _render_category("Rigid Only (BM 964XXX)", _cat_rigid)
    _render_category("Tipper Only (BM 964230, 964214)", _cat_tipper)
    _render_category("Other (Custom)", _cat_other)

    # ── Export (Excel) button ──────────────────────────────────────────────────
    st.divider()
    rows = []
    for code in sam_codes:
        rows.append({"Section": "Only in SAM", "Code": code, "Description": _lookup_code(code)})
    for code in wings_codes:
        rows.append({"Section": "Only in WINGS", "Code": code, "Description": _lookup_code(code)})
    for code in except_codes:
        rows.append({"Section": "Factory Control Codes (ref)", "Code": code, "Description": _lookup_code(code)})
    for code in sorted_mand:
        desc, note, cat = _mand_info(code)
        custom = _mand_desc.get(code)
        if custom:
            desc = custom
        if code in _group_satisfied:
            active = _group_active.get(code, '?')
            status = f"N/A ({active} applied)"
        else:
            in_w = code in all_wings
            in_s = code in all_sam
            status = "Both" if (in_w and in_s) else ("WINGS only" if in_w else ("SAM only" if in_s else "Missing"))
        rows.append({"Section": "Mandatory Codes", "Code": code, "Description": desc, "Note": note, "Category": cat, "Status": status})
    df_export = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name=f"{commission_no}")
        ws = writer.sheets[f"{commission_no}"]
        for col_cells in ws.columns:
            max_len = 0
            col_letter = col_cells[0].column_letter
            for cell in col_cells:
                val = str(cell.value) if cell.value is not None else ''
                max_len = max(max_len, len(val))
            ws.column_dimensions[col_letter].width = min(max_len + 2, 60)
    buf.seek(0)
    _, btn_col = st.columns([4, 1])
    with btn_col:
        st.download_button(
            label="Export (Excel)",
            data=buf,
            file_name=f"{commission_no}_detail.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"export_{commission_no}",
        )


@st.dialog("SAM File Code Verification", width="large")
def show_sam_file_codes():
    fpath = st.session_state.get('_sam_view_file', '')
    if not fpath:
        st.warning('No file selected.')
        return
    fp = Path(fpath)
    st.markdown(f"**File:** {fp.name}")
    st.markdown("---")
    # Parse the file
    _mapping = {}
    try:
        with open(fp, 'rb') as f:
            _parse_single_sam_file(f, fp.name, _mapping)
    except Exception as e:
        st.error(f'Parse error: {e}')
        return
    if not _mapping:
        st.warning('No codes extracted from this file.')
        return
    _mand_set = st.session_state.get('_mand_codes_set', set(MANDATORY_CODES.keys()))
    _exc_set = st.session_state.get('_except_codes_set', set())

    def _render_code_section(title, code_list, color):
        if not code_list:
            return
        st.markdown(f"**{title}** ({len(code_list)})")
        cols = st.columns(4)
        for i, code in enumerate(sorted(code_list)):
            desc = OPTION_CODE_MAP.get(code, '')
            cols[i % 4].markdown(
                f"<span style='color:{color};font-weight:600;font-size:17px'>{code}</span>"
                f"&nbsp; <span style='font-size:15px'>{desc}</span>",
                unsafe_allow_html=True
            )

    for model_key, pto_dict in _mapping.items():
        for is_pto, data in pto_dict.items():
            codes = sorted(data['codes'])
            pto_label = 'PTO' if is_pto else 'non-PTO'
            st.markdown(f"**Model:** `{model_key}` ({pto_label}) — **{len(codes)} codes total**")
            st.markdown("---")

            mand_codes = [c for c in codes if c in _mand_set]
            prod_codes = [c for c in codes if c in _exc_set]
            other_codes = [c for c in codes if c not in _mand_set and c not in _exc_set]

            _render_code_section("🔴 Mandatory Codes", mand_codes, "#c0392b")
            if mand_codes:
                st.markdown("---")
            _render_code_section("🔧 Factory Control Codes", prod_codes, "#e67e22")
            if prod_codes:
                st.markdown("---")
            _render_code_section("📋 Other Codes", other_codes, "#1a5276")


@st.dialog("Factory Control Codes List", width="large")
def show_exception_codes():
    st.markdown("""<style>
    [data-testid="stDialog"] button[kind="secondary"] {
        padding: 2px 8px; font-size: 12px; min-height: 0; line-height: 1.2;
    }
    </style>""", unsafe_allow_html=True)
    _exc_set = st.session_state.get('_except_codes_set', set())
    _exc_custom = st.session_state.get('_except_custom_desc', {})
    _all = sorted(
        [(code, _exc_custom.get(code, OPTION_CODE_MAP.get(code, ''))) for code in _exc_set],
        key=lambda x: x[0],
    )

    # Add code section
    st.markdown(f"**Total: {len(_all)} codes**")
    _ac1, _ac2, _ac3 = st.columns([2, 3, 1])
    with _ac1:
        _new_code = st.text_input('Code', key='_exc_dlg_new_code', placeholder='e.g. A1B', label_visibility='collapsed')
    with _ac2:
        _new_desc = st.text_input('Description', key='_exc_dlg_new_desc', placeholder='Description', label_visibility='collapsed')
    with _ac3:
        if st.button('+ Add', key='_exc_dlg_add_btn', type='primary', use_container_width=True):
            _nc = _new_code.strip().upper()
            if _nc:
                st.session_state['_except_codes_set'].add(_nc)
                if _new_desc.strip():
                    st.session_state['_except_custom_desc'][_nc] = _new_desc.strip()
                _auto_save()
                st.rerun()

    # Search
    _q = st.text_input('Search codes...', key='_exc_dialog_search', placeholder='Type code or description...')
    if _q and _q.strip():
        _qu = _q.strip().upper()
        _all = [(c, d) for c, d in _all if _qu in c.upper() or _qu in d.upper()]
        st.caption(f'{len(_all)} results')
    st.divider()

    # Edit form at the top if editing
    _editing_exc = st.session_state.get('_exc_editing', None)
    if _editing_exc:
        _edit_desc_orig = _exc_custom.get(_editing_exc, OPTION_CODE_MAP.get(_editing_exc, ''))
        st.markdown(f'**✏️ Editing: {_editing_exc}**')
        _ec1, _ec2, _ec3, _ec4 = st.columns([2, 4, 1, 1])
        with _ec1:
            _edit_new_code = st.text_input('Code', value=_editing_exc, key='_exc_edit_code')
        with _ec2:
            _edit_new_desc = st.text_input('Description', value=_edit_desc_orig, key='_exc_edit_desc')
        with _ec3:
            if st.button('✓ Save', key='_exc_edit_save', type='primary', use_container_width=True):
                _nc = _edit_new_code.strip().upper()
                _nd = _edit_new_desc.strip()
                if _nc:
                    if _nc != _editing_exc:
                        st.session_state['_except_codes_set'].discard(_editing_exc)
                        st.session_state['_except_custom_desc'].pop(_editing_exc, None)
                        st.session_state['_except_codes_set'].add(_nc)
                    if _nd:
                        st.session_state['_except_custom_desc'][_nc] = _nd
                _auto_save()
                st.session_state['_exc_editing'] = None
        with _ec4:
            if st.button('Cancel', key='_exc_edit_cancel', use_container_width=True):
                st.session_state['_exc_editing'] = None
        st.divider()

    # Scrollable code list
    _scroll = st.container(height=450)
    with _scroll:
        for i in range(0, len(_all), 3):
            cols = st.columns(3)
            for j, col in enumerate(cols):
                if i + j < len(_all):
                    code, desc = _all[i + j]
                    with col:
                        _cc1, _cc2, _cc3 = st.columns([8, 1, 1])
                        _cc1.markdown(f'<span style="font-size:17px"><b style="color:#2a7ab5">{code}</b>&nbsp; {desc}</span>', unsafe_allow_html=True)
                        if _cc2.button('✎', key=f'_exc_dlg_edit_{code}'):
                            st.session_state['_exc_editing'] = code
                        if _cc3.button('×', key=f'_exc_dlg_del_{code}'):
                            st.session_state['_except_codes_set'].discard(code)
                            st.session_state['_except_custom_desc'].pop(code, None)
                            _auto_save()
                            st.rerun()


@st.dialog("All Code List", width="large")
def show_all_codes():
    st.markdown("""<style>
    [data-testid="stDialog"] button[kind="secondary"] {
        padding: 2px 8px; font-size: 12px; min-height: 0; line-height: 1.2;
    }
    </style>""", unsafe_allow_html=True)

    # Initialize undo stack (cleared when dialog closes/reopens)
    if '_allcode_undo' not in st.session_state:
        st.session_state['_allcode_undo'] = []

    _all_map = dict(OPTION_CODE_MAP)
    # Merge custom descriptions from session state
    _custom = st.session_state.get('_allcode_custom_desc', {})
    _all_map.update(_custom)
    # Merge custom codes added at runtime
    _added = st.session_state.get('_allcode_added', set())
    # Removed codes
    _removed = st.session_state.get('_allcode_removed', set())
    _visible_map = {k: v for k, v in _all_map.items() if k not in _removed}
    for c in _added:
        if c not in _removed:
            _visible_map.setdefault(c, _custom.get(c, ''))

    _all = sorted(_visible_map.items(), key=lambda x: x[0])

    st.markdown(f"**Total: {len(_all)} codes**")

    # Add code section
    _ac1, _ac2, _ac3 = st.columns([2, 3, 1])
    with _ac1:
        _new_code = st.text_input('Code', key='_allcode_dlg_new_code', placeholder='e.g. A1B', label_visibility='collapsed')
    with _ac2:
        _new_desc = st.text_input('Description', key='_allcode_dlg_new_desc', placeholder='Description', label_visibility='collapsed')
    with _ac3:
        if st.button('+ Add', key='_allcode_dlg_add_btn', type='primary', use_container_width=True):
            _nc = _new_code.strip().upper()
            if _nc:
                if '_allcode_added' not in st.session_state:
                    st.session_state['_allcode_added'] = set()
                if '_allcode_custom_desc' not in st.session_state:
                    st.session_state['_allcode_custom_desc'] = {}
                st.session_state['_allcode_added'].add(_nc)
                st.session_state['_allcode_removed'].discard(_nc)
                if _new_desc.strip():
                    st.session_state['_allcode_custom_desc'][_nc] = _new_desc.strip()
                _auto_save()
                st.rerun()

    # Undo bar
    _undo_stack = st.session_state.get('_allcode_undo', [])
    if _undo_stack:
        _last = _undo_stack[-1]
        _undo_col1, _undo_col2 = st.columns([6, 1])
        _undo_col1.caption(f"Deleted: **{_last[0]}** — {_last[1]}")
        if _undo_col2.button('↩ Undo', key='_allcode_undo_btn'):
            code_restore, _desc, _was_mand, _was_exc = _undo_stack.pop()
            st.session_state['_allcode_removed'].discard(code_restore)
            # Restore to Mandatory / Factory Control if it was there
            if _was_mand:
                st.session_state.get('_mand_codes_set', set()).add(code_restore)
            if _was_exc:
                st.session_state.get('_except_codes_set', set()).add(code_restore)
            _auto_save()
            st.rerun()

    # Search
    _q = st.text_input('Search codes...', key='_allcode_dlg_search', placeholder='Type code or description...')
    if _q and _q.strip():
        _qu = _q.strip().upper()
        _all = [(c, d) for c, d in _all if _qu in c.upper() or _qu in d.upper()]
        st.caption(f'{len(_all)} results')
    st.divider()

    # Scrollable code list
    _editing = st.session_state.get('_allcode_editing', None)  # code currently being edited
    _scroll = st.container(height=450)
    with _scroll:
        # If editing, show edit form at the top
        if _editing:
            _edit_code_orig = _editing
            _edit_desc_orig = dict(OPTION_CODE_MAP)
            _edit_desc_orig.update(st.session_state.get('_allcode_custom_desc', {}))
            _edit_cur_desc = _edit_desc_orig.get(_edit_code_orig, '')
            st.markdown(f'**✏️ Editing: {_edit_code_orig}**')
            _ec1, _ec2, _ec3, _ec4 = st.columns([2, 4, 1, 1])
            with _ec1:
                _edit_new_code = st.text_input('Code', value=_edit_code_orig, key='_allcode_edit_code')
            with _ec2:
                _edit_new_desc = st.text_input('Description', value=_edit_cur_desc, key='_allcode_edit_desc')
            with _ec3:
                if st.button('✓ Save', key='_allcode_edit_save', type='primary', use_container_width=True):
                    _nc = _edit_new_code.strip().upper()
                    _nd = _edit_new_desc.strip()
                    if _nc:
                        _custom_desc = st.session_state.get('_allcode_custom_desc', {})
                        _added_set = st.session_state.get('_allcode_added', set())
                        if _nc != _edit_code_orig:
                            # Code name changed: remove old, add new
                            st.session_state['_allcode_removed'].add(_edit_code_orig)
                            _added_set.add(_nc)
                            st.session_state['_allcode_removed'].discard(_nc)
                            st.session_state['_allcode_added'] = _added_set
                            # Move in mandatory/factory control sets
                            _ms = st.session_state.get('_mand_codes_set', set())
                            if _edit_code_orig in _ms:
                                _ms.discard(_edit_code_orig)
                                _ms.add(_nc)
                            _es = st.session_state.get('_except_codes_set', set())
                            if _edit_code_orig in _es:
                                _es.discard(_edit_code_orig)
                                _es.add(_nc)
                        # Update description
                        _custom_desc[_nc] = _nd
                        st.session_state['_allcode_custom_desc'] = _custom_desc
                    _auto_save()
                    st.session_state['_allcode_editing'] = None
            with _ec4:
                if st.button('Cancel', key='_allcode_edit_cancel', use_container_width=True):
                    st.session_state['_allcode_editing'] = None
            st.divider()

        for i in range(0, len(_all), 3):
            cols = st.columns(3)
            for j, col in enumerate(cols):
                if i + j < len(_all):
                    code, desc = _all[i + j]
                    with col:
                        _cc1, _cc2, _cc3 = st.columns([8, 1, 1])
                        _cc1.markdown(f'<span style="font-size:17px"><b style="color:#2a7ab5">{code}</b>&nbsp; {desc}</span>', unsafe_allow_html=True)
                        if _cc2.button('✎', key=f'_allcode_dlg_edit_{code}'):
                            st.session_state['_allcode_editing'] = code
                        if _cc3.button('×', key=f'_allcode_dlg_del_{code}'):
                            # Track which lists had this code for undo
                            _was_in_mand = code in st.session_state.get('_mand_codes_set', set())
                            _was_in_exc = code in st.session_state.get('_except_codes_set', set())
                            # Remove from all lists
                            st.session_state['_allcode_removed'].add(code)
                            st.session_state.get('_mand_codes_set', set()).discard(code)
                            st.session_state.get('_except_codes_set', set()).discard(code)
                            # Save undo info
                            if '_allcode_undo' not in st.session_state:
                                st.session_state['_allcode_undo'] = []
                            st.session_state['_allcode_undo'].append((code, desc, _was_in_mand, _was_in_exc))
                            _auto_save()
                            st.rerun()


@st.dialog("Mandatory Codes List", width="large")
def show_mandatory_codes():
    st.markdown("""<style>
    [data-testid="stDialog"] button[kind="secondary"] {
        padding: 2px 8px; font-size: 12px; min-height: 0; line-height: 1.2;
    }
    </style>""", unsafe_allow_html=True)
    _mand_set = st.session_state.get('_mand_codes_set', set(MANDATORY_CODES.keys()))
    _mand_custom = st.session_state.get('_mand_custom_desc', {})
    _all = []
    for code in sorted(_mand_set):
        custom = _mand_custom.get(code)
        if custom:
            desc_display = custom
        else:
            desc, note, _ = _mand_info(code)
            desc_display = f"{desc} ({note})" if note else desc
        _all.append((code, desc_display))

    st.markdown(f"**Total: {len(_all)} codes**")
    st.markdown('<span style="color:red; font-size:15px;">These are codes that still need modification. For reference only.</span>', unsafe_allow_html=True)

    # Add code section
    _ac1, _ac2, _ac3 = st.columns([2, 3, 1])
    with _ac1:
        _new_code = st.text_input('Code', key='_mand_dlg_new_code', placeholder='e.g. A1B', label_visibility='collapsed')
    with _ac2:
        _new_desc = st.text_input('Description', key='_mand_dlg_new_desc', placeholder='Description', label_visibility='collapsed')
    with _ac3:
        if st.button('+ Add', key='_mand_dlg_add_btn', type='primary', use_container_width=True):
            _nc = _new_code.strip().upper()
            if _nc:
                st.session_state['_mand_codes_set'].add(_nc)
                if _new_desc.strip():
                    st.session_state['_mand_custom_desc'][_nc] = _new_desc.strip()
                _auto_save()
                st.rerun()

    # Search
    _q = st.text_input('Search codes...', key='_mand_dialog_search', placeholder='Type code or description...')
    if _q and _q.strip():
        _qu = _q.strip().upper()
        _all = [(c, d) for c, d in _all if _qu in c.upper() or _qu in d.upper()]
        st.caption(f'{len(_all)} results')
    st.divider()

    # Edit form at the top if editing
    _editing_mand = st.session_state.get('_mand_editing', None)
    if _editing_mand:
        _edit_desc_orig = _mand_custom.get(_editing_mand, '')
        if not _edit_desc_orig:
            _d, _n, _ = _mand_info(_editing_mand)
            _edit_desc_orig = f"{_d} ({_n})" if _n else _d
        st.markdown(f'**✏️ Editing: {_editing_mand}**')
        _ec1, _ec2, _ec3, _ec4 = st.columns([2, 4, 1, 1])
        with _ec1:
            _edit_new_code = st.text_input('Code', value=_editing_mand, key='_mand_edit_code')
        with _ec2:
            _edit_new_desc = st.text_input('Description', value=_edit_desc_orig, key='_mand_edit_desc')
        with _ec3:
            if st.button('✓ Save', key='_mand_edit_save', type='primary', use_container_width=True):
                _nc = _edit_new_code.strip().upper()
                _nd = _edit_new_desc.strip()
                if _nc:
                    if _nc != _editing_mand:
                        st.session_state['_mand_codes_set'].discard(_editing_mand)
                        st.session_state['_mand_custom_desc'].pop(_editing_mand, None)
                        st.session_state['_mand_codes_set'].add(_nc)
                    if _nd:
                        st.session_state['_mand_custom_desc'][_nc] = _nd
                _auto_save()
                st.session_state['_mand_editing'] = None
        with _ec4:
            if st.button('Cancel', key='_mand_edit_cancel', use_container_width=True):
                st.session_state['_mand_editing'] = None
        st.divider()

    # Helper to render a code row with edit and delete buttons
    def _render_mand_row(code, desc):
        _cc1, _cc2, _cc3 = st.columns([8, 1, 1])
        _cc1.markdown(f'<span style="font-size:17px"><b style="color:#2a7ab5">{code}</b>&nbsp; {desc}</span>', unsafe_allow_html=True)
        if _cc2.button('✎', key=f'_mand_dlg_edit_{code}'):
            st.session_state['_mand_editing'] = code
        if _cc3.button('×', key=f'_mand_dlg_del_{code}'):
            st.session_state['_mand_codes_set'].discard(code)
            st.session_state['_mand_custom_desc'].pop(code, None)
            _auto_save()
            st.rerun()

    # Categorize codes using _mand_info category
    _all_vehicle = [(c, d) for c, d in _all if _mand_info(c)[2] == 'all']
    _tractor = [(c, d) for c, d in _all if _mand_info(c)[2] == 'tractor']
    _rigid = [(c, d) for c, d in _all if _mand_info(c)[2] == 'rigid']
    _tipper = [(c, d) for c, d in _all if _mand_info(c)[2] == 'tipper']
    # Codes that don't fit any category (user-added)
    _categorized = {c for c, _ in _all_vehicle + _tractor + _rigid + _tipper}
    _other = [(c, d) for c, d in _all if c not in _categorized]

    _scroll = st.container(height=450)
    with _scroll:
        if _all_vehicle:
            st.markdown("**All Vehicle Mandatory**")
            for i in range(0, len(_all_vehicle), 3):
                cols = st.columns(3)
                for j, col in enumerate(cols):
                    if i + j < len(_all_vehicle):
                        with col:
                            _render_mand_row(*_all_vehicle[i + j])

        if _tractor:
            st.markdown("**Tractor Only (BM 963425, 964416, 963403, 964424)**")
            for i in range(0, len(_tractor), 3):
                cols = st.columns(3)
                for j, col in enumerate(cols):
                    if i + j < len(_tractor):
                        with col:
                            _render_mand_row(*_tractor[i + j])

        if _rigid:
            st.markdown("**Rigid Only (BM 964XXX)**")
            for i in range(0, len(_rigid), 3):
                cols = st.columns(3)
                for j, col in enumerate(cols):
                    if i + j < len(_rigid):
                        with col:
                            _render_mand_row(*_rigid[i + j])

        if _tipper:
            st.markdown("**Tipper Only (BM 964230, 964214)**")
            for i in range(0, len(_tipper), 3):
                cols = st.columns(3)
                for j, col in enumerate(cols):
                    if i + j < len(_tipper):
                        with col:
                            _render_mand_row(*_tipper[i + j])

        if _other:
            st.markdown("**Other (Custom)**")
            for i in range(0, len(_other), 3):
                cols = st.columns(3)
                for j, col in enumerate(cols):
                    if i + j < len(_other):
                        with col:
                            _render_mand_row(*_other[i + j])


def parse_wings(file) -> pd.DataFrame:
    # supports uploaded CSV or Excel bytes
    try:
        df = pd.read_csv(file, encoding='utf-8')
    except Exception:
        file.seek(0)
        df = pd.read_excel(file)

    # normalize column names
    cols = {c: c.strip() for c in df.columns}
    df.rename(columns=cols, inplace=True)

    # expected columns in sample: 'Commission no.' and code columns
    if 'Commission no.' not in df.columns:
        st.error('Cannot find `Commission no.` column in the CSV/Excel file.')
        return pd.DataFrame()

    # Find model name column: prefer 'Type (brief)', fallback to 'Type', or 'Baumuster'
    model_col = None
    for col_name in df.columns:
        if 'type' in col_name.lower() and 'brief' in col_name.lower():
            model_col = col_name
            break
    if not model_col:
        for col_name in df.columns:
            if col_name.lower() == 'type':
                model_col = col_name
                break
    if not model_col:
        model_col = 'Baumuster' if 'Baumuster' in df.columns else None

    if model_col is None:
        st.warning('Model name column not found. Using Baumuster column as model name.')
        model_col = df.columns[1] if len(df.columns) > 1 else 'Commission no.'

    # Prefer explicit option code columns from WINGS export (case-insensitive)
    wings_opt_col1 = None
    wings_opt_col2 = None

    for col_name in df.columns:
        col_lower = col_name.lower()
        if 'standard' in col_lower and 'equipment' in col_lower:
            wings_opt_col1 = col_name
        elif 'additional' in col_lower and 'equipment' in col_lower:
            wings_opt_col2 = col_name

    # If neither column found by name, try positional approach
    if not wings_opt_col1 and not wings_opt_col2:
        try:
            if df.shape[1] >= 11:
                wings_opt_col1 = df.columns[8]
                wings_opt_col2 = df.columns[10]
        except Exception:
            pass

    # Fallback: search by keyword for any still-missing column
    if not wings_opt_col1 or not wings_opt_col2:
        for name in df.columns:
            low = name.lower()
            if 'equipment' in low or 'offer code' in low or 'enumeration' in low:
                if wings_opt_col1 is None:
                    wings_opt_col1 = name
                elif wings_opt_col2 is None and name != wings_opt_col1:
                    wings_opt_col2 = name
                    break

    def extract_codes(text):
        if pd.isna(text):
            return set()
        text = str(text)
        # Remove 'nan' strings produced by pandas NaN-to-string conversion
        text = re.sub(r'\bnan\b', '', text, flags=re.IGNORECASE)
        raw_tokens = re.findall(r"[A-Z0-9]{3,4}", text.upper())
        return set(raw_tokens)

    # Extract codes from specified columns
    code_cols_to_use = []
    if wings_opt_col1:
        code_cols_to_use.append(wings_opt_col1)
    if wings_opt_col2:
        code_cols_to_use.append(wings_opt_col2)
    
    if code_cols_to_use:
        # Extract each column individually to avoid issues with duplicate column names
        # (duplicate names in Excel make df[col] return a DataFrame, not a Series)
        text_parts = []
        for col in dict.fromkeys(code_cols_to_use):  # deduplicate while preserving order
            col_data = df[col]
            if isinstance(col_data, pd.DataFrame):
                col_data = col_data.iloc[:, 0]  # take first if duplicate columns exist
            text_parts.append(col_data.astype(str))
        combined = text_parts[0]
        for part in text_parts[1:]:
            combined = combined + ' ' + part
        df['WINGS_codes'] = combined.apply(extract_codes)
        # Flag rows where the raw equipment text itself contains "PTO" —
        # catches codes whose descriptions are written in the WINGS export but
        # are not yet in OPTION_CODE_MAP (e.g. 2853 LS PTO variants).
        df['WINGS_has_pto'] = combined.str.contains(r'\bPTO\b', case=False, na=False)
    else:
        # Final fallback
        df['WINGS_codes'] = df.astype(str).agg(' '.join, axis=1).apply(extract_codes)
        _all_text = df.astype(str).agg(' '.join, axis=1)
        df['WINGS_has_pto'] = _all_text.str.contains(r'\bPTO\b', case=False, na=False)
    
    # Return with both Model name and Baumuster number, plus additional columns
    result_cols = ['Commission no.', model_col, 'WINGS_codes', 'WINGS_has_pto']
    if 'Baumuster' in df.columns and model_col != 'Baumuster':
        result_cols.insert(2, 'Baumuster')
    
    # Add additional WINGS columns if they exist
    additional_cols = [
        'Order status financial', 'Order status logistical',
        'Additional equipment (enumeration)', 'FIN', 'Subcategory (ID)',
        'Vehicle alterable until', 'Requested delivery date'
    ]
    for col in additional_cols:
        if col in df.columns:
            result_cols.append(col)
    
    result = df[result_cols].copy()
    result.rename(columns={model_col: 'Model'}, inplace=True)
    return result


def _normalize_model(model: str) -> str:
    """Normalize model name: remove spaces/DNA, apply historic mappings, convert 28xx->26xx"""
    if not isinstance(model, str):
        return ''
    # Remove axle patterns (e.g. 8x4, 6x2), DNA suffix, then non-alphanumeric
    tmp = re.sub(r'\d[Xx]\d', '', model)  # remove axle info like 8x4, 6x2
    cleaned = re.sub(r'[^A-Z0-9]', '', tmp.upper().replace('DNA', '').strip())
    
    # Apply historic mappings (4153->3253, etc)
    historic = {
        '3253': '4153',
        '4140': '4440',
        '2643': '3343',
        '2851': '2651',
        '2135': '1835',
        '2863': '2663',
        '2853': '2653',
    }
    for old, new in historic.items():
        if cleaned.startswith(old):
            cleaned = new + cleaned[len(old):]
            break
    
    # Convert 28xx -> 26xx pattern
    if cleaned.startswith('28'):
        cleaned = '26' + cleaned[2:]
    
    return cleaned


def _extract_variant_tokens(text: str, codes: set) -> set:
    tokens = set()
    if not text:
        text = ''
    t = text.upper()
    # detect S-pattern like S5F
    for m in re.findall(r"\bS\d[A-Z0-9]?\b", t):
        tokens.add(m)
    # detect axle patterns like 8x4, 6x4
    for m in re.findall(r"\b\dX\d\b", t):
        tokens.add(m)
    # also check codes set
    for c in codes:
        uc = c.upper()
        if re.match(r"^S\d[A-Z0-9]?$", uc) or re.match(r"^\dX\d$", uc):
            tokens.add(uc)
    return tokens


def _parse_single_sam_file(file_obj, name: str, mapping: dict, log_fn=None):
    """Parse one SAM file (file-like object) and update mapping in place."""
    model_raw = None
    codes = set()
    full_text = ''

    try:
        if name.lower().endswith('.docx'):
            with zipfile.ZipFile(file_obj) as z:
                xml_content = z.read('word/document.xml')
            root = ET.fromstring(xml_content)

            W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

            full_text = "".join(
                t.text for t in root.iter(f'{W}t') if t.text
            )

            # Parse equipment codes from the equipment table cell-by-cell.
            # This avoids capturing text outside the boxes (footers, descriptions, etc.)
            # Prefer the Equipment overview table (compact box format) over detailed list tables.
            codes = set()
            eq_overview_table = None
            fallback_table = None
            for table in root.iter(f'{W}tbl'):
                tbl_text = "".join(t.text or '' for t in table.iter(f'{W}t'))
                if 'Equipment overview' in tbl_text and eq_overview_table is None:
                    eq_overview_table = table
                if 'Standard equipment' in tbl_text and fallback_table is None:
                    fallback_table = table
            target_table = eq_overview_table or fallback_table

            if target_table is not None:
                section = None
                for para in target_table.iter(f'{W}p'):
                    para_text = "".join(t.text or '' for t in para.iter(f'{W}t')).strip()
                    para_upper = para_text.upper()
                    # Detect section headers (short label paragraphs)
                    if para_upper in ('STANDARD EQUIPMENT', 'SPECIAL EQUIPMENT',
                                      'ADDITIONAL EQUIPMENT', 'EQUIPMENT OVERVIEW'):
                        section = para_upper
                        continue
                    if not para_text or section is None:
                        continue
                    if section in ('STANDARD EQUIPMENT', 'SPECIAL EQUIPMENT'):
                        # Use word boundaries to capture 3-4 char codes (semicolon not required)
                        codes |= set(re.findall(r'\b([A-Z][A-Z0-9]{2,3})\b', para_upper))
                    elif section == 'ADDITIONAL EQUIPMENT':
                        # Each paragraph: first token = code, rest = description
                        m = re.match(r'^([A-Z][A-Z0-9]{2,3})\b', para_upper)
                        if m:
                            codes.add(m.group(1))

            # Pre-process: uppercase + strip 'DNA' so '2663 LSDNA' -> '2663 LS'
            # without the DNA suffix the next XML field ('Drivetrain') starts
            # right after the model letters, so a lookahead terminates the capture.
            full_text_model = re.sub(r'DNA', '', full_text, flags=re.IGNORECASE).upper()
            for pattern in [
                r'VEHICLE\s*TYPE[:\s]+([0-9]{4}\s*[A-Z]{1,3})(?=DRIVETRAIN|SUBCATEGORY|BAUMUSTER|\s|[0-9]|$)',
                r'TYPE[:\s]+([0-9]{4}\s*[A-Z]{1,3})(?=DRIVETRAIN|SUBCATEGORY|BAUMUSTER|\s|[0-9]|$)',
                r'MODEL[:\s]+([0-9]{4}\s*[A-Z]{1,3})(?=DRIVETRAIN|SUBCATEGORY|BAUMUSTER|\s|[0-9]|$)',
            ]:
                m = re.search(pattern, full_text_model)
                if m:
                    model_raw = m.group(1).strip()
                    break
        else:
            try:
                raw = file_obj.read() if hasattr(file_obj, 'read') else file_obj.getvalue()
                text = raw.decode('utf-8') if isinstance(raw, bytes) else str(raw)
            except Exception:
                text = ''
            raw_codes = re.findall(r'\b[A-Z0-9]{3,4}\b', text.upper())
            codes = set(c for c in raw_codes if any(ch.isdigit() for ch in c))
    except Exception as e:
        if log_fn:
            log_fn(f'SAM file read error ({name}): {str(e)[:80]}')
        return

    # Always try to extract model from filename - prefer filename over document content
    # because document content may contain older/internal model numbers (e.g. 4153 inside a 4453K file)
    fname_upper = name.upper()
    fname_model = None
    m_fname = re.search(r'(\d{4}\s*[A-Z]{0,3})(?=\s+[A-Z]\d[A-Z]|\s+\d[Xx]\d|\s+HUB|\s+CLASSIC|\s+EURO|\s|$)', fname_upper)
    if not m_fname:
        m_fname = re.search(r'(\d{4}\s*[A-Z]{1,3})', fname_upper)
    if m_fname:
        fname_model = m_fname.group(1)
    # Use filename model if available, otherwise fall back to document content
    if fname_model:
        model_raw = fname_model

    if model_raw and codes:
        model_norm = _normalize_model(model_raw)
        if model_norm:
            # Detect PTO: check filename first (most reliable), then codes, then doc text
            is_pto = bool(re.search(r'\bPTO\b', name, re.IGNORECASE))
            if not is_pto:
                is_pto = any('PTO' in OPTION_CODE_MAP.get(c, '').upper() for c in codes)
            if not is_pto:
                _doc_text = full_text if name.lower().endswith('.docx') else ''
                if _doc_text and re.search(r'\bPTO\b', _doc_text, re.IGNORECASE):
                    is_pto = True
            if model_norm not in mapping:
                mapping[model_norm] = {}
            mapping[model_norm][is_pto] = {'codes': codes, 'file': name}
            if log_fn:
                log_fn(f"✓ '{name}' → model '{model_norm}' ({'PTO' if is_pto else 'non-PTO'}, {len(codes)} codes)")


def load_sam_from_folder(folder: Path) -> dict:
    """Load all SAM .docx/.csv files from a local folder; return {normalized_model: set(codes)}"""
    mapping = {}
    files = sorted(folder.glob('*'))
    valid_exts = {'.docx', '.csv', '.txt'}
    sam_files = [f for f in files if f.suffix.lower() in valid_exts and not f.name.startswith('.')]
    for fpath in sam_files:
        with open(fpath, 'rb') as fobj:
            _parse_single_sam_file(fobj, fpath.name, mapping)
    # Add aliases: if filename model differs from document-internal model,
    # Auto-generate aliases: for each existing key, create aliases using
    # the reverse of _normalize_model's historic mappings so WINGS models
    # (which use newer numbering) can find SAM data (which uses older numbering).
    _reverse_prefixes = {
        '3253': ['4153'],   # SAM 3253 <- WINGS 4153
    }
    existing_keys = list(mapping.keys())
    for key in existing_keys:
        m = re.match(r'^(\d+)([A-Z]*)$', key)
        if not m:
            continue
        num, suffix = m.group(1), m.group(2)
        for src_prefix, alias_prefixes in _reverse_prefixes.items():
            if num == src_prefix:
                for ap in alias_prefixes:
                    alias_key = ap + suffix
                    if alias_key not in mapping:
                        mapping[alias_key] = mapping[key]
    return mapping


def parse_sam_docx(uploaded_files) -> dict:
    """Parse SAM .docx files using XML extraction; return {normalized_model: set(codes)}"""
    mapping = {}

    def _log(msg):
        st.write(msg)

    for up in uploaded_files:
        _parse_single_sam_file(up, up.name, mapping, log_fn=_log)

    return mapping


def compare(df_wings: pd.DataFrame, sam_maps_by_month: dict) -> pd.DataFrame:
    sorted_yyyymm = sorted(sam_maps_by_month.keys())

    def _get_sam_maps_for_prod_date(prod_date_raw) -> list:
        """Return SAM maps ordered by priority: closest month to production date first.
        Includes both past and future months so SAM files dated after production still match."""
        if not sorted_yyyymm:
            return []
        if prod_date_raw:
            try:
                prod_dt = pd.to_datetime(str(prod_date_raw), errors='coerce')
                if not pd.isna(prod_dt):
                    prod_yyyymm = prod_dt.year * 100 + prod_dt.month
                    # Sort all available months by distance from production date (closest first)
                    by_distance = sorted(sorted_yyyymm, key=lambda ym: abs(ym - prod_yyyymm))
                    return [sam_maps_by_month[ym] for ym in by_distance]
            except Exception:
                pass
        # Fallback: return all maps, most recent first
        return [sam_maps_by_month[ym] for ym in reversed(sorted_yyyymm)]

    rows = []
    for _, r in df_wings.iterrows():
        prod_date_raw = r.get('Requested delivery date', '') if 'Requested delivery date' in r.index else ''
        sam_maps_list = _get_sam_maps_for_prod_date(prod_date_raw)

        com = r['Commission no.']
        # Handle both 'Model' (new format) and 'Baumuster' (legacy format)
        model_raw = r.get('Model') or r.get('Baumuster', '')
        baumuster_num = r.get('Baumuster', '') if 'Model' in r else ''
        wings_codes = set(r['WINGS_codes'] or [])
        model_norm = _normalize_model(model_raw)

        # Initial PTO detection: look up each WINGS code in All Code List (includes user-added descriptions)
        is_pto = any('PTO' in _lookup_code(c).upper() for c in wings_codes)

        def _split_model(s: str):
            # split into leading digits and trailing letters e.g. '3253K' -> ('3253', 'K')
            m = re.match(r'^(\d+)([A-Z]*)$', s)
            if m:
                return m.group(1), m.group(2)
            return s, ''

        def _get_sam_data(entry, prefer_pto: bool):
            """Return (codes_set, filename) from a sam_map entry, preferring the requested PTO variant."""
            # Handle legacy cached format where entry is a plain set of codes
            if isinstance(entry, set):
                return entry, ''
            data = entry.get(prefer_pto) or entry.get(not prefer_pto)
            if data:
                return data['codes'], data['file']
            return set(), ''

        # Try each SAM map in priority order (most recent first, then older)
        sam_entry = {}
        sam_map = sam_maps_list[0] if sam_maps_list else {}
        for _try_map in sam_maps_list:
            # Exact match first
            _try_entry = _try_map.get(model_norm, {})
            _try_codes, _ = _get_sam_data(_try_entry, is_pto)
            if _try_codes:
                sam_entry = _try_entry
                sam_map = _try_map
                break
            # Relaxed matching: numeric prefix + letter suffix
            num_norm, suf_norm = _split_model(model_norm)
            _found = False
            for k, v in _try_map.items():
                try:
                    k_norm = _normalize_model(k)
                except Exception:
                    k_norm = _normalize_model(str(k))
                num_k, suf_k = _split_model(k_norm)
                if k_norm == model_norm or (num_k == num_norm and suf_k == suf_norm):
                    _try_codes2, _ = _get_sam_data(v, is_pto)
                    if _try_codes2:
                        sam_entry = v
                        sam_map = _try_map
                        _found = True
                        break
            if _found:
                break

        # If still no match after trying all maps, do one last relaxed search on the primary map
        _probe_codes, _ = _get_sam_data(sam_entry, is_pto)
        if not _probe_codes and sam_maps_list:
            sam_map = sam_maps_list[0]
            num_norm, suf_norm = _split_model(model_norm)
            for k, v in sam_map.items():
                try:
                    k_norm = _normalize_model(k)
                except Exception:
                    k_norm = _normalize_model(str(k))
                num_k, suf_k = _split_model(k_norm)
                if k_norm == model_norm or (num_k == num_norm and suf_k == suf_norm):
                    sam_entry = v
                    break

        # Fallback for 2853 LS: if no 2653LS SAM found, try 2663LS (2863 LS SAM files)
        _probe_codes2, _ = _get_sam_data(sam_entry, is_pto)
        if not _probe_codes2 and model_norm == '2653LS' and sam_maps_list:
            _fallback_entry = sam_maps_list[0].get('2663LS', {})
            if _fallback_entry:
                sam_entry = _fallback_entry
                sam_map = sam_maps_list[0]

        # Refine PTO detection: if both PTO/non-PTO SAM variants exist,
        # check whether WINGS contains any code that only appears in the PTO SAM file.
        # This catches cases where PTO codes (e.g. N1G, Z5M) are present in WINGS
        # but their OPTION_CODE_MAP description doesn't include the word "PTO".
        if not is_pto and isinstance(sam_entry, dict) and True in sam_entry and False in sam_entry:
            pto_unique = sam_entry[True]['codes'] - sam_entry[False]['codes']
            if wings_codes & pto_unique:
                is_pto = True

        sam_codes, sam_file = _get_sam_data(sam_entry, is_pto)

        _exc_set = st.session_state.get('_except_codes_set', {c for c in OPTION_CODE_MAP if c and c[0] in {'I','O','Z','U'}} | {'DUP0', 'A0B', 'E0D', 'E0Q', 'J7G'})
        _mand_set = st.session_state.get('_mand_codes_set', set(MANDATORY_CODES.keys()))
        # Factory Control: in _exc_set OR starts with I/O/Z/U
        def _is_fc(c):
            return c in _exc_set or (c and c[0] in ('I','O','Z','U'))
        # Exclude both Factory Control codes AND mandatory codes from Only_in lists
        only_w = sorted(c for c in (wings_codes - sam_codes) if c and not _is_fc(c) and c not in _mand_set) if sam_codes else []
        only_s = sorted(c for c in (sam_codes - wings_codes) if c and not _is_fc(c) and c not in _mand_set)
        except_codes_row = sorted(
            c for c in ((wings_codes - sam_codes) | (sam_codes - wings_codes))
            if c and _is_fc(c)
        ) if sam_codes else []
        # Mandatory codes found in mismatches (for Mandatory Codes column)
        mand_in_sam = [c for c in sorted(sam_codes - wings_codes) if c and c in _mand_set]
        mand_in_wings = [c for c in sorted(wings_codes - sam_codes) if c and c in _mand_set]
        mand_codes_row = sorted(set(mand_in_sam + mand_in_wings))
        # No 🔴 markers needed - mandatory codes are in their own section now
        only_s_display = list(only_s)
        only_w_display = list(only_w)

        # Place important columns in desired order. Put Model_norm first, then
        # Changeability Date (renamed from 'Vehicle alterable until'), then Until Dealine,
        # and prefer Only_in_SAM before Only_in_WINGS.
        # Extract Vehicle, Type (axle config), Cab, PTO from SAM filename
        _vehicle = ''
        _axle_type = ''
        _cab_code = ''
        _pto_flag = ''
        if sam_file:
            # Vehicle name: Actros-L, Actros, Arocs, Atego, eActros, Econic, etc.
            _veh_m = re.search(r'\b(Actros-L|Actros|Arocs|Atego|eActros|Econic|Unimog)\b', sam_file, re.IGNORECASE)
            if _veh_m:
                _vehicle = _veh_m.group(1)
            # Axle config: 4x2, 6x2, 6x4, 8x4, 8x8, etc.
            _axle_m = re.search(r'\b(\d+x\d+)\b', sam_file, re.IGNORECASE)
            if _axle_m:
                _axle_type = _axle_m.group(1)
            # Cab code: 2-3 char alphanumeric like S5F, G5F, B5F, C3H
            _cab_m = re.search(r'\b([A-Z]\d[A-Z])\b', sam_file)
            if _cab_m:
                _cab_code = _cab_m.group(1)
            # PTO
            if re.search(r'\bPTO\b', sam_file, re.IGNORECASE):
                _pto_flag = 'PTO'
        # Also mark PTO when WINGS codes indicate PTO (e.g. Z5M, N1G for 2853 LS)
        if not _pto_flag and is_pto:
            _pto_flag = 'PTO'
        # Fallback: infer Vehicle from model number if SAM didn't provide it
        if not _vehicle:
            _model_upper = model_raw.upper()
            if any(k in _model_upper for k in ['2651', '2851', '2653', '2853', '2663', '2863']):
                _vehicle = 'Actros-L'
            elif any(k in _model_upper for k in ['3363']):
                _vehicle = 'Actros'
            elif any(k in _model_upper for k in ['2643', '3343', '4153', '4453', '3253', '2135', '4440', '4140']):
                _vehicle = 'Arocs'

        # Start with explicit copies from the WINGS row to avoid accidental blanks
        row_dict = {
            'Commission no.': com,
            'Baumuster': r.get('Baumuster', '') if 'Baumuster' in r.index else baumuster_num,
            'Model(WINGS)': re.sub(r'DNA$', '', str(r.get('Model', model_raw) if 'Model' in r.index else model_raw).strip()).replace('4140', '4440').replace('2651 LS', '2851 LS').replace('2653 LS', '2853 LS').replace('2663 LS', '2863 LS').replace('2643 A', '3343 A'),
            'Vehicle': _vehicle,
            'Type': _axle_type,
            'Cab': _cab_code,
            'PTO': _pto_flag,
            'Previous Model(SAM)': re.sub(r'4453|4153|3343|2853|2851', lambda m: {'4453':'4153','4153':'3253','3343':'2643','2853':'2663','2851':'2661'}[m.group()], re.sub(r'DNA$', '', re.sub(r'[^A-Z0-9]', '', str(r.get('Model') or r.get('Baumuster') or model_raw).upper().strip()))),
            'Current Model(SAM)': re.sub(r'4453|4153|3343|2853|2851', lambda m: {'4453':'4463','4153':'4163','3343':'3363','2853':'2863','2851':'2861'}[m.group()], re.sub(r'DNA$', '', re.sub(r'[^A-Z0-9]', '', str(r.get('Model') or r.get('Baumuster') or model_raw).upper().strip()))),
            'Changeability Date': '',
            'Until Dealine': '',
            'Production date': r.get('Requested delivery date', '') if 'Requested delivery date' in r.index else '',
            'Only_in_SAM': ','.join(only_s_display),
            'Only_in_WINGS': ','.join(only_w_display) if sam_codes else '',
            'Factory Control Codes': ','.join(except_codes_row),
            'Mandatory Codes': ','.join(mand_codes_row),
            '_all_wings_codes': ','.join(sorted(wings_codes)),
            '_all_sam_codes': ','.join(sorted(sam_codes)),
            'Compared SAM file name': sam_file,
            'SAM Status': 'Match' if sam_file else 'Mismatch',
        }
        
        # compute days until deadline (Vehicle alterable until)
        # Process Changeability Date display and Until Dealine together.
        change_raw = r.get('Vehicle alterable until', '')
        change_display = ''
        days_left = ''
        if change_raw:
            try:
                cdt = pd.to_datetime(change_raw, errors='coerce')
                if not pd.isna(cdt):
                    days_left = (cdt.date() - date.today()).days
                    change_display = cdt.strftime('%Y-%m-%d')
                else:
                    s = str(change_raw).strip()
                    if s:
                        if s.lower() in ('done', 'passed'):
                            change_display = 'Passed'
                            days_left = 'Passed'
                        else:
                            change_display = s
                            days_left = ''
            except Exception:
                s = str(change_raw).strip()
                change_display = 'Passed' if s.lower() in ('done', 'passed') else s
                days_left = 'Passed' if s.lower() in ('done', 'passed') else ''

        row_dict['Changeability Date'] = change_display
        row_dict['Until Dealine'] = days_left
        # Add additional WINGS columns if they exist in df_wings, excluding
        # 'Vehicle alterable until' because we've already exposed it as
        # 'Changeability Date'. Also exclude gross price column per request.
        additional_cols = [
            'Order status financial', 'Order status logistical',
            'Additional equipment (enumeration)', 'FIN', 'Subcategory (ID)',
            'Requested delivery date'
        ]
        for col in additional_cols:
            if col in r.index:
                row_dict[col] = r[col]

        rows.append(row_dict)
    return pd.DataFrame(rows)


def _style_deadline(df: pd.DataFrame) -> pd.DataFrame:
    """Return same-shape DataFrame of CSS strings; colour passed-deadline cells red.
    NOTE: kept for Excel export styling; not used for st.dataframe (plain DF needed for row-click).
    """
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    if 'Until Dealine' in df.columns:
        deadline_num = pd.to_numeric(df['Until Dealine'], errors='coerce')
        mask_passed = deadline_num.lt(0) | (df['Until Dealine'].astype(str).str.strip().str.lower() == 'passed')
        mask_orange = (~mask_passed) & deadline_num.le(14) & deadline_num.ge(0)
        for col in ('Until Dealine', 'Changeability Date'):
            if col in df.columns:
                styles.loc[mask_passed, col] = 'color: red; font-weight: bold'
                styles.loc[mask_orange, col] = 'color: orange; font-weight: bold'
    if 'SAM Status' in df.columns:
        styles.loc[df['SAM Status'] == 'Match', 'SAM Status'] = 'background-color: #d4edda; color: #155724; font-weight: bold; border-radius: 4px; text-align: center'
        styles.loc[df['SAM Status'] == 'Mismatch', 'SAM Status'] = 'background-color: #f8d7da; color: #721c24; font-weight: bold; border-radius: 4px; text-align: center'
    return styles


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    towrite = io.BytesIO()
    with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
        # Select key columns for output in desired order
        output_cols = ['Commission no.', 'Baumuster', 'Model(WINGS)', 'Vehicle', 'Type', 'Cab', 'PTO', 'Previous Model(SAM)', 'Current Model(SAM)', 'Changeability Date',
                       'Until Dealine', 'Production date', 'Only_in_SAM', 'Only_in_WINGS', 'Factory Control Codes',
                       'Order status financial', 'Order status logistical', 'Gross equipment price (repricing)',
                       'Additional equipment (enumeration)', 'FIN', 'Subcategory (ID)',
                       'Requested delivery date', 'Compared SAM file name', 'SAM Status']
        available_cols = [c for c in output_cols if c in df.columns]
        df[available_cols].to_excel(writer, index=False, sheet_name='comparison')
        ws = writer.sheets['comparison']
        for col_cells in ws.columns:
            max_len = 0
            col_letter = col_cells[0].column_letter
            for cell in col_cells:
                val = str(cell.value) if cell.value is not None else ''
                max_len = max(max_len, len(val))
            ws.column_dimensions[col_letter].width = min(max_len + 2, 60)
    return towrite.getvalue()


def main():
    st.set_page_config(page_title='AFAB vs SAM Comparison', layout='wide')

    # ── Global CSS ────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    /* Remove Streamlit default top padding */
    .block-container {
        padding-top: 0rem !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 2.5rem !important;
    }

    /* Page background */
    .stApp {
        background-color: #f0f2f5;
    }

    /* Content sections as white cards */
    .section-card {
        background: #ffffff;
        border-radius: 10px;
        padding: 1.5rem 2rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 6px rgba(0,0,0,0.08);
        border: 1px solid #e0e4e8;
    }

    /* Dataframe column headers */
    /* Make dataframe rows appear clickable */
    [data-testid="stDataFrame"] div[role="gridcell"] {
        cursor: pointer !important;
    }
    [data-testid="stDataFrame"] div[role="columnheader"],
    [data-testid="stDataFrame"] div[role="columnheader"] *,
    [data-testid="stDataFrame"] div[role="row"]:first-child > div,
    [data-testid="stDataFrame"] th,
    [data-testid="stDataFrame"] .col_heading,
    [data-testid="stDataFrame"] [class*="headerCell"],
    [data-testid="stDataFrame"] [class*="ColumnHeader"],
    [data-testid="stDataFrame"] [class*="column-header"] {
        color: #000000 !important;
        opacity: 1 !important;
        font-weight: 800 !important;
    }

    /* Primary buttons: dark navy */
    button[kind="primary"],
    [data-testid="stBaseButton-primary"] {
        background-color: #1a3a5c !important;
        border-color: #1a3a5c !important;
        color: #ffffff !important;
    }
    button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {
        background-color: #24527a !important;
        border-color: #24527a !important;
    }

    /* Multiselect tags: dark navy */
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] {
        background-color: #1a3a5c !important;
    }
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] span {
        color: #ffffff !important;
    }

    /* Dark navy header bar */
    .header-bar {
        background: linear-gradient(135deg, #0d1b2a 0%, #1a3a5c 60%, #1f618d 100%);
        padding: 1.2rem 2.5rem;
        border-radius: 0;
        margin: -1rem -1rem 1.5rem -1rem;
        display: flex;
        align-items: center;
        gap: 1.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    .header-bar img {
        height: 72px;
        filter: brightness(0) invert(1);
    }
    .header-bar .title {
        color: #ffffff;
        font-size: 2.1rem;
        font-weight: normal;
        letter-spacing: 0.5px;
    }
    .header-bar .subtitle {
        color: rgba(255,255,255,0.7);
        font-size: 1rem;
        margin-top: 4px;
    }

    /* KPI metric cards */
    .kpi-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.5rem 1.5rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.10);
        border-left: 5px solid #1a3a5c;
        text-align: center;
    }
    .kpi-card.red { border-left-color: #cb4335; }
    .kpi-card.green { border-left-color: #27ae60; }
    .kpi-card.blue { border-left-color: #1f618d; }
    .kpi-card.orange { border-left-color: #e67e22; }
    .kpi-card .kpi-value {
        font-size: 2.8rem;
        font-weight: 700;
        margin: 0;
        line-height: 1.2;
    }
    .kpi-card.red .kpi-value { color: #cb4335; }
    .kpi-card.green .kpi-value { color: #27ae60; }
    .kpi-card.blue .kpi-value { color: #1f618d; }
    .kpi-card.orange .kpi-value { color: #e67e22; }
    .kpi-card .kpi-label {
        font-size: 1rem;
        color: #444;
        margin: 0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #d0d5db;
    }
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #1a3a5c;
        border-bottom: 2px solid #1a3a5c;
        padding-bottom: 0.3rem;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        border-bottom: 2px solid #e0e0e0;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 14px 28px;
        font-weight: 700;
        font-size: 1.1rem;
    }
    .stTabs [aria-selected="true"] {
        background: #1a3a5c;
        color: white !important;
        border-radius: 8px 8px 0 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- Dashboard (existing code below) ---
    # 앱 배경 및 로고 처리: workspace의 assets/ 아래 파일이 있으면 사용,
    # 없으면 업로드 위젯으로 업로드하도록 합니다.
    assets_dir = Path('assets')
    assets_dir.mkdir(exist_ok=True)

    def _b64_from_bytes(b: bytes) -> str:
        return base64.b64encode(b).decode('ascii')

    def _set_background_from_path(p: Path):
        try:
            b = p.read_bytes()
            b64 = _b64_from_bytes(b)
            mime = 'image/png' if p.suffix.lower() == '.png' else 'image/jpeg'
            # Create a background that fades to white toward the edges so
            # the image blends with Streamlit's white page background.
            # We place a transparent-to-white radial-gradient on top of the
            # image so the edges become white while the center stays visible.
            css = f"""
            <style>
            .stApp {{
                background-image: url('data:{mime};base64,{b64}');
                background-size: cover;
                background-position: center top;
                background-repeat: no-repeat;
                background-attachment: fixed;
            }}
            /* semi-transparent white overlay on the entire app */
            .stApp::before {{
                content: '';
                position: fixed;
                inset: 0;
                background: rgba(255, 255, 255, 0.82);
                z-index: 0;
                pointer-events: none;
            }}
            /* keep all content above the overlay */
            .stApp > * {{
                position: relative;
                z-index: 1;
            }}
            </style>
            """
            st.markdown(css, unsafe_allow_html=True)
        except Exception:
            pass

    def _set_logo_from_path(p: Path):
        try:
            b = p.read_bytes()
            b64 = _b64_from_bytes(b)
            mime = 'image/png' if p.suffix.lower() == '.png' else 'image/jpeg'
            # place a small, sharp logo centered above the title
            html = f"""
            <div style="position:fixed;left:50%;top:8px;transform:translateX(-50%);z-index:9999;">
                <img src='data:{mime};base64,{b64}' style='height:36px;opacity:1;border-radius:2px;display:block;'/>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)
        except Exception:
            pass

    # Load existing images from assets but do not show selection/upload widgets
    img_files = [p for p in assets_dir.iterdir() if p.suffix.lower() in ('.png', '.jpg', '.jpeg')]

    bg_path = None
    logo_path = None
    if img_files:
        # Prefer files with semantic names; otherwise use the first discovered file
        bg_path = next((p for p in img_files if 'background' in p.stem.lower() or 'truck' in p.stem.lower()), img_files[0])
        logo_path = next((p for p in img_files if 'logo' in p.stem.lower()), None)

    # Apply visuals if available (background first, then logo overlay)
    if bg_path and bg_path.exists():
        _set_background_from_path(bg_path)
    # logo disabled - Star Truck Korea logo removed
    # if logo_path and logo_path.exists():
    #     _set_logo_from_path(logo_path)

    # ── Dark navy header bar ─────────────────────────────────────────────────
    logo_file = Path('MB Star_Logo_black.png')
    _logo_html = ''
    if logo_file.exists():
        _logo_b64 = base64.b64encode(logo_file.read_bytes()).decode('ascii')
        _logo_html = f'<img src="data:image/png;base64,{_logo_b64}" />'
    st.markdown(f'''
    <div class="header-bar">
        {_logo_html}
        <div>
            <div class="title"><span style="font-weight:700;">ASCD</span> <span style="font-size:0.45em; font-weight:300; opacity:0.85; margin-left:10px;"><b>AFAB</b> ↔ <b>SAM</b> Option Code <b>Comparison</b> <b>Dashboard</b></span></div>
            <div class="subtitle">Upload an AFAB CSV/Excel file to automatically compare with SAM data</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

    # ── Auto-load SAM files from sam_files/<YYYY_MM>/ folders ────────────────
    sam_base = Path('sam_files')
    sam_base.mkdir(exist_ok=True)

    import re as _re
    month_folders = sorted(
        [p for p in sam_base.iterdir() if p.is_dir() and _re.fullmatch(r'\d{4}_\d{2}', p.name)],
        key=lambda p: p.name
    )
    if not month_folders:
        month_folders = [sam_base]

    _SAM_CACHE_VER = 'v2'  # bump to invalidate cache when alias logic changes

    @st.cache_data(show_spinner=False)
    def _cached_sam_map(folder_str: str, mtime_key: str, _ver: str = _SAM_CACHE_VER) -> dict:
        _ = mtime_key
        return load_sam_from_folder(Path(folder_str))

    valid_exts = {'.docx', '.csv', '.txt'}
    sam_maps_by_month = {}
    all_sam_file_paths = []
    for folder in month_folders:
        m_match = _re.fullmatch(r'(\d{4})_(\d{2})', folder.name)
        yyyymm = int(m_match.group(1)) * 100 + int(m_match.group(2)) if m_match else 0
        file_paths = sorted(
            p for p in folder.glob('*')
            if p.suffix.lower() in valid_exts and not p.name.startswith('.')
        )
        if not file_paths:
            continue  # skip empty folders so comparison falls back to nearest month with data
        all_sam_file_paths.extend(file_paths)
        mtime_key = f'v10,{folder.name},' + ','.join(f'{p.name}:{p.stat().st_mtime}' for p in file_paths)
        sam_maps_by_month[yyyymm] = _cached_sam_map(str(folder), mtime_key)

    # ── Load persistent data from GitHub (once per session) ──────────────────
    if not st.session_state.get('_persistent_loaded'):
        _pdata = _load_persistent_data()
        if _pdata:
            _apply_persistent_data(_pdata)

    # ── Mandatory codes (dynamic, stored in session state) ──────────────────
    if '_mand_codes_set' not in st.session_state:
        st.session_state['_mand_codes_set'] = set(MANDATORY_CODES.keys())
    if '_mand_custom_desc' not in st.session_state:
        st.session_state['_mand_custom_desc'] = {}

    # ── Exception codes (dynamic, stored in session state) ───────────────────
    _EXCEPT_PREFIXES = ('I', 'O', 'Z', 'U')
    _EXCEPT_EXTRA = {'DUP0', 'A0B', 'E0D', 'E0Q', 'J7G'}
    if '_except_codes_set' not in st.session_state:
        st.session_state['_except_codes_set'] = {
            code for code in OPTION_CODE_MAP if code and code[0] in _EXCEPT_PREFIXES
        } | _EXCEPT_EXTRA
    if '_except_custom_desc' not in st.session_state:
        st.session_state['_except_custom_desc'] = {}
    if '_allcode_removed' not in st.session_state:
        st.session_state['_allcode_removed'] = set()
    if '_allcode_added' not in st.session_state:
        st.session_state['_allcode_added'] = set()
    if '_allcode_custom_desc' not in st.session_state:
        st.session_state['_allcode_custom_desc'] = {}

    _exc_set = st.session_state['_except_codes_set']
    _exc_custom = st.session_state['_except_custom_desc']

    except_codes = sorted(
        [(code, _exc_custom.get(code, OPTION_CODE_MAP.get(code, ''))) for code in _exc_set],
        key=lambda x: x[0],
    )

    # ══════════════════════════════════════════════════════════════════════════
    #  SIDEBAR
    # ══════════════════════════════════════════════════════════════════════════
    with st.sidebar:
        # SAM Data — collapsed by default to save sidebar space
        _all_month_dirs = sorted(
            [p for p in sam_base.iterdir() if p.is_dir() and _re.fullmatch(r'\d{4}_\d{2}', p.name)],
            key=lambda p: p.name,
        )
        _total_sam_count = sum(
            1 for _d in _all_month_dirs
            for _f in _d.glob('*')
            if _f.suffix.lower() in valid_exts and not _f.name.startswith('.')
        )
        with st.expander(f'### SAM Data  ({_total_sam_count} files)', expanded=False):
            if any(sam_maps_by_month.values()):
                _loaded_labels = [f.name for f in month_folders if any(
                    p.suffix.lower() in valid_exts and not p.name.startswith('.') for p in f.glob('*')
                )]
                st.success(f'{", ".join(_loaded_labels)} — {len(all_sam_file_paths)} files loaded')

            with st.container(height=350):
                for _mdir in _all_month_dirs:
                    _mfiles = sorted(
                        p for p in _mdir.glob('*')
                        if p.suffix.lower() in valid_exts and not p.name.startswith('.')
                    )
                    with st.expander(f'{_mdir.name}  ({len(_mfiles)} files)', expanded=False):
                        # Upload button
                        _uploaded = st.file_uploader(
                            f'Add .docx to {_mdir.name}',
                            type=['docx'],
                            key=f'_sam_upload_{_mdir.name}',
                            accept_multiple_files=True,
                            label_visibility='collapsed',
                        )
                        if _uploaded:
                            for _uf in _uploaded:
                                _save_path = _mdir / _uf.name
                                _save_path.write_bytes(_uf.read())
                            st.rerun()

                        # List files with view-codes and delete buttons
                        for _fp in _mfiles:
                            _fc1, _fc2, _fc3 = st.columns([5, 1, 1])
                            _fc1.caption(_fp.name)
                            if _fc2.button('🔍', key=f'_sam_view_{_mdir.name}_{_fp.name}', help='View codes'):
                                st.session_state['_sam_view_file'] = str(_fp)
                                show_sam_file_codes()
                            if _fc3.button('✕', key=f'_sam_del_{_mdir.name}_{_fp.name}'):
                                _fp.unlink()
                                st.rerun()
                        if not _mfiles:
                            st.caption('No files')

            if not any(sam_maps_by_month.values()):
                st.warning('No SAM .docx files found.')

        st.markdown('---')
        _mand_count = len(st.session_state.get('_mand_codes_set', set()))
        if st.button(f'🔴 Mandatory Codes ({_mand_count})  — View List', key='_mand_view_btn', use_container_width=True):
            show_mandatory_codes()
        if st.button(f'Factory Control Codes ({len(except_codes)})  — View List', key='_exc_view_btn', use_container_width=True):
            show_exception_codes()
        _allcode_total = len(OPTION_CODE_MAP) + len(st.session_state.get('_allcode_added', set())) - len(st.session_state.get('_allcode_removed', set()))
        if st.button(f'📖 All Code List ({_allcode_total})  — View List', key='_allcode_view_btn', use_container_width=True):
            # Clear undo stack when opening dialog fresh
            st.session_state['_allcode_undo'] = []
            show_all_codes()

        _new_code = st.text_input('Code', key='_exc_new_code', placeholder='e.g. A1B', label_visibility='collapsed')
        _new_desc = st.text_input('Description', key='_exc_new_desc', placeholder='Description', label_visibility='collapsed')
        if st.button('+ Add', key='_exc_add_btn', type='primary', use_container_width=True):
            _nc = _new_code.strip().upper()
            if _nc:
                st.session_state['_except_codes_set'].add(_nc)
                if _new_desc.strip():
                    st.session_state['_except_custom_desc'][_nc] = _new_desc.strip()
                _auto_save()
                st.rerun()

        # Production Date section removed from sidebar (exists in main area)

    # ── Month options (shared) ────────────────────────────────────────────────
    _today = date.today()
    _end_date = date(_today.year + 1, _today.month, 1)
    _month_opts = []
    _d = date(_today.year, _today.month, 1)
    while _d <= _end_date:
        _month_opts.append(f'{_d.year}-{_d.month:02d}')
        if _d.month == 12:
            _d = date(_d.year + 1, 1, 1)
        else:
            _d = date(_d.year, _d.month + 1, 1)

    # ── Auto-fetch via query parameter (?auto_fetch=true) ────────────────────
    _qp = st.query_params
    _auto_fetch_mode = _qp.get('auto_fetch', '').lower() == 'true'
    if _auto_fetch_mode and not st.session_state.get('_auto_fetch_done') and not st.session_state.get('_wings_auto_bytes'):
        # Build months: this month + future months up to +6
        _auto_months = []
        for _i in range(7):
            _d = date(_today.year, _today.month, 1) + timedelta(days=32 * _i)
            _ms = f"{_d.year}-{_d.month:02d}"
            if _ms not in _auto_months:
                _auto_months.append(_ms)
        st.session_state['_auto_fetch_months'] = _auto_months
        st.session_state['_auto_fetch_trigger'] = True

    # ── Search by Production Date (main area) ───────────────────────────────
    st.subheader('Search by Production Date')
    _sel_months = st.multiselect(
        'Select Production Month(s)',
        options=_month_opts,
        default=st.session_state.get('_auto_fetch_months', []),
        key='wings_months_main',
    )
    _main_col1, _main_col2 = st.columns([2, 1])
    with _main_col1:
        _fetch_btn = st.button(
            'Auto-fetch from WINGS',
            key='wings_fetch_btn_main',
            type='primary',
            disabled=not _sel_months,
        )
    with _main_col2:
        if st.session_state.get('_wings_auto_name'):
            st.caption(f"Loaded: {st.session_state['_wings_auto_name']}")
            if st.button('Clear', key='wings_clear_main'):
                st.session_state.pop('_wings_auto_bytes', None)
                st.session_state.pop('_wings_auto_name', None)
                st.rerun()

    # ── 이전 다운로드 결과 자동 복구 (스케줄러 또는 이전 세션 결과) ────────────
    if not st.session_state.get('_wings_auto_bytes'):
        _prev_result = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_wings_dl', '_result.json')
        if os.path.exists(_prev_result):
            try:
                import json as _json_mod
                with open(_prev_result, 'r', encoding='utf-8') as _rf:
                    _prev = _json_mod.load(_rf)
                if _prev.get('ok') and _prev.get('path') and os.path.exists(_prev['path']):
                    with open(_prev['path'], 'rb') as _f:
                        st.session_state['_wings_auto_bytes'] = _f.read()
                    st.session_state['_wings_auto_name'] = os.path.basename(_prev['path'])
                    st.session_state['_auto_fetch_done'] = True
                    st.success(f"이전 다운로드 자동 로드: {st.session_state['_wings_auto_name']}")
                    st.rerun()
            except Exception:
                pass

    # ── Handle Auto-fetch (button OR auto_fetch query param) ────────────────
    _auto_trigger = st.session_state.pop('_auto_fetch_trigger', False)
    if (_fetch_btn or _auto_trigger) and _sel_months:
        if not _WINGS_AUTO:
            st.warning('Auto-fetch requires the local environment with WINGS access. Please upload a file manually below.')
        else:
            _prog = st.progress(0, text='Connecting to WINGS...')
            _status_ph = st.empty()
            _step_count = [0]
            def _on_status(msg):
                _step_count[0] += 1
                _pct = min(_step_count[0] * 15, 90)
                _prog.progress(_pct, text=msg)
                _status_ph.info(msg)
            try:
                _dl_path = _wings_fetch(
                    months=_sel_months,
                    on_status=_on_status,
                )
                _prog.progress(100, text='Download complete!')
                with open(_dl_path, 'rb') as _f:
                    st.session_state['_wings_auto_bytes'] = _f.read()
                st.session_state['_wings_auto_name'] = os.path.basename(_dl_path)
                st.session_state['_auto_fetch_done'] = True
                _status_ph.success(f"Download complete: {st.session_state['_wings_auto_name']}")
                st.rerun()
            except Exception as _e:
                import traceback as _tb
                _prog.empty()
                _status_ph.error(
                    f'Download failed: {type(_e).__name__}: {_e}\n\n'
                    f'```\n{_tb.format_exc()}\n```'
                )

    st.divider()
    st.markdown('**Or upload a file directly:**')

    # ── File uploader (main area) ─────────────────────────────────────────────
    wings_file = st.file_uploader('Upload AFAB CSV/Excel File', type=['csv', 'xlsx', 'xls'])

    # 자동 다운로드된 파일이 있고 업로드된 파일이 없으면 자동 파일 사용
    if wings_file is None and st.session_state.get('_wings_auto_bytes'):
        wings_file = io.BytesIO(st.session_state['_wings_auto_bytes'])
        st.info(f"Using auto-downloaded file: {st.session_state.get('_wings_auto_name', 'wings.xlsx')}")

    # Fallback: load latest file from wings_data/ only in auto_fetch mode
    if wings_file is None and _auto_fetch_mode:
        _wd = Path('wings_data')
        if _wd.exists():
            _wfiles = sorted(_wd.glob('WINGS_*.csv'), key=lambda p: p.stat().st_mtime, reverse=True)
            if _wfiles:
                wings_file = open(_wfiles[0], 'rb')
                st.info(f"Using scheduled data: {_wfiles[0].name}")

    if wings_file is not None:
        df_w = parse_wings(wings_file)
        st.success(f'AFAB file loaded: {len(df_w)} rows')

        comp = compare(df_w, sam_maps_by_month)

        # ── Prepare data splits ──────────────────────────────────────────────
        cols_table = ['Commission no.', 'Baumuster', 'Until Dealine', 'Changeability Date',
                      'Production date', 'Vehicle', 'Model(WINGS)', 'Type', 'Cab', 'PTO', 'Previous Model(SAM)', 'Current Model(SAM)', 'Only_in_SAM', 'Only_in_WINGS', 'Mandatory Codes', 'Factory Control Codes', 'Compared SAM file name', 'SAM Status']
        _hidden_cols = ['_all_wings_codes', '_all_sam_codes']

        # Sort by Production date (earlier months first), then by Until Dealine
        if 'Production date' in comp.columns:
            comp['_prod_date_sort'] = pd.to_datetime(comp['Production date'], errors='coerce')
            comp['_change_date_sort'] = pd.to_datetime(comp['Changeability Date'], errors='coerce')
            comp = comp.sort_values(['_prod_date_sort', '_change_date_sort'], ascending=[True, True])

        if 'Until Dealine' in comp.columns:
            comp['_UntilDealine_days'] = pd.to_numeric(comp['Until Dealine'], errors='coerce')
            very_urgent = comp[
                (comp['_UntilDealine_days'].notna()) &
                (comp['_UntilDealine_days'] >= 0) &
                (comp['_UntilDealine_days'] <= 14)
            ].copy().sort_values(['_prod_date_sort', '_UntilDealine_days'], ascending=[True, True])
            urgent = comp[
                (comp['_UntilDealine_days'].notna()) &
                (comp['_UntilDealine_days'] >= 0) &
                (comp['_UntilDealine_days'] <= 60)
            ].copy().sort_values(['_prod_date_sort', '_UntilDealine_days'], ascending=[True, True])
        else:
            very_urgent = pd.DataFrame()
            urgent = pd.DataFrame()

        # ── KPI metric cards ─────────────────────────────────────────────────
        _total = len(comp)
        # Match/Mismatch based on SAM Status column
        _match = len(comp[comp['SAM Status'] == 'Match']) if 'SAM Status' in comp.columns else 0
        _mismatch = _total - _match
        _vu_count = len(very_urgent)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(f'''<div class="kpi-card blue">
                <p class="kpi-label">Total Commissions</p>
                <p class="kpi-value">{_total}</p>
            </div>''', unsafe_allow_html=True)
        with k2:
            st.markdown(f'''<div class="kpi-card red">
                <p class="kpi-label">Mismatch</p>
                <p class="kpi-value">{_mismatch}</p>
            </div>''', unsafe_allow_html=True)
        with k3:
            st.markdown(f'''<div class="kpi-card green">
                <p class="kpi-label">Match</p>
                <p class="kpi-value">{_match}</p>
            </div>''', unsafe_allow_html=True)
        with k4:
            st.markdown(f'''<div class="kpi-card orange">
                <p class="kpi-label">Urgent (≤ 2 wks)</p>
                <p class="kpi-value">{_vu_count}</p>
            </div>''', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Tabbed results ───────────────────────────────────────────────────
        tab1, tab2, tab3 = st.tabs([
            f'🚨 Changeability Date ≤ 2 weeks ({_vu_count})',
            f'📋 Changeability Date ≤ 60 days ({len(urgent)})',
            f'📊 All Data ({_total})',
        ])

        def _render_tab(display_df, available_cols, tab_key, dl_label, dl_filename, empty_msg=None):
            """Render a dataframe tab with checkbox row selection."""
            if display_df.empty:
                if empty_msg:
                    st.info(empty_msg)
                return
            st.caption('Select a row using the checkbox on the left to view option code details.')
            event = st.dataframe(
                display_df[available_cols].style.apply(_style_deadline, axis=None),
                on_select="rerun",
                selection_mode="single-row",
                use_container_width=True,
                key=f"df_{tab_key}",
            )
            if event.selection.rows:
                idx = event.selection.rows[0]
                row = display_df.iloc[idx]
                show_code_details(
                    str(row.get("Commission no.", "")),
                    str(row.get("Only_in_SAM", "")),
                    str(row.get("Only_in_WINGS", "")),
                    str(row.get("Factory Control Codes", "")),
                    str(row.get("_all_wings_codes", "")),
                    str(row.get("_all_sam_codes", "")),
                    vehicle_row=row.to_dict(),
                )
            st.download_button(
                f'📥 {dl_label}',
                data=to_excel_bytes(display_df),
                file_name=dl_filename,
                key=f'dl_{tab_key}',
            )

        with tab1:
            if not very_urgent.empty:
                available = [c for c in cols_table if c in very_urgent.columns]
                available_with_hidden = available + [c for c in _hidden_cols if c in very_urgent.columns]
                very_urgent_display = very_urgent[available_with_hidden].reset_index(drop=True)
                _render_tab(very_urgent_display, available, 'very_urgent',
                            'Download Urgent (≤ 2 weeks) Excel', 'urgent_2weeks.xlsx')
            else:
                st.success("No urgent corrections needed within 2 weeks.")

        with tab2:
            if not urgent.empty:
                available = [c for c in cols_table if c in urgent.columns]
                available_with_hidden = available + [c for c in _hidden_cols if c in urgent.columns]
                urgent_display = urgent[available_with_hidden].reset_index(drop=True)
                _render_tab(urgent_display, available, '60days',
                            'Download Changeability (≤ 60 days) Excel', 'changeability_60days.xlsx')
            else:
                st.info("No corrections needed within 60 days.")

        with tab3:
            available_all = [c for c in cols_table if c in comp.columns]
            available_all_with_hidden = available_all + [c for c in _hidden_cols if c in comp.columns]
            all_display = comp[available_all_with_hidden].reset_index(drop=True)
            _render_tab(all_display, available_all, 'all',
                        'Download All Data Excel', 'afab_sam_comparison_all.xlsx')


if __name__ == '__main__':
    main()
