"""
HR Coil Monthly Quality Dashboard Engine — Fully Dynamic
=========================================================
Detects ALL tables from ANY HR Coil Excel file automatically.
"""
import io, re, warnings, zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
import openpyxl
warnings.filterwarnings('ignore')

_PCT_HEADERS  = {'%', '%WRP', '% WRP', 'PERCENTAGE', 'PCT'}
_PARETO_KW    = {'defect', 'cat-i reason', 'cat i reason', 'reasons'}
_TITLE_MAP    = {
    'QC STATUS':             'PRODUCT QUALITY',
    'DEFECTS':               'CAT-I REASONS',
    'THICKNESS RANGE':       'THICKNESS WISE PRODUCTION',
    'WIDTH RANGE':           'WIDTH WISE PRODUCTION',
    'WIDTH WISE':            'WIDTH WISE PRODUCTION',
    'GRADES':                'GRADE DIVERSION',
    'ROLLED GRADE':          'CATEGORY-I GRADE WISE',
}
_PRIORITY = [
    'QC STATUS','CERTIFIED GRADE','DEFECTS',
    'THICKNESS RANGE','WIDTH RANGE','STEEL TYPE','MODE OF KILLING',
    'GRADES','GRADE DIVERSION','ROLLED GRADE','CATEGORY-I GRADE WISE',
]

def _pct(v):
    if v is None: return 0.0
    try:
        f = float(v)
        return round(f*100,4) if abs(f)<=1.5 else round(f,4)
    except: return 0.0

def _is_pct_hdr(v):   return v is not None and str(v).strip() in _PCT_HEADERS
def _is_grand(v):     return v is not None and str(v).strip().lower()=='grand total'
def _is_col_hdr(v):
    if v is None: return False
    s=str(v).strip().lower()
    return s.startswith('sum of') or s.startswith('count of') or s.startswith('nos ')
def _is_num(v):       return isinstance(v,(int,float)) and not isinstance(v,bool)
def _is_pareto(t):    return any(k in t.lower() for k in _PARETO_KW)
def _nice(k):         return _TITLE_MAP.get(k.upper().strip(),k)

_GENERIC_LABEL_WORDS = {
    'grade', 'name', 'item', 'category', 'type', 'label', 'labels',
    'description', 'code', 'id',
}
def _is_generic_label(v) -> bool:
    """A bare single-word column label (e.g. 'Grade', 'Name') — never a real
    section title on its own, so it shouldn't stop the title search."""
    if v is None: return False
    return str(v).strip().lower() in _GENERIC_LABEL_WORDS

def _find_name_col_dynamic(grid: Dict[Tuple[int,int],Any], hr: int, pc: int, max_row: int) -> Optional[int]:
    """
    Find the name/label column for a table anchored at header row `hr`,
    percentage column `pc` — WITHOUT assuming a fixed number of columns
    between them. Different tables in the same file (or different files)
    may have 1, 2, 3, or more intermediate columns (Count, Qty, Weight, etc).

    Strategy: walk left from pc, and for each candidate column, check
    whether the rows immediately below the header contain STRING labels
    there (not numbers). The first column (scanning right-to-left) with
    genuine string data in most of its data rows is the name column.
    """
    best_col   = None
    best_score = 0
    for nc in range(pc - 1, max(0, pc - 8), -1):
        string_rows = 0
        checked     = 0
        for r in range(hr + 1, min(hr + 12, max_row + 1)):
            v = grid.get((r, nc))
            if v is None:
                continue
            checked += 1
            if isinstance(v, str) and v.strip() and not _is_col_hdr(v) and not _is_pct_hdr(v):
                string_rows += 1
        if checked > 0 and string_rows >= 1 and string_rows >= checked * 0.5:
            # This column mostly holds string labels — good candidate.
            # Prefer the one closest to pc (rightmost qualifying column).
            if best_col is None:
                best_col = nc
                best_score = string_rows
            break  # first (rightmost) qualifying column wins
    return best_col


def _classify_columns_between(grid: Dict[Tuple[int,int],Any], hr: int, nc: int, pc: int, max_row: int) -> dict:
    """
    Look at every column between name_col and pct_col (exclusive) and
    classify what kind of data each holds — used to decide the best chart
    type for a table (e.g. a table with a numeric trend across many
    categories may suit a bar chart better than a pie; a table with very
    skewed magnitude differences may suit a Pareto).
    """
    info = {'intermediate_cols': [], 'n_rows': 0}
    for r in range(hr + 1, min(hr + 30, max_row + 1)):
        if grid.get((r, nc)) is not None or grid.get((r, pc)) is not None:
            info['n_rows'] += 1
    return info


