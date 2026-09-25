import os
import sys
import ctypes
import urllib.parse
import sqlite3
import requests
import json
import traceback
import base64
import time
from datetime import datetime, timezone, timedelta

if not sys.argv or sys.argv[0] == '':
    sys.argv = [sys.executable if sys.executable else 'CursorWidget.exe']

os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'

def show_error_dialog(title, message):
    ctypes.windll.user32.MessageBoxW(0, str(message), str(title), 0x10)

try:
    from PyQt6.QtCore import Qt, QCoreApplication, QTimer
    from PyQt6.QtGui import QColor
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    import PyQt6.QtWebEngineWidgets
    from PyQt6.QtWidgets import QApplication
    
    app_inst = QApplication.instance()
    if not app_inst:
        app_inst = QApplication(sys.argv)
except Exception as e:
    pass

try:
    import webview
except Exception as e:
    show_error_dialog("Import Error", f"Failed to import pywebview:\n{e}")
    sys.exit(1)

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    assets_path = os.path.join(application_path, 'assets')
else:
    application_path = os.path.dirname(os.path.abspath(__file__))
    assets_path = os.path.join(os.path.dirname(application_path), 'assets')

html_file = os.path.join(application_path, 'index.html')
icon_ico = os.path.join(assets_path, 'app-icon.ico')
icon_png = os.path.join(assets_path, 'app-icon.png')
config_file = os.path.join(os.path.expanduser('~'), '.cursor_widget_config.json')

# IMPORTANT: use cursor.com (no www). www.cursor.com 308-redirects and drops the Cookie header → 401.
API_BASE = 'https://cursor.com'


def _strip_quotes(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='replace')
    return str(value).strip().strip('"')


def _decode_jwt_payload(jwt_token):
    try:
        parts = jwt_token.split('.')
        if len(parts) < 2:
            return {}
        payload = parts[1] + ('=' * (-len(parts[1]) % 4))
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def _user_id_from_jwt(jwt_token):
    sub = _decode_jwt_payload(jwt_token).get('sub') or ''
    # Cursor stores sub as "google-oauth2|user_01..." — cookie needs the user_… part.
    if '|' in sub:
        return sub.split('|')[-1]
    return sub or None


def _format_plan(membership_type):
    if not membership_type:
        return 'Pro+'
    mapping = {
        'pro_plus': 'Pro+',
        'pro': 'Pro',
        'free': 'Free',
        'business': 'Business',
        'enterprise': 'Enterprise',
        'ultra': 'Ultra',
    }
    key = str(membership_type).lower()
    return mapping.get(key, str(membership_type).replace('_', ' ').title())


def _format_reset_date(iso_or_ms):
    if iso_or_ms is None:
        return 'End of Month'
    try:
        if isinstance(iso_or_ms, (int, float)) or (isinstance(iso_or_ms, str) and iso_or_ms.isdigit()):
            ms = int(iso_or_ms)
            dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(iso_or_ms).replace('Z', '+00:00'))
        return dt.strftime('%b %d')
    except Exception:
        return str(iso_or_ms)[:16]


def _classify_model(model_name):
    """Map model id to chart series: cursor (auto) vs other (named/API)."""
    m = (model_name or '').lower().strip()
    if not m:
        return 'other'
    if m in ('default', 'auto'):
        return 'cursor'
    if m.startswith(('composer', 'vega')):
        return 'cursor'
    # Grok variants are in Cursor's auto bucket on the dashboard
    if 'grok' in m:
        return 'cursor'
    return 'other'


def _format_hour_ampm(hour_value):
    h = int(hour_value) % 24
    if h == 0:
        return '12 AM'
    if h < 12:
        return f'{h} AM'
    if h == 12:
        return '12 PM'
    return f'{h - 12} PM'


