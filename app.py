from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, Response
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import requests

# Application version
APP_VERSION = "1.0.1"
from requests.adapters import HTTPAdapter
from urllib3.util.connection import create_connection
import urllib3
from icalendar import Calendar
import csv
import io
import json
import re
import threading
import time
import secrets
import qrcode
from io import BytesIO
import base64
import os
import tempfile
import urllib.parse
import ipaddress
import socket
import zipfile
import shutil
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from backup_manager import BackupManager
from tlc_client import TrailLifeConnectClient

# Disable SSL warnings for whitelisted calendar domains
# We disable SSL verification only for pre-approved domains in ALLOWED_ICAL_DOMAINS
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables from .env file
load_dotenv()

# Allowed domains for iCal imports (SSRF protection)
# Add trusted calendar providers here
ALLOWED_ICAL_DOMAINS = [
    # Google Calendar
    'calendar.google.com',
    
    # Microsoft Outlook/Office 365
    'outlook.office365.com',
    'outlook.live.com',
    
    # Apple iCloud
    'calendars.icloud.com',
    'ical.mac.com',
    'p01-caldav.icloud.com',
    'p02-caldav.icloud.com',
    'p03-caldav.icloud.com',
    'p04-caldav.icloud.com',
    'p05-caldav.icloud.com',
    'p06-caldav.icloud.com',
    'p07-caldav.icloud.com',
    'p08-caldav.icloud.com',
    
    # Trail Life USA
    'traillifeconnect.com',
    'www.traillifeconnect.com',
    
    # Church Management Systems
    'planningcenteronline.com',
    'api.planningcenteronline.com',
    'churchcenter.com',
    'breezechms.com',
    'secure.breezechms.com',
    'elvanto.com',
    'elvanto.net',
    'subsplash.com',
    'pushpay.com',
    
    # Other Calendar Services
    'calendar.yahoo.com',
    'zimbra.free-av.de',
    'calendar.zoho.com',
    'fastmail.com',
    'protonmail.com',
    'tutanota.com',
]

# Optional label printing support
try:
    from label_printer import generate_unique_code, print_checkout_label
    LABEL_PRINTING_AVAILABLE = True
except ImportError:
    LABEL_PRINTING_AVAILABLE = False
    print("Warning: Label printing libraries not available. Install Pillow to enable this feature.")

def normalize_address(address):
    if not address:
        return ''
    # Lower case
    addr = address.lower()
    # Remove punctuation
    addr = re.sub(r'[^\w\s]', '', addr)
    # Replace abbreviations
    addr = re.sub(r'\bst\b', 'street', addr)
    addr = re.sub(r'\bsr\b', 'street', addr)
    addr = re.sub(r'\bave\b', 'avenue', addr)
    addr = re.sub(r'\brd\b', 'road', addr)
    addr = re.sub(r'\bdr\b', 'drive', addr)
    # Replace directional abbreviations
    addr = re.sub(r'\bn\b', 'north', addr)
    addr = re.sub(r'\bs\b', 'south', addr)
    addr = re.sub(r'\be\b', 'east', addr)
    addr = re.sub(r'\bw\b', 'west', addr)
    # Replace multiple spaces with one
    addr = re.sub(r'\s+', ' ', addr).strip()
    return addr

# Database path - use DATABASE_PATH env var if set (for demo), otherwise default location
if os.getenv('DATABASE_PATH'):
    DB_PATH = Path(os.getenv('DATABASE_PATH'))
else:
    # Use /app/data for Docker containers, otherwise use local directory
    DATA_DIR = Path(__file__).parent / 'data'
    if DATA_DIR.exists() and DATA_DIR.is_dir():
        # Running in Docker or with data directory
        DB_PATH = DATA_DIR / 'checkin.db'
    else:
        # Running locally without data directory
        DB_PATH = Path(__file__).parent / 'checkin.db'