def _choose_chart_type(title: str, rows: list) -> str:
    """
    Decide the best chart type for a table:
      - Title contains defect/reason keywords → Pareto (bars + cumulative line),
        matching the convention used in the source Excel dashboard.
      - Very many categories (>12) → a pie chart becomes unreadable at that
        density, so a horizontal bar chart is used instead.
      - Otherwise → pie_3d, which is the correct default for a labeled
        percentage breakdown with a small number of categories.
    """
    t = title.lower()
    if any(k in t for k in _PARETO_KW):
        return 'pareto'

    n = len(rows)
    if n > 12:
        return 'bar'

    return 'pie_3d'


def _find_titles_missing_pct_header(grid: Dict[Tuple[int,int],Any], max_row: int) -> list:
    """
    Some tables in these reports have a blank cell where the '%' header
    should be (a formatting slip in the source Excel file), even though the
    percentage DATA is still present one column to the right of "Sum of
    Qty(MT)". This finds those tables by looking for a section-title cell
    (e.g. "Mode of Killing") followed by a "Row Labels" / column-header row,
    then checking if the column after "Sum of Qty(MT)" holds fraction-like
    numbers even though its header is empty.
    Returns a list of (header_row, name_col, pct_col) triples to also process.
    """
    extra = []
    for (r, c), v in list(grid.items()):
        if not isinstance(v, str):
            continue
        # Look for "Sum of Qty(MT)" column headers — the % column is directly right of these
        if v.strip().lower() in ('sum of qty(mt)', 'sum of qty'):
            pc = c + 1
            hr = r
            nc = c - 1  # name column is directly left of "Count of BATCH"/"Sum of Qty(MT)"
            if grid.get((hr, pc)) is not None:
                continue  # already has a real header there, not a candidate
            # Check if data rows below have fraction-like values in pc
            frac_count = 0
            for rr in range(hr + 1, min(hr + 15, max_row + 1)):
                pv = grid.get((rr, pc))
                if isinstance(pv, (int, float)) and 0 <= abs(pv) <= 1.5:
                    frac_count += 1
            if frac_count >= 1 and nc >= 1:
                extra.append((hr, nc, pc))
    return extra