def _history_bucket_plan(range_key, now_local):
    """Return (start_ms, end_ms, num_buckets, bucket_ms, labels) for a history range."""
    hour = 3600 * 1000
    day = 24 * hour
    now_ms = int(now_local.timestamp() * 1000)

    if range_key in ('hr', 'hourly', '12h'):
        # Last 12 clock hours, 1 bucket each
        aligned = now_local.replace(minute=0, second=0, microsecond=0)
        end_aligned_ms = int(aligned.timestamp() * 1000) + hour
        n, width = 12, hour
        start_ms = end_aligned_ms - n * width
        labels = []
        for i in range(n):
            if i == n - 1:
                labels.append('Now')
                continue
            dt = datetime.fromtimestamp((start_ms + i * width) / 1000.0)
            labels.append(_format_hour_ampm(dt.hour))
        return start_ms, max(now_ms, end_aligned_ms), n, width, labels

    if range_key == '24h':
        # Align to 4-hour clock boundaries so labels are clean AM/PM
        aligned = now_local.replace(minute=0, second=0, microsecond=0)
        aligned = aligned.replace(hour=(aligned.hour // 4) * 4)
        end_aligned_ms = int(aligned.timestamp() * 1000) + 4 * hour
        n, width = 7, 4 * hour
        start_ms = end_aligned_ms - n * width
        labels = []
        for i in range(n):
            if i == n - 1:
                labels.append('Now')
                continue
            dt = datetime.fromtimestamp((start_ms + i * width) / 1000.0)
            labels.append(_format_hour_ampm(dt.hour))
        return start_ms, max(now_ms, end_aligned_ms), n, width, labels

    if range_key == '7d':
        start_day = (now_local - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        start_ms = int(start_day.timestamp() * 1000)
        n, width = 7, day
        labels = []
        for i in range(n):
            if i == n - 1:
                labels.append('Today')
                continue
            dt = datetime.fromtimestamp((start_ms + i * width) / 1000.0)
            labels.append(dt.strftime('%a'))
        return start_ms, now_ms, n, width, labels

    # 30d (default)
    n, width = 6, (30 * day) // 6
    start_ms = now_ms - 30 * day
    labels = []
    for i in range(n):
        if i == n - 1:
            labels.append('Now')
        else:
            day_num = int((i * width) / day) + 1
            labels.append(str(day_num))
    return start_ms, now_ms, n, width, labels


class Api:
    def close_app(self):
        for window in webview.windows:
            window.destroy()
        sys.exit(0)

    def move_window(self, dx, dy):
        try:
            if webview.windows:
                w = webview.windows[0]
                w.move(w.x + dx, w.y + dy)
        except Exception:
            pass

    def resize_window(self, height):
        try:
            if webview.windows:
                w = webview.windows[0]
                w.resize(380, int(height))
        except Exception as e:
            print("Resize error:", e)

    def set_on_top(self, on_top):
        try:
            if webview.windows:
                w = webview.windows[0]
                w.on_top = on_top
        except Exception:
            pass

    def save_custom_token(self, token):
        try:
            cfg = {}
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        cfg = json.load(f)
                except Exception:
                    pass
            cfg['custom_token'] = token.strip()
            with open(config_file, 'w') as f:
                json.dump(cfg, f)
            return True
        except Exception as e:
            print("Save token error:", e)
            return False

    def get_saved_token(self):
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    cfg = json.load(f)
                    return cfg.get('custom_token', '')
        except Exception:
            pass
        return ''

    def _read_cursor_auth(self):
        email = None
        user_id = None
        access_token = None
        membership = None

        possible_paths = [
            os.path.expandvars(r'%APPDATA%\Cursor\User\globalStorage\state.vscdb'),
            os.path.expandvars(r'%LOCALAPPDATA%\Cursor\User\globalStorage\state.vscdb'),
            os.path.expanduser(r'~\.config\Cursor\User\globalStorage\state.vscdb'),
        ]

        db_path = next((p for p in possible_paths if os.path.exists(p)), None)
        if not db_path:
            return access_token, user_id, email, membership

        try:
            conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
            cursor = conn.cursor()
            keys = (
                'cursorAuth/accessToken', 'cursorAuth/userId', 'cursorAuth/cachedEmail',
                'cursorAuth/stripeMembershipType',
                'cursor/accessToken', 'cursor/userId', 'cursor/email',
            )
            placeholders = ','.join('?' * len(keys))
            cursor.execute(f'SELECT key, value FROM ItemTable WHERE key IN ({placeholders})', keys)
            rows = {k: _strip_quotes(v) for k, v in cursor.fetchall()}
            conn.close()

            access_token = rows.get('cursorAuth/accessToken') or rows.get('cursor/accessToken')
            user_id = rows.get('cursorAuth/userId') or rows.get('cursor/userId')
            email = rows.get('cursorAuth/cachedEmail') or rows.get('cursor/email')
            membership = rows.get('cursorAuth/stripeMembershipType')
        except Exception as db_err:
            print('DB Query Exception:', db_err)

        return access_token, user_id, email, membership

    def _build_session_cookie(self, raw_token, user_id=None):
        unquoted = urllib.parse.unquote(_strip_quotes(raw_token) or '')
        jwt_part = unquoted.split('::')[-1] if '::' in unquoted else unquoted

        if '::' not in unquoted:
            if not user_id:
                user_id = _user_id_from_jwt(jwt_part)
            if user_id:
                unquoted = f'{user_id}::{jwt_part}'

        encoded = urllib.parse.quote(unquoted, safe='')
        return unquoted, jwt_part, encoded

    def _resolve_auth(self):
        """Return (cookie_headers, email, membership, error_dict_or_None)."""
        saved_token = self.get_saved_token()
        db_token, user_id, email, membership = self._read_cursor_auth()
        email = email or 'unknown@cursor.sh'

        token = saved_token.strip() if saved_token else db_token
        if not token:
            return None, email, membership, {'error': 'No token found in Cursor DB or Settings', 'email': email}

        formatted_token, jwt_part, encoded_token = self._build_session_cookie(token, user_id)
        if '::' not in formatted_token:
            return None, email, membership, {
                'error': 'Could not build WorkosCursorSessionToken (missing user id). Paste cookie from cursor.com in Settings.',
                'email': email,
            }

        common = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Origin': API_BASE,
            'Referer': f'{API_BASE}/dashboard',
        }
        cookie_headers = [
            {**common, 'Cookie': f'WorkosCursorSessionToken={encoded_token}'},
            {**common, 'Cookie': f'WorkosCursorSessionToken={formatted_token}'},
        ]
        return cookie_headers, email, membership, None

    def _request_with_cookies(self, cookie_headers, method, url, **kwargs):
        last = None
        for headers in cookie_headers:
            try:
                hdrs = dict(headers)
                if method.upper() == 'POST':
                    hdrs['Content-Type'] = 'application/json'
                r = requests.request(method, url, headers=hdrs, timeout=kwargs.pop('timeout', 20), **kwargs)
                last = r
                if r.status_code == 200:
                    return r
            except Exception:
                pass
        return last

    def _fetch_numeric_user_id(self, cookie_headers):
        r = self._request_with_cookies(cookie_headers, 'GET', f'{API_BASE}/api/auth/me', timeout=10)
        if r is not None and r.status_code == 200:
            try:
                return r.json().get('id')
            except Exception:
                return None
        return None

    def _fetch_usage_events(self, cookie_headers, start_ms, end_ms, numeric_user_id=None):
        events = []
        page = 1
        page_size = 500
        total = None

        while page <= 30:
            body = {
                'teamId': 0,
                'startDate': str(int(start_ms)),
                'endDate': str(int(end_ms)),
                'page': page,
                'pageSize': page_size,
            }
            if numeric_user_id is not None:
                body['userId'] = int(numeric_user_id)

            r = self._request_with_cookies(
                cookie_headers,
                'POST',
                f'{API_BASE}/api/dashboard/get-filtered-usage-events',
                json=body,
                timeout=30,
            )
            if r is None or r.status_code != 200:
                break

            data = r.json()
            batch = data.get('usageEventsDisplay') or []
            total = data.get('totalUsageEventsCount', len(batch))
            events.extend(batch)
            if not batch or len(events) >= int(total or 0):
                break
            page += 1

        return events, total if total is not None else len(events)

    def get_usage_history(self, range_key='24h'):
        """Live request-history series for the Stats chart."""
        try:
            range_key = (range_key or 'hr').strip().lower()
            if range_key in ('hourly', '12h'):
                range_key = 'hr'
            if range_key in ('24', '7days', '7 day', '7 days'):
                range_key = {'24': '24h', '7days': '7d', '7 day': '7d', '7 days': '7d'}.get(range_key, range_key)
            if range_key in ('30', '30days', '30 day', '30 days'):
                range_key = '30d'
            if range_key not in ('hr', '24h', '7d', '30d'):
                range_key = 'hr'

            cookie_headers, email, membership, err = self._resolve_auth()
            if err:
                return err

            now_local = datetime.now()
            now_ms = int(time.time() * 1000)
            start_ms, end_ms, n, width, labels = _history_bucket_plan(range_key, now_local)
            # Fetch slightly wider than bucket window so edge events aren't missed
            fetch_start = min(start_ms, now_ms - {
                'hr': 12 * 3600 * 1000,
                '24h': 24 * 3600 * 1000,
                '7d': 7 * 24 * 3600 * 1000,
                '30d': 30 * 24 * 3600 * 1000,
            }[range_key])
            today = now_local.date()
            yesterday = today - timedelta(days=1)

            numeric_id = self._fetch_numeric_user_id(cookie_headers)
            events, total = self._fetch_usage_events(cookie_headers, fetch_start, now_ms, numeric_id)

            cursor_counts = [0] * n
            other_counts = [0] * n
            input_tokens = [0] * n
            output_tokens = [0] * n
            cache_tokens = [0] * n
            total_token_sum = 0
            event_rows = []

            for ev in events:
                try:
                    ts = int(ev.get('timestamp') or 0)
                except (TypeError, ValueError):
                    continue
                if ts < start_ms or ts > end_ms:
                    continue
                idx = int((ts - start_ms) // width)
                if idx < 0:
                    idx = 0
                if idx >= n:
                    idx = n - 1
                series = _classify_model(ev.get('model'))
                if series == 'cursor':
                    cursor_counts[idx] += 1
                else:
                    other_counts[idx] += 1

                usage = ev.get('tokenUsage') or {}
                try:
                    inp = int(usage.get('inputTokens') or 0)
                    out = int(usage.get('outputTokens') or 0)
                    cache = int(usage.get('cacheReadTokens') or 0) + int(usage.get('cacheWriteTokens') or 0)
                except (TypeError, ValueError):
                    inp = out = cache = 0
                input_tokens[idx] += inp
                output_tokens[idx] += out
                cache_tokens[idx] += cache
                total_token_sum += inp + out + cache

                model_name = str(ev.get('model') or 'unknown')
                day_flag = ''
                try:
                    dt = datetime.fromtimestamp(ts / 1000.0)
                    time_label = dt.strftime('%I:%M %p').lstrip('0')
                    ev_date = dt.date()
                    if ev_date == today:
                        day_flag = 'today'
                    elif ev_date == yesterday:
                        day_flag = 'yesterday'
                except Exception:
                    time_label = str(ts)
                event_rows.append({
                    'ts': ts,
                    'time': time_label,
                    'day': day_flag,
                    'model': model_name,
                    'tokens': inp + out + cache,
                    'input': inp,
                    'output': out,
                    'cache': cache,
                })

            event_rows.sort(key=lambda row: row.get('ts', 0), reverse=True)
            events_out = []
            for row in event_rows[:500]:
                events_out.append({
                    'time': row['time'],
                    'day': row['day'],
                    'model': row['model'],
                    'tokens': row['tokens'],
                    'input': row['input'],
                    'output': row['output'],
                    'cache': row['cache'],
                })

            return {
                'live': True,
                'range': range_key,
                'labels': labels,
                'cursor': cursor_counts,
                'other': other_counts,
                'tokens': {
                    'input': input_tokens,
                    'output': output_tokens,
                    'cache': cache_tokens,
                },
                'events': events_out,
                'totalEvents': int(total or len(events)),
                'totalTokens': int(total_token_sum),
                'email': email,
            }
        except Exception as e:
            return {'error': str(e), 'live': False}

    def get_live_usage(self):
        try:
            cookie_headers, email, membership, err = self._resolve_auth()
            if err:
                return err

            summary = None
            last_status = None
            for headers in cookie_headers:
                try:
                    r = requests.get(f'{API_BASE}/api/usage-summary', headers=headers, timeout=10)
                    last_status = r.status_code
                    if r.status_code == 200:
                        summary = r.json()
                        break
                except Exception:
                    pass

            period = None
            if summary is None:
                r = self._request_with_cookies(
                    cookie_headers,
                    'POST',
                    f'{API_BASE}/api/dashboard/get-current-period-usage',
                    json={},
                    timeout=10,
                )
                if r is not None:
                    last_status = r.status_code
                    if r.status_code == 200:
                        period = r.json()

            if summary is None and period is None:
                if last_status == 401:
                    return {
                        'error': 'API HTTP 401 (Session Expired - Paste WorkosCursorSessionToken from cursor.com in Settings)',
                        'email': email,
                        'plan': _format_plan(membership),
                    }
                return {
                    'error': f'API HTTP {last_status if last_status is not None else "Timeout"}',
                    'email': email,
                    'plan': _format_plan(membership),
                }

            if summary:
                plan_usage = (summary.get('individualUsage') or {}).get('plan') or {}
                on_demand = (summary.get('individualUsage') or {}).get('onDemand') or {}
                cursor_pct = int(round(float(plan_usage.get('autoPercentUsed') or 0)))
                other_pct = int(round(float(plan_usage.get('apiPercentUsed') or 0)))
                total_pct = int(round(float(plan_usage.get('totalPercentUsed') or 0)))
                if cursor_pct == 0 and other_pct == 0 and total_pct > 0:
                    cursor_pct = total_pct
                on_demand_spend = float(on_demand.get('used') or 0) / 100.0
                reset_date = _format_reset_date(summary.get('billingCycleEnd'))
                plan = _format_plan(summary.get('membershipType') or membership)
            else:
                plan_usage = period.get('planUsage') or {}
                spend = period.get('spendLimitUsage') or {}
                cursor_pct = int(round(float(plan_usage.get('autoPercentUsed') or 0)))
                other_pct = int(round(float(plan_usage.get('apiPercentUsed') or 0)))
                total_pct = int(round(float(plan_usage.get('totalPercentUsed') or 0)))
                if cursor_pct == 0 and other_pct == 0 and total_pct > 0:
                    cursor_pct = total_pct
                on_demand_spend = float(spend.get('individualUsed') or spend.get('totalSpend') or 0) / 100.0
                reset_date = _format_reset_date(period.get('billingCycleEnd'))
                plan = _format_plan(membership)

            return {
                'email': email,
                'plan': plan,
                'cursorPct': cursor_pct,
                'otherPct': other_pct,
                'grokPct': 0,
                'onDemandSpend': on_demand_spend,
                'resetDate': reset_date,
            }

        except Exception as e:
            return {'error': str(e), 'email': 'dev.wizard@cursor.sh', 'plan': 'Pro+'}

def apply_app_icon():
    """Set taskbar / window icon from assets (works in source + frozen EXE)."""
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QIcon
        app = QApplication.instance()
        if not app:
            return
        icon_path = icon_ico if os.path.exists(icon_ico) else icon_png
        if not icon_path or not os.path.exists(icon_path):
            return
        icon = QIcon(icon_path)
        app.setWindowIcon(icon)
        for win in app.topLevelWidgets():
            win.setWindowIcon(icon)
    except Exception as ex:
        print('Icon apply exception:', ex)


def enforce_pure_alpha_transparency():
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QColor
        
        app = QApplication.instance()
        if not app:
            return
            
        for win in app.topLevelWidgets():
            win.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            win.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            win.setStyleSheet("background: transparent !important; background-color: rgba(0,0,0,0) !important;")
            
            for child in win.findChildren(object):
                if hasattr(child, 'page'):
                    child.page().setBackgroundColor(QColor(0, 0, 0, 0))
                    if hasattr(child, 'setStyleSheet'):
                        child.setStyleSheet("background: transparent !important; background-color: rgba(0,0,0,0) !important;")
                if hasattr(child, 'setAttribute'):
                    child.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                    child.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        apply_app_icon()
    except Exception as ex:
        print("Glass enforce exception:", ex)

if __name__ == '__main__':
    try:
        # Prefer icon early for Windows taskbar grouping
        try:
            from PyQt6.QtGui import QIcon
            from PyQt6.QtWidgets import QApplication
            _app = QApplication.instance()
            _path = icon_ico if os.path.exists(icon_ico) else icon_png
            if _app and _path and os.path.exists(_path):
                _app.setWindowIcon(QIcon(_path))
        except Exception:
            pass

        api = Api()
        window = webview.create_window(
            'Cursor Pro+ Widget',
            url=html_file,
            js_api=api,
            frameless=True,
            transparent=True,
            on_top=True,
            width=380,
            height=252,
            resizable=False,
            easy_drag=False
        )
        
        QTimer.singleShot(10, enforce_pure_alpha_transparency)
        QTimer.singleShot(100, enforce_pure_alpha_transparency)
        QTimer.singleShot(400, enforce_pure_alpha_transparency)
        QTimer.singleShot(50, lambda: api.resize_window(252))

        try:
            webview.start(gui='qt', debug=False)
        except Exception:
            webview.start(debug=False)
    except Exception as main_err:
        show_error_dialog("Cursor Widget Crash", f"Fatal Error:\n\n{traceback.format_exc()}")