def get_db():
    db_path = app.config.get('DATABASE', DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_tlc_synced_column():
    """Ensure the tlc_synced column exists in the checkins table."""
    conn = get_db()
    try:
        conn.execute('SELECT tlc_synced FROM checkins LIMIT 1')
    except sqlite3.OperationalError:
        try:
            conn.execute('ALTER TABLE checkins ADD COLUMN tlc_synced BOOLEAN DEFAULT 0')
            conn.commit()
        except Exception:
            pass # Might have been added by another thread/process
    finally:
        conn.close()

def ensure_adult_phone_column():
    """Ensure the phone column exists in the adults table."""
    conn = get_db()
    try:
        conn.execute('SELECT phone FROM adults LIMIT 1')
    except sqlite3.OperationalError:
        try:
            conn.execute('ALTER TABLE adults ADD COLUMN phone TEXT')
            conn.commit()
            app.logger.info('Added phone column to adults table')
        except Exception:
            pass # Might have been added by another thread/process
    finally:
        conn.close()

def init_db():
    conn = sqlite3.connect(app.config.get('DATABASE', DB_PATH))
    conn.row_factory = sqlite3.Row
    schema_path = Path(__file__).parent / 'schema.sql'
    if schema_path.exists():
        with open(schema_path) as f:
            conn.executescript(f.read())
        conn.commit()
    conn.close()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-key-for-local')  # override in prod with env var

# Trust proxy headers for HTTPS detection behind reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# File upload configuration
UPLOAD_FOLDER = Path(__file__).parent / 'static' / 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'svg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max

# Ensure upload folder exists
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# Make version, current year, and footer settings available to all templates
@app.context_processor
def inject_version():
    try:
        conn = get_db()
        
        # Get footer settings
        footer_enabled_row = conn.execute("SELECT value FROM settings WHERE key = 'footer_enabled'").fetchone()
        footer_enabled = footer_enabled_row[0] == 'True' if footer_enabled_row else True
        
        footer_text_row = conn.execute("SELECT value FROM settings WHERE key = 'footer_text'").fetchone()
        footer_text = footer_text_row[0] if footer_text_row else ''
        
        footer_show_github_row = conn.execute("SELECT value FROM settings WHERE key = 'footer_show_github'").fetchone()
        footer_show_github = footer_show_github_row[0] == 'True' if footer_show_github_row else True
        
        footer_show_version_row = conn.execute("SELECT value FROM settings WHERE key = 'footer_show_version'").fetchone()
        footer_show_version = footer_show_version_row[0] == 'True' if footer_show_version_row else True
        
        footer_show_admin_link_row = conn.execute("SELECT value FROM settings WHERE key = 'footer_show_admin_link'").fetchone()
        footer_show_admin_link = footer_show_admin_link_row[0] == 'True' if footer_show_admin_link_row else True
        
        conn.close()
        
        return {
            'app_version': APP_VERSION,
            'current_year': datetime.now().year,
            'footer_enabled': footer_enabled,
            'footer_text': footer_text,
            'footer_show_github': footer_show_github,
            'footer_show_version': footer_show_version,
            'footer_show_admin_link': footer_show_admin_link
        }
    except:
        # Fallback if database isn't available yet
        return {
            'app_version': APP_VERSION,
            'current_year': datetime.now().year,
            'footer_enabled': True,
            'footer_text': '',
            'footer_show_github': True,
            'footer_show_version': True,
            'footer_show_admin_link': True
        }

# Get timezone from database, default to America/Chicago
def get_timezone():
    """Get the configured timezone as a ZoneInfo object."""
    try:
        conn = get_db()
        row = conn.execute("SELECT value FROM settings WHERE key = 'timezone'").fetchone()
        conn.close()
        if row:
            try:
                return ZoneInfo(row[0])
            except Exception as e:
                app.logger.warning(f"Invalid timezone '{row[0]}' in settings: {e}")
    except:
        pass
    return ZoneInfo('America/Chicago')

def get_timezone_name():
    """Get the configured timezone name (IANA string) for template selection."""
    try:
        conn = get_db()
        row = conn.execute("SELECT value FROM settings WHERE key = 'timezone'").fetchone()
        conn.close()
        if row:
            return row[0]
    except:
        pass
    return 'America/Chicago'

def local_date_to_utc_range(date_str, tz):
    """
    Convert a local date string (YYYY-MM-DD) to UTC start and end ISO strings.
    
    Args:
        date_str: Date string in YYYY-MM-DD format
        tz: ZoneInfo timezone object
    
    Returns:
        Tuple of (utc_start_iso, utc_end_iso) for filtering
    """
    try:
        # Parse the date and create start of day (00:00:00) and end of day (23:59:59.999999) in local timezone
        naive_date = datetime.strptime(date_str, '%Y-%m-%d')
        local_start = datetime(naive_date.year, naive_date.month, naive_date.day, 0, 0, 0, tzinfo=tz)
        local_end = datetime(naive_date.year, naive_date.month, naive_date.day, 23, 59, 59, 999999, tzinfo=tz)
        
        # Convert to UTC
        utc_start = local_start.astimezone(timezone.utc)
        utc_end = local_end.astimezone(timezone.utc)
        
        return utc_start.isoformat(), utc_end.isoformat()
    except Exception as e:
        app.logger.warning(f"Error converting date '{date_str}' to UTC range: {e}")
        # Return values that won't filter anything on error
        return None, None

# Developer password from environment variable for security
# Falls back to None if not set (disables developer override features)
DEVELOPER_PASSWORD = os.getenv('DEVELOPER_PASSWORD', None)

# Initialize scheduled backup
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.start()
except ImportError:
    scheduler = None
    app.logger.warning("APScheduler not installed. Scheduled backups disabled.")

def get_backup_encryption_password():
    """Get backup encryption password from settings"""
    try:
        conn = get_db()
        cur = conn.execute("SELECT value FROM settings WHERE key = 'backup_encryption_password'")
        row = cur.fetchone()
        conn.close()
        return row['value'] if row and row['value'] else None
    except:
        return None

# Initialize Backup Manager with timezone and encryption
backup_manager = BackupManager(
    db_path=str(Path(__file__).parent / 'checkin.db'),
    backup_dir=str(Path(__file__).parent / 'data' / 'backups'),
    uploads_dir=str(Path(__file__).parent / 'uploads'),
    static_uploads_dir=str(Path(__file__).parent / 'static' / 'uploads'),
    timezone=get_timezone(),
    encryption_password=get_backup_encryption_password()
)

def update_backup_manager_timezone():
    """Update backup manager timezone from database settings"""
    backup_manager.set_timezone(get_timezone())

def update_backup_manager_encryption():
    """Update backup manager encryption password from database settings"""
    backup_manager.set_encryption_password(get_backup_encryption_password())

@app.context_processor
def inject_branding():
    """Make branding settings available to all templates"""
    demo_mode = os.getenv('DEMO_MODE', 'false').lower() == 'true'
    demo_banner = None
    if demo_mode:
        conn = get_db()
        cur = conn.execute("SELECT value FROM settings WHERE key = 'demo_banner'")
        row = cur.fetchone()
        demo_banner = row['value'] if row else 'This is a demonstration instance. Data resets periodically.'
        conn.close()
    
    return {
        'branding': get_branding_settings(),
        'demo_mode': demo_mode,
        'demo_banner': demo_banner
    }

@app.before_request
def check_setup():
    """Check if initial setup is needed and redirect if necessary"""
    # Skip check for static files and setup route itself
    if request.endpoint and (request.endpoint == 'static' or request.endpoint == 'setup'):
        return
    
    # Skip setup check in demo mode - database is pre-configured
    if os.getenv('DEMO_MODE', 'false').lower() == 'true':
        return
    
    # Check if setup is complete
    try:
        conn = get_db()
        cur = conn.execute("SELECT value FROM settings WHERE key = 'is_setup_complete'")
        row = cur.fetchone()
        conn.close()
        
        is_complete = row['value'] if row else 'false'
        
        # Redirect to setup if not complete
        if is_complete != 'true':
            return redirect(url_for('setup'))
    except:
        # If database doesn't exist or there's an error, allow access to continue
        pass

def ensure_db():
    # kept for manual invocation; do not run at import time so tests can control DB_PATH
    if not DB_PATH.exists():
        init_db()
    # Run migrations to ensure schema is up to date
    ensure_adult_phone_column()

def get_app_password():
    """Get the app password from settings, or return default"""
    conn = get_db()
    cur = conn.execute("SELECT value FROM settings WHERE key = 'app_password'")
    row = cur.fetchone()
    conn.close()
    return row['value'] if row else 'changeme'

def set_app_password(password):
    """Set the app password in settings"""
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('app_password', ?)", (password,))
    conn.commit()
    conn.close()

def get_override_password():
    """Get the admin override checkout password from settings, or return app password as default"""
    conn = get_db()
    cur = conn.execute("SELECT value FROM settings WHERE key = 'admin_override_password'")
    row = cur.fetchone()
    conn.close()
    # If no override password set, fall back to app password for backward compatibility
    return row['value'] if row else get_app_password()

def set_override_password(password):
    """Set the admin override checkout password in settings"""
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_override_password', ?)", (password,))
    conn.commit()
    conn.close()

def check_authenticated():
    """Check if user is authenticated"""
    return session.get('authenticated', False)

def allowed_file(filename, allowed_extensions=None):
    """Check if file extension is allowed"""
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_EXTENSIONS
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_logo_filename():
    """Get the current logo filename from settings"""
    conn = get_db()
    cur = conn.execute("SELECT value FROM settings WHERE key = 'logo_filename'")
    row = cur.fetchone()
    conn.close()
    return row['value'] if row else None

def set_logo_filename(filename):
    """Set the logo filename in settings"""
    conn = get_db()
    if filename:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('logo_filename', ?)", (filename,))
    else:
        conn.execute("DELETE FROM settings WHERE key = 'logo_filename'")
    conn.commit()
    conn.close()

def get_favicon_filename():
    """Get the current favicon filename from settings"""
    conn = get_db()
    cur = conn.execute("SELECT value FROM settings WHERE key = 'favicon_filename'")
    row = cur.fetchone()
    conn.close()
    return row['value'] if row else None

def set_favicon_filename(filename):
    """Set the favicon filename in settings"""
    conn = get_db()
    if filename:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('favicon_filename', ?)", (filename,))
    else:
        conn.execute("DELETE FROM settings WHERE key = 'favicon_filename'")
    conn.commit()
    conn.close()

def get_branding_settings():
    """Get all branding/customization settings for templates"""
    conn = get_db()
    settings = {}
    defaults = {
        'organization_name': 'Check-In System',
        'organization_type': 'other',
        'primary_color': '#79060d',
        'secondary_color': '#003b59',
        'accent_color': '#4a582d',
        'group_term': 'Group',
        'group_term_lower': 'group',
        'favicon_filename': None,
    }
    
    for key, default in defaults.items():
        cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        settings[key] = row['value'] if row else default
    
    conn.close()
    return settings

def set_branding_setting(key, value):
    """Update a branding setting"""
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_smtp_settings():
    """Get all SMTP settings from database"""
    conn = get_db()
    settings = {}
    keys = ['smtp_server', 'smtp_port', 'smtp_from', 'smtp_username', 'smtp_password', 'smtp_use_tls']
    
    for key in keys:
        cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        settings[key] = row['value'] if row else None
    
    conn.close()
    return settings

def set_smtp_settings(smtp_dict):
    """Save SMTP settings to database"""
    conn = get_db()
    for key, value in smtp_dict.items():
        if key.startswith('smtp_') and value is not None:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def send_email(to_address, subject, html_body, plain_text_body=None, attachment_path=None, attachment_name=None):
    """Send an email using configured SMTP settings.
    
    Args:
        to_address: Recipient email address
        subject: Email subject line
        html_body: HTML content of email
        plain_text_body: Plain text fallback (optional)
        attachment_path: Path to file to attach (optional)
        attachment_name: Name for attachment (optional, defaults to filename)
    
    Returns:
        Tuple of (success, message)
    """
    try:
        smtp_settings = get_smtp_settings()
        
        # Validate SMTP settings are configured
        if not all([smtp_settings.get('smtp_server'), 
                    smtp_settings.get('smtp_port'),
                    smtp_settings.get('smtp_from'),
                    smtp_settings.get('smtp_username'),
                    smtp_settings.get('smtp_password')]):
            return False, "SMTP settings not configured. Please configure SMTP in admin settings."
        
        # Create message - use mixed if we have an attachment, alternative otherwise
        if attachment_path:
            msg = MIMEMultipart('mixed')
            msg_alt = MIMEMultipart('alternative')
            msg.attach(msg_alt)
        else:
            msg = MIMEMultipart('alternative')
            msg_alt = msg
        
        msg['Subject'] = subject
        msg['From'] = smtp_settings['smtp_from']
        msg['To'] = to_address
        
        # Attach plain text and HTML versions
        if plain_text_body:
            msg_alt.attach(MIMEText(plain_text_body, 'plain'))
        msg_alt.attach(MIMEText(html_body, 'html'))
        
        # Add attachment if provided
        if attachment_path:
            attachment_file = Path(attachment_path)
            if attachment_file.exists():
                with open(attachment_file, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    fname = attachment_name or attachment_file.name
                    part.add_header('Content-Disposition', f'attachment; filename="{fname}"')
                    msg.attach(part)
        
        # Connect to SMTP server
        use_tls = smtp_settings.get('smtp_use_tls', 'false') == 'true'
        port = int(smtp_settings.get('smtp_port', 587))
        
        if use_tls:
            server = smtplib.SMTP(smtp_settings['smtp_server'], port, timeout=10)
            server.starttls()
        else:
            # For SSL, use SMTP_SSL
            if port == 465:
                server = smtplib.SMTP_SSL(smtp_settings['smtp_server'], port, timeout=10)
            else:
                server = smtplib.SMTP(smtp_settings['smtp_server'], port, timeout=10)
        
        # Login and send
        server.login(smtp_settings['smtp_username'], smtp_settings['smtp_password'])
        server.send_message(msg)
        server.quit()
        
        return True, f"Email sent successfully to {to_address}"
    
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP Authentication failed. Check username and password."
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"

def get_event_date_range_months():
    """Get the number of months (past and future) to show events for. Default is 1 month."""
    conn = get_db()
    cur = conn.execute("SELECT value FROM settings WHERE key = 'event_date_range_months'")
    row = cur.fetchone()
    conn.close()
    
    if row and row['value']:
        try:
            return int(row['value'])
        except (ValueError, TypeError):
            return 1
    return 1

def parse_concat_list(concat_str, separator=':'):
    """Parse GROUP_CONCAT result into a list of dicts.
    
    Args:
        concat_str: String from GROUP_CONCAT like "1:name:notes,2:name2:notes2"
        separator: Field separator within each item (default ':')
    
    Returns:
        List of tuples with parsed values
    """
    if not concat_str:
        return []
    
    items = []
    for item_str in concat_str.split(','):
        parts = item_str.split(separator)
        items.append(parts)
    return items

def require_auth(f):
    """Decorator to require authentication"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not check_authenticated():
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def generate_share_token():
    """Generate a secure random token for sharing checkout codes.
    Using 6 bytes results in an 8-character URL-safe string.
    This is short enough for simple QR codes without needing an external shortener,
    while still providing sufficient entropy for temporary tokens.
    """
    return secrets.token_urlsafe(6)

def create_qr_code(url):
    """Generate a QR code image as base64 string"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for embedding in HTML
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"

def cleanup_expired_tokens():
    """Remove expired share tokens from database"""
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("DELETE FROM share_tokens WHERE expires_at < ? OR used = 1", (now,))
    conn.commit()
    conn.close()

def safe_http_get(url, timeout=10, max_size=10*1024*1024):
    """
    Perform a safe HTTP GET request with SSRF protection.
    Validates that the domain is in ALLOWED_ICAL_DOMAINS.
    """
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    
    # Basic SSRF protection: only allow whitelisted domains
    allowed = False
    for allowed_domain in ALLOWED_ICAL_DOMAINS:
        if domain == allowed_domain or domain.endswith('.' + allowed_domain):
            allowed = True
            break
            
    if not allowed:
        # Also allow localhost for testing if needed, or just fail
        # For now, strict whitelist
        raise ValueError(f"Domain {domain} is not in the allowed list")
        
    response = requests.get(url, timeout=timeout, stream=True)
    response.raise_for_status()
    
    content = b''
    for chunk in response.iter_content(chunk_size=8192):
        content += chunk
        if len(content) > max_size:
            raise ValueError("Response too large")
            
    return content

def sync_ical_events():
    """Sync events from iCal URL - can be called manually or automatically"""
    try:
        with app.app_context():
            conn = get_db()
            cur = conn.execute("SELECT value FROM settings WHERE key = 'ical_url'")
            ical_row = cur.fetchone()
            if not ical_row or not ical_row['value']:
                conn.close()
                return False, "No iCal URL set"
            ical_url = ical_row['value']
            conn.close()

            # Use safe HTTP request with SSRF protection
            content = safe_http_get(ical_url, timeout=10, max_size=10*1024*1024)
            cal = Calendar.from_ical(content.decode('utf-8'))

            conn = get_db()
            # Track events from calendar to identify which ones to keep
            calendar_events = []
            event_count = 0
            
            for component in cal.walk():
                if component.name == "VEVENT":
                    name = str(component.get('summary', 'Event'))
                    start_dt = component.get('dtstart')
                    end_dt = component.get('dtend')
                    start_time = None
                    end_time = None
                    tz = get_timezone()
                    if start_dt:
                        dt = start_dt.dt
                        if hasattr(dt, 'tzinfo') and dt.tzinfo:
                            dt = dt.astimezone(tz)
                        else:
                            dt = dt.replace(tzinfo=tz)
                        start_time = dt.isoformat()
                    if end_dt:
                        dt = end_dt.dt
                        if hasattr(dt, 'tzinfo') and dt.tzinfo:
                            dt = dt.astimezone(tz)
                        else:
                            dt = dt.replace(tzinfo=tz)
                        end_time = dt.isoformat()
                    description = str(component.get('description', ''))
                    
                    # Check if event already exists (match by name and start_time)
                    existing = conn.execute(
                        "SELECT id FROM events WHERE name = ? AND start_time = ?",
                        (name, start_time)
                    ).fetchone()
                    
                    if existing:
                        # Update existing event
                        conn.execute(
                            "UPDATE events SET end_time = ?, description = ? WHERE id = ?",
                            (end_time, description, existing['id'])
                        )
                        calendar_events.append(existing['id'])
                    else:
                        # Insert new event
                        cursor = conn.execute(
                            "INSERT INTO events (name, start_time, end_time, description) VALUES (?, ?, ?, ?)",
                            (name, start_time, end_time, description)
                        )
                        calendar_events.append(cursor.lastrowid)
                    event_count += 1
            
            # Delete events that are no longer in the calendar (but only old ones with no active check-ins)
            if calendar_events:
                placeholders = ','.join('?' * len(calendar_events))
                conn.execute(f"""
                    DELETE FROM events 
                    WHERE id NOT IN ({placeholders})
                    AND start_time < datetime('now', '-7 days')
                    AND id NOT IN (SELECT DISTINCT event_id FROM checkins WHERE checkout_time IS NULL)
                """, calendar_events)
            
            conn.commit()

            # Update last sync time
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('last_ical_sync', ?)",
                        (datetime.now(timezone.utc).isoformat(),))
            conn.commit()
            conn.close()
            return True, f"Synced {event_count} events"
    except Exception as e:
        return False, f"Error syncing: {str(e)}"

def auto_sync_ical():
    """Background thread to automatically sync iCal every hour"""
    while True:
        time.sleep(3600)  # Wait 1 hour
        try:
            sync_ical_events()
        except:
            pass  # Silently fail, will try again next hour

# Start background sync thread
sync_thread = threading.Thread(target=auto_sync_ical, daemon=True)
sync_thread.start()

@app.route('/health')
def health():
    """Health check endpoint for Docker and monitoring"""
    return jsonify({'status': 'ok'}), 200

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """First-time setup wizard"""
    # Check if setup is already complete
    conn = get_db()
    cur = conn.execute("SELECT value FROM settings WHERE key = 'is_setup_complete'")
    row = cur.fetchone()
    is_complete = row['value'] if row else 'false'
    
    if is_complete == 'true':
        # Setup already done, redirect to login
        conn.close()
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Validate required fields
        org_name = request.form.get('organization_name', '').strip()
        org_type = request.form.get('organization_type', 'other')
        group_term = request.form.get('group_term', 'Group').strip()
        event_date_range_months = request.form.get('event_date_range_months', '1')
        primary_color = request.form.get('primary_color', '#667eea')
        secondary_color = request.form.get('secondary_color', '#764ba2')
        accent_color = request.form.get('accent_color', '#48bb78')
        admin_password = request.form.get('admin_password', '').strip()
        admin_password_confirm = request.form.get('admin_password_confirm', '').strip()
        
        # Validate
        errors = []
        if not org_name:
            errors.append('Organization name is required')
        if len(admin_password) < 4:
            errors.append('Admin password must be at least 4 characters')
        if admin_password != admin_password_confirm:
            errors.append('Admin passwords do not match')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            conn.close()
            return render_template('setup.html')
        
        # Save organization settings
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('organization_name', ?)", (org_name,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('organization_type', ?)", (org_type,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('group_term', ?)", (group_term,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('group_term_lower', ?)", (group_term.lower(),))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('event_date_range_months', ?)", (event_date_range_months,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('primary_color', ?)", (primary_color,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('secondary_color', ?)", (secondary_color,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('accent_color', ?)", (accent_color,))
        
        # Handle favicon upload if provided
        if 'favicon' in request.files:
            file = request.files['favicon']
            if file and file.filename and allowed_file(file.filename, allowed_extensions={'png', 'jpg', 'jpeg', 'ico'}):
                filename = secure_filename(file.filename)
                name, ext = os.path.splitext(filename)
                filename = f"favicon_{int(time.time())}{ext}"
                filepath = app.config['UPLOAD_FOLDER'] / filename
                file.save(str(filepath))
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('favicon_filename', ?)", (filename,))
        
        # Handle logo upload if provided
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                name, ext = os.path.splitext(filename)
                filename = f"logo_{int(time.time())}{ext}"
                filepath = app.config['UPLOAD_FOLDER'] / filename
                file.save(str(filepath))
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('logo_filename', ?)", (filename,))
        
        # Set admin password (store as plain text for now, matching existing pattern)
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('app_password', ?)", (admin_password,))
        
        # Mark setup as complete
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('is_setup_complete', ?)", ('true',))
        conn.commit()
        conn.close()
        
        flash('Setup completed successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    
    conn.close()
    return render_template('setup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        app_password = get_app_password()

        # Check against app password or developer password
        if password == app_password or password == DEVELOPER_PASSWORD:
            session['authenticated'] = True
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('index'))
        else:
            flash('Incorrect password. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@require_auth
def index():
    event_id = request.args.get('event_id')
    if not event_id:
        # Redirect to select event
        conn = get_db()
        months = get_event_date_range_months()
        cur = conn.execute(f"""
            SELECT id, name FROM events
            WHERE start_time >= datetime('now', '-{months} month') AND start_time <= datetime('now', '+{months} month')
            ORDER BY ABS(strftime('%s', start_time) - strftime('%s', 'now')) ASC
            LIMIT 1
        """)
        default_event = cur.fetchone()
        conn.close()
        if default_event:
            return redirect(url_for('index', event_id=default_event['id']))
        else:
            flash('No events available. Please add events in admin.', 'warning')
            return redirect(url_for('admin_index'))

    conn = get_db()
    cur = conn.execute("""
        SELECT c.id, k.id as kid_id, c.checkin_time, c.checkout_time, k.name as kid_name, k.notes as kid_notes,
               f.authorized_adults, f.phone, f.troop, a.name as adult_name
        FROM checkins c
        JOIN kids k ON c.kid_id = k.id
        JOIN families f ON k.family_id = f.id
        JOIN adults a ON c.adult_id = a.id
        WHERE c.checkout_time IS NULL AND c.event_id = ?
        ORDER BY c.checkin_time DESC
    """, (event_id,))
    checked_in = cur.fetchall()

    # Convert to dicts and format times
    checked_in = [dict(r) for r in checked_in]
    for checkin in checked_in:
        dt = datetime.fromisoformat(checkin['checkin_time']).replace(tzinfo=timezone.utc).astimezone(get_timezone())
        checkin['formatted_time'] = dt.strftime('%b %d %I:%M %p')

    months = get_event_date_range_months()
    cur2 = conn.execute(f"SELECT id, name, start_time FROM events WHERE start_time >= datetime('now', '-{months} month') AND start_time <= datetime('now', '+{months} month') ORDER BY start_time DESC")
    events = cur2.fetchall()
    
    # Get require_codes setting
    setting = conn.execute("SELECT value FROM settings WHERE key = 'require_checkout_code'").fetchone()
    require_codes = setting and setting[0] == 'true'
    
    conn.close()

    # Check if TLC is configured (for UI button)
    tlc_configured = 'tlc_email' in session and 'tlc_password' in session

    return render_template('index.html', checked_in=checked_in, events=events, current_event_id=int(event_id), require_codes=require_codes, tlc_configured=tlc_configured)

@app.route('/checkin_last4', methods=['POST'])
@require_auth
def checkin_last4():
    phone_digits = request.form.get('last4', '').strip()
    event_id = request.form.get('event_id')
    if not phone_digits:
        return jsonify({'error': 'Invalid input'}), 400
    
    conn = get_db()
    
    # First, check if this is a checkout code (before checking phone numbers)
    # Checkout codes are alphanumeric and stored in checkins table
    if len(phone_digits) >= 4:
        checkout_match = conn.execute("""
            SELECT c.id as checkin_id, c.kid_id, c.event_id, c.checkout_code, c.checkout_time,
                   k.name as kid_name, k.family_id, f.phone as family_phone
            FROM checkins c
            JOIN kids k ON k.id = c.kid_id
            JOIN families f ON f.id = k.family_id
            WHERE c.checkout_code = ? AND c.checkout_time IS NULL
        """, (phone_digits,)).fetchall()
        
        if checkout_match:
            # This is a checkout code! Return checkout info instead of family search
            kids_to_checkout = []
            family_id = None
            family_phone = None
            event_id_from_checkin = None
            
            for row in checkout_match:
                kids_to_checkout.append({
                    'checkin_id': row['checkin_id'],
                    'kid_id': row['kid_id'],
                    'kid_name': row['kid_name']
                })
                family_id = row['family_id']
                family_phone = row['family_phone']
                event_id_from_checkin = row['event_id']
            
            conn.close()
            return jsonify({
                'is_checkout_code': True,
                'checkout_code': phone_digits,
                'family_id': family_id,
                'family_phone': family_phone,
                'event_id': event_id_from_checkin,
                'kids': kids_to_checkout
            })
    
    # Not a checkout code, proceed with phone number search
    if not phone_digits.isdigit():
        conn.close()
        return jsonify({'error': 'Invalid phone number'}), 400
    
    # Search for phone in both families table and adults table
    # Using REPLACE to remove common phone formatting characters
    # Match only if the phone ENDS with the entered digits (last 4)
    cur = conn.execute("""
        SELECT DISTINCT f.id, f.phone, f.troop, f.default_adult_id,
               (SELECT GROUP_CONCAT(a.id || ':' || a.name || ':' || COALESCE(a.phone, ''))
                FROM adults a WHERE a.family_id = f.id) as adults,
               (SELECT GROUP_CONCAT(k.id || ':' || k.name || ':' || COALESCE(k.notes, ''))
                FROM kids k WHERE k.family_id = f.id) as kids,
               (SELECT a.id FROM adults a WHERE a.family_id = f.id 
                AND (REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(a.phone, '-', ''), ' ', ''), '(', ''), ')', ''), '.', '') LIKE ?
                     OR REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(a.phone, '-', ''), ' ', ''), '(', ''), ')', ''), '.', '') = ?)
                LIMIT 1) as matched_adult_id
        FROM families f
        LEFT JOIN adults a ON a.family_id = f.id
        WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(f.phone, '-', ''), ' ', ''), '(', ''), ')', ''), '.', '') LIKE ?
           OR REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(f.phone, '-', ''), ' ', ''), '(', ''), ')', ''), '.', '') = ?
           OR REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(a.phone, '-', ''), ' ', ''), '(', ''), ')', ''), '.', '') LIKE ?
           OR REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(a.phone, '-', ''), ' ', ''), '(', ''), ')', ''), '.', '') = ?
    """, ('%' + phone_digits, phone_digits, '%' + phone_digits, phone_digits, '%' + phone_digits, phone_digits))
    families = cur.fetchall()
    
    if not families:
        conn.close()
        return jsonify({'error': 'No family found with that phone number'}), 404
    
    # Helper function to parse family data
    def parse_family_data(family):
        # Parse concatenated adult and kid data (now includes phone)
        adults_list = parse_concat_list(family['adults'], ':') if family['adults'] else []
        adults = []
        for adult_parts in adults_list:
            if len(adult_parts) >= 2:
                adults.append({
                    'id': int(adult_parts[0]), 
                    'name': adult_parts[1],
                    'phone': adult_parts[2] if len(adult_parts) > 2 else ''
                })
        
        kids_list = parse_concat_list(family['kids'], ':') if family['kids'] else []
        kids = []
        for kid_parts in kids_list:
            if len(kid_parts) >= 2:
                kid_id = int(kid_parts[0]) if kid_parts[0].isdigit() else None
                if kid_id:
                    kids.append({
                        'id': kid_id, 
                        'name': kid_parts[1], 
                        'notes': kid_parts[2] if len(kid_parts) > 2 else ''
                    })
        
        # Check which kids are already checked in to this event (if provided)
        if event_id and kids:
            kid_ids = [k['id'] for k in kids]
            placeholders = ','.join('?' * len(kid_ids))
            checked_in_cur = conn.execute(f"""
                SELECT kid_id FROM checkins 
                WHERE kid_id IN ({placeholders}) AND event_id = ? AND checkout_time IS NULL
            """, kid_ids + [event_id])
            checked_in_kids = {row[0] for row in checked_in_cur.fetchall()}
            
            # Mark kids as already checked in
            for kid in kids:
                kid['already_checked_in'] = kid['id'] in checked_in_kids
        
        # If an adult's phone was matched, use that adult as default
        matched_adult_id = family['matched_adult_id'] if 'matched_adult_id' in family.keys() and family['matched_adult_id'] else None
        default_adult = matched_adult_id if matched_adult_id else family['default_adult_id']
        
        return {
            'family_id': family['id'],
            'phone': family['phone'],
            'troop': family['troop'],
            'default_adult_id': default_adult,
            'adults': adults,
            'kids': kids
        }
    
    # If multiple matches, return all of them (like search_name does)
    if len(families) > 1:
        families_data = [parse_family_data(f) for f in families]
        conn.close()
        return jsonify({'families': families_data})
    
    # Single match - return family data directly
    family_data = parse_family_data(families[0])
    conn.close()
    
    return jsonify(family_data)


@app.route('/search_name', methods=['POST'])
@require_auth
def search_name():
    """Search families by kid or adult name (partial match). Returns similar structure to checkin_last4 for the first match or an array of families."""
    name = request.form.get('name', '').strip()
    event_id = request.form.get('event_id')
    if not name:
        return jsonify({'error': 'Name required'}), 400

    likeparam = f"%{name}%"
    conn = get_db()
    cur = conn.execute("""
        SELECT f.id, f.phone, f.troop, f.default_adult_id,
               (SELECT GROUP_CONCAT(a.id || ':' || a.name)
                FROM adults a WHERE a.family_id = f.id) as adults,
               (SELECT GROUP_CONCAT(k.id || ':' || k.name || ':' || COALESCE(k.notes, ''))
                FROM kids k WHERE k.family_id = f.id) as kids
        FROM families f
        WHERE EXISTS (SELECT 1 FROM kids k WHERE k.family_id = f.id AND k.name LIKE ? COLLATE NOCASE)
           OR EXISTS (SELECT 1 FROM adults a WHERE a.family_id = f.id AND a.name LIKE ? COLLATE NOCASE)
        LIMIT 20
    """, (likeparam, likeparam))
    families = cur.fetchall()

    if not families:
        conn.close()
        return jsonify({'families': []})

    # Get all family IDs first
    family_ids = [family['id'] for family in families]
    
    # Get all checked-in kids for this event in a single query (if provided)
    checked_in_kids = set()
    if event_id and family_ids:
        placeholders = ','.join('?' * len(family_ids))
        checked_in_cur = conn.execute(f"""
            SELECT DISTINCT c.kid_id
            FROM checkins c
            JOIN kids k ON c.kid_id = k.id
            WHERE k.family_id IN ({placeholders})
            AND c.event_id = ? AND c.checkout_time IS NULL
        """, family_ids + [event_id])
        checked_in_kids = {row[0] for row in checked_in_cur.fetchall()}

    # Build a list of family objects similar to checkin_last4
    results = []
    for family in families:
        # Parse concatenated adult and kid data
        adults_list = parse_concat_list(family['adults'], ':') if family['adults'] else []
        adults = []
        for adult_parts in adults_list:
            if len(adult_parts) >= 2:
                adults.append({'id': int(adult_parts[0]), 'name': adult_parts[1]})
        
        kids_list = parse_concat_list(family['kids'], ':') if family['kids'] else []
        kids = []
        for kid_parts in kids_list:
            if len(kid_parts) >= 2:
                kid_id = int(kid_parts[0]) if kid_parts[0].isdigit() else None
                if kid_id:
                    kids.append({
                        'id': kid_id, 
                        'name': kid_parts[1], 
                        'notes': kid_parts[2] if len(kid_parts) > 2 else ''
                    })

        # Mark kids as already checked in
        if event_id:
            for kid in kids:
                kid['already_checked_in'] = kid['id'] in checked_in_kids

        results.append({
            'family_id': family['id'],
            'phone': family['phone'],
            'troop': family['troop'],
            'default_adult_id': family['default_adult_id'],
            'adults': adults,
            'kids': kids
        })

    conn.close()
    # Return array of matches; client will handle single vs multiple
    return jsonify({'families': results})


@app.route('/checkout-page')
@require_auth
def checkout_page():
    """Dedicated checkout page with all checked-in children displayed, with search to filter"""
    event_id = request.args.get('event_id')
    if not event_id:
        # Redirect to select event
        conn = get_db()
        months = get_event_date_range_months()
        cur = conn.execute(f"""
            SELECT id, name FROM events
            WHERE start_time >= datetime('now', '-{months} month') AND start_time <= datetime('now', '+{months} month')
            ORDER BY ABS(strftime('%s', start_time) - strftime('%s', 'now')) ASC
            LIMIT 1
        """)
        default_event = cur.fetchone()
        conn.close()
        if default_event:
            return redirect(url_for('checkout_page', event_id=default_event['id']))
        else:
            flash('No events available. Please add events in admin.', 'warning')
            return redirect(url_for('admin_index'))

    conn = get_db()
    
    # Get all checked-in children for this event
    cur = conn.execute("""
        SELECT DISTINCT k.id as kid_id, k.name as kid_name, k.notes as kid_notes,
               f.id as family_id, f.phone, f.authorized_adults,
               a.name as adult_name, c.checkin_time, c.checkout_code, c.id as checkin_id
        FROM kids k
        JOIN checkins c ON c.kid_id = k.id
        JOIN families f ON k.family_id = f.id
        JOIN adults a ON c.adult_id = a.id
        WHERE c.event_id = ? 
          AND c.checkout_time IS NULL
        ORDER BY k.name
    """, (event_id,))
    checked_in_children = cur.fetchall()
    
    # Convert to list of dicts and format times
    children = []
    for row in checked_in_children:
        dt = datetime.fromisoformat(row['checkin_time']).replace(tzinfo=timezone.utc).astimezone(get_timezone())
        formatted_time = dt.strftime('%b %d %I:%M %p')
        
        children.append({
            'kid_id': row['kid_id'],
            'kid_name': row['kid_name'],
            'kid_notes': row['kid_notes'] or '',
            'family_id': row['family_id'],
            'phone': row['phone'] or '',
            'authorized_adults': row['authorized_adults'] or '',
            'adult_name': row['adult_name'],
            'checkin_time': row['checkin_time'],
            'formatted_time': formatted_time,
            'checkout_code': row['checkout_code'] or '',
            'checkin_id': row['checkin_id']
        })
    
    # Get all events for dropdown
    months = get_event_date_range_months()
    cur2 = conn.execute(f"SELECT id, name, start_time FROM events WHERE start_time >= datetime('now', '-{months} month') AND start_time <= datetime('now', '+{months} month') ORDER BY start_time DESC")
    events = cur2.fetchall()
    
    # Get require_codes setting
    setting = conn.execute("SELECT value FROM settings WHERE key = 'require_checkout_code'").fetchone()
    require_codes = setting and setting[0] == 'true'
    
    conn.close()

    # Check if TLC is configured (for UI button)
    tlc_configured = 'tlc_email' in session and 'tlc_password' in session

    return render_template('checkout.html', events=events, current_event_id=int(event_id), require_codes=require_codes, tlc_configured=tlc_configured, checked_in_children=children)


@app.route('/search_checked_in', methods=['POST'])
@require_auth
def search_checked_in():
    """Search for checked-in children by name or phone number (last 4 digits)"""
    query = request.form.get('query', '').strip()
    event_id = request.form.get('event_id')
    
    if not query:
        return jsonify({'error': 'Search query required'}), 400
    
    if not event_id:
        return jsonify({'error': 'Event ID required'}), 400
    
    conn = get_db()
    
    # Detect if query is numeric (phone search) or text (name search)
    is_phone_search = query.isdigit()
    
    if is_phone_search:
        # Phone search - search for families/adults where phone ends with digits AND kids are checked in
        likeparam = f"%{query}"
        cur = conn.execute("""
            SELECT DISTINCT k.id as kid_id, k.name as kid_name, k.notes as kid_notes,
                   f.id as family_id, f.phone, f.authorized_adults,
                   a.name as adult_name, c.checkin_time, c.checkout_code, c.id as checkin_id
            FROM kids k
            JOIN checkins c ON c.kid_id = k.id
            JOIN families f ON k.family_id = f.id
            JOIN adults a ON c.adult_id = a.id
            LEFT JOIN adults auth_adults ON auth_adults.family_id = f.id
            WHERE c.event_id = ? 
              AND c.checkout_time IS NULL
              AND (REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(f.phone, '-', ''), ' ', ''), '(', ''), ')', ''), '.', '') LIKE ?
                   OR REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(auth_adults.phone, '-', ''), ' ', ''), '(', ''), ')', ''), '.', '') LIKE ?)
            ORDER BY k.name
        """, (event_id, likeparam, likeparam))
    else:
        # Name search - search kids/adults by name (partial match) WHERE checked in
        likeparam = f"%{query}%"
        cur = conn.execute("""
            SELECT DISTINCT k.id as kid_id, k.name as kid_name, k.notes as kid_notes,
                   f.id as family_id, f.phone, f.authorized_adults,
                   a.name as adult_name, c.checkin_time, c.checkout_code, c.id as checkin_id
            FROM kids k
            JOIN checkins c ON c.kid_id = k.id
            JOIN families f ON k.family_id = f.id
            JOIN adults a ON c.adult_id = a.id
            WHERE c.event_id = ? 
              AND c.checkout_time IS NULL
              AND k.name LIKE ? COLLATE NOCASE
            ORDER BY k.name
            LIMIT 50
        """, (event_id, likeparam))
    
    results = cur.fetchall()
    conn.close()
    
    if not results:
        return jsonify({'children': []})
    
    # Convert to list of dicts and format times
    children = []
    for row in results:
        dt = datetime.fromisoformat(row['checkin_time']).replace(tzinfo=timezone.utc).astimezone(get_timezone())
        formatted_time = dt.strftime('%b %d %I:%M %p')
        
        children.append({
            'kid_id': row['kid_id'],
            'kid_name': row['kid_name'],
            'kid_notes': row['kid_notes'] or '',
            'family_id': row['family_id'],
            'phone': row['phone'] or '',
            'authorized_adults': row['authorized_adults'] or '',
            'adult_name': row['adult_name'],
            'checkin_time': row['checkin_time'],
            'formatted_time': formatted_time,
            'checkout_code': row['checkout_code'] or '',
            'checkin_id': row['checkin_id']
        })
    
    return jsonify({'children': children})


@app.route('/admin/backup_db')
@require_auth
def admin_backup_db():
    """Create and return a zip containing the database and uploads/data directories (if present)."""
    # Use in-memory zip if small, otherwise temporary file
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    tmpdir = tempfile.mkdtemp(prefix='youth_checkin_backup_')
    zip_path = Path(tmpdir) / f'youth-secure-checkin-backup-{timestamp}.zip'

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add the main SQLite DB
            try:
                if DB_PATH.exists():
                    zf.write(str(DB_PATH), arcname='checkin.db')
            except Exception:
                pass

            # Add data directory contents (if any)
            data_dir = Path(__file__).parent / 'data'
            if data_dir.exists():
                for root, dirs, files in os.walk(data_dir):
                    for f in files:
                        full = os.path.join(root, f)
                        arc = os.path.relpath(full, start=Path(__file__).parent)
                        zf.write(full, arcname=arc)

            # Add uploads if present
            uploads_dir = Path(__file__).parent / 'uploads'
            if uploads_dir.exists():
                for root, dirs, files in os.walk(uploads_dir):
                    for f in files:
                        full = os.path.join(root, f)
                        arc = os.path.relpath(full, start=Path(__file__).parent)
                        zf.write(full, arcname=arc)

        # Schedule cleanup of tempdir after short delay
        def _cleanup(path):
            time.sleep(60)
            try:
                shutil.rmtree(path)
            except Exception:
                pass
        threading.Thread(target=_cleanup, args=(tmpdir,), daemon=True).start()

        return send_file(str(zip_path), as_attachment=True, download_name=f'youth-secure-checkin-backup-{timestamp}.zip')
    except Exception as e:
        # cleanup on error
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass
        return jsonify({'error': 'Backup failed', 'details': str(e)}), 500

@app.route('/admin/restore_db', methods=['POST'])
@require_auth
def admin_restore_db():
    """Restore database from uploaded backup zip file."""
    if 'backup_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('admin_utilities'))
    
    backup_file = request.files['backup_file']
    if backup_file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('admin_utilities'))
    
    if not backup_file.filename.endswith('.zip'):
        flash('File must be a .zip backup file', 'error')
        return redirect(url_for('admin_utilities'))
    
    tmpdir = tempfile.mkdtemp(prefix='youth_checkin_restore_')
    try:
        # Save uploaded file
        zip_path = Path(tmpdir) / 'backup.zip'
        backup_file.save(str(zip_path))
        
        # Extract and validate
        extract_dir = Path(tmpdir) / 'extracted'
        extract_dir.mkdir()
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(str(extract_dir))
        
        # Check for checkin.db in extracted files
        db_file = extract_dir / 'checkin.db'
        if not db_file.exists():
            flash('Invalid backup file: checkin.db not found', 'error')
            shutil.rmtree(tmpdir)
            return redirect(url_for('admin_utilities'))
        
        # Backup current database before replacing
        app_root = Path(__file__).parent
        current_backup_name = f'checkin-before-restore-{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}.db'
        if DB_PATH.exists():
            shutil.copy2(str(DB_PATH), str(app_root / current_backup_name))
        
        # Replace database
        shutil.copy2(str(db_file), str(DB_PATH))
        
        # Restore data directory if present in backup
        data_backup = extract_dir / 'data'
        if data_backup.exists():
            data_dir = app_root / 'data'
            # Clear existing data dir contents (except the DB we just restored)
            if data_dir.exists():
                for item in data_dir.iterdir():
                    if item.name != 'checkin.db':
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)
            else:
                data_dir.mkdir(exist_ok=True)
            
            # Copy restored data
            for item in data_backup.iterdir():
                if item.name != 'checkin.db':  # Skip DB, already restored
                    dest = data_dir / item.name
                    if item.is_file():
                        shutil.copy2(item, dest)
                    elif item.is_dir():
                        shutil.copytree(item, dest, dirs_exist_ok=True)
        
        # Restore uploads directory if present in backup
        uploads_backup = extract_dir / 'uploads'
        if uploads_backup.exists():
            uploads_dir = app_root / 'uploads'
            if uploads_dir.exists():
                shutil.rmtree(uploads_dir)
            shutil.copytree(uploads_backup, uploads_dir)
        
        # Cleanup temp directory
        shutil.rmtree(tmpdir)
        
        flash(f'Database restored successfully! Previous database saved as {current_backup_name}', 'success')
        return redirect(url_for('admin_utilities'))
        
    except Exception as e:
        # Cleanup on error
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass
        flash(f'Restore failed: {str(e)}', 'error')
        return redirect(url_for('admin_utilities'))

@app.route('/checkin_selected', methods=['POST'])
@require_auth
def checkin_selected():
    family_id = request.form.get('family_id')
    adult_id = request.form.get('adult_id')
    kid_ids = request.form.getlist('kid_ids')
    event_id = request.form.get('event_id')
    if not family_id or not adult_id or not kid_ids or not event_id:
        return jsonify({'success': False, 'message': 'Missing data'}), 400
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    # Check if checkout codes are enabled and get method
    require_codes_setting = conn.execute("SELECT value FROM settings WHERE key = 'require_checkout_code'").fetchone()
    require_codes = require_codes_setting and require_codes_setting[0] == 'true'
    
    checkout_method_setting = conn.execute("SELECT value FROM settings WHERE key = 'checkout_code_method'").fetchone()
    checkout_method = checkout_method_setting[0] if checkout_method_setting else 'qr'  # Default to QR
    
    # Get label printer settings if printing is needed
    label_size = '30336'  # Default
    if require_codes and checkout_method in ['label', 'both'] and LABEL_PRINTING_AVAILABLE:
        printer_type = conn.execute("SELECT value FROM settings WHERE key = 'label_printer_type'").fetchone()
        label_size_setting = conn.execute("SELECT value FROM settings WHERE key = 'label_size'").fetchone()
        printer_type = printer_type[0] if printer_type else 'dymo'
        label_size = label_size_setting[0] if label_size_setting else '30336'
        
        # Get event info for label
        event_row = conn.execute("SELECT name, start_time FROM events WHERE id = ?", (event_id,)).fetchone()
        event_name = event_row[0] if event_row else "Event"
        event_date = event_row[1][:10] if event_row else datetime.now().strftime('%Y-%m-%d')
    
    checked_in_count = 0
    labels_to_print = []  # Collect label data for client-side printing
    checked_in_data = []  # Collect check-in data for UI update
    kid_names_for_label = []  # Collect names for combined label
    
    # Get family info for the response
    family_row = conn.execute("""
        SELECT f.phone, f.troop, f.authorized_adults,
               a.name as adult_name
        FROM families f
        JOIN adults a ON a.id = ?
        WHERE f.id = ?
    """, (adult_id, family_id)).fetchone()
    
    adult_name = family_row['adult_name'] if family_row else 'Unknown'
    phone = family_row['phone'] if family_row else ''
    authorized_adults = family_row['authorized_adults'] if family_row else ''
    
    # Check if this family already has a checkout code for this event from previous check-ins
    family_checkout_code = None
    if require_codes:
        # Look for existing checkout code for this family/event combination
        existing_code = conn.execute("""
            SELECT DISTINCT c.checkout_code 
            FROM checkins c
            JOIN kids k ON k.id = c.kid_id
            WHERE k.family_id = ? AND c.event_id = ? AND c.checkout_time IS NULL AND c.checkout_code IS NOT NULL
            LIMIT 1
        """, (family_id, event_id)).fetchone()
        
        if existing_code and existing_code[0]:
            # Reuse existing code for siblings checked in separately
            family_checkout_code = existing_code[0]
        else:
            # Generate new code if none exists
            try:
                family_checkout_code = generate_unique_code(int(event_id), str(DB_PATH))
            except Exception as e:
                print(f"Error generating checkout code: {e}")
                family_checkout_code = None
    
    for kid_id in kid_ids:
        # Check if already checked in to this event
        cur = conn.execute("SELECT id FROM checkins WHERE kid_id = ? AND event_id = ? AND checkout_time IS NULL", (kid_id, event_id))
        if cur.fetchone():
            continue
        
        # Insert check-in with the SAME family code for all kids
        cursor = conn.execute("INSERT INTO checkins (kid_id, adult_id, event_id, checkin_time, checkout_code) VALUES (?, ?, ?, ?, ?)", 
                    (kid_id, adult_id, event_id, now, family_checkout_code))
        checkin_id = cursor.lastrowid
        checked_in_count += 1
        
        # Get kid data for response
        kid_row = conn.execute("SELECT name, notes FROM kids WHERE id = ?", (kid_id,)).fetchone()
        kid_name = kid_row['name'] if kid_row else "Unknown"
        kid_notes = kid_row['notes'] if kid_row else ''
        
        # Convert UTC to configured timezone for display
        utc_time = datetime.fromisoformat(now).replace(tzinfo=timezone.utc)
        local_time = utc_time.astimezone(get_timezone())
        checkin_time = local_time.strftime('%I:%M %p')
        formatted_time = local_time.strftime('%b %d %I:%M %p')
        
        # Add to checked-in data for UI update
        checked_in_data.append({
            'id': checkin_id,
            'kid_id': int(kid_id),
            'kid_name': kid_name,
            'kid_notes': kid_notes,
            'adult_name': adult_name,
            'phone': phone,
            'authorized_adults': authorized_adults,
            'formatted_time': formatted_time
        })
        
        # Collect kid names for combined label
        kid_names_for_label.append(kid_name)
    
    # Create a single combined label if multiple kids checked in together
    if family_checkout_code and checkout_method in ['label', 'both'] and len(kid_names_for_label) > 0:
        try:
            # Combine all kid names for the label (comma separated)
            combined_names = ', '.join(kid_names_for_label)
            
            # Convert UTC to configured timezone for display
            utc_time = datetime.fromisoformat(now).replace(tzinfo=timezone.utc)
            local_time = utc_time.astimezone(get_timezone())
            checkin_time = local_time.strftime('%I:%M %p')
            
            # Add single label with all names
            labels_to_print.append({
                'kid_name': combined_names,
                'event_name': event_name,
                'event_date': event_date,
                'checkin_time': checkin_time,
                'checkout_code': family_checkout_code
            })
        except Exception as e:
            print(f"Error preparing label data: {e}")
    
    conn.commit()
    
    # Generate share token and QR code ONLY if codes are required and method includes QR
    share_token = None
    qr_code_data = None
    short_url = None
    if require_codes and checkout_method in ['qr', 'both'] and checked_in_data and len(checked_in_data) > 0 and any(c['id'] for c in checked_in_data):
        share_token = generate_share_token()
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        checkin_ids = ','.join([str(c['id']) for c in checked_in_data])
        
        conn.execute("""
            INSERT INTO share_tokens (token, family_id, event_id, checkin_ids, created_at, expires_at, used)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (share_token, family_id, event_id, checkin_ids, now, expires_at))
        conn.commit()
        
        # Generate QR code URL
        share_url = url_for('share_codes', token=share_token, _external=True)
        qr_code_data = create_qr_code(share_url)
    
    conn.close()
    
    # Return response with label data for client-side printing and check-in data for UI
    return jsonify({
        'success': True, 
        'message': f'Checked in {checked_in_count} kid(s)',
        'labels': labels_to_print,
        'label_size': label_size,
        'checkins': checked_in_data,
        'share_token': share_token,
        'qr_code': qr_code_data,
        'short_url': short_url,
        'checkout_code': family_checkout_code
    })

@app.route('/checkout/<int:kid_id>', methods=['POST'])
@require_auth
def checkout(kid_id):
    event_id = request.form.get('event_id')
    checkout_code = request.form.get('checkout_code', '').strip()
    additional_kid_ids = request.form.getlist('additional_kid_ids')  # Get additional kids to checkout
    
    if not event_id:
        return jsonify({'success': False, 'message': 'Missing event_id'}), 400
    
    # Combine primary kid with additional kids
    all_kid_ids = [kid_id] + [int(kid) for kid in additional_kid_ids if kid]
    
    conn = get_db()
    
    # Check if codes are required
    setting = conn.execute("SELECT value FROM settings WHERE key = 'require_checkout_code'").fetchone()
    require_codes = setting and setting[0] == 'true'
    
    # If codes are required, verify the code or admin override password
    if require_codes:
        if not checkout_code:
            conn.close()
            return jsonify({'success': False, 'message': 'Checkout code required', 'code_required': True}), 400
        
        # Check if it's the admin override password
        override_password = get_override_password()
        is_admin_password = (checkout_code == override_password or checkout_code == DEVELOPER_PASSWORD)
        
        if not is_admin_password:
            # Verify the checkout code matches for the primary kid
            checkin = conn.execute("""
                SELECT checkout_code FROM checkins 
                WHERE kid_id = ? AND event_id = ? AND checkout_time IS NULL
            """, (kid_id, event_id)).fetchone()
            
            if not checkin:
                conn.close()
                return jsonify({'success': False, 'message': 'Check-in not found'}), 404
            
            if checkin[0] != checkout_code:
                conn.close()
                return jsonify({'success': False, 'message': 'Invalid checkout code', 'code_required': True}), 403
    
    # Perform checkout for all selected kids
    now = datetime.now(timezone.utc).isoformat()
    checked_out_count = 0
    checkin_ids = []
    
    for current_kid_id in all_kid_ids:
        # Get the checkin_id
        checkin_row = conn.execute("""
            SELECT id FROM checkins 
            WHERE kid_id = ? AND event_id = ? AND checkout_time IS NULL
        """, (current_kid_id, event_id)).fetchone()
        
        if checkin_row:
            checkin_ids.append(checkin_row['id'])
            conn.execute("UPDATE checkins SET checkout_time = ? WHERE kid_id = ? AND event_id = ? AND checkout_time IS NULL", 
                        (now, current_kid_id, event_id))
            checked_out_count += 1
    
    # Mark share token as used if all kids are checked out
    if checkin_ids:
        # Find tokens containing any of these checkins
        tokens = conn.execute("""
            SELECT id, checkin_ids FROM share_tokens 
            WHERE used = 0
        """).fetchall()
        
        for token in tokens:
            token_checkin_ids = token['checkin_ids'].split(',')
            # Check if any of our checked out kids are in this token
            has_overlap = any(str(cid) in token_checkin_ids for cid in checkin_ids)
            if has_overlap:
                # Check if all checkins in this token are now checked out
                all_checked_out = True
                for cid in token_checkin_ids:
                    check = conn.execute("""
                        SELECT checkout_time FROM checkins WHERE id = ?
                    """, (cid,)).fetchone()
                    if check and not check['checkout_time']:
                        all_checked_out = False
                        break
                
                # Mark token as used if all kids are checked out
                if all_checked_out:
                    conn.execute("UPDATE share_tokens SET used = 1 WHERE id = ?", (token['id'],))
    
    conn.commit()
    conn.close()
    
    # Return JSON if it's an AJAX request, otherwise redirect
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': f'Checked out {checked_out_count} kid(s) successfully'})
    return redirect(request.referrer or url_for('kiosk'))

@app.route('/get_siblings/<int:kid_id>', methods=['POST'])
@require_auth
def get_siblings(kid_id):
    """Get checked-in siblings for a kid to allow group checkout"""
    event_id = request.form.get('event_id')
    
    if not event_id:
        return jsonify({'success': False, 'message': 'Missing event_id'}), 400
    
    conn = get_db()
    
    # Get the family_id for this kid
    kid_row = conn.execute("SELECT family_id, name FROM kids WHERE id = ?", (kid_id,)).fetchone()
    
    if not kid_row:
        conn.close()
        return jsonify({'success': False, 'message': 'Kid not found'}), 404
    
    family_id = kid_row['family_id']
    kid_name = kid_row['name']
    
    # Get all siblings checked in to this event (excluding the current kid)
    siblings = conn.execute("""
        SELECT k.id, k.name
        FROM kids k
        JOIN checkins c ON c.kid_id = k.id
        WHERE k.family_id = ? AND k.id != ? AND c.event_id = ? AND c.checkout_time IS NULL
        ORDER BY k.name
    """, (family_id, kid_id, event_id)).fetchall()
    
    conn.close()
    
    sibling_list = [{'kid_id': s['id'], 'name': s['name']} for s in siblings]
    
    return jsonify({
        'success': True,
        'kid_name': kid_name,
        'siblings': sibling_list
    })

@app.route('/share/<token>')
def share_codes(token):
    """Display checkout codes for a family's check-ins with Web Share API support"""
    cleanup_expired_tokens()  # Clean up old tokens first
    
    conn = get_db()
    
    # Get token data
    token_data = conn.execute("""
        SELECT st.*, e.name as event_name, e.start_time
        FROM share_tokens st
        JOIN events e ON e.id = st.event_id
        WHERE st.token = ? AND st.used = 0 AND st.expires_at > ?
    """, (token, datetime.now(timezone.utc).isoformat())).fetchone()
    
    if not token_data:
        conn.close()
        return render_template('share_expired.html'), 404
    
    # Get checkin details - all kids share the same code
    checkin_ids = token_data['checkin_ids'].split(',')
    kids = []
    family_code = None
    checkin_time = None
    all_checked_out = True
    
    for checkin_id in checkin_ids:
        checkin = conn.execute("""
            SELECT c.checkout_code, c.checkin_time, c.checkout_time,
                   k.name as kid_name
            FROM checkins c
            JOIN kids k ON k.id = c.kid_id
            WHERE c.id = ?
        """, (checkin_id,)).fetchone()
        
        if checkin:
            # Get the family code from the first checkin (they're all the same)
            if not family_code:
                family_code = checkin['checkout_code']
                # Convert UTC to local time
                utc_time = datetime.fromisoformat(checkin['checkin_time']).replace(tzinfo=timezone.utc)
                checkin_time = utc_time.astimezone(get_timezone()).strftime('%I:%M %p')
            
            kids.append({
                'name': checkin['kid_name'],
                'checked_out': checkin['checkout_time'] is not None
            })
            
            if not checkin['checkout_time']:
                all_checked_out = False
    
    conn.close()
    
    if not kids or not family_code:
        return render_template('share_expired.html'), 404
    
    # Format event time
    event_time = datetime.fromisoformat(token_data['start_time']).astimezone(get_timezone())
    
    logo_filename = get_logo_filename()
    
    return render_template('share_codes.html',
                         event_name=token_data['event_name'],
                         event_date=event_time.strftime('%B %d, %Y'),
                         checkout_code=family_code,
                         checkin_time=checkin_time,
                         kids=kids,
                         all_checked_out=all_checked_out,
                         logo_filename=logo_filename)

@app.route('/kiosk')
@require_auth
def kiosk():
    event_id = request.args.get('event_id')
    if not event_id:
        # Redirect to select event
        conn = get_db()
        months = get_event_date_range_months()
        cur = conn.execute(f"""
            SELECT id, name FROM events
            WHERE start_time >= datetime('now', '-{months} month') AND start_time <= datetime('now', '+{months} month')
            ORDER BY ABS(strftime('%s', start_time) - strftime('%s', 'now')) ASC
            LIMIT 1
        """)
        default_event = cur.fetchone()
        conn.close()
        if default_event:
            return redirect(url_for('kiosk', event_id=default_event['id']))
        else:
            return "No events available", 404

    conn = get_db()
    cur = conn.execute("""
        SELECT c.id, k.id as kid_id, c.checkin_time, c.checkout_time, k.name as kid_name, k.notes as kid_notes,
               f.authorized_adults, f.phone, f.troop, a.name as adult_name
        FROM checkins c
        JOIN kids k ON c.kid_id = k.id
        JOIN families f ON k.family_id = f.id
        JOIN adults a ON c.adult_id = a.id
        WHERE c.checkout_time IS NULL AND c.event_id = ?
        ORDER BY c.checkin_time DESC
    """, (event_id,))
    checked_in = cur.fetchall()

    months = get_event_date_range_months()
    cur2 = conn.execute(f"SELECT id, name, start_time FROM events WHERE start_time >= datetime('now', '-{months} month') AND start_time <= datetime('now', '+{months} month') ORDER BY start_time DESC")
    events = cur2.fetchall()
    current_event = next((e for e in events if e['id'] == int(event_id)), None)
    if current_event:
        dt = datetime.fromisoformat(current_event['start_time']).astimezone(get_timezone())
        current_event_name = current_event['name']
        current_event_date = dt.strftime('%b %d, %Y')
    else:
        current_event_name = 'Event'
        current_event_date = ''

    # Convert to dicts for mutability
    checked_in = [dict(c) for c in checked_in]
    events = [dict(e) for e in events]

    # Format times for display
    for c in checked_in:
        dt = datetime.fromisoformat(c['checkin_time']).replace(tzinfo=timezone.utc).astimezone(get_timezone())
        c['formatted_time'] = dt.strftime('%b %d %I:%M %p')
    for e in events:
        dt = datetime.fromisoformat(e['start_time']).astimezone(get_timezone())
        e['formatted_start'] = dt.strftime('%b %d, %Y %I:%M %p')

    logo_filename = get_logo_filename()
    
    conn.close()

    return render_template('kiosk.html', checked_in=checked_in, events=events, current_event_id=int(event_id), current_event_name=current_event_name, current_event_date=current_event_date, logo_filename=logo_filename)

@app.route('/history')
@require_auth
def history():
    event_id = request.args.get('event_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    conn = get_db()

    # Get all events for the filter dropdown
    events_cur = conn.execute("SELECT id, name, start_time FROM events ORDER BY start_time DESC")
    events = events_cur.fetchall()

    # Build the query with filters
    query = """
        SELECT c.id, c.checkin_time, c.checkout_time, k.name as kid_name, f.phone, f.troop, e.name as event_name, a.name as adult_name
        FROM checkins c
        JOIN kids k ON c.kid_id = k.id
        JOIN families f ON k.family_id = f.id
        JOIN adults a ON c.adult_id = a.id
        JOIN events e ON c.event_id = e.id
        WHERE 1=1
    """
    params = []

    if event_id:
        query += " AND c.event_id = ?"
        params.append(event_id)

    # Convert local dates to UTC ranges for proper filtering
    tz = get_timezone()
    if start_date:
        utc_start, _ = local_date_to_utc_range(start_date, tz)
        if utc_start:
            query += " AND c.checkin_time >= ?"
            params.append(utc_start)

    if end_date:
        _, utc_end = local_date_to_utc_range(end_date, tz)
        if utc_end:
            query += " AND c.checkin_time <= ?"
            params.append(utc_end)

    query += " ORDER BY c.checkin_time DESC LIMIT 200"

    cur = conn.execute(query, params)
    rows = cur.fetchall()

    # Convert to dicts and format times
    rows = [dict(r) for r in rows]
    for r in rows:
        dt = datetime.fromisoformat(r['checkin_time']).replace(tzinfo=timezone.utc).astimezone(get_timezone())
        r['formatted_checkin'] = dt.strftime('%b %d, %Y %I:%M %p')
        if r['checkout_time']:
            dt = datetime.fromisoformat(r['checkout_time']).replace(tzinfo=timezone.utc).astimezone(get_timezone())
            r['formatted_checkout'] = dt.strftime('%b %d, %Y %I:%M %p')
        else:
            r['formatted_checkout'] = ''
    conn.close()

    return render_template('history.html', rows=rows, events=events, event_id=event_id, start_date=start_date, end_date=end_date)

@app.route('/admin/history/email', methods=['POST'])
@require_auth
def email_history():
    """Generate and email the check-in/check-out history report"""
    email_address = request.form.get('email_address', '').strip()
    email_subject = request.form.get('email_subject', 'Check-in Report').strip()
    event_id = request.form.get('event_id', '').strip()
    start_date = request.form.get('start_date', '').strip()
    end_date = request.form.get('end_date', '').strip()
    
    if not email_address:
        flash('Email address is required', 'danger')
        return redirect(url_for('history', event_id=event_id, start_date=start_date, end_date=end_date))
    
    try:
        conn = get_db()
        
        # Build the query with filters (same as history page)
        query = """
            SELECT c.id, c.checkin_time, c.checkout_time, k.name as kid_name, f.phone, f.troop, e.name as event_name, a.name as adult_name
            FROM checkins c
            JOIN kids k ON c.kid_id = k.id
            JOIN families f ON k.family_id = f.id
            JOIN adults a ON c.adult_id = a.id
            JOIN events e ON c.event_id = e.id
            WHERE 1=1
        """
        params = []
        
        if event_id:
            query += " AND c.event_id = ?"
            params.append(event_id)
        
        # Convert local dates to UTC ranges for proper filtering
        tz = get_timezone()
        if start_date:
            utc_start, _ = local_date_to_utc_range(start_date, tz)
            if utc_start:
                query += " AND c.checkin_time >= ?"
                params.append(utc_start)
        
        if end_date:
            _, utc_end = local_date_to_utc_range(end_date, tz)
            if utc_end:
                query += " AND c.checkin_time <= ?"
                params.append(utc_end)
        
        query += " ORDER BY c.checkin_time DESC"
        
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        rows = [dict(r) for r in rows]
        
        # Format times and build HTML table
        html_rows = []
        for r in rows:
            dt = datetime.fromisoformat(r['checkin_time']).replace(tzinfo=timezone.utc).astimezone(get_timezone())
            checkin_time = dt.strftime('%b %d, %Y %I:%M %p')
            
            checkout_time = ''
            if r['checkout_time']:
                dt = datetime.fromisoformat(r['checkout_time']).replace(tzinfo=timezone.utc).astimezone(get_timezone())
                checkout_time = dt.strftime('%b %d, %Y %I:%M %p')
            
            html_rows.append({
                'kid_name': r['kid_name'],
                'adult_name': r['adult_name'],
                'phone': r['phone'],
                'event_name': r['event_name'],
                'checkin_time': checkin_time,
                'checkout_time': checkout_time or '-'
            })
        
        conn.close()
        
        # Build HTML table
        html_table = """
        <table style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; font-size: 12px;">
            <thead>
                <tr style="background-color: #f0f0f0; border-bottom: 2px solid #333;">
                    <th style="padding: 8px; text-align: left; border: 1px solid #999;">Youth Name</th>
                    <th style="padding: 8px; text-align: left; border: 1px solid #999;">Adult</th>
                    <th style="padding: 8px; text-align: left; border: 1px solid #999;">Phone</th>
                    <th style="padding: 8px; text-align: left; border: 1px solid #999;">Event</th>
                    <th style="padding: 8px; text-align: left; border: 1px solid #999;">Check-in Time</th>
                    <th style="padding: 8px; text-align: left; border: 1px solid #999;">Check-out Time</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for row in html_rows:
            html_table += f"""
                <tr style="border-bottom: 1px solid #ddd;">
                    <td style="padding: 8px; border: 1px solid #ccc;">{row['kid_name']}</td>
                    <td style="padding: 8px; border: 1px solid #ccc;">{row['adult_name']}</td>
                    <td style="padding: 8px; border: 1px solid #ccc;">{row['phone']}</td>
                    <td style="padding: 8px; border: 1px solid #ccc;">{row['event_name']}</td>
                    <td style="padding: 8px; border: 1px solid #ccc;">{row['checkin_time']}</td>
                    <td style="padding: 8px; border: 1px solid #ccc;">{row['checkout_time']}</td>
                </tr>
            """
        
        html_table += """
            </tbody>
        </table>
        """
        
        # Build HTML email body
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 900px; margin: 0 auto;">
                    <h2 style="color: #0dcaf0; border-bottom: 2px solid #0dcaf0; padding-bottom: 10px;">Check-in Report</h2>
                    
                    <div style="background-color: #f9f9f9; padding: 10px; margin: 15px 0; border-left: 4px solid #0dcaf0;">
                        <p><strong>Report Generated:</strong> {datetime.now().strftime('%b %d, %Y %I:%M %p')}</p>
                        <p><strong>Total Records:</strong> {len(html_rows)}</p>
                    </div>
                    
                    {html_table}
                    
                    <div style="margin-top: 20px; font-size: 11px; color: #666; border-top: 1px solid #ddd; padding-top:  10px;">
                        <p>This is an automated report. Please do not reply to this email.</p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        # Send email
        success, message = send_email(email_address, email_subject, html_body)
        
        if success:
            flash(f'Report sent successfully to {email_address}', 'success')
        else:
            flash(f'Failed to send report: {message}', 'danger')
        
        return redirect(url_for('history', event_id=event_id, start_date=start_date, end_date=end_date))
    
    except Exception as e:
        flash(f'Error generating report: {str(e)}', 'danger')
        return redirect(url_for('history', event_id=event_id, start_date=start_date, end_date=end_date))

# Admin routes
@app.route('/admin')
@require_auth
def admin_index():
    return render_template('admin/index.html')

# Admin: Families management page
@app.route('/admin/families')
@require_auth
def admin_families():
    conn = get_db()
    # Get all families with aggregated adult and kid names
    families = conn.execute("""
        SELECT f.*,
               (SELECT GROUP_CONCAT(a.name, ', ') FROM adults a WHERE a.family_id = f.id) as adults,
               (SELECT GROUP_CONCAT(k.name, ', ') FROM kids k WHERE k.family_id = f.id) as kids
        FROM families f
        ORDER BY f.id
    """).fetchall()
    conn.close()
    
    tlc_configured = 'tlc_email' in session and 'tlc_password' in session
    return render_template('admin/families.html', families=families, tlc_configured=tlc_configured)

# Admin: Events management page
@app.route('/admin/events')
@require_auth
def admin_events():
    conn = get_db()
    events = conn.execute("SELECT * FROM events ORDER BY start_time DESC").fetchall()
    
    # Get iCal settings
    ical_url_row = conn.execute("SELECT value FROM settings WHERE key = 'ical_url'").fetchone()
    ical_url = ical_url_row['value'] if ical_url_row else ''
    
    last_sync_row = conn.execute("SELECT value FROM settings WHERE key = 'last_ical_sync'").fetchone()
    last_sync = ''
    if last_sync_row and last_sync_row['value']:
        try:
            dt = datetime.fromisoformat(last_sync_row['value']).replace(tzinfo=timezone.utc).astimezone(get_timezone())
            last_sync = dt.strftime('%b %d, %Y %I:%M %p')
        except:
            last_sync = last_sync_row['value']
            
    conn.close()
    return render_template('admin/events.html', events=events, ical_url=ical_url, last_sync=last_sync)

@app.route('/admin/events/set_ical', methods=['POST'])
@require_auth
def set_ical_url():
    ical_url = request.form.get('ical_url', '').strip()
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ical_url', ?)", (ical_url,))
    conn.commit()
    conn.close()
    
    if ical_url:
        # Trigger initial sync
        success, message = sync_ical_events()
        if success:
            flash(f'iCal URL saved and initial sync completed: {message}', 'success')
        else:
            flash(f'iCal URL saved but sync failed: {message}', 'warning')
    else:
        flash('iCal URL cleared', 'info')
        
    return redirect(url_for('admin_events'))

@app.route('/admin/events/sync', methods=['POST'])
@require_auth
def sync_events():
    success, message = sync_ical_events()
    if success:
        flash(f'Sync completed: {message}', 'success')
    else:
        flash(f'Sync failed: {message}', 'danger')
    return redirect(url_for('admin_events'))

@app.route('/admin/events/clear', methods=['POST'])
@require_auth
def clear_events():
    conn = get_db()
    # Only delete events that have no checkins
    conn.execute("DELETE FROM events WHERE id NOT IN (SELECT DISTINCT event_id FROM checkins)")
    conn.commit()
    conn.close()
    flash('All events without check-ins have been deleted.', 'success')
    return redirect(url_for('admin_events'))

@app.route('/admin/events/add', methods=['GET', 'POST'])
@require_auth
def add_event():
    if request.method == 'POST':
        name = request.form.get('name')
        date = request.form.get('date')
        time = request.form.get('time')
        description = request.form.get('description')
        
        if not name or not date or not time:
            flash('Name, date, and time are required', 'danger')
            return render_template('admin/add_event.html')
            
        start_time = f"{date}T{time}:00"
        
        conn = get_db()
        conn.execute("INSERT INTO events (name, start_time, description) VALUES (?, ?, ?)",
                    (name, start_time, description))
        conn.commit()
        conn.close()
        
        flash('Event added successfully', 'success')
        return redirect(url_for('admin_events'))
        
    return render_template('admin/add_event.html')

@app.route('/admin/events/edit/<int:event_id>', methods=['GET', 'POST'])
@require_auth
def edit_event(event_id):
    conn = get_db()
    if request.method == 'POST':
        name = request.form.get('name')
        date = request.form.get('date')
        time = request.form.get('time')
        description = request.form.get('description')
        
        start_time = f"{date}T{time}:00"
        
        conn.execute("UPDATE events SET name = ?, start_time = ?, description = ? WHERE id = ?",
                    (name, start_time, description, event_id))
        conn.commit()
        conn.close()
        
        flash('Event updated successfully', 'success')
        return redirect(url_for('admin_events'))
        
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()
    
    if not event:
        flash('Event not found', 'danger')
        return redirect(url_for('admin_events'))
        
    return render_template('admin/edit_event.html', event=event)

@app.route('/admin/events/delete/<int:event_id>', methods=['POST'])
@require_auth
def delete_event(event_id):
    conn = get_db()
    # Check if event has checkins
    checkins = conn.execute("SELECT COUNT(*) FROM checkins WHERE event_id = ?", (event_id,)).fetchone()[0]
    
    if checkins > 0:
        flash(f'Cannot delete event because it has {checkins} check-ins. Clear check-ins first if you really want to delete it.', 'danger')
    else:
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.commit()
        flash('Event deleted successfully', 'success')
        
    conn.close()
    return redirect(url_for('admin_events'))

@app.route('/admin/families/add', methods=['GET', 'POST'])
@require_auth
def add_family():
    if request.method == 'POST':
        troop = request.form.get('troop')
        authorized_adults = request.form.get('authorized_adults')
        
        adult_names = request.form.getlist('adults')
        adult_phones = request.form.getlist('adult_phones')
        default_adult_index = int(request.form.get('default_adult_index', 0))
        
        kid_names = request.form.getlist('kids')
        kid_notes = request.form.getlist('kid_notes')
        
        # Use first adult's phone as family phone for backwards compatibility
        family_phone = adult_phones[0].strip() if adult_phones and adult_phones[0].strip() else ''
            
        conn = get_db()
        try:
            # Create family
            cur = conn.execute("INSERT INTO families (phone, troop, authorized_adults) VALUES (?, ?, ?)",
                              (family_phone, troop, authorized_adults))
            family_id = cur.lastrowid
            
            # Add adults
            default_adult_id = None
            for i, name in enumerate(adult_names):
                if name.strip():
                    adult_phone = adult_phones[i].strip() if i < len(adult_phones) else ''
                    cur = conn.execute("INSERT INTO adults (family_id, name, phone) VALUES (?, ?, ?)", 
                                      (family_id, name.strip(), adult_phone if adult_phone else None))
                    if i == default_adult_index:
                        default_adult_id = cur.lastrowid
            
            # Update default adult if set
            if default_adult_id:
                conn.execute("UPDATE families SET default_adult_id = ? WHERE id = ?", (default_adult_id, family_id))
                
            # Add kids
            for i, name in enumerate(kid_names):
                if name.strip():
                    note = kid_notes[i] if i < len(kid_notes) else ''
                    conn.execute("INSERT INTO kids (family_id, name, notes) VALUES (?, ?, ?)", 
                                (family_id, name.strip(), note))
            
            conn.commit()
            flash('Family added successfully', 'success')
            return redirect(url_for('admin_families'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Error adding family: {str(e)}', 'danger')
            return render_template('admin/add_family.html')
        finally:
            conn.close()
            
    return render_template('admin/add_family.html')

@app.route('/admin/families/edit/<int:family_id>', methods=['GET', 'POST'])
@require_auth
def edit_family(family_id):
    conn = get_db()
    
    if request.method == 'POST':
        troop = request.form.get('troop')
        authorized_adults = request.form.get('authorized_adults')
        default_adult_id = request.form.get('default_adult_id')
        
        adult_ids = request.form.getlist('adult_ids')
        adult_names = request.form.getlist('adults')
        adult_phones = request.form.getlist('adult_phones')
        
        kid_ids = request.form.getlist('kid_ids')
        kid_names = request.form.getlist('kids')
        kid_notes = request.form.getlist('kid_notes')
        
        # Use first adult's phone as family phone for backwards compatibility
        family_phone = ''
        for phone in adult_phones:
            if phone and phone.strip():
                family_phone = phone.strip()
                break
        
        try:
            # Update family details
            conn.execute("UPDATE families SET phone = ?, troop = ?, authorized_adults = ?, default_adult_id = ? WHERE id = ?",
                        (family_phone, troop, authorized_adults, default_adult_id if default_adult_id else None, family_id))
            
            # Update/Add adults
            # First, get existing adults to know which ones to delete if not in list
            existing_adults = [row['id'] for row in conn.execute("SELECT id FROM adults WHERE family_id = ?", (family_id,)).fetchall()]
            processed_adult_ids = []
            
            for i, name in enumerate(adult_names):
                if not name.strip():
                    continue
                    
                adult_id = adult_ids[i] if i < len(adult_ids) and adult_ids[i] else None
                adult_phone = adult_phones[i].strip() if i < len(adult_phones) else ''
                
                if adult_id:
                    # Update existing
                    conn.execute("UPDATE adults SET name = ?, phone = ? WHERE id = ?", 
                               (name.strip(), adult_phone if adult_phone else None, adult_id))
                    processed_adult_ids.append(int(adult_id))
                else:
                    # Add new
                    conn.execute("INSERT INTO adults (family_id, name, phone) VALUES (?, ?, ?)", 
                               (family_id, name.strip(), adult_phone if adult_phone else None))
            
            # Delete removed adults
            for aid in existing_adults:
                if aid not in processed_adult_ids:
                    # Check if this was the default adult
                    if str(aid) == str(default_adult_id):
                        conn.execute("UPDATE families SET default_adult_id = NULL WHERE id = ?", (family_id,))
                    conn.execute("DELETE FROM adults WHERE id = ?", (aid,))

            # Update/Add kids
            existing_kids = [row['id'] for row in conn.execute("SELECT id FROM kids WHERE family_id = ?", (family_id,)).fetchall()]
            processed_kid_ids = []
            
            for i, name in enumerate(kid_names):
                if not name.strip():
                    continue
                    
                kid_id = kid_ids[i] if i < len(kid_ids) and kid_ids[i] else None
                note = kid_notes[i] if i < len(kid_notes) else ''
                
                if kid_id:
                    # Update existing
                    conn.execute("UPDATE kids SET name = ?, notes = ? WHERE id = ?", (name.strip(), note, kid_id))
                    processed_kid_ids.append(int(kid_id))
                else:
                    # Add new
                    conn.execute("INSERT INTO kids (family_id, name, notes) VALUES (?, ?, ?)", (family_id, name.strip(), note))
            
            # Delete removed kids
            for kid in existing_kids:
                if kid not in processed_kid_ids:
                    conn.execute("DELETE FROM kids WHERE id = ?", (kid,))
            
            conn.commit()
            flash('Family updated successfully', 'success')
            return redirect(url_for('admin_families'))
            
        except Exception as e:
            conn.rollback()
            flash(f'Error updating family: {str(e)}', 'danger')
            # Re-fetch data for form after error
            family = conn.execute("SELECT * FROM families WHERE id = ?", (family_id,)).fetchone()
            adults = conn.execute("SELECT * FROM adults WHERE family_id = ?", (family_id,)).fetchall()
            kids = conn.execute("SELECT * FROM kids WHERE family_id = ?", (family_id,)).fetchall()
            branding = get_branding_settings()
            conn.close()
            return render_template('admin/edit_family.html', family=family, adults=adults, kids=kids, branding=branding)
        finally:
            conn.close()
            
        # If we successfully committed, we return above, so this won't be reached
        return redirect(url_for('admin_families'))
    
    # GET request
    family = conn.execute("SELECT * FROM families WHERE id = ?", (family_id,)).fetchone()
    if not family:
        conn.close()
        flash('Family not found', 'danger')
        return redirect(url_for('admin_families'))
        
    adults = conn.execute("SELECT * FROM adults WHERE family_id = ?", (family_id,)).fetchall()
    kids = conn.execute("SELECT * FROM kids WHERE family_id = ?", (family_id,)).fetchall()
    conn.close()
    
    return render_template('admin/edit_family.html', family=family, adults=adults, kids=kids)

@app.route('/admin/families/clear', methods=['POST'])
@require_auth
def clear_families():
    conn = get_db()
    try:
        # Check for checkins first? Or just cascade delete?
        # SQLite doesn't always cascade by default unless enabled, so let's be manual to be safe
        conn.execute("DELETE FROM checkins") # Clear history too? Maybe not.
        # If we clear families, we break checkin history integrity usually.
        # But the user asked for "Clear All Families".
        # Let's assume they want a fresh start.
        
        # Actually, let's keep checkins but set kid_id/adult_id to NULL? No, that's messy.
        # Let's just delete families, adults, kids.
        conn.execute("DELETE FROM kids")
        conn.execute("DELETE FROM adults")
        conn.execute("DELETE FROM families")
        conn.commit()
        flash('All families cleared successfully', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error clearing families: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('admin_families'))

@app.route('/admin/families/export')
@require_auth
def export_families():
    conn = get_db()
    families = conn.execute("SELECT * FROM families").fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Phone', 'Troop', 'Authorized Adults', 'Adults', 'Kids', 'Kid Notes'])
    
    for f in families:
        adults = conn.execute("SELECT name FROM adults WHERE family_id = ?", (f['id'],)).fetchall()
        adult_str = "; ".join([a['name'] for a in adults])
        
        kids = conn.execute("SELECT name, notes FROM kids WHERE family_id = ?", (f['id'],)).fetchall()
        kid_str = "; ".join([k['name'] for k in kids])
        note_str = "; ".join([k['notes'] or '' for k in kids])
        
        writer.writerow([
            f['phone'],
            f['troop'],
            f['authorized_adults'],
            adult_str,
            kid_str,
            note_str
        ])
        
    conn.close()
    
    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=families_export.csv"}
    )

@app.route('/admin/families/import', methods=['GET', 'POST'])
@require_auth
def import_families():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
            
        if not file.filename.endswith('.csv'):
            flash('File must be a CSV', 'danger')
            return redirect(request.url)
            
        try:
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.reader(stream)
            header = next(csv_input) # Skip header
            
            conn = get_db()
            count = 0
            
            for row in csv_input:
                if len(row) < 5:
                    continue
                    
                phone = row[0].strip()
                troop = row[1].strip()
                auth_adults = row[2].strip()
                adults_str = row[3].strip()
                kids_str = row[4].strip()
                notes_str = row[5].strip() if len(row) > 5 else ""
                
                if not phone:
                    continue
                    
                # Create family
                cur = conn.execute("INSERT INTO families (phone, troop, authorized_adults) VALUES (?, ?, ?)",
                                  (phone, troop, auth_adults))
                family_id = cur.lastrowid
                
                # Add adults
                if adults_str:
                    for name in adults_str.split(';'):
                        if name.strip():
                            conn.execute("INSERT INTO adults (family_id, name) VALUES (?, ?)", (family_id, name.strip()))
                
                # Add kids
                if kids_str:
                    kid_names = [k.strip() for k in kids_str.split(';')]
                    kid_notes = [n.strip() for n in notes_str.split(';')]
                    
                    for i, name in enumerate(kid_names):
                        if name:
                            note = kid_notes[i] if i < len(kid_notes) else ""
                            conn.execute("INSERT INTO kids (family_id, name, notes) VALUES (?, ?, ?)", 
                                        (family_id, name, note))
                
                count += 1
                
            conn.commit()
            conn.close()
            flash(f'Successfully imported {count} families', 'success')
            return redirect(url_for('admin_families'))
            
        except Exception as e:
            flash(f'Error importing CSV: {str(e)}', 'danger')
            return redirect(request.url)
            
    return render_template('admin/import_families.html')

@app.route('/admin/families/delete/<int:family_id>', methods=['POST'])
@require_auth
def delete_family(family_id):
    conn = get_db()
    try:
        # Delete related records first
        conn.execute("DELETE FROM kids WHERE family_id = ?", (family_id,))
        conn.execute("DELETE FROM adults WHERE family_id = ?", (family_id,))
        conn.execute("DELETE FROM families WHERE id = ?", (family_id,))
        conn.commit()
        flash('Family deleted successfully', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting family: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('admin_families'))

@app.route('/admin/families/import_tlc', methods=['POST'])
@require_auth
def import_families_tlc():
    if 'tlc_email' not in session or 'tlc_password' not in session:
        flash('TLC not configured. Please login first.', 'danger')
        return redirect(url_for('admin_tlc'))

    client = TrailLifeConnectClient(session['tlc_email'], session['tlc_password'])
    if not client.login():
        flash('Failed to login to TLC.', 'danger')
        return redirect(url_for('admin_families'))

    # Get roster from first upcoming event
    events = client.get_upcoming_events()
    if not events:
        flash('No upcoming events found in TLC to fetch roster from.', 'warning')
        return redirect(url_for('admin_families'))

    event_id = events[0]['id']
    roster = client.get_event_roster(event_id) # Dict: Name -> {'id': ..., 'profile_url': ...}
    
    if not roster:
        flash('Empty roster found.', 'warning')
        return redirect(url_for('admin_families'))

    conn = get_db()
    added_families = 0
    added_kids = 0
    updated_kids = 0
    
    # Group roster by last name
    # Name format in roster is usually "First Last" (normalized in client)
    # We'll assume the last word is the last name
    by_lastname = {}
    for name, data in roster.items():
        parts = name.split()
        if len(parts) > 1:
            lastname = parts[-1]
        else:
            lastname = name # Fallback
        
        by_lastname.setdefault(lastname, []).append({'name': name, 'tlc_id': data['id'], 'profile_url': data['profile_url']})

    try:
        for lastname, members in by_lastname.items():
            # 1. Find existing family by checking if any member is already in DB
            family_id = None
            
            # Check if any member exists as a kid
            for member in members:
                kid = conn.execute("SELECT family_id FROM kids WHERE name = ? COLLATE NOCASE", (member['name'],)).fetchone()
                if kid:
                    family_id = kid['family_id']
                    break
            
            # Check if any member exists as an adult (if we haven't found family yet)
            if not family_id:
                for member in members:
                    adult = conn.execute("SELECT family_id FROM adults WHERE name = ? COLLATE NOCASE", (member['name'],)).fetchone()
                    if adult:
                        family_id = adult['family_id']
                        break
            
            # If still no family, create one
            if not family_id:
                # Try to fetch phone number from the first member with a profile URL
                phone = ''
                for member in members:
                    if member['profile_url']:
                        details = client.get_member_details(member['profile_url'])
                        if details.get('phone'):
                            phone = details['phone']
                            break
                
                # Create new family
                cur = conn.execute("INSERT INTO families (phone, troop) VALUES (?, ?)", (phone, ''))
                family_id = cur.lastrowid
                added_families += 1
            
            # 2. Process members
            for member in members:
                name = member['name']
                tlc_id = member['tlc_id']
                
                # Check if exists as kid
                kid = conn.execute("SELECT id FROM kids WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
                if kid:
                    # Update TLC ID
                    conn.execute("UPDATE kids SET tlc_id = ? WHERE id = ?", (tlc_id, kid['id']))
                    updated_kids += 1
                else:
                    # Check if exists as adult
                    adult = conn.execute("SELECT id FROM adults WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
                    if not adult:
                        # Not found as kid or adult -> Add as Kid (default)
                        conn.execute("INSERT INTO kids (family_id, name, tlc_id) VALUES (?, ?, ?)", 
                                    (family_id, name, tlc_id))
                        added_kids += 1

        conn.commit()
        flash(f'Import complete: Added {added_families} families, {added_kids} new members, updated {updated_kids} existing members.', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error importing from TLC: {str(e)}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('admin_families'))

@app.route('/admin/backups')
@require_auth
def backup_list():
    """Display list of backups"""
    try:
        backups = backup_manager.list_backups()
        summary = backup_manager.get_backup_summary()
        
        # Get backup schedule settings
        conn = get_db()
        backup_frequency = conn.execute("SELECT value FROM settings WHERE key = 'backup_frequency'").fetchone()
        backup_frequency = backup_frequency[0] if backup_frequency else 'daily'
        
        backup_hour = conn.execute("SELECT value FROM settings WHERE key = 'backup_hour'").fetchone()
        backup_hour = int(backup_hour[0]) if backup_hour else 2
        
        # Get email backup settings
        backup_email_enabled = conn.execute("SELECT value FROM settings WHERE key = 'backup_email_enabled'").fetchone()
        backup_email_enabled = backup_email_enabled[0] if backup_email_enabled else 'false'
        
        backup_email_recipients = conn.execute("SELECT value FROM settings WHERE key = 'backup_email_recipients'").fetchone()
        backup_email_recipients = backup_email_recipients[0] if backup_email_recipients else ''
        
        # Get encryption settings
        backup_encryption_enabled = conn.execute("SELECT value FROM settings WHERE key = 'backup_encryption_password'").fetchone()
        backup_encryption_enabled = bool(backup_encryption_enabled and backup_encryption_enabled[0])
        
        conn.close()
        
        return render_template('admin/backups.html',
                             backups=backups,
                             summary=summary,
                             backup_frequency=backup_frequency,
                             backup_hour=backup_hour,
                             backup_email_enabled=backup_email_enabled,
                             backup_email_recipients=backup_email_recipients,
                             backup_encryption_enabled=backup_encryption_enabled,
                             encryption_available=backup_manager.is_encryption_available())
    except Exception as e:
        flash(f'Error loading backups: {str(e)}', 'danger')
        return redirect(url_for('admin_index'))

def send_backup_email(backup_path, description=''):
    """Send backup file via email to configured recipients.
    
    Args:
        backup_path: Path to the backup file
        description: Description of the backup (for email subject/body)
    
    Returns:
        Tuple of (success, message) or (None, None) if email not enabled
    """
    try:
        conn = get_db()
        
        # Check if email backup is enabled
        row = conn.execute("SELECT value FROM settings WHERE key = 'backup_email_enabled'").fetchone()
        email_enabled = row[0] if row else 'false'
        
        if email_enabled != 'true':
            conn.close()
            return None, None  # Email not enabled, not an error
        
        # Get recipients
        row = conn.execute("SELECT value FROM settings WHERE key = 'backup_email_recipients'").fetchone()
        recipients = row[0] if row else ''
        conn.close()
        
        if not recipients.strip():
            return False, "Email backup enabled but no recipients configured"
        
        # Get branding for email
        branding = get_branding_settings()
        org_name = branding.get('organization_name', 'Youth Secure Check-in')
        
        # Get backup file info
        backup_file = Path(backup_path)
        if not backup_file.exists():
            return False, f"Backup file not found: {backup_path}"
        
        backup_size_mb = round(backup_file.stat().st_size / (1024 * 1024), 2)
        backup_name = backup_file.name
        
        # Build email content
        tz = get_timezone()
        now = datetime.now(tz) if tz else datetime.now()
        timestamp = now.strftime('%Y-%m-%d %H:%M %Z')
        
        subject = f"[{org_name}] Backup - {backup_name}"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">{org_name} - Backup</h2>
            <p>A backup has been created and is attached to this email.</p>
            <table style="border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>File:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{backup_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Size:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{backup_size_mb} MB</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Created:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{timestamp}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; background: #f5f5f5;"><strong>Description:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{description or 'N/A'}</td>
                </tr>
            </table>
            <p style="color: #666; font-size: 12px;">
                This is an automated backup from {org_name}.<br>
                Store this file securely for disaster recovery.
            </p>
        </body>
        </html>
        """
        
        plain_body = f"""
{org_name} - Backup

A backup has been created and is attached to this email.

File: {backup_name}
Size: {backup_size_mb} MB
Created: {timestamp}
Description: {description or 'N/A'}

This is an automated backup. Store this file securely for disaster recovery.
        """
        
        # Send to each recipient
        recipient_list = [r.strip() for r in recipients.split(',') if r.strip()]
        success_count = 0
        errors = []
        
        for recipient in recipient_list:
            success, msg = send_email(
                to_address=recipient,
                subject=subject,
                html_body=html_body,
                plain_text_body=plain_body,
                attachment_path=str(backup_file),
                attachment_name=backup_name
            )
            if success:
                success_count += 1
            else:
                errors.append(f"{recipient}: {msg}")
        
        if success_count == len(recipient_list):
            return True, f"Backup emailed to {success_count} recipient(s)"
        elif success_count > 0:
            return True, f"Backup emailed to {success_count}/{len(recipient_list)} recipients. Errors: {'; '.join(errors)}"
        else:
            return False, f"Failed to email backup: {'; '.join(errors)}"
            
    except Exception as e:
        return False, f"Error sending backup email: {str(e)}"

@app.route('/admin/backups/create', methods=['POST'])
@require_auth
def backup_create():
    """Create a new backup"""
    try:
        description = request.form.get('description', '').strip()
        if not description:
            description = f'Manual backup at {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        
        backup_path = backup_manager.create_backup(description)
        
        # Rotate old backups according to retention policy
        removed = backup_manager.rotate_backups()
        
        flash(f'✓ Backup created successfully: {Path(backup_path).name}', 'success')
        if removed:
            flash(f'Rotated {removed} old backup(s) according to retention policy', 'info')
        
        # Send backup via email if enabled
        email_success, email_msg = send_backup_email(backup_path, description)
        if email_success is True:
            flash(f'✓ {email_msg}', 'success')
        elif email_success is False:
            flash(f'Email failed: {email_msg}', 'warning')
        # If email_success is None, email is not enabled - no message needed
    
    except Exception as e:
        flash(f'Error creating backup: {str(e)}', 'danger')
    
    return redirect(url_for('backup_list'))

@app.route('/admin/backups/download/<filename>')
@require_auth
def backup_download(filename):
    """Download a backup file"""
    try:
        backup_path = Path(backup_manager.backup_dir) / filename
        if not backup_path.exists():
            flash('Backup file not found', 'danger')
            return redirect(url_for('backup_list'))
        
        return send_file(backup_path, as_attachment=True, download_name=filename)
    
    except Exception as e:
        flash(f'Error downloading backup: {str(e)}', 'danger')
        return redirect(url_for('backup_list'))

@app.route('/admin/backups/restore/<filename>', methods=['POST'])
@require_auth
def backup_restore(filename):
    """Restore from a backup"""
    try:
        # Confirmation required
        confirm = request.form.get('confirm', '').lower()
        if confirm != 'restore':
            flash('Restoration cancelled: confirmation not provided', 'warning')
            return redirect(url_for('backup_list'))
        
        # Get optional restore password (for encrypted backups with different password)
        restore_password = request.form.get('restore_password', '').strip() or None
        
        success, message = backup_manager.restore_backup(filename, password=restore_password)
        if success:
            flash(f'✓ Database restored successfully from {filename}', 'success')
            flash('NOTE: You may need to restart the application for all changes to take effect', 'info')
        else:
            flash(f'Restore failed: {message}', 'danger')
    
    except Exception as e:
        flash(f'Error restoring backup: {str(e)}', 'danger')
    
    return redirect(url_for('backup_list'))

@app.route('/admin/backups/delete/<filename>', methods=['POST'])
@require_auth
def backup_delete(filename):
    """Delete a backup"""
    try:
        backup_manager.delete_backup(filename)
        flash(f'✓ Backup deleted: {filename}', 'success')
    
    except Exception as e:
        flash(f'Error deleting backup: {str(e)}', 'danger')
    
    return redirect(url_for('backup_list'))

@app.route('/admin/backups/rotate', methods=['POST'])
@require_auth
def backup_rotate():
    """Manually trigger backup rotation"""
    try:
        removed = backup_manager.rotate_backups()
        if removed > 0:
            flash(f'✓ Rotated {removed} old backup(s)', 'success')
        else:
            flash('No backups needed to be rotated', 'info')
    
    except Exception as e:
        flash(f'Error rotating backups: {str(e)}', 'danger')
    
    return redirect(url_for('backup_list'))

@app.route('/admin/backups/schedule', methods=['POST'])
@require_auth
def backup_schedule():
    """Update backup schedule settings"""
    try:
        frequency = request.form.get('backup_frequency', 'daily').strip()
        hour = int(request.form.get('backup_hour', '2').strip())
        
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('backup_frequency', ?)", (frequency,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('backup_hour', ?)", (str(hour),))
        conn.commit()
        conn.close()
        
        # Update backup manager timezone
        update_backup_manager_timezone()
        
        # Get the configured timezone for the scheduler
        tz = get_timezone()
        
        # Update scheduler if available
        if scheduler:
            # Remove existing backup job if present
            if scheduler.get_job('local_backup_job'):
                scheduler.remove_job('local_backup_job')
            
            # Add new scheduled job with timezone
            try:
                if frequency == 'hourly':
                    scheduler.add_job(perform_scheduled_local_backup, 'cron', minute=0, timezone=tz, id='local_backup_job', replace_existing=True)
                elif frequency == 'daily':
                    scheduler.add_job(perform_scheduled_local_backup, 'cron', hour=hour, minute=0, timezone=tz, id='local_backup_job', replace_existing=True)
                elif frequency == 'weekly':
                    scheduler.add_job(perform_scheduled_local_backup, 'cron', day_of_week='6', hour=hour, minute=0, timezone=tz, id='local_backup_job', replace_existing=True)
                elif frequency == 'monthly':
                    scheduler.add_job(perform_scheduled_local_backup, 'cron', day=1, hour=hour, minute=0, timezone=tz, id='local_backup_job', replace_existing=True)
                
                tz_name = str(tz)
                app.logger.info(f"Scheduled backup job updated: {frequency} at {hour:02d}:00 ({tz_name})")
                flash(f'✓ Backup schedule updated: {frequency} at {hour:02d}:00 ({tz_name})', 'success')
            except Exception as e:
                app.logger.warning(f"Failed to update scheduled backup: {e}")
                flash(f'Settings saved but scheduler update failed: {str(e)}', 'warning')
        else:
            flash('✓ Backup schedule saved (scheduler not available)', 'warning')
    
    except Exception as e:
        flash(f'Error updating backup schedule: {str(e)}', 'danger')
    
    return redirect(url_for('backup_list'))

@app.route('/admin/backups/email-config', methods=['POST'])
@require_auth
def backup_email_config():
    """Update email backup configuration"""
    try:
        email_enabled = 'true' if request.form.get('backup_email_enabled') == 'on' else 'false'
        email_recipients = request.form.get('backup_email_recipients', '').strip()
        
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('backup_email_enabled', ?)", (email_enabled,))
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('backup_email_recipients', ?)", (email_recipients,))
        conn.commit()
        conn.close()
        
        flash('✓ Email backup settings updated successfully!', 'success')
    
    except Exception as e:
        flash(f'Error updating email backup settings: {str(e)}', 'danger')
    
    return redirect(url_for('backup_list'))

@app.route('/admin/backups/encryption-config', methods=['POST'])
@require_auth
def backup_encryption_config():
    """Update backup encryption configuration"""
    try:
        action = request.form.get('action', '')
        
        if action == 'enable':
            password = request.form.get('backup_encryption_password', '').strip()
            confirm_password = request.form.get('backup_encryption_password_confirm', '').strip()
            
            if not password:
                flash('Encryption password is required', 'danger')
                return redirect(url_for('backup_list'))
            
            if len(password) < 8:
                flash('Encryption password must be at least 8 characters', 'danger')
                return redirect(url_for('backup_list'))
            
            if password != confirm_password:
                flash('Passwords do not match', 'danger')
                return redirect(url_for('backup_list'))
            
            conn = get_db()
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('backup_encryption_password', ?)", (password,))
            conn.commit()
            conn.close()
            
            # Update backup manager
            update_backup_manager_encryption()
            
            flash('✓ Backup encryption enabled! All new backups will be encrypted with AES-256.', 'success')
            
        elif action == 'disable':
            conn = get_db()
            conn.execute("DELETE FROM settings WHERE key = 'backup_encryption_password'")
            conn.commit()
            conn.close()
            
            # Update backup manager
            update_backup_manager_encryption()
            
            flash('✓ Backup encryption disabled. New backups will not be encrypted.', 'info')
        
        elif action == 'change':
            current_password = request.form.get('current_encryption_password', '').strip()
            new_password = request.form.get('new_encryption_password', '').strip()
            confirm_password = request.form.get('new_encryption_password_confirm', '').strip()
            
            # Verify current password
            conn = get_db()
            row = conn.execute("SELECT value FROM settings WHERE key = 'backup_encryption_password'").fetchone()
            stored_password = row[0] if row else None
            
            if stored_password != current_password:
                conn.close()
                flash('Current encryption password is incorrect', 'danger')
                return redirect(url_for('backup_list'))
            
            if not new_password:
                conn.close()
                flash('New encryption password is required', 'danger')
                return redirect(url_for('backup_list'))
            
            if len(new_password) < 8:
                conn.close()
                flash('New encryption password must be at least 8 characters', 'danger')
                return redirect(url_for('backup_list'))
            
            if new_password != confirm_password:
                conn.close()
                flash('New passwords do not match', 'danger')
                return redirect(url_for('backup_list'))
            
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('backup_encryption_password', ?)", (new_password,))
            conn.commit()
            conn.close()
            
            # Update backup manager
            update_backup_manager_encryption()
            
            flash('✓ Encryption password changed successfully!', 'success')
    
    except Exception as e:
        flash(f'Error updating encryption settings: {str(e)}', 'danger')
    
    return redirect(url_for('backup_list'))

def perform_scheduled_local_backup():
    """Perform a scheduled local backup (called by APScheduler)"""
    try:
        description = f'Scheduled backup at {datetime.now().strftime("%Y-%m-%d %H:%M")}'
        backup_path = backup_manager.create_backup(description)
        
        # Rotate old backups
        removed = backup_manager.rotate_backups()
        
        app.logger.info(f"Scheduled backup completed: {backup_path} (rotated {removed} old backups)")
        
        # Send backup via email if enabled
        with app.app_context():
            email_success, email_msg = send_backup_email(backup_path, description)
            if email_success is True:
                app.logger.info(f"Backup email sent: {email_msg}")
            elif email_success is False:
                app.logger.warning(f"Backup email failed: {email_msg}")
            # If email_success is None, email not enabled - no log needed
            
    except Exception as e:
        app.logger.error(f"Error performing scheduled backup: {str(e)}")

@app.route('/admin/security', methods=['GET', 'POST'])
@require_auth
def admin_security():
    """Security settings page - access codes and checkout settings"""
    conn = get_db()
    
    if request.method == 'POST':
        # Handle password changes
        if request.form.get('new_password') or request.form.get('new_override_password'):
            # Update login access code
            new_password = request.form.get('new_password', '').strip()
            if new_password:
                set_app_password(new_password)
                flash('Login access code updated successfully!', 'success')
            
            # Update admin override checkout code
            new_override = request.form.get('new_override_password', '').strip()
            if new_override:
                set_override_password(new_override)
                flash('Admin override checkout code updated successfully!', 'success')
        
        # Handle label printing settings
        elif 'require_checkout_code' in request.form or 'checkout_code_method' in request.form:
            require_codes = 'true' if request.form.get('require_checkout_code') else 'false'
            checkout_code_method = request.form.get('checkout_code_method', 'qr')
            printer_type = request.form.get('label_printer_type', 'dymo')
            label_size = request.form.get('label_size', '30336')
            
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('require_checkout_code', ?)", (require_codes,))
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('checkout_code_method', ?)", (checkout_code_method,))
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('label_printer_type', ?)", (printer_type,))
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('label_size', ?)", (label_size,))
            conn.commit()
            flash('Checkout code settings updated successfully!', 'success')
        
        conn.close()
        return redirect(url_for('admin_security'))
    
    # GET request - fetch current settings
    current_password = get_app_password()
    current_override_password = get_override_password()
    
    # Check if override section is unlocked (persists during session)
    override_unlocked = session.get('override_unlocked', False)
    
    # Fetch label printing settings
    label_settings = {}
    for key in ['require_checkout_code', 'checkout_code_method', 'label_printer_type', 'label_size']:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        label_settings[key] = row[0] if row else None
    
    # Fetch YOURLS settings
    yourls_settings = {}
    for key in ['yourls_api_url', 'yourls_signature']:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        yourls_settings[key] = row[0] if row else None
    
    conn.close()
    
    return render_template('admin/security.html', 
                         branding=get_branding_settings(),
                         current_password=current_password,
                         current_override_password=current_override_password,
                         override_unlocked=override_unlocked,
                         label_settings=label_settings,
                         yourls_settings=yourls_settings)

@app.route('/admin/security/unlock-override', methods=['POST'])
@require_auth
def unlock_override():
    """Unlock override settings with developer password"""
    dev_password = request.form.get('dev_password')
    if dev_password == DEVELOPER_PASSWORD:
        session['override_unlocked'] = True
        flash('Override settings unlocked', 'success')
    else:
        flash('Incorrect developer password', 'danger')
    return redirect(url_for('admin_security'))

@app.route('/admin/security/lock-override', methods=['POST'])
@require_auth
def lock_override():
    """Lock override settings"""
    session['override_unlocked'] = False
    flash('Override settings locked', 'info')
    return redirect(url_for('admin_security'))

@app.route('/admin/branding', methods=['GET', 'POST'])
@require_auth
def admin_branding():
    """Branding settings page"""
    conn = get_db()
    
    if request.method == 'POST':
        action = request.form.get('action', '')
        
        if action == 'update_timezone':
            # Handle timezone update
            timezone = request.form.get('timezone', 'America/New_York')
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('timezone', ?)", (timezone,))
            conn.commit()
            conn.close()
            
            # Update backup manager with new timezone
            update_backup_manager_timezone()
            
            flash(f'Timezone updated to {timezone}', 'success')
            return redirect(url_for('admin_branding'))
        else:
            # Update branding settings
            settings_to_update = [
                'organization_name', 'organization_type', 'group_term', 'group_term_lower',
                'primary_color', 'secondary_color', 'accent_color'
            ]
            
            for key in settings_to_update:
                value = request.form.get(key, '')
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            
            # Handle logo upload if provided
            if 'logo' in request.files:
                logo = request.files['logo']
                if logo.filename:
                    # Save logo logic here (simplified)
                    pass
            
            conn.commit()
            conn.close()
            flash('Branding settings updated successfully', 'success')
            return redirect(url_for('admin_branding'))
    
    # Get current timezone name for the dropdown
    current_timezone = get_timezone_name()
    
    conn.close()
    return render_template('admin/branding.html', branding=get_branding_settings(), current_timezone=current_timezone)

@app.route('/admin/email', methods=['GET', 'POST'])
@require_auth
def admin_email():
    """Email/SMTP settings page"""
    conn = get_db()
    
    if request.method == 'POST':
        # Update email settings - use smtp_server to match get_smtp_settings() and send_email()
        email_keys = ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_from', 'smtp_use_tls']
        for key in email_keys:
            value = request.form.get(key, '')
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        
        # Handle password separately (only if provided)
        smtp_password = request.form.get('smtp_password', '').strip()
        if smtp_password:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('smtp_password', ?)", (smtp_password,))
        
        conn.commit()
        conn.close()
        flash('Email settings updated successfully', 'success')
        return redirect(url_for('admin_email'))
    
    # Check if SMTP section is unlocked
    smtp_unlocked = session.get('smtp_unlocked', False)
    
    # Fetch current settings as an object - use smtp_server to match template and send_email()
    smtp_settings = {}
    for key in ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_password', 'smtp_from', 'smtp_use_tls']:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        smtp_settings[key] = row[0] if row else ''
    
    conn.close()
    return render_template('admin/email_settings.html', branding=get_branding_settings(), smtp_unlocked=smtp_unlocked, smtp_settings=smtp_settings)

@app.route('/admin/email/unlock-smtp', methods=['POST'])
@require_auth
def unlock_smtp():
    """Unlock SMTP settings with developer password"""
    dev_password = request.form.get('dev_password')
    if dev_password == DEVELOPER_PASSWORD:
        session['smtp_unlocked'] = True
        flash('SMTP settings unlocked', 'success')
    else:
        flash('Incorrect developer password', 'danger')
    return redirect(url_for('admin_email'))

@app.route('/admin/email/lock-smtp', methods=['POST'])
@require_auth
def lock_smtp():
    """Lock SMTP settings"""
    session['smtp_unlocked'] = False
    flash('SMTP settings locked', 'info')
    return redirect(url_for('admin_email'))

@app.route('/admin/email/test', methods=['POST'])
@require_auth
def test_email():
    """Send a test email to verify SMTP settings"""
    test_recipient = request.form.get('test_email', '').strip()
    if not test_recipient:
        flash('Please provide an email address', 'danger')
        return redirect(url_for('admin_email'))
    
    # Get SMTP settings - use smtp_server to match the rest of the codebase
    conn = get_db()
    smtp_config = {}
    for key in ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_password', 'smtp_from']:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        smtp_config[key] = row[0] if row else ''
    conn.close()
    
    # Validate settings
    if not all([smtp_config['smtp_server'], smtp_config['smtp_port'], smtp_config['smtp_from']]):
        flash('SMTP settings are incomplete. Please configure all required fields.', 'danger')
        return redirect(url_for('admin_email'))
    
    # Send test email
    success, message = send_email(
        test_recipient,
        'Test Email from Check-in System',
        '<h2>Test Email</h2><p>This is a test email to verify your SMTP configuration is working correctly.</p><p>If you received this email, your settings are configured properly!</p>'
    )
    
    if success:
        flash(f'Test email sent successfully to {test_recipient}', 'success')
    else:
        flash(f'Failed to send test email: {message}', 'danger')
    
    return redirect(url_for('admin_email'))

@app.route('/admin/utilities', methods=['GET'])
@require_auth
def admin_utilities():
    """Database utilities page"""
    conn = get_db()
    
    # Get statistics
    stats = {}
    stats['total_families'] = conn.execute("SELECT COUNT(*) FROM families").fetchone()[0]
    stats['total_kids'] = conn.execute("SELECT COUNT(*) FROM kids").fetchone()[0]
    stats['total_events'] = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    stats['total_checkins'] = conn.execute("SELECT COUNT(*) FROM checkins").fetchone()[0]
    stats['active_checkins'] = conn.execute("SELECT COUNT(*) FROM checkins WHERE checkout_time IS NULL").fetchone()[0]
    
    # Check for orphaned checkins (where kid_id doesn't exist in kids table)
    stats['orphaned_checkins'] = conn.execute(
        "SELECT COUNT(*) FROM checkins WHERE kid_id NOT IN (SELECT id FROM kids)"
    ).fetchone()[0]
    
    # Get database size
    import os
    db_path = os.path.join(app.instance_path, 'checkin.db')
    if os.path.exists(db_path):
        stats['db_size_mb'] = round(os.path.getsize(db_path) / (1024 * 1024), 2)
    else:
        stats['db_size_mb'] = 0
    
    conn.close()
    return render_template('admin/utilities.html', branding=get_branding_settings(), stats=stats)

@app.route('/admin/backup/export')
@require_auth
def export_configuration():
    """Export all configuration settings as JSON backup"""
    conn = get_db()
    
    # Collect all settings
    settings = {}
    
    # Branding settings
    branding_keys = ['organization_name', 'organization_type', 'group_term', 'group_term_lower',
                     'primary_color', 'secondary_color', 'accent_color', 
                     'logo_filename', 'favicon_filename']
    for key in branding_keys:
        val = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if val:
            settings[key] = val['value']
    
    # Security/access settings (exclude developer_password as it's env-only)
    security_keys = ['app_password', 'admin_override_password', 'checkout_code']
    for key in security_keys:
        val = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if val:
            settings[key] = val['value']
    
    # Other settings
    other_keys = ['event_date_range_months', 'label_line_1', 'label_line_2', 'label_line_3']
    for key in other_keys:
        val = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if val:
            settings[key] = val['value']
    
    conn.close()
    
    # Add metadata
    backup = {
        'export_date': datetime.now().isoformat(),
        'app_version': '1.0',
        'settings': settings
    }
    
    # Generate JSON
    output = json.dumps(backup, indent=2)
    
    response = app.response_class(
        response=output,
        status=200,
        mimetype='application/json'
    )
    response.headers['Content-Disposition'] = f'attachment; filename=configuration_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    return response

@app.route('/admin/backup/import', methods=['POST'])
@require_auth
def import_configuration():
    """Import/restore configuration settings from JSON backup"""
    if 'backup_file' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('admin_index'))
    
    file = request.files['backup_file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('admin_index'))
    
    if not file.filename.endswith('.json'):
        flash('Invalid file type. Please upload a JSON backup file.', 'danger')
        return redirect(url_for('admin_index'))
    
    try:
        # Read and parse JSON
        content = file.read().decode('utf-8')
        backup = json.loads(content)
        
        if 'settings' not in backup:
            flash('Invalid backup file format', 'danger')
            return redirect(url_for('admin_index'))
        
        # Restore settings
        conn = get_db()
        for key, value in backup['settings'].items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()
        
        flash('Configuration restored successfully', 'success')
    except Exception as e:
        flash(f'Error restoring configuration: {str(e)}', 'danger')
    
    return redirect(url_for('admin_index'))

# Integrations Management
@app.route('/admin/integrations')
@require_auth
def admin_integrations():
    conn = get_db()
    
    # Check TLC status
    tlc_enabled = False
    last_tlc_sync = None
    
    tlc_enabled_row = conn.execute("SELECT value FROM settings WHERE key = 'tlc_enabled'").fetchone()
    if tlc_enabled_row and tlc_enabled_row['value'] == 'true':
        tlc_enabled = True
    
    last_sync_row = conn.execute("SELECT value FROM settings WHERE key = 'last_tlc_sync'").fetchone()
    if last_sync_row:
        last_tlc_sync = last_sync_row['value']
    
    conn.close()
    
    return render_template('admin/integrations.html', 
                         tlc_enabled=tlc_enabled,
                         last_tlc_sync=last_tlc_sync)

@app.route('/admin/integrations/toggle', methods=['POST'])
@require_auth
def toggle_integration():
    data = request.get_json()
    integration = data.get('integration')
    enabled = data.get('enabled')
    
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (f'{integration}_enabled', 'true' if enabled else 'false')
    )
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# Trail Life Connect Integration Routes
@app.route('/admin/tlc', methods=['GET'])
@require_auth
def admin_tlc():
    branding = get_branding_settings()
    
    # Check if we have credentials in session
    if 'tlc_email' not in session or 'tlc_password' not in session:
        return render_template('admin/tlc_sync.html', step='login', branding=branding)
    
    # Try to fetch events
    try:
        client = TrailLifeConnectClient(session['tlc_email'], session['tlc_password'])
        if not client.login():
            flash('Login failed. Please check your credentials.', 'error')
            session.pop('tlc_email', None)
            session.pop('tlc_password', None)
            return render_template('admin/tlc_sync.html', step='login', branding=branding)
            
        events = client.get_upcoming_events()
        return render_template('admin/tlc_sync.html', step='events', events=events, branding=branding)
        
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return render_template('admin/tlc_sync.html', step='login', branding=branding)

@app.route('/admin/tlc/login', methods=['POST'])
@require_auth
def admin_tlc_login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    if email and password:
        session['tlc_email'] = email
        session['tlc_password'] = password
        return redirect(url_for('admin_tlc'))
    
    flash('Please provide both email and password.', 'error')
    return redirect(url_for('admin_tlc'))

@app.route('/admin/tlc/sync/<event_id>', methods=['GET'])
@require_auth
def admin_tlc_sync_confirm(event_id):
    branding = get_branding_settings()
    
    if 'tlc_email' not in session:
        return redirect(url_for('admin_tlc'))
        
    client = TrailLifeConnectClient(session['tlc_email'], session['tlc_password'])
    if not client.login():
        return redirect(url_for('admin_tlc'))
        
    # 1. Get TLC Roster
    tlc_roster = client.get_event_roster(event_id) # Dict: Name -> ID
    
    # 2. Determine Event Date
    # We need to know the date of the TLC event to find matching local check-ins.
    # Since we only have the ID, we'll fetch the upcoming events list and find it.
    # If it's a past event not in "upcoming", we might default to today or need a better way.
    tlc_events = client.get_upcoming_events()
    target_date_str = datetime.now().strftime('%Y-%m-%d') # Default to today
    
    found_event = next((e for e in tlc_events if e['id'] == event_id), None)
    if found_event:
        # Parse date from "MM/DD/YYYY" to "YYYY-MM-DD"
        try:
            dt = datetime.strptime(found_event['date'], '%m/%d/%Y')
            target_date_str = dt.strftime('%Y-%m-%d')
        except ValueError:
            pass # Keep default if parsing fails
            
    # Ensure DB schema is up to date
    ensure_tlc_synced_column()
    ensure_adult_phone_column()
            
    conn = get_db()
    # Get checkins for the specific date of the event
    # Also fetch tlc_synced status
    # Convert UTC checkin_time to local timezone before comparing dates
    # Get timezone offset for the target date
    tz = get_timezone()
    naive_dt = datetime.strptime(target_date_str, '%Y-%m-%d')
    localized_dt = naive_dt.replace(tzinfo=tz)
    tz_offset_hours = localized_dt.utcoffset().total_seconds() / 3600
    tz_offset_str = f"{tz_offset_hours:+.0f} hours"
    
    checkins = conn.execute('''
        SELECT k.id, k.name, k.tlc_id, c.checkin_time, c.tlc_synced
        FROM checkins c
        JOIN kids k ON c.kid_id = k.id
        WHERE date(datetime(c.checkin_time, ?)) = ?
    ''', (tz_offset_str, target_date_str)).fetchall()
    conn.close()
    
    matches = []
    seen_kid_ids = set()  # Track kids we've already processed to avoid duplicates
    
    # Helper for name normalization
    def normalize(n):
        return n.lower().replace(',', '').replace('.', '').strip()
    
    # Common nickname mappings (formal -> [nicknames])
    nickname_map = {
        'ezekiel': ['zeke', 'zek'],
        'matthew': ['matt', 'matty'],
        'matteo': ['matt', 'matty'],
        'mackenzie': ['mac', 'mack'],
        'macklin': ['mac', 'mack'],
        'maclyn': ['mac', 'mack'],
        'michael': ['mike', 'mikey'],
        'william': ['will', 'bill', 'billy', 'willy'],
        'james': ['jim', 'jimmy', 'jamie'],
        'robert': ['rob', 'bob', 'bobby', 'robby'],
        'richard': ['rick', 'dick', 'ricky'],
        'joseph': ['joe', 'joey'],
        'benjamin': ['ben', 'benny'],
        'samuel': ['sam', 'sammy'],
        'daniel': ['dan', 'danny'],
        'nicholas': ['nick', 'nicky'],
        'alexander': ['alex'],
        'christopher': ['chris'],
        'jonathan': ['jon', 'jonny'],
        'timothy': ['tim', 'timmy'],
        'anthony': ['tony'],
        'joshua': ['josh'],
        'nathaniel': ['nate', 'nathan'],
        'zachary': ['zach', 'zack'],
        'theodore': ['ted', 'teddy', 'theo'],
        'edward': ['ed', 'eddie', 'ted'],
        'elizabeth': ['liz', 'lizzy', 'beth'],
        'katherine': ['kate', 'kathy', 'katie'],
        'margaret': ['maggie', 'meg', 'peggy'],
        'jennifer': ['jen', 'jenny'],
        'jessica': ['jess', 'jessie'],
        'patricia': ['pat', 'patty'],
        'abigail': ['abby'],
        'isabella': ['bella', 'izzy'],
        'madeline': ['maddie'],
        'victoria': ['vicky', 'tori'],
    }
    
    # Build reverse map (nickname -> formal names)
    reverse_nickname_map = {}
    for formal, nicks in nickname_map.items():
        for nick in nicks:
            if nick not in reverse_nickname_map:
                reverse_nickname_map[nick] = []
            reverse_nickname_map[nick].append(formal)
    
    def get_name_variants(name):
        """Get all variants of a first name (formal + nicknames)."""
        parts = name.lower().split()
        if not parts:
            return [name.lower()]
        first = parts[0]
        variants = [first]
        # Add nicknames if this is a formal name
        if first in nickname_map:
            variants.extend(nickname_map[first])
        # Add formal names if this is a nickname
        if first in reverse_nickname_map:
            variants.extend(reverse_nickname_map[first])
        return variants
    
    # 3. Match
    for checkin in checkins:
        # Skip duplicate kids (same kid checked in multiple times)
        if checkin['id'] in seen_kid_ids:
            continue
        seen_kid_ids.add(checkin['id'])
        local_name = checkin['name']
        local_tlc_id = checkin['tlc_id']
        local_norm = normalize(local_name)
        is_synced = checkin['tlc_synced'] == 1
        
        match_found = None
        
        # 1. Try ID match first
        if local_tlc_id:
            for tlc_name, tlc_data in tlc_roster.items():
                # tlc_data is {'id': '...', 'profile_url': '...'}
                tlc_user_id = tlc_data['id'] if isinstance(tlc_data, dict) else tlc_data
                if tlc_user_id == local_tlc_id:
                    match_found = {'name': tlc_name, 'id': tlc_user_id}
                    break
        
        # 2. If no ID match, try name match
        if not match_found:
            # Parse local name into first/last
            local_parts = local_norm.split()
            local_first = local_parts[0] if local_parts else ''
            local_last = local_parts[-1] if len(local_parts) > 1 else ''
            local_first_variants = get_name_variants(local_first) if local_first else []
            
            for tlc_name, tlc_data in tlc_roster.items():
                # tlc_data is {'id': '...', 'profile_url': '...'}
                tlc_user_id = tlc_data['id'] if isinstance(tlc_data, dict) else tlc_data
                tlc_norm = normalize(tlc_name)
                
                # Check exact match
                if local_norm == tlc_norm:
                    match_found = {'name': tlc_name, 'id': tlc_user_id}
                    break
                
                # Check "Last First" vs "First Last"
                tlc_parts = tlc_norm.split()
                if len(tlc_parts) >= 2:
                    # Swap first two parts
                    swapped = f"{tlc_parts[1]} {tlc_parts[0]}"
                    if local_norm == swapped:
                        match_found = {'name': tlc_name, 'id': tlc_user_id}
                        break
                
                # Check nickname variants (e.g., "Ezekiel Gray" matches "Zeke Gray")
                if local_last and len(tlc_parts) >= 2:
                    tlc_first = tlc_parts[0]
                    tlc_last = tlc_parts[-1]
                    
                    # Same last name?
                    if local_last == tlc_last:
                        # Check if first names are variants of each other
                        tlc_first_variants = get_name_variants(tlc_first)
                        # Check if any local variant matches any TLC variant
                        if any(lv in tlc_first_variants for lv in local_first_variants) or \
                           any(tv in local_first_variants for tv in tlc_first_variants):
                            match_found = {'name': tlc_name, 'id': tlc_user_id}
                            break
                            
        status = 'matched' if match_found else 'unmatched'
        if is_synced:
            status = 'synced'
        
        matches.append({
            'local_id': checkin['id'], # This is the KID ID, not checkin ID. Wait, query selects k.id.
            # We need checkin ID to update tlc_synced later? No, we update by kid_id/event_id usually?
            # Actually, admin_tlc_sync_execute iterates form keys.
            # The form uses checkin['id'] which is k.id in the query above.
            # We should probably use c.id to be precise, but the logic uses kid_id to find mapping.
            # Let's keep using k.id for mapping, but we might need c.id to update status.
            'kid_id': checkin['id'], 
            'local_name': local_name,
            'tlc_name': match_found['name'] if match_found else None,
            'tlc_id': match_found['id'] if match_found else None,
            'status': status,
            'checkin_date': checkin['checkin_time']
        })
        
    return render_template('admin/tlc_sync.html', 
                         step='confirm', 
                         event_id=event_id, 
                         matches=matches, 
                         branding=branding,
                         target_date=target_date_str)

@app.route('/admin/tlc/sync/<event_id>/execute', methods=['POST'])
@require_auth
def admin_tlc_sync_execute(event_id):
    if 'tlc_email' not in session:
        return redirect(url_for('admin_tlc'))
        
    client = TrailLifeConnectClient(session['tlc_email'], session['tlc_password'])
    if not client.login():
        return redirect(url_for('admin_tlc'))
        
    count = 0
    errors = 0
    
    # Get target date from form or determine it again (safer to pass it)
    target_date_str = request.form.get('target_date')
    
    conn = get_db()
    
    # Iterate through form data
    # Look for sync_{local_id} checkboxes
    for key, value in request.form.items():
        if key.startswith('sync_') and value == 'on':
            kid_id = key.replace('sync_', '')
            # Get the mapped TLC ID
            tlc_id = request.form.get(f'mapping_{kid_id}')
            
            if tlc_id:
                # SAFE SYNC: We only mark attendance as Present (True).
                # We do NOT mark anyone as Absent (False).
                # This ensures that if someone is marked Present on TLC but not checked in locally,
                # their status on TLC is preserved (not overwritten).
                if client.mark_attendance(event_id, tlc_id, present=True):
                    count += 1
                    # Update local sync status
                    # We need to find the checkin record for this kid on this date
                    if target_date_str:
                        # Convert UTC checkin_time to local timezone before comparing dates
                        tz = get_timezone()
                        naive_dt = datetime.strptime(target_date_str, '%Y-%m-%d')
                        localized_dt = naive_dt.replace(tzinfo=tz)
                        tz_offset_hours = localized_dt.utcoffset().total_seconds() / 3600
                        tz_offset_str = f"{tz_offset_hours:+.0f} hours"
                        conn.execute('''
                            UPDATE checkins 
                            SET tlc_synced = 1 
                            WHERE kid_id = ? AND date(datetime(checkin_time, ?)) = ?
                        ''', (kid_id, tz_offset_str, target_date_str))
                else:
                    errors += 1
    
    conn.commit()
    conn.close()
                    
    if errors > 0:
        flash(f'Synced {count} records, but {errors} failed.', 'warning')
    else:
        flash(f'Successfully synced {count} records to Trail Life Connect!', 'success')
        
    return redirect(url_for('admin_tlc'))

@app.route('/admin/tlc/roster', methods=['GET'])
@require_auth
def admin_tlc_roster():
    branding = get_branding_settings()
    if 'tlc_email' not in session:
        return redirect(url_for('admin_tlc'))
    
    client = TrailLifeConnectClient(session['tlc_email'], session['tlc_password'])
    if not client.login():
        return redirect(url_for('admin_tlc'))

    # We need an event to get the roster. 
    # If provided in args, use it. Otherwise try to find one.
    event_id = request.args.get('event_id')
    
    if not event_id:
        # Try to get the first upcoming event
        events = client.get_upcoming_events()
        if events:
            event_id = events[0]['id']
        else:
            flash("No upcoming events found to fetch roster from. Please ensure there is at least one event in TLC.", "warning")
            return redirect(url_for('admin_tlc'))
            
    tlc_roster = client.get_event_roster(event_id) # Dict: Name -> {'id': ..., 'profile_url': ...}
    
    conn = get_db()
    kids = conn.execute("SELECT id, name, tlc_id FROM kids ORDER BY name").fetchall()
    conn.close()
    
    # Prepare options for dropdown
    tlc_options = [{'id': data['id'], 'name': name} for name, data in tlc_roster.items()]
    tlc_options.sort(key=lambda x: x['name'])
    
    # Helper for name normalization
    def normalize(n):
        return n.lower().replace(',', '').replace('.', '').strip()

    roster_rows = []
    for kid in kids:
        current_tlc_id = kid['tlc_id']
        match_status = 'unlinked'
        suggested_id = current_tlc_id
        
        # If not linked, try to auto-match
        if not current_tlc_id:
            local_norm = normalize(kid['name'])
            for tlc_name, tlc_id in tlc_roster.items():
                tlc_norm = normalize(tlc_name)
                if local_norm == tlc_norm:
                    suggested_id = tlc_id
                    match_status = 'auto-match'
                    break
                # Check swapped
                parts = tlc_norm.split()
                if len(parts) >= 2:
                    swapped = f"{parts[1]} {parts[0]}"
                    if local_norm == swapped:
                        suggested_id = tlc_id
                        match_status = 'auto-match'
                        break
        else:
            match_status = 'linked'
            
        roster_rows.append({
            'id': kid['id'],
            'name': kid['name'],
            'current_tlc_id': current_tlc_id,
            'suggested_id': suggested_id,
            'status': match_status
        })
        
    return render_template('admin/tlc_sync.html', 
                         step='roster', 
                         roster_rows=roster_rows, 
                         tlc_options=tlc_options, 
                         branding=branding)

@app.route('/admin/tlc/roster/save', methods=['POST'])
@require_auth
def admin_tlc_roster_save():
    conn = get_db()
    count = 0
    
    for key, value in request.form.items():
        if key.startswith('tlc_id_'):
            kid_id = key.replace('tlc_id_', '')
            tlc_id = value if value else None
            
            conn.execute("UPDATE kids SET tlc_id = ? WHERE id = ?", (tlc_id, kid_id))
            count += 1
            
    conn.commit()
    conn.close()
    
    flash(f"Updated roster links for {count} records.", "success")
    return redirect(url_for('admin_tlc'))

@app.route('/admin/tlc/roster/sync', methods=['GET'])
@require_auth
def admin_tlc_roster_sync():
    """Sync roster from TLC - creates local kids for any TLC members not yet in the system."""
    branding = get_branding_settings()
    if 'tlc_email' not in session:
        flash("Please login to Trail Life Connect first.", "warning")
        return redirect(url_for('admin_tlc'))
    
    client = TrailLifeConnectClient(session['tlc_email'], session['tlc_password'])
    if not client.login():
        flash("TLC Login failed. Please try again.", "danger")
        return redirect(url_for('admin_tlc'))

    # Get first upcoming event to fetch roster
    events = client.get_upcoming_events()
    if not events:
        flash("No upcoming events found to fetch roster from.", "warning")
        return redirect(url_for('admin_tlc_roster'))
        
    event_id = events[0]['id']
    tlc_roster = client.get_event_roster(event_id)  # Dict: Name -> {'id': ..., 'profile_url': ...}
    
    conn = get_db()
    
    # Get existing kids with TLC IDs
    existing_tlc_ids = set()
    rows = conn.execute("SELECT tlc_id FROM kids WHERE tlc_id IS NOT NULL AND tlc_id != ''").fetchall()
    for row in rows:
        existing_tlc_ids.add(row['tlc_id'])
    
    # Get or create a default "TLC Import" family using placeholder phone
    # Use a recognizable placeholder phone number
    tlc_family_phone = '000-000-0000'
    tlc_family = conn.execute("SELECT id FROM families WHERE phone = ?", (tlc_family_phone,)).fetchone()
    if not tlc_family:
        conn.execute("INSERT INTO families (phone, troop) VALUES (?, ?)", 
                    (tlc_family_phone, 'TLC Import'))
        conn.commit()
        tlc_family = conn.execute("SELECT id FROM families WHERE phone = ?", (tlc_family_phone,)).fetchone()
    
    family_id = tlc_family['id']
    
    # Add new kids from TLC roster
    added_count = 0
    updated_count = 0
    
    for tlc_name, tlc_data in tlc_roster.items():
        tlc_id = tlc_data['id']
        
        if tlc_id in existing_tlc_ids:
            # Already linked, skip
            continue
        
        # Check if there's a kid with matching name (not yet linked)
        # Normalize names for comparison
        def normalize(n):
            return n.lower().replace(',', '').replace('.', '').strip()
        
        tlc_norm = normalize(tlc_name)
        
        # Try to find existing unlinked kid with same name
        kids = conn.execute("SELECT id, name FROM kids WHERE (tlc_id IS NULL OR tlc_id = '')").fetchall()
        matched_kid = None
        
        for kid in kids:
            local_norm = normalize(kid['name'])
            if local_norm == tlc_norm:
                matched_kid = kid
                break
            # Check swapped name (Last First vs First Last)
            parts = tlc_norm.split()
            if len(parts) >= 2:
                swapped = f"{parts[1]} {parts[0]}"
                if local_norm == swapped:
                    matched_kid = kid
                    break
        
        if matched_kid:
            # Update existing kid with TLC ID
            conn.execute("UPDATE kids SET tlc_id = ? WHERE id = ?", (tlc_id, matched_kid['id']))
            updated_count += 1
        else:
            # Create new kid with this TLC member
            conn.execute("INSERT INTO kids (name, family_id, tlc_id) VALUES (?, ?, ?)",
                        (tlc_name, family_id, tlc_id))
            added_count += 1
    
    conn.commit()
    conn.close()
    
    if added_count > 0 or updated_count > 0:
        flash(f"Roster sync complete! Added {added_count} new kids, linked {updated_count} existing kids.", "success")
    else:
        flash("Roster sync complete. All TLC members are already in the system.", "info")
    
    return redirect(url_for('admin_tlc_roster'))

@app.route('/admin/tlc/autosync/<int:local_event_id>', methods=['GET'])
@require_auth
def admin_tlc_autosync(local_event_id):
    if 'tlc_email' not in session:
        flash("Please login to Trail Life Connect first.", "warning")
        return redirect(url_for('admin_tlc'))

    # 1. Get Local Event Date
    conn = get_db()
    local_event = conn.execute("SELECT start_time, name FROM events WHERE id = ?", (local_event_id,)).fetchone()
    conn.close()

    if not local_event:
        flash("Local event not found.", "danger")
        return redirect(url_for('admin_tlc'))

    # Parse local date (YYYY-MM-DD HH:MM:SS or ISO -> MM/DD/YYYY)
    start_time_str = local_event['start_time']
    try:
        # Try standard format first
        local_dt = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            # Try ISO format (handles T and timezone)
            local_dt = datetime.fromisoformat(start_time_str)
        except ValueError:
            try:
                # Try just date part if it's YYYY-MM-DD...
                local_dt = datetime.strptime(start_time_str[:10], '%Y-%m-%d')
            except ValueError:
                flash(f"Error parsing local event date: {start_time_str}", "danger")
                return redirect(url_for('admin_tlc'))
    
    target_date_str = local_dt.strftime('%m/%d/%Y')

    # 2. Login and Fetch TLC Events
    client = TrailLifeConnectClient(session['tlc_email'], session['tlc_password'])
    if not client.login():
        flash("TLC Login failed.", "danger")
        return redirect(url_for('admin_tlc'))

    tlc_events = client.get_upcoming_events()
    
    # 3. Find Match
    matched_event_id = None
    
    # First pass: Exact Date Match
    date_matches = [e for e in tlc_events if e['date'] == target_date_str]
    
    if len(date_matches) == 1:
        matched_event_id = date_matches[0]['id']
    elif len(date_matches) > 1:
        # Tie-breaker: Name similarity?
        # For now, just pick the first one, or maybe the one with "Troop" in the name?
        # Let's try to find one that contains "Troop" if the local one does
        if "troop" in local_event['name'].lower():
            for e in date_matches:
                if "troop" in e['name'].lower():
                    matched_event_id = e['id']
                    break
        
        # If still no match, just take the first one
        if not matched_event_id:
            matched_event_id = date_matches[0]['id']
            
    if matched_event_id:
        # Redirect directly to confirmation page
        return redirect(url_for('admin_tlc_sync_confirm', event_id=matched_event_id))
    else:
        flash(f"Could not automatically find a TLC event for date {target_date_str}. Please select manually.", "warning")
        return redirect(url_for('admin_tlc'))


if __name__ == '__main__':
    # Initialize database on startup
    ensure_db()
    
    # Get configuration from environment variables
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    
    # Start the Flask development server
    print(f"Starting Flask application on {host}:{port}")
    print(f"Debug mode: {debug_mode}")
    print(f"Access the application at: http://localhost:{port}")
    
    app.run(host=host, port=port, debug=debug_mode)