def _parse_all_tables(ws) -> Dict[str,list]:
    # Load grid
    grid:Dict[Tuple[int,int],Any]={}
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                grid[(cell.row,cell.column)]=cell.value

    tables:Dict[str,list]={}
    seen:(set)=set()

    pct_cells=sorted([(r,c) for (r,c),v in grid.items() if _is_pct_hdr(v)])
    # Also catch tables whose % header cell is blank but the % data column is real
    pct_cells += [(r, c) for (r, _nc, c) in _find_titles_missing_pct_header(grid, ws.max_row)]
    pct_cells = sorted(set(pct_cells))

    for (hr,pc) in pct_cells:
        # Dynamically find the name column — do NOT assume a fixed gap.
        # Different tables (and different files) may have 1, 2, 3+ columns
        # between the label and the % column.
        nc = _find_name_col_dynamic(grid, hr, pc, ws.max_row)
        if nc is None:
            nc = pc - 3   # fallback to the common report layout if detection is inconclusive
        if nc<1: continue
        if (hr,nc) in seen: continue
        seen.add((hr,nc))

        # Find title. Two layouts exist across different report versions:
        #  (a) title sits on the SAME row as the % header (common in these files)
        #  (b) title sits on a row ABOVE the header (a separate section-title row)
        # To tell (b) apart from "the row above is actually the previous
        # table's last data row" (which happens when tables are stacked with
        # no blank row between them), only accept a row above as a title
        # source if that row's pct column is empty — a genuine title row has
        # nothing in the % column, whereas a trailing data row of the
        # previous table does.
        title=''
        v_same = grid.get((hr,nc))
        if v_same and not _is_pct_hdr(v_same) and not _is_col_hdr(v_same) and not _is_num(v_same) and not _is_generic_label(v_same):
            s=str(v_same).strip()
            if s and s.lower() not in ('grand total','%','%wrp','% wrp','row labels'):
                title=s

        if not title:
            for tr in range(hr-1, max(0,hr-4), -1):
                if grid.get((tr, pc)) is not None:
                    break  # that row belongs to another table's data — stop looking further up
                v=grid.get((tr,nc))
                if v and not _is_pct_hdr(v) and not _is_col_hdr(v) and not _is_num(v):
                    s=str(v).strip()
                    if s and s.lower() not in ('grand total','%','%wrp','% wrp','row labels'):
                        title=s; break

        if not title: title=f"Table_r{hr}"
        key=title.upper().strip()

        # Identify any intermediate columns between name_col and pct_col
        # (e.g. "Count of BATCH", "Sum of Qty(MT)") so their values can be
        # attached to each row as extra tooltip fields. This is fully
        # dynamic — whatever the column header text says becomes the field
        # label, so it adapts to any report layout without hardcoding.
        extra_cols=[]
        for c in range(nc+1, pc):
            hv=grid.get((hr,c))
            if hv and not _is_pct_hdr(hv) and not _is_num(hv):
                hs=str(hv).strip()
                if hs and hs.lower() not in ('row labels',''):
                    extra_cols.append((c,hs))

        # Collect data rows — stop at Grand Total OR when pct value is huge (>2 = not a fraction)
        rows=[]
        r=hr+1
        blank=0
        while r<=ws.max_row:
            lbl=grid.get((r,nc))
            pv =grid.get((r,pc))

            if lbl is None and pv is None:
                blank+=1
                if blank>=2: break
                r+=1; continue
            blank=0

            if lbl is not None:
                if _is_grand(lbl): break
                ls=str(lbl).strip()
                if ls and not _is_col_hdr(lbl) and not _is_pct_hdr(lbl):
                    if _is_num(pv) and abs(float(pv))<=1.5:
                        row_d={'label':ls,'pct':_pct(pv)}
                        for c,fname in extra_cols:
                            fv=grid.get((r,c))
                            if fv is not None:
                                row_d[fname]=fv
                        rows.append(row_d)
                    elif _is_num(pv) and abs(float(pv))>1.5:
                        # Large number = this is Qty or Count, not %; might be wrong col
                        pass
            r+=1

        if not rows: continue
        # Keep version with more rows
        if key not in tables or len(rows)>len(tables[key]):
            tables[key]=rows

    return tables


def _parse_data_sheet(ws)->dict:
    if ws is None: return {}
    hdrs={}
    for cell in ws[1]:
        if cell.value: hdrs[cell.column-1]=str(cell.value).strip()
    def col(name):
        for i,h in hdrs.items():
            if name.lower() in h.lower(): return i
        return None
    mc=col('MONTH'); sc=col('QC STATUS')
    oc=col('OBSERVATION'); qc=col('Qty')
    if mc is None or sc is None: return {}

    mt=defaultdict(float); mc1=defaultdict(float)
    md=defaultdict(lambda:defaultdict(float))
    _MN={'01':'Jan','02':'Feb','03':'Mar','04':'Apr','05':'May','06':'Jun',
         '07':'Jul','08':'Aug','09':'Sep','10':'Oct','11':'Nov','12':'Dec'}

    for row in ws.iter_rows(min_row=2,values_only=True):
        r=list(row)
        if not any(r): continue
        month=str(r[mc]).strip() if r[mc] else None
        status=str(r[sc]).strip() if r[sc] else ''
        obs=str(r[oc]).strip() if oc is not None and r[oc] else ''
        qty=float(r[qc]) if qc is not None and isinstance(r[qc],(int,float)) else 0.0
        if not month or month=='None': continue
        try:
            m=re.search(r'(\d{4})-(\d{2})',month)
            if m: month=f"{_MN.get(m.group(2),m.group(2))}-{m.group(1)}"
        except: pass
        mt[month]+=qty
        if 'CATEGORY-I' in status.upper() or status.upper().startswith('CAT'):
            mc1[month]+=qty
            if obs:
                short=' '.join(obs.split()[:4]) if len(obs)>30 else obs
                md[month][short]+=qty

    months=sorted(mt.keys())
    cat1=[{'month':m,'pct':round(mc1[m]/mt[m]*100,4) if mt[m] else 0} for m in months]
    dt=defaultdict(float)
    for m in months:
        for d,v in md[m].items(): dt[d]+=v
    tdefs=sorted(dt,key=dt.get,reverse=True)[:12]
    trend=[]
    for m in months:
        tot=mt[m]; row_d={'month':m}
        for d in tdefs: row_d[d]=round(md[m].get(d,0)/tot*100,6) if tot else 0
        trend.append(row_d)
    return {'cat1_trend':cat1,'major_defects_trend':trend,'defect_series':tdefs}


