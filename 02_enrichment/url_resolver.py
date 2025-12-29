#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enriquecedor Ultimate de Google News - Versión Híbrida Optimizada
Combina lo mejor de múltiples implementaciones con procesamiento de las primeras 100 filas por defecto

Uso:
  python enriquecedor_ultimate.py --excel datos.xlsx
  python enriquecedor_ultimate.py --excel datos.xlsx --limit 100 --use-cache
  python enriquecedor_ultimate.py --excel datos.xlsx --parallel --workers 5
"""

import argparse
import base64
import hashlib
import json
import logging
import os
import random
import re
import shutil
import sqlite3
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs, unquote, quote, urljoin

# Definir USER_AGENTS antes de su uso
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0',
]

# Definir ENRICH_COLS
ENRICH_COLS = [
    'URL_Directa','Metodo_Resolucion','Titulo_Extraido','Fecha_Extraida_Raw','Fecha_Extraida_ISO',
    'Contenido_Completo','Descripcion_Breve','Autor','Palabras','HTTP_Status','Estado_Procesamiento',
    'Error_Tipo','Fecha_Procesamiento','Intentos_Resolucion', 'Tiempo_Procesamiento', 
    'Hash_Contenido', 'Confianza_Extraccion', 'Fuente_Dominio'
]

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Importaciones opcionales con verificación
try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    trafilatura = None
    HAS_TRAFILATURA = False
    logging.warning("trafilatura no instalado - extracción menos precisa")

try:
    from newspaper import Article
    HAS_NEWSPAPER = True
except ImportError:
    Article = None
    HAS_NEWSPAPER = False
    logging.warning("newspaper3k no instalado - usando fallback")

try:
    import dateparser
    HAS_DATEPARSER = True
except ImportError:
    dateparser = None
    HAS_DATEPARSER = False
    logging.warning("dateparser no instalado - fechas sin normalizar")

def _load_gnewsdecoder():
    """Función para cargar googlenewsdecoder desde múltiples ubicaciones posibles"""
    global HAS_GNEWSDECODER, gnewsdecoder

    try:
        import googlenewsdecoder
        gnewsdecoder = googlenewsdecoder.gnewsdecoder
        HAS_GNEWSDECODER = True
        logging.info("googlenewsdecoder cargado correctamente desde instalación estándar")
        return
    except ImportError:
        gnewsdecoder = None
        HAS_GNEWSDECODER = False
        try:
            import importlib.util
            fallback_paths = [
                os.path.join(os.path.dirname(__file__), 'google-news-url-decoder-main'),
                os.path.join(os.path.dirname(__file__), 'googlenewsdecoder.py'),
                os.path.join(os.path.dirname(__file__), 'googlenewsdecoder', '__init__.py'),
            ]
            for p in fallback_paths:
                try:
                    if p.endswith('.py'):
                        # Cargar módulo directamente desde archivo .py
                        spec = importlib.util.spec_from_file_location("googlenewsdecoder", p)
                        if spec and spec.loader:
                            try:
                                module = importlib.util.module_from_spec(spec)
                                spec.loader.exec_module(module)
                            except Exception as e:
                                logging.debug("Error cargando módulo desde archivo %s: %s", p, str(e))
                                continue
                            try:
                                gnewsdecoder = getattr(module, 'gnewsdecoder', None)
                            except Exception as e:
                                logging.debug("Error obteniendo 'gnewsdecoder' del módulo cargado desde %s: %s", p, str(e))
                                continue
                            if gnewsdecoder:
                                HAS_GNEWSDECODER = True
                                logging.info("googlenewsdecoder cargado desde archivo local: %s", p)
                                return
                    else:
                        # Insertar carpeta en path e intentar import normal
                        if os.path.isdir(p):
                            inserted = False
                            if p not in sys.path:
                                sys.path.insert(0, p)
                                inserted = True
                            try:
                                from googlenewsdecoder import gnewsdecoder
                                HAS_GNEWSDECODER = True
                                logging.info("googlenewsdecoder cargado desde path: %s", p)
                                return
                            except ImportError as e:
                                logging.debug("No se pudo importar googlenewsdecoder desde %s: %s", p, str(e))
                                HAS_GNEWSDECODER = False
                            finally:
                                if inserted and p in sys.path and not HAS_GNEWSDECODER:
                                    try:
                                        sys.path.remove(p)
                                    except ValueError:
                                        pass
                                HAS_GNEWSDECODER = False
                except Exception as e:
                    logging.debug("Error procesando la ruta de fallback %s: %s", p, str(e))
                    continue
        except Exception as e:
            logging.debug("No fue posible usar importlib.util para cargar googlenewsdecoder: %s", str(e))

# Llamar a la función para cargar el módulo
_load_gnewsdecoder()

class RateLimiter:
    """Control de rate limiting con estrategia anti-bloqueo robusta"""

    def __init__(self):
        self.last_request = {}
        self.error_count = {}
        self.backoff_until = {}
        self.request_count = 0
        # Nuevas variables para estrategia anti-bloqueo
        self.google_request_count = 0
        self.last_google_reset = time.time()
        self.daily_google_limit = 999999  # Límite desactivado - Colab cambia IP al reconectar

    def wait_if_needed(self, url: str):
        """Aplica delay inteligente con estrategia anti-bloqueo robusta"""
        domain = urlparse(url).netloc.lower()
        now = time.time()

        # Contador global de requests
        self.request_count += 1

        # Estrategia especial anti-bloqueo para Google News
        if 'google.' in domain:
            self.google_request_count += 1
            
            # Reset contador cada 24 horas
            if now - self.last_google_reset > 86400:  # 24 horas
                self.google_request_count = 0
                self.last_google_reset = now
                logging.info("🔄 Reset contador diario Google News - Estrategia anti-bloqueo")
            
            # Límite diario conservador para evitar bloqueos
            if self.google_request_count > self.daily_google_limit:
                remaining_time = 86400 - (now - self.last_google_reset)
                logging.warning(f"🛡️ Límite diario Google alcanzado ({self.daily_google_limit}). Pausa hasta mañana: {remaining_time/3600:.1f}h")
                # En lugar de esperar 24h, hacer pausa de 1 hora y reducir límite
                time.sleep(3600)  # 1 hora
                self.daily_google_limit = max(100, self.daily_google_limit - 50)  # Reducir límite
                self.google_request_count = 0
                logging.info(f"🛡️ Límite reducido a {self.daily_google_limit} para evitar futuros bloqueos")

        # Verificar backoff
        if domain in self.backoff_until:
            wait_time = self.backoff_until[domain] - now
            if wait_time > 0:
                logging.debug(f"🛡️ Backoff anti-bloqueo para {domain}: esperando {wait_time:.1f}s")
                time.sleep(wait_time)

        # Delay base adaptativo con estrategia anti-bloqueo
        if domain in self.last_request:
            elapsed = now - self.last_request[domain]

            # Delays más conservadores y progresivos para Google
            if 'google.' in domain:
                # Delay progresivo basado en número de requests para evitar detección
                base_delay = 2.5 + (self.google_request_count / 100)  # Aumenta gradualmente
                # Variación aleatoria para parecer más humano
                min_delay = random.uniform(base_delay, base_delay + 4)
                
                # Pausa extra cada 100 requests para evitar patrones (reducida)
                if self.google_request_count % 100 == 0:
                    extra_pause = random.uniform(10, 20)  # 10-20 segundos (reducido)
                    logging.info(f"🛡️ Pausa anti-detección: {extra_pause:.1f}s (cada 100 requests)")
                    time.sleep(extra_pause)
                    
                logging.debug(f"🛡️ Delay Google anti-bloqueo: {min_delay:.1f}s (request #{self.google_request_count})")
            else:
                min_delay = random.uniform(0.8, 2.0)  # Más conservador

            if elapsed < min_delay:
                sleep_time = min_delay - elapsed
                time.sleep(sleep_time)
        else:
            # Primera request al dominio - delay inicial
            if 'google.' in domain:
                initial_delay = random.uniform(2.0, 4.0)
                time.sleep(initial_delay)
        
        self.last_request[domain] = time.time()
    
    def record_error(self, url: str):
        """Registra error y aplica backoff"""
        domain = urlparse(url).netloc.lower()
        self.error_count[domain] = self.error_count.get(domain, 0) + 1
        
        if self.error_count[domain] >= 3:
            # FAIL FAST: Si hay 3+ errores consecutivos, abortar en lugar de backoff infinito
            if self.error_count[domain] >= 5:
                raise Exception(f"🚨 FAIL FAST: Demasiados errores consecutivos para {domain}. Google News puede estar bloqueando.")
            backoff_seconds = min(30, 2 ** (self.error_count[domain] - 2))  # Max 30s en lugar de 120s
            self.backoff_until[domain] = time.time() + backoff_seconds
            logging.warning(f"Backoff de {backoff_seconds}s para {domain}")
    
    def record_success(self, url: str):
        """Registra éxito y reduce contador de errores"""
        domain = urlparse(url).netloc.lower()
        if domain in self.error_count:
            self.error_count[domain] = max(0, self.error_count[domain] - 1)

class PersistentCache:
    """Cache SQLite mejorado con índices y limpieza automática"""
    
    def __init__(self, db_path: str = 'news_enrichment_cache.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._cleanup_old_entries()
    
    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS url_resolution (
                google_url TEXT PRIMARY KEY,
                direct_url TEXT,
                method TEXT,
                resolved_at TIMESTAMP,
                attempts INTEGER DEFAULT 1,
                success BOOLEAN DEFAULT 1
            );
            
            CREATE TABLE IF NOT EXISTS content_cache (
                url TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                date_raw TEXT,
                date_iso TEXT,
                author TEXT,
                description TEXT,
                word_count INTEGER,
                http_status INTEGER,
                extraction_method TEXT,
                cached_at TIMESTAMP,
                content_hash TEXT,
                confidence REAL
            );
            
            CREATE INDEX IF NOT EXISTS idx_content_hash ON content_cache(content_hash);
            CREATE INDEX IF NOT EXISTS idx_resolved_at ON url_resolution(resolved_at);
            CREATE INDEX IF NOT EXISTS idx_cached_at ON content_cache(cached_at);
        """)
        self.conn.commit()
    
    def _cleanup_old_entries(self, days: int = 30):
        """Limpia entradas antiguas del cache"""
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        self.conn.execute(
            "DELETE FROM url_resolution WHERE julianday('now') - julianday(resolved_at) > ?",
            (days,)
        )
        self.conn.execute(
            "DELETE FROM content_cache WHERE julianday('now') - julianday(cached_at) > ?",
            (days,)
        )
        self.conn.commit()
    
    def get_resolution(self, google_url: str) -> Optional[Tuple[str, str]]:
        cursor = self.conn.execute(
            "SELECT direct_url, method FROM url_resolution WHERE google_url = ? AND success = 1",
            (google_url,)
        )
        row = cursor.fetchone()
        return (row['direct_url'], row['method']) if row else None
    
    def save_resolution(self, google_url: str, direct_url: str, method: str, success: bool = True):
        self.conn.execute(
            "INSERT OR REPLACE INTO url_resolution VALUES (?, ?, ?, ?, 1, ?)",
            (google_url, direct_url, method, datetime.now().isoformat(), success)
        )
        self.conn.commit()
    
    def get_content(self, url: str) -> Optional[Dict]:
        cursor = self.conn.execute(
            "SELECT * FROM content_cache WHERE url = ?",
            (url,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def save_content(self, url: str, data: Dict):
        content_hash = hashlib.md5(
            data.get('content', '').encode('utf-8')
        ).hexdigest() if data.get('content') else ''
        
        self.conn.execute(
            """INSERT OR REPLACE INTO content_cache 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                url,
                data.get('title', ''),
                data.get('content', ''),
                data.get('date_raw', ''),
                data.get('date_iso', ''),
                data.get('author', ''),
                data.get('description', ''),
                data.get('word_count', 0),
                data.get('http_status', 0),
                data.get('extraction_method', ''),
                datetime.now().isoformat(),
                content_hash,
                data.get('confidence', 0.0)
            )
        )
        self.conn.commit()

class RobustSession:
    """Sesión HTTP mejorada con reintentos y rotación de headers"""
    
    def __init__(self):
        self.session = self._create_session()
        self.request_count = 0
        
    def _create_session(self) -> requests.Session:
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504, 520, 521, 522, 523, 524],
            allowed_methods=["GET", "POST", "HEAD"]
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        session.headers.update({
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
        
        return session
    
    def get(self, url: str, **kwargs) -> requests.Response:
        self.request_count += 1
        
        # Rotar user agent periódicamente
        if self.request_count % 5 == 0:
            self.session.headers['User-Agent'] = random.choice(USER_AGENTS)
        
        # Headers específicos para RSS
        if 'news.google.com/rss' in url:
            headers = kwargs.get('headers', {})
            headers.update({
                'Accept': 'application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5',
                'Referer': 'https://news.google.com/'
            })
            kwargs['headers'] = headers
        
        kwargs.setdefault('timeout', 20)
        kwargs.setdefault('allow_redirects', True)
        
        return self.session.get(url, **kwargs)

class UltimateGoogleNewsResolver:
    """Resolvedor definitivo con todos los métodos disponibles"""
    
    def __init__(self, rate_limiter: RateLimiter, cache: Optional[PersistentCache] = None):
        self.session = RobustSession()
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.logger = logging.getLogger(__name__)
        self._gnews_tried_urls = set()
        
    def resolve(self, google_url: str, max_attempts: int = 3) -> Tuple[str, str]:
        """Resuelve URL con múltiples intentos y métodos"""
        
        if not google_url or not isinstance(google_url, str):
            return '', 'invalid_input'
        
        # Verificar cache
        if self.cache:
            cached = self.cache.get_resolution(google_url)
            if cached:
                self.logger.debug(f"Resolución en cache: {cached[0][:50]}...")
                return cached
        
        # Intentar con googlenewsdecoder primero si está disponible
        if HAS_GNEWSDECODER and google_url not in self._gnews_tried_urls:
            self._gnews_tried_urls.add(google_url)
            result = self._try_gnewsdecoder(google_url)
            if result:
                if self.cache:
                    self.cache.save_resolution(google_url, result, 'gnewsdecoder')
                return result, 'gnewsdecoder'
        
        # Array de métodos ordenados por efectividad
        methods = [
            ('decode_cbm_advanced', self._decode_cbm_advanced),
            ('extract_url_params', self._extract_from_params),
            ('resolve_via_rss', self._resolve_via_rss),
            ('resolve_via_articles', self._resolve_via_articles_page),
            ('follow_redirects', self._follow_redirects),
            ('parse_html_advanced', self._parse_html_advanced),
            ('decode_base64_variations', self._decode_base64_variations),
        ]
        
        for attempt in range(max_attempts):
            if attempt > 0:
                self.logger.info(f"Intento {attempt + 1}/{max_attempts} para {google_url[:50]}...")
                time.sleep(random.uniform(2, 4))
            
            for method_name, method_func in methods:
                try:
                    self.logger.debug(f"Probando método: {method_name}")
                    result = method_func(google_url)
                    
                    if result and self._is_valid_external_url(result):
                        self.logger.info(f"✓ Resuelto con {method_name}: {result[:50]}...")
                        
                        if self.cache:
                            self.cache.save_resolution(google_url, result, method_name)
                        
                        return result, method_name
                        
                except Exception as e:
                    self.logger.debug(f"Error en {method_name}: {str(e)[:100]}")
                    continue
        
        self.logger.warning(f"✗ No resuelto después de {max_attempts} intentos: {google_url[:50]}...")
        
        if self.cache:
            self.cache.save_resolution(google_url, google_url, 'no_resolution', success=False)
        
        return google_url, 'no_resolution'
    
    def _is_valid_external_url(self, url: str) -> bool:
        """Valida que sea una URL externa válida"""
        if not url or not isinstance(url, str):
            return False
        if not url.startswith(('http://', 'https://')):
            return False
        
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        blocked_domains = [
            'google.', 'gstatic.', 'googleusercontent.',
            'googlevideo.', 'youtube.', 'youtu.be'
        ]
        
        return not any(blocked in domain for blocked in blocked_domains)
    
    def _try_gnewsdecoder(self, url: str) -> Optional[str]:
        """Intenta resolver con googlenewsdecoder"""
        if not HAS_GNEWSDECODER or 'news.google.com' not in url:
            return None
        
        try:
            self.rate_limiter.wait_if_needed(url)
            result = gnewsdecoder(url, interval=0)
            
            if isinstance(result, dict) and result.get('status') and result.get('decoded_url'):
                decoded = result['decoded_url']
                if self._is_valid_external_url(decoded):
                    self.rate_limiter.record_success(url)
                    return decoded
            
        except Exception as e:
            self.logger.debug(f"gnewsdecoder error: {e}")
            self.rate_limiter.record_error(url)
        
        return None
    
    def _decode_cbm_advanced(self, url: str) -> Optional[str]:
        """Decodificación avanzada de tokens CBM/CAE/CAI"""
        try:
            patterns = [
                r'/articles/([^?/]+)',
                r'/read/([^?/]+)',
                r'(C[AB][MEI0-9][A-Za-z0-9_\-]+)',
                r'articles%2F([^&]+)',
                r'read%2F([^&]+)'
            ]
            
            token = None
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    token = match.group(1)
                    break
            
            if not token:
                return None
            
            # Limpiar token
            token = unquote(token)
            candidates = []
            
            # Remover prefijos conocidos
            prefixes = ['CBM', 'CAE', 'CAI', 'CB0', 'CB1', 'CB2']
            clean_token = token
            for prefix in prefixes:
                if clean_token.startswith(prefix):
                    clean_token = clean_token[len(prefix):]
            
            # Variaciones del token
            test_tokens = [
                token, clean_token,
                token.replace('-', '+').replace('_', '/'),
                clean_token.replace('-', '+').replace('_', '/'),
                token.replace('%3D', '=').replace('%2B', '+').replace('%2F', '/')
            ]
            
            for test_token in test_tokens:
                for padding in ['', '=', '==', '===']:
                    try:
                        # Base64 estándar
                        decoded = base64.b64decode(test_token + padding)
                        text = decoded.decode('utf-8', errors='ignore')
                        candidates.append(text)
                    except:
                        pass
                    
                    try:
                        # Base64 URL-safe
                        decoded = base64.urlsafe_b64decode(test_token + padding)
                        text = decoded.decode('utf-8', errors='ignore')
                        candidates.append(text)
                    except:
                        pass
            
            # Buscar URLs en candidatos
            url_pattern = re.compile(r'https?://[^\s"\'<>\x00-\x1f]+')
            
            for candidate in candidates:
                urls = url_pattern.findall(candidate)
                for found_url in urls:
                    found_url = found_url.rstrip('.,;:)]}\'"')
                    if self._is_valid_external_url(found_url):
                        return found_url
                        
        except Exception as e:
            self.logger.debug(f"Error en decode_cbm: {e}")
            
        return None
    
    def _extract_from_params(self, url: str) -> Optional[str]:
        """Extrae URL de parámetros de query string"""
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            param_names = ['url', 'u', 'q', 'link', 'redirect', 'target', 'dest', 'goto', 'out']
            
            for param_name in param_names:
                if param_name in params:
                    candidate = params[param_name][0]
                    candidate = unquote(candidate)
                    
                    if self._is_valid_external_url(candidate):
                        return candidate
                        
        except Exception as e:
            self.logger.debug(f"Error en extract_params: {e}")
            
        return None
    
    def _resolve_via_rss(self, url: str) -> Optional[str]:
        """Resuelve mediante feed RSS"""
        try:
            token_match = re.search(r'/read/([^?]+)', url)
            if not token_match:
                token_match = re.search(r'/articles/([^?]+)', url)
            
            if not token_match:
                return None
            
            token = token_match.group(1)
            rss_url = f"https://news.google.com/rss/articles/{token}"
            
            parsed = urlparse(url)
            if parsed.query:
                rss_url = f"{rss_url}?{parsed.query}"
            
            self.rate_limiter.wait_if_needed(rss_url)
            
            try:
                response = self.session.get(rss_url)
                response.raise_for_status()
                
                # Parsear con BeautifulSoup en modo XML
                soup = BeautifulSoup(response.content, 'xml')
                
                # Buscar links dentro de items
                for item in soup.find_all('item'):
                    link_tag = item.find('link')
                    if link_tag and link_tag.text:
                        link = link_tag.text.strip()
                        if self._is_valid_external_url(link):
                            self.rate_limiter.record_success(rss_url)
                            return link
                
                # Fallback: regex
                for link in re.findall(r'<link>(.*?)</link>', response.text):
                    link = link.strip()
                    if self._is_valid_external_url(link):
                        self.rate_limiter.record_success(rss_url)
                        return link
                        
            except requests.RequestException as e:
                self.rate_limiter.record_error(rss_url)
                self.logger.debug(f"Error HTTP en RSS: {e}")
                
        except Exception as e:
            self.logger.debug(f"Error en resolve_via_rss: {e}")
            
        return None
    
    def _resolve_via_articles_page(self, url: str) -> Optional[str]:
        """Resuelve mediante página de artículos"""
        try:
            token_match = re.search(r'/read/([^?]+)', url)
            if not token_match:
                return None
            
            token = token_match.group(1)
            articles_url = f"https://news.google.com/articles/{token}"
            
            parsed = urlparse(url)
            if parsed.query:
                articles_url = f"{articles_url}?{parsed.query}"
            
            self.rate_limiter.wait_if_needed(articles_url)
            
            try:
                response = self.session.get(articles_url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 1. Canonical link
                canonical = soup.find('link', {'rel': 'canonical'})
                if canonical and canonical.get('href'):
                    href = canonical['href']
                    if self._is_valid_external_url(href):
                        self.rate_limiter.record_success(articles_url)
                        return href
                
                # 2. Open Graph URL
                og_url = soup.find('meta', {'property': 'og:url'})
                if og_url and og_url.get('content'):
                    content = og_url['content']
                    if self._is_valid_external_url(content):
                        self.rate_limiter.record_success(articles_url)
                        return content
                
                # 3. AMP HTML
                amp = soup.find('link', {'rel': 'amphtml'})
                if amp and amp.get('href'):
                    href = amp['href']
                    if self._is_valid_external_url(href):
                        self.rate_limiter.record_success(articles_url)
                        return href
                
                # 4. JSON-LD
                json_scripts = soup.find_all('script', type='application/ld+json')
                for script in json_scripts:
                    try:
                        data = json.loads(script.string)
                        items = [data] if isinstance(data, dict) else data
                        
                        for item in items:
                            if isinstance(item, dict):
                                for key in ['url', 'mainEntityOfPage', '@id']:
                                    if key in item:
                                        url_candidate = item[key]
                                        if isinstance(url_candidate, str) and self._is_valid_external_url(url_candidate):
                                            self.rate_limiter.record_success(articles_url)
                                            return url_candidate
                    except:
                        continue
                
                # 5. Scripts con URLs
                for script in soup.find_all('script'):
                    if script.string:
                        urls = re.findall(r'https?://[^\s"\'<>]+', script.string)
                        for found_url in urls:
                            found_url = found_url.rstrip('.,;:)]}\'"')
                            if self._is_valid_external_url(found_url):
                                self.rate_limiter.record_success(articles_url)
                                return found_url
                
                # 6. Enlaces normales
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    
                    # Convertir URLs relativas a absolutas
                    if not href.startswith('http'):
                        href = urljoin(articles_url, href)
                    
                    if self._is_valid_external_url(href):
                        self.rate_limiter.record_success(articles_url)
                        return href
                    
                    # Extraer de parámetros si es URL de Google
                    if 'google.' in href:
                        extracted = self._extract_from_params(href)
                        if extracted:
                            self.rate_limiter.record_success(articles_url)
                            return extracted
                        
            except requests.RequestException as e:
                self.rate_limiter.record_error(articles_url)
                self.logger.debug(f"Error HTTP: {e}")
                
        except Exception as e:
            self.logger.debug(f"Error en articles_page: {e}")
            
        return None
    
    def _follow_redirects(self, url: str) -> Optional[str]:
        """Sigue redirecciones HTTP"""
        try:
            self.rate_limiter.wait_if_needed(url)
            
            response = self.session.get(url)
            
            if response.url != url and self._is_valid_external_url(response.url):
                self.rate_limiter.record_success(url)
                return response.url
                
        except Exception as e:
            self.logger.debug(f"Error en follow_redirects: {e}")
            self.rate_limiter.record_error(url)
            
        return None
    
    def _parse_html_advanced(self, url: str) -> Optional[str]:
        """Parseo avanzado de HTML buscando URLs"""
        try:
            self.rate_limiter.wait_if_needed(url)
            
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 1. Meta refresh
            meta_refresh = soup.find('meta', attrs={'http-equiv': lambda x: x and x.lower() == 'refresh'})
            if meta_refresh and meta_refresh.get('content'):
                content = meta_refresh['content']
                url_match = re.search(r'url=(.+)', content, re.IGNORECASE)
                if url_match:
                    refresh_url = url_match.group(1).strip('\'"')
                    if self._is_valid_external_url(refresh_url):
                        self.rate_limiter.record_success(url)
                        return refresh_url
            
            # 2. JavaScript window.location
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # Buscar window.location
                    location_matches = re.findall(r'window\.location\s*=\s*[\'"]([^\'"]+)[\'"]', script.string)
                    for match in location_matches:
                        if self._is_valid_external_url(match):
                            self.rate_limiter.record_success(url)
                            return match
                    
                    # Buscar document.location
                    doc_matches = re.findall(r'document\.location\s*=\s*[\'"]([^\'"]+)[\'"]', script.string)
                    for match in doc_matches:
                        if self._is_valid_external_url(match):
                            self.rate_limiter.record_success(url)
                            return match
            
            # 3. Buscar URLs en texto completo
            text_content = soup.get_text()
            url_matches = re.findall(r'https?://[^\s<>"]+', text_content)
            for found_url in url_matches:
                found_url = found_url.rstrip('.,;:)]}\'"')
                if self._is_valid_external_url(found_url):
                    self.rate_limiter.record_success(url)
                    return found_url
                    
        except Exception as e:
            self.logger.debug(f"Error en parse_html_advanced: {e}")
            self.rate_limiter.record_error(url)
            
        return None
    
    def _decode_base64_variations(self, url: str) -> Optional[str]:
        """Intenta múltiples variaciones de decodificación base64"""
        try:
            # Extraer posibles tokens base64 de la URL
            base64_patterns = [
                r'([A-Za-z0-9+/=]{20,})',  # Base64 estándar
                r'([A-Za-z0-9_-]{20,})',   # Base64 URL-safe
                r'%3D([A-Za-z0-9+/%]+)%3D',  # URL encoded base64
            ]
            
            candidates = set()
            
            for pattern in base64_patterns:
                matches = re.findall(pattern, url)
                for match in matches:
                    # Limpiar y normalizar
                    clean_match = unquote(match)
                    candidates.add(clean_match)
                    candidates.add(clean_match.replace('-', '+').replace('_', '/'))
                    candidates.add(clean_match.replace('+', '-').replace('/', '_'))
            
            # Intentar decodificar cada candidato
            for candidate in candidates:
                for padding in ['', '=', '==', '===']:
                    test_string = candidate + padding
                    
                    # Base64 estándar
                    try:
                        decoded = base64.b64decode(test_string)
                        text = decoded.decode('utf-8', errors='ignore')
                        urls = re.findall(r'https?://[^\s<>"]+', text)
                        for found_url in urls:
                            found_url = found_url.rstrip('.,;:)]}\'"')
                            if self._is_valid_external_url(found_url):
                                return found_url
                    except:
                        pass
                    
                    # Base64 URL-safe
                    try:
                        decoded = base64.urlsafe_b64decode(test_string)
                        text = decoded.decode('utf-8', errors='ignore')
                        urls = re.findall(r'https?://[^\s<>"]+', text)
                        for found_url in urls:
                            found_url = found_url.rstrip('.,;:)]}\'"')
                            if self._is_valid_external_url(found_url):
                                return found_url
                    except:
                        pass
                        
        except Exception as e:
            self.logger.debug(f"Error en decode_base64_variations: {e}")
            
        return None

class NewsContentExtractor:
    """Extractor de contenido con múltiples métodos"""
    
    def __init__(self, rate_limiter: RateLimiter, cache: Optional[PersistentCache] = None):
        self.session = RobustSession()
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.logger = logging.getLogger(__name__)
    
    def extract_content(self, url: str) -> Dict:
        """Extrae contenido usando múltiples métodos"""
        
        if not url or not isinstance(url, str):
            return self._empty_result('invalid_url')
        
        # Verificar cache
        if self.cache:
            cached = self.cache.get_content(url)
            if cached:
                self.logger.debug(f"Contenido en cache: {url[:50]}...")
                return cached
        
        start_time = time.time()
        
        # Intentar extracción con trafilatura (más preciso)
        if HAS_TRAFILATURA:
            try:
                result = self._extract_with_trafilatura(url)
                if result and result.get('content'):
                    result['extraction_method'] = 'trafilatura'
                    result['processing_time'] = time.time() - start_time
                    
                    if self.cache:
                        self.cache.save_content(url, result)
                    
                    return result
            except Exception as e:
                self.logger.debug(f"Error con trafilatura: {e}")
        
        # Intentar con newspaper3k
        if HAS_NEWSPAPER:
            try:
                result = self._extract_with_newspaper(url)
                if result and result.get('content'):
                    result['extraction_method'] = 'newspaper3k'
                    result['processing_time'] = time.time() - start_time
                    
                    if self.cache:
                        self.cache.save_content(url, result)
                    
                    return result
            except Exception as e:
                self.logger.debug(f"Error con newspaper3k: {e}")
        
        # Fallback con BeautifulSoup
        try:
            result = self._extract_with_beautifulsoup(url)
            result['extraction_method'] = 'beautifulsoup'
            result['processing_time'] = time.time() - start_time
            
            if self.cache:
                self.cache.save_content(url, result)
            
            return result
        except Exception as e:
            self.logger.warning(f"Error extrayendo contenido de {url}: {e}")
            result = self._empty_result('extraction_error')
            result['processing_time'] = time.time() - start_time
            return result
    
    def _empty_result(self, error_type: str = '') -> Dict:
        """Resultado vacío con estructura completa"""
        return {
            'title': '',
            'content': '',
            'date_raw': '',
            'date_iso': '',
            'author': '',
            'description': '',
            'word_count': 0,
            'http_status': 0,
            'extraction_method': 'failed',
            'confidence': 0.0,
            'error_type': error_type,
            'processing_time': 0.0
        }
    
    def _extract_with_trafilatura(self, url: str) -> Optional[Dict]:
        """Extracción con trafilatura"""
        if not HAS_TRAFILATURA:
            return None
        
        self.rate_limiter.wait_if_needed(url)
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            # Extraer con trafilatura
            content = trafilatura.extract(
                response.content,
                include_comments=False,
                include_tables=True,
                include_formatting=False,
                deduplicate=True,
                favor_precision=True
            )
            
            if not content or len(content.strip()) < 100:
                return None
            
            # Extraer metadatos adicionales
            metadata = trafilatura.extract_metadata(response.content)
            
            title = ''
            author = ''
            date_raw = ''
            description = ''
            
            if metadata:
                title = metadata.title or ''
                author = metadata.author or ''
                date_raw = metadata.date or ''
                description = metadata.description or ''
            
            # Si no hay título, extraer del HTML
            if not title:
                soup = BeautifulSoup(response.content, 'html.parser')
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text().strip()
            
            # Contar palabras
            word_count = len(content.split())
            
            # Calcular confianza basada en longitud y metadatos
            confidence = min(1.0, (word_count / 500) * 0.6 + (0.1 if title else 0) + 
                           (0.1 if author else 0) + (0.1 if date_raw else 0) + 
                           (0.1 if description else 0))
            
            self.rate_limiter.record_success(url)
            
            return {
                'title': title,
                'content': content,
                'date_raw': date_raw,
                'date_iso': self._normalize_date(date_raw),
                'author': author,
                'description': description,
                'word_count': word_count,
                'http_status': response.status_code,
                'confidence': confidence
            }
            
        except Exception as e:
            self.rate_limiter.record_error(url)
            self.logger.debug(f"Error trafilatura para {url}: {e}")
            return None
    
    def _extract_with_newspaper(self, url: str) -> Optional[Dict]:
        """Extracción con newspaper3k"""
        if not HAS_NEWSPAPER:
            return None
        
        try:
            article = Article(url, language='es')
            article.download()
            
            if article.download_state != 2:  # ArticleDownloadState.SUCCESS
                return None
            
            article.parse()
            
            if not article.text or len(article.text.strip()) < 100:
                return None
            
            # Normalizar fecha
            date_iso = ''
            if article.publish_date:
                try:
                    date_iso = article.publish_date.isoformat()
                except:
                    pass
            
            word_count = len(article.text.split())
            confidence = min(1.0, (word_count / 500) * 0.7 + 
                           (0.1 if article.title else 0) + 
                           (0.1 if article.authors else 0) + 
                           (0.1 if date_iso else 0))
            
            self.rate_limiter.record_success(url)
            
            return {
                'title': article.title or '',
                'content': article.text,
                'date_raw': str(article.publish_date) if article.publish_date else '',
                'date_iso': date_iso,
                'author': ', '.join(article.authors) if article.authors else '',
                'description': article.summary or '',
                'word_count': word_count,
                'http_status': 200,
                'confidence': confidence
            }
            
        except Exception as e:
            self.rate_limiter.record_error(url)
            self.logger.debug(f"Error newspaper3k para {url}: {e}")
            return None
    
    def _extract_with_beautifulsoup(self, url: str) -> Dict:
        """Extracción fallback con BeautifulSoup"""
        
        self.rate_limiter.wait_if_needed(url)
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extraer título
            title = ''
            title_selectors = ['title', 'h1', '[property="og:title"]', '[name="title"]']
            for selector in title_selectors:
                element = soup.select_one(selector)
                if element:
                    title = element.get_text().strip() or element.get('content', '').strip()
                    if title:
                        break
            
            # Extraer contenido
            content = self._extract_main_content(soup)
            
            # Extraer autor
            author = ''
            author_selectors = [
                '[property="article:author"]', '[name="author"]', 
                '.author', '.byline', '[rel="author"]'
            ]
            for selector in author_selectors:
                element = soup.select_one(selector)
                if element:
                    author = element.get_text().strip() or element.get('content', '').strip()
                    if author:
                        break
            
            # Extraer fecha
            date_raw = ''
            date_selectors = [
                '[property="article:published_time"]', 
                '[name="publish_date"]', 
                'time[datetime]',
                '.date', '.published'
            ]
            for selector in date_selectors:
                element = soup.select_one(selector)
                if element:
                    date_raw = (element.get('datetime') or 
                              element.get('content') or 
                              element.get_text()).strip()
                    if date_raw:
                        break
            
            # Extraer descripción
            description = ''
            desc_selectors = [
                '[property="og:description"]', 
                '[name="description"]',
                'meta[name="description"]'
            ]
            for selector in desc_selectors:
                element = soup.select_one(selector)
                if element:
                    description = element.get('content', '').strip()
                    if description:
                        break
            
            word_count = len(content.split())
            confidence = min(1.0, (word_count / 500) * 0.4 + 
                           (0.15 if title else 0) + 
                           (0.15 if author else 0) + 
                           (0.15 if date_raw else 0) + 
                           (0.15 if description else 0))
            
            self.rate_limiter.record_success(url)
            
            return {
                'title': title,
                'content': content,
                'date_raw': date_raw,
                'date_iso': self._normalize_date(date_raw),
                'author': author,
                'description': description,
                'word_count': word_count,
                'http_status': response.status_code,
                'confidence': confidence
            }
            
        except Exception as e:
            self.rate_limiter.record_error(url)
            self.logger.debug(f"Error BeautifulSoup para {url}: {e}")
            
            return self._empty_result('http_error')
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extrae el contenido principal usando heurísticas"""
        
        # Remover elementos no deseados
        for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        
        # Selectores de contenido principal (en orden de preferencia)
        content_selectors = [
            'article', '[role="main"]', 'main', '.article-content', 
            '.entry-content', '.post-content', '.content', '.story-body',
            '.article-body', '.post-body', '#content', '.main-content'
        ]
        
        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(separator=' ', strip=True)
                if len(text) > 200:  # Contenido mínimo
                    return text
        
        # Fallback: buscar el div con más texto
        divs = soup.find_all(['div', 'section', 'article'])
        best_div = None
        max_length = 0
        
        for div in divs:
            text = div.get_text(separator=' ', strip=True)
            if len(text) > max_length and len(text) > 200:
                max_length = len(text)
                best_div = div
        
        if best_div:
            return best_div.get_text(separator=' ', strip=True)
        
        # Último recurso: todo el texto del body
        body = soup.find('body')
        if body:
            return body.get_text(separator=' ', strip=True)
        
        return soup.get_text(separator=' ', strip=True)
    
    def _normalize_date(self, date_str: str) -> str:
        """Normaliza fecha a formato ISO"""
        if not date_str or not HAS_DATEPARSER:
            return ''
        
        try:
            parsed_date = dateparser.parse(date_str)
            if parsed_date:
                return parsed_date.isoformat()
        except:
            pass
        
        return ''

class NewsProcessor:
    """Clase que procesa las URLs usando el enriquecedor"""
    
    def __init__(self, enricher: 'UltimateNewsEnricher', cache: Optional[PersistentCache] = None):
        self.enricher = enricher
        self.cache = cache
        self.logger = logging.getLogger(__name__)
    
    def process_sequential(self, df: pd.DataFrame, url_column: str) -> List[Tuple[str, str, str, Dict]]:
        """Procesamiento secuencial que retorna lista de tuplas"""
        results = []
        urls = df[url_column].tolist()
        
        for i, url in enumerate(urls):
            if pd.isna(url) or not isinstance(url, str):
                results.append(('', 'invalid_url', '', {}))
                continue
            
            try:
                # Resolver URL
                direct_url, method = self.enricher.resolver.resolve(url)
                
                # Extraer contenido si se resolvió la URL
                content = ''
                metadata = {}
                
                if direct_url and direct_url != url:
                    content_data = self.enricher.extractor.extract_content(direct_url)
                    content = content_data.get('content', '')
                    metadata = {
                        'title': content_data.get('title', ''),
                        'author': content_data.get('author', ''),
                        'date': content_data.get('date_iso', ''),
                        'confidence': content_data.get('confidence', 0.0)
                    }
                
                results.append((direct_url, method, content, metadata))
                
                if (i + 1) % 10 == 0:
                    self.logger.info(f"Procesadas {i + 1}/{len(urls)} URLs")
                    
            except Exception as e:
                self.logger.error(f"Error procesando URL {i}: {e}")
                results.append(('', 'error', '', {}))
        
        return results
    
    def process_parallel(self, df: pd.DataFrame, url_column: str, workers: int) -> List[Tuple[str, str, str, Dict]]:
        """Procesamiento paralelo que retorna lista de tuplas"""
        results = [None] * len(df)
        urls = df[url_column].tolist()
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_index = {
                executor.submit(self._process_single_url, url): i
                for i, url in enumerate(urls)
                if pd.notna(url) and isinstance(url, str)
            }
            
            completed = 0
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    results[index] = result
                    completed += 1
                    
                    if completed % 10 == 0:
                        self.logger.info(f"Completadas {completed}/{len(future_to_index)} URLs")
                        
                except Exception as e:
                    self.logger.error(f"Error procesando índice {index}: {e}")
                    results[index] = ('', 'error', '', {})
        
        # Llenar espacios None con resultados vacíos
        for i in range(len(results)):
            if results[i] is None:
                results[i] = ('', 'invalid_url', '', {})
        
        return results
    
    def _process_single_url(self, url: str) -> Tuple[str, str, str, Dict]:
        """Procesa una sola URL y retorna tupla"""
        try:
            # Resolver URL
            direct_url, method = self.enricher.resolver.resolve(url)
            
            # Extraer contenido si se resolvió la URL
            content = ''
            metadata = {}
            
            if direct_url and direct_url != url:
                content_data = self.enricher.extractor.extract_content(direct_url)
                content = content_data.get('content', '')
                metadata = {
                    'title': content_data.get('title', ''),
                    'author': content_data.get('author', ''),
                    'date': content_data.get('date_iso', ''),
                    'confidence': content_data.get('confidence', 0.0)
                }
            
            return (direct_url, method, content, metadata)
            
        except Exception as e:
            self.logger.error(f"Error procesando URL {url}: {e}")
            return ('', 'error', '', {})

class UltimateNewsEnricher:
    """Enriquecedor principal que combina resolución y extracción"""
    
    def __init__(self, use_cache: bool = True, workers: int = 3):
        self.rate_limiter = RateLimiter()
        self.cache = PersistentCache() if use_cache else None
        self.resolver = UltimateGoogleNewsResolver(self.rate_limiter, self.cache)
        self.extractor = NewsContentExtractor(self.rate_limiter, self.cache)
        self.workers = workers
        self.logger = logging.getLogger(__name__)

def crear_backup_excel(excel_path: str) -> str:
    """Crea backup del archivo Excel antes de modificarlo"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = excel_path.replace('.xlsx', f'_backup_{timestamp}.xlsx')
        shutil.copy2(excel_path, backup_path)
        print(f"📋 Backup creado: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"⚠️ Error creando backup: {e}")
        return ""

def validar_escritura_excel(excel_path: str, sheet_name: str, indices_esperados: List[int], df_esperado: pd.DataFrame) -> bool:
    """Valida que los datos se escribieron correctamente al Excel"""
    try:
        df_leido = pd.read_excel(excel_path, sheet_name=sheet_name)
        
        urls_esperadas = 0
        urls_encontradas = 0
        
        for idx in indices_esperados:
            if idx < len(df_esperado) and idx < len(df_leido):
                url_esperada = df_esperado.iloc[idx]['URL_Directa']
                url_leida = df_leido.iloc[idx]['URL_Directa']
                
                if pd.notna(url_esperada) and url_esperada != '':
                    urls_esperadas += 1
                    if pd.notna(url_leida) and url_leida != '':
                        urls_encontradas += 1
        
        exito = urls_encontradas == urls_esperadas
        print(f"✅ Validación: {urls_encontradas}/{urls_esperadas} URLs escritas correctamente")
        
        return exito
        
    except Exception as e:
        print(f"❌ Error validando escritura: {e}")
        return False

def main():
    """Función principal con argumentos de línea de comandos"""
    
    parser = argparse.ArgumentParser(description='Enriquecedor Ultimate de Google News')
    parser.add_argument('--excel', required=True, help='Archivo Excel de entrada')
    parser.add_argument('--url-column', default='enlace', help='Nombre de la columna con URLs (default: enlace)')
    parser.add_argument('--limit', type=int, default=500, help='Límite de filas a procesar por tanda (default: 500 - límite de Google News)')
    parser.add_argument('--workers', type=int, default=3, help='Número de workers para procesamiento paralelo')
    parser.add_argument('--parallel', action='store_true', help='Activar procesamiento paralelo')
    parser.add_argument('--use-cache', action='store_true', help='Usar cache SQLite')
    parser.add_argument('--verbose', '-v', action='store_true', help='Logging detallado')
    parser.add_argument('--input-sheet', default='Datos', help='Nombre de la hoja de entrada (default: Datos)')
    parser.add_argument('--output-sheet', default='Datos_enriquecidos', help='Nombre de la hoja de salida (default: Datos_enriquecidos)')
    parser.add_argument('--start-from', type=int, default=1, help='Fila desde donde comenzar a procesar (1-indexed, default: 1)')
    parser.add_argument('--save-frequency', type=int, default=50, help='Guardar progreso cada N elementos (default: 50)')
    parser.add_argument('--anti-block', action='store_true', help='Activar estrategia anti-bloqueo robusta (recomendado para lotes grandes)')
    parser.add_argument('--daily-limit', type=int, default=500, help='Límite diario de requests a Google News (default: 500)')

    args = parser.parse_args()

    # Configurar logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Verificar archivo de entrada
    if not os.path.exists(args.excel):
        print(f"Error: Archivo {args.excel} no encontrado")
        return 1

    try:
        # Cargar datos desde la hoja de entrada
        print(f"Cargando hoja '{args.input_sheet}' de {args.excel}...")
        df_input = pd.read_excel(args.excel, sheet_name=args.input_sheet)
        print(f"Cargadas {len(df_input)} filas desde hoja de entrada")

        # Cargar hoja de salida para continuar desde donde se quedó
        print(f"Cargando hoja '{args.output_sheet}' para continuar procesamiento...")
        try:
            df_output = pd.read_excel(args.excel, sheet_name=args.output_sheet)
            print(f"Encontradas {len(df_output)} filas ya procesadas en la hoja de salida")
        except:
            print("No se pudo cargar la hoja de salida, se creará nueva")
            df_output = df_input.copy()
            # Añadir columnas de enriquecimiento si no existen
            for col in ENRICH_COLS:
                if col not in df_output.columns:
                    df_output[col] = ''

        # Verificar columna URL
        if args.url_column not in df_input.columns:
            print(f"Error: Columna '{args.url_column}' no encontrada")
            print(f"Columnas disponibles: {', '.join(df_input.columns)}")
            return 1

        # Verificar que las hojas tengan el mismo tamaño
        if len(df_input) != len(df_output):
            print(f"Advertencia: La hoja de entrada tiene {len(df_input)} filas, pero la de salida tiene {len(df_output)}")
            # Ajustar tamaño de la hoja de salida
            if len(df_output) < len(df_input):
                # Expandir hoja de salida
                additional_rows = len(df_input) - len(df_output)
                empty_rows = pd.DataFrame(index=range(additional_rows), columns=df_output.columns)
                for col in df_output.columns:
                    if col in df_input.columns:
                        empty_rows[col] = df_input.iloc[len(df_output):][col].values
                    else:
                        empty_rows[col] = ''
                df_output = pd.concat([df_output, empty_rows], ignore_index=True)
            else:
                # Truncar hoja de salida
                df_output = df_output.iloc[:len(df_input)].copy()

        # Añadir columnas de enriquecimiento si no existen
        for col in ENRICH_COLS:
            if col not in df_output.columns:
                df_output[col] = ''

        # Inicializar enriquecedor con estrategia anti-bloqueo
        enricher = UltimateNewsEnricher(
            use_cache=args.use_cache,
            workers=args.workers
        )
        
        # Configurar estrategia anti-bloqueo si está activada
        if args.anti_block:
            enricher.rate_limiter.daily_google_limit = args.daily_limit
            print(f"🛡️ Estrategia anti-bloqueo activada (límite diario: {args.daily_limit})")
        else:
            print("⚠️ Estrategia anti-bloqueo desactivada - usar --anti-block para lotes grandes")

        # Determinar qué filas procesar (solo las que no han sido procesadas)
        start_idx = max(0, args.start_from - 1)  # Convertir a 0-indexed
        
        # Encontrar la primera fila sin procesar (donde URL_Directa esté vacía)
        if 'URL_Directa' in df_output.columns:
            unprocessed_mask = df_output['URL_Directa'].isna() | (df_output['URL_Directa'] == '')
            unprocessed_indices = df_output[unprocessed_mask].index.tolist()
            
            if unprocessed_indices:
                actual_start = max(start_idx, min(unprocessed_indices))
                print(f"Comenzando desde fila {actual_start + 1} (primera fila sin procesar)")
            else:
                print("Todas las filas ya están procesadas")
                return 0
        else:
            actual_start = start_idx
            print(f"Comenzando desde fila {actual_start + 1} (columna URL_Directa no existe)")

        if args.limit == 0:
            end_idx = len(df_input)
        else:
            end_idx = min(actual_start + args.limit, len(df_input))

        # Seleccionar subconjunto de filas para procesar
        indices_to_process = list(range(actual_start, end_idx))
        df_subset = df_input.iloc[indices_to_process].copy()
        
        print(f"Procesando {len(df_subset)} filas (desde la fila {actual_start + 1} hasta {end_idx})...")

        # Procesar URLs
        processor = NewsProcessor(enricher, enricher.cache)

        start_time = time.time()
        
        if args.parallel:
            results = processor.process_parallel(df_subset, args.url_column, args.workers)
        else:
            results = processor.process_sequential(df_subset, args.url_column)

        # Crear backup antes de comenzar las actualizaciones
        print("📋 Creando backup antes del procesamiento...")
        backup_path = crear_backup_excel(args.excel)
        
        # Actualizar DataFrame con resultados y guardado más frecuente
        print("🔄 Actualizando DataFrame con resultados...")
        
        # Variables para tracking de progreso mejorado
        update_start_time = time.time()
        
        for i, (resolved_url, method, content, metadata) in enumerate(results):
            actual_idx = indices_to_process[i]
            
            # Actualizar usando .loc para mayor seguridad
            df_output.loc[actual_idx, 'URL_Directa'] = resolved_url
            df_output.loc[actual_idx, 'Metodo_Resolucion'] = method
            df_output.loc[actual_idx, 'Fecha_Procesamiento'] = datetime.now().isoformat()
            
            if content:
                df_output.loc[actual_idx, 'Titulo_Extraido'] = metadata.get('title', '')
                df_output.loc[actual_idx, 'Contenido_Completo'] = content
                df_output.loc[actual_idx, 'Autor'] = metadata.get('author', '')
                df_output.loc[actual_idx, 'Fecha_Extraida_ISO'] = metadata.get('date', '')
                df_output.loc[actual_idx, 'Palabras'] = len(content.split()) if content else 0
                df_output.loc[actual_idx, 'Fuente_Dominio'] = urlparse(resolved_url).netloc if resolved_url else ''
                df_output.loc[actual_idx, 'Confianza_Extraccion'] = metadata.get('confidence', 0.0)
                df_output.loc[actual_idx, 'Estado_Procesamiento'] = 'exitoso'
                
                # Hash del contenido
                if content:
                    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                    df_output.loc[actual_idx, 'Hash_Contenido'] = content_hash
            else:
                if resolved_url and resolved_url != df_input.loc[actual_idx, args.url_column]:
                    df_output.loc[actual_idx, 'Estado_Procesamiento'] = 'sin_contenido'
                else:
                    df_output.loc[actual_idx, 'Estado_Procesamiento'] = 'url_no_resuelta'

            # Guardar progreso con frecuencia configurable y mostrar estadísticas mejoradas
            if (i + 1) % args.save_frequency == 0:
                # Calcular estadísticas de progreso
                elapsed_update = time.time() - update_start_time
                speed = (i + 1) / elapsed_update if elapsed_update > 0 else 0
                remaining = len(results) - (i + 1)
                eta_seconds = remaining / speed if speed > 0 else 0
                eta_minutes = eta_seconds / 60
                
                print(f"💾 Guardando progreso... ({i + 1}/{len(results)} procesadas)")
                print(f"   📊 Velocidad: {speed:.1f} URLs/seg | ETA: {eta_minutes:.1f} min")
                try:
                    # Crear un ExcelWriter para actualizar solo la hoja de salida
                    with pd.ExcelWriter(args.excel, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                        df_output.to_excel(writer, sheet_name=args.output_sheet, index=False)
                    
                    # Validar escritura intermedia
                    indices_parciales = indices_to_process[:i+1]
                    if not validar_escritura_excel(args.excel, args.output_sheet, indices_parciales, df_output):
                        print(f"⚠️ Advertencia: Problema en escritura intermedia en elemento {i+1}")
                        
                except Exception as e:
                    print(f"❌ Error en guardado intermedio: {e}")
                    print("🔄 Continuando con el procesamiento...")

        processing_time = time.time() - start_time

        # Guardar resultados finales con validación mejorada
        print(f"\n💾 Guardando resultados finales en la hoja '{args.output_sheet}'...")
        
        try:
            with pd.ExcelWriter(args.excel, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_output.to_excel(writer, sheet_name=args.output_sheet, index=False)
            
            # Validar escritura final
            if validar_escritura_excel(args.excel, args.output_sheet, indices_to_process, df_output):
                print("✅ Escritura final validada exitosamente")
            else:
                print("⚠️ Problema en escritura final - algunas URLs pueden no haberse guardado")
                print("💡 Ejecuta 'python recuperar_urls_cache.py' para recuperar URLs faltantes desde el cache")
                
        except Exception as e:
            print(f"❌ Error en guardado final: {e}")
            print("🔄 Intentando recuperación automática desde cache...")
            return 1
        
        # Estadísticas finales mejoradas
        processed_rows = df_output.iloc[indices_to_process]
        
        # Verificar URLs directas realmente escritas
        urls_directas_escritas = (processed_rows['URL_Directa'].notna() & (processed_rows['URL_Directa'] != '')).sum()
        
        print(f"\n📊 === ESTADÍSTICAS FINALES ===")
        print(f"⏱️ Tiempo total: {processing_time:.1f}s")
        print(f"🔗 URLs procesadas: {len(processed_rows)}")
        print(f"✅ URLs directas obtenidas: {urls_directas_escritas}/{len(processed_rows)}")
        
        if len(processed_rows) > 0:
            success_rate = (urls_directas_escritas / len(processed_rows)) * 100
            print(f"📈 Tasa de éxito: {success_rate:.1f}%")
        
        # Estadísticas por estado de procesamiento
        stats = processed_rows['Estado_Procesamiento'].value_counts()
        if not stats.empty:
            print(f"📋 Estados de procesamiento:")
            for status, count in stats.items():
                if pd.notna(status) and status != '':
                    print(f"   {status}: {count}")
        
        # Estadísticas de contenido
        contenido_extraido = (processed_rows['Contenido_Completo'].notna() & (processed_rows['Contenido_Completo'] != '')).sum()
        if contenido_extraido > 0:
            print(f"📄 Contenido completo extraído: {contenido_extraido} artículos")
            
            # Promedio de palabras
            palabras_rows = processed_rows[processed_rows['Palabras'].notna() & (processed_rows['Palabras'] > 0)]
            if not palabras_rows.empty:
                avg_words = palabras_rows['Palabras'].mean()
                print(f"📝 Promedio de palabras por artículo: {avg_words:.0f}")

        # Advertencias finales
        if urls_directas_escritas < len(processed_rows):
            faltantes = len(processed_rows) - urls_directas_escritas
            print(f"\n⚠️ URLs faltantes: {faltantes}")
            print(f"💡 Sugerencia: Ejecuta 'python recuperar_urls_cache.py' para recuperarlas")
        
        print(f"\n🎉 Procesamiento completado. Resultados guardados en hoja '{args.output_sheet}'")
        
        return 0

    except Exception as e:
        print(f"Error durante el procesamiento: {str(e)}")
        if args.verbose:
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())