def _pareto(items):
    if not items: return []
    srt=sorted(items,key=lambda x:x['pct'],reverse=True)
    total=sum(i['pct'] for i in srt) or 1
    cum=0; out=[]
    for i in srt:
        cum+=i['pct']
        out.append({'label':i['label'],'pct':round(i['pct'],4),'cumulative':round(cum/total*100,2)})
    return out



def _parse_external_link_trends(raw_bytes: bytes) -> dict:
    """
    Some HR Coil reports embed 'Monthwise CAT-I' and 'Major Defects' as native
    Excel charts that pull data via an EXTERNAL WORKBOOK LINK (e.g. a separate
    "3 Months.xlsx" file with month-over-month history) rather than storing
    that data as a table inside this workbook.

    When Excel last refreshed that link, it caches the resulting values inside
    this file's xl/externalLinks/externalLink*.xml — even though the source
    workbook itself is not included. This function reads that cache so the
    Month-wise CAT-I and Major Defects Trend charts can still be reproduced
    even when no separate DATA sheet exists in the uploaded file.

    Returns the same shape as _parse_data_sheet()'s trend output, or {} if
    no external link (or no usable cached data) is present.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
            link_files = [n for n in z.namelist()
                          if re.match(r'xl/externalLinks/externalLink\d+\.xml$', n)]
            if not link_files:
                return {}

            ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            best_grid: Dict[str, Dict[str, str]] = {}

            for lf in link_files:
                content = z.read(lf)
                root = ET.fromstring(content)
                for sd in root.findall('.//m:sheetData', ns):
                    rows = sd.findall('m:row', ns)
                    if not rows:
                        continue
                    grid: Dict[str, str] = {}
                    for row in rows:
                        for cell in row.findall('m:cell', ns):
                            ref = cell.get('r')
                            v = cell.find('m:v', ns)
                            if v is not None and v.text is not None:
                                grid[ref] = v.text
                    # Keep the sheet with the most cached cells (most likely the real data)
                    if len(grid) > len(best_grid):
                        best_grid = grid

            if not best_grid:
                return {}

            return _grid_to_trends(best_grid)
    except Exception:
        return {}


def _grid_to_trends(grid: Dict[str, str]) -> dict:
    """
    Convert a sparse {cellRef: value} grid (from a cached external-link sheet)
    into month-wise CAT-I trend + major-defects-trend data.

    Expected shape (matches the standard HR Coil "3 Months" history sheet):
      Row 2: month headers across columns B, C, D, ... (e.g. "April-26(%)")
      Rows 3+: one row per defect, column A = defect name, B/C/D = % per month
      Last populated row (no label in col A): the CAT-I total per month
    """
    def col_letter(ref: str) -> str:
        return re.match(r'([A-Z]+)', ref).group(1)
    def row_num(ref: str) -> int:
        return int(re.search(r'(\d+)', ref).group(1))

    rows_by_num: Dict[int, Dict[str, str]] = defaultdict(dict)
    for ref, val in grid.items():
        rows_by_num[row_num(ref)][col_letter(ref)] = val

    if not rows_by_num:
        return {}

    header_row_num = min(rows_by_num.keys())
    header_row = rows_by_num[header_row_num]

    # Month columns = every column in the header row except A (label column)
    month_cols = sorted([c for c in header_row if c != 'A'])
    if not month_cols:
        return {}

    def clean_month(raw: str) -> str:
        # "April-26(%)" -> "Apr-2026"
        m = re.match(r'([A-Za-z]+)-?(\d{2,4})', raw)
        if not m:
            return raw.strip()
        mon_raw, yr = m.group(1), m.group(2)
        mon_map = {'jan':'Jan','feb':'Feb','mar':'Mar','apr':'Apr','may':'May','jun':'Jun',
                   'jul':'Jul','aug':'Aug','sep':'Sep','oct':'Oct','nov':'Nov','dec':'Dec'}
        mon = mon_map.get(mon_raw.lower()[:3], mon_raw[:3].title())
        if len(yr) == 2:
            yr = '20' + yr
        return f"{mon}-{yr}"

    months = [clean_month(header_row[c]) for c in month_cols]

    defect_rows = []
    total_row = None

    for rn in sorted(rows_by_num.keys()):
        if rn == header_row_num:
            continue
        row = rows_by_num[rn]
        label = row.get('A')
        # A row with no label but numeric values in the month columns = the total row
        if not label and any(c in row for c in month_cols):
            total_row = row
        elif label:
            defect_rows.append((label.strip(), row))

    cat1_trend = []
    if total_row:
        for i, c in enumerate(month_cols):
            try:
                v = float(total_row.get(c, 0)) * 100
            except (TypeError, ValueError):
                v = 0.0
            cat1_trend.append({'month': months[i], 'pct': round(v, 4)})

    defect_series = [label for label, _ in defect_rows]
    trend = []
    for i, c in enumerate(month_cols):
        entry = {'month': months[i]}
        for label, row in defect_rows:
            try:
                v = float(row.get(c, 0))
            except (TypeError, ValueError):
                v = 0.0
            entry[label] = round(v, 6)
        trend.append(entry)

    return {
        'cat1_trend': cat1_trend,
        'major_defects_trend': trend,
        'defect_series': defect_series,
    }


def build_hr_coil_dashboard(raw_bytes:bytes)->Optional[dict]:
    try:
        wb=openpyxl.load_workbook(io.BytesIO(raw_bytes),data_only=True)
    except: return None

    ws_sum=None
    for name in wb.sheetnames:
        if 'summary' in name.lower(): ws_sum=wb[name]; break
    if ws_sum is None:
        for name in wb.sheetnames:
            if name.upper()!='DATA': ws_sum=wb[name]; break
    if ws_sum is None: return None

    ws_data=next((wb[n] for n in wb.sheetnames if n.upper()=='DATA'),None)
    all_tables=_parse_all_tables(ws_sum)
    trends=_parse_data_sheet(ws_data)

    # Fallback: if there's no DATA sheet (or it produced nothing), the Month-wise
    # CAT-I / Major Defects charts might still be recoverable from a cached
    # external-workbook link that Excel embedded when the link was last refreshed.
    if not trends.get('cat1_trend'):
        ext_trends = _parse_external_link_trends(raw_bytes)
        if ext_trends.get('cat1_trend'):
            trends = ext_trends

    import sys
    print(f"[hr_coil] sheet='{ws_sum.title}' tables={list(all_tables.keys())}",file=sys.stderr)

    sections=[]; used=set()
    for key in _PRIORITY:
        if key in all_tables:
            data=all_tables[key]
            ctype=_choose_chart_type(key, data)
            sections.append({'key':key,'title':_nice(key),
                'chart_type':ctype,
                'data':_pareto(data) if ctype=='pareto' else data})
            used.add(key)
    for key in sorted(all_tables.keys()):
        if key in used: continue
        data=all_tables[key]
        ctype=_choose_chart_type(key, data)
        sections.append({'key':key,'title':_nice(key),
            'chart_type':ctype,
            'data':_pareto(data) if ctype=='pareto' else data})
        used.add(key)
    if trends.get('cat1_trend') and len(trends['cat1_trend'])>=1:
        sections.append({'key':'MONTHWISE_CAT1','title':'MONTH-WISE CAT-I (%)','chart_type':'column','data':trends['cat1_trend']})
    if trends.get('major_defects_trend') and trends.get('defect_series'):
        sections.append({'key':'MAJOR_DEFECTS_TREND','title':'MAJOR DEFECTS TREND','chart_type':'stacked_column','data':trends['major_defects_trend'],'defect_series':trends['defect_series']})

    report_month=''
    if trends.get('cat1_trend'): report_month=trends['cat1_trend'][-1].get('month','')
    if not report_month:
        for v in [ws_sum.title,ws_sum.cell(1,1).value,ws_sum.cell(1,7).value]:
            if v:
                m=re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[\-\s]*(\d{4})',str(v),re.I)
                if m: report_month=f"{m.group(1).capitalize()}-{m.group(2)}"; break

    return {'report_type':'hr_coil_monthly','report_month':report_month,
            'sections':sections,'all_tables':all_tables,'table_count':len(all_tables)}
