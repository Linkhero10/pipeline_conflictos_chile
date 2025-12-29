"""
SCRAPER TEMPORAL MEJORADO CON ROTACIÓN AVANZADA
Implementa scraping por períodos específicos con User-Agent y proxy rotation mejorados
"""

import time
import random
import hashlib
import logging
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import undetected_chromedriver as uc
import sys
import os

from database_handler import DatabaseManager
from search_keywords import get_all_queries, get_estadisticas  # Keywords completas FONDECYT
# from full_content_extractor import FullContentExtractor  # Deshabilitado para segundo scraping

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedTemporalScraper:
    def __init__(self, use_proxy=False, headless=True, extract_full_content=False):
        self.use_proxy = use_proxy
        self.headless = headless
        self.extract_full_content = extract_full_content
        self.driver = None
        self.results = []
        self.scraped_urls = set()
        
        # Base de datos para transición energética (ruta absoluta al Excel principal)
        excel_path = os.path.join(os.path.dirname(__file__), '..', 'conflictos_transicion_energetica')
        self.db_manager = DatabaseManager(base_filename=excel_path)
        
        # Extractor de contenido completo (deshabilitado)
        self.content_extractor = None  # FullContentExtractor() if extract_full_content else None
        
        # User-Agents rotativos avanzados
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36"
        ]
        
        # Proxies rotativos reales de Chile y región cercana
        self.proxies = [
            "181.225.253.186:3128",  # Chile
            "190.61.88.147:8080",    # Chile  
            "200.54.194.13:53281",   # Chile
            "181.78.23.135:999",     # Argentina
            "177.93.33.219:999",     # Brasil
            "200.115.53.193:3128"    # Argentina
        ]
        self.current_proxy_index = 0
        
        # Estadísticas de sesión
        self.session_stats = {
            'start_time': datetime.now(),
            'queries_executed': 0,
            'articles_found': 0,
            'unique_sources': set(),
            'period_name': '',
            'captcha_detected': 0,
            'retries_total': 0
        }
        
        # Configuración de retry con backoff exponencial
        self.max_retries = 5
        self.base_delay = 2  # segundos
        self.max_delay = 60  # segundos máximo de espera
        
        # Patrones para detectar CAPTCHA
        self.captcha_patterns = [
            'captcha',
            'robot',
            'verify you',
            'verificar que',
            'unusual traffic',
            'tráfico inusual',
            'not a robot',
            'no soy un robot',
            'recaptcha',
            'challenge',
            'blocked',
            'bloqueado'
        ]
    
    def setup_driver(self):
        """Configurar driver temporal con configuración mínima y estable"""
        print("Configurando driver temporal con configuración estable...")
        
        # Configuración mínima y compatible
        options = webdriver.ChromeOptions()
        
        # Solo opciones básicas y estables
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # User-Agent básico
        user_agent = random.choice(self.user_agents)
        options.add_argument(f'--user-agent={user_agent}')
        
        print(f"User-Agent: {user_agent[:50]}...")
        
        # Estrategia 1: Intentar usar ChromeDriver del PATH o webdriver-manager
        # (Nota: Las rutas hardcodeadas fueron eliminadas para portabilidad)
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            print("Driver configurado con webdriver-manager")
            return True
        except Exception as e:
            print(f"Fallo webdriver-manager: {e}")
        
        # Estrategia 2: undetected-chromedriver básico
        try:
            self.driver = uc.Chrome(options=options, version_main=131, use_subprocess=False)
            
            print("Driver configurado con undetected-chromedriver BÁSICO")
            return True
        except Exception as e:
            print(f"Fallo undetected-chromedriver: {e}")
        
        # Estrategia 3: webdriver-manager
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            print("Driver configurado con webdriver-manager")
            return True
        except Exception as e:
            print(f"Fallo webdriver-manager: {e}")
        
        # Estrategia 4: Configuración mínima
        try:
            self.driver = webdriver.Chrome(options=options)
            print("Driver configurado con configuración mínima")
            return True
        except Exception as e:
            print(f"Fallo configuración mínima: {e}")
            return False
    
    def build_search_url(self, query, year, semester):
        """Construir URL de búsqueda con operadores booleanos y parámetros temporales"""
        base_url = "https://news.google.com/search"
        
        # Determinar fechas del semestre
        if semester == 1:
            start_date = f"{year}-01-01"
            end_date = f"{year}-06-30"
        else:
            start_date = f"{year}-07-01"
            end_date = f"{year}-12-31"
        
        # Si el query ya incluye operadores booleanos, usarlo directamente
        # Si no, agregar "Chile" y comillas
        if any(op in query for op in ['AND', 'OR', '(', ')', '"']):
            # Query con operadores booleanos - agregar Chile y delimitación temporal
            search_query = f'({query}) AND Chile after:{start_date} before:{end_date}'
        else:
            # Query simple - formato tradicional
            search_query = f'"{query}" Chile after:{start_date} before:{end_date}'
        
        # Parámetros de búsqueda
        params = {
            'q': search_query,
            'hl': 'es',
            'gl': 'CL',
            'ceid': 'CL:es'
        }
        
        # Construir URL con encoding apropiado para operadores booleanos
        import urllib.parse
        encoded_query = urllib.parse.quote_plus(params['q'])
        
        url = f"{base_url}?q={encoded_query}"
        url += f"&hl={params['hl']}&gl={params['gl']}&ceid={params['ceid']}"
        
        return url
    
    def generate_date_filters(self, year=None, semester=None, start_date=None, end_date=None):
        """Generar filtros de fecha para Google News.
        Prioridad:
        1) Rango personalizado con start_date y end_date
        2) Semestre específico (year + semester)
        3) Año completo (solo year)
        4) Períodos recientes por defecto
        """
        date_filters = []
        
        if start_date and end_date:
            # Rango personalizado explícito
            date_filters.append(f"after:{start_date} before:{end_date}")
        elif year and semester:
            # Filtro por semestre específico
            if semester == 1:
                start_date = f"{year}-01-01"
                end_date = f"{year}-06-30"
            else:
                start_date = f"{year}-07-01"
                end_date = f"{year}-12-31"
            date_filters.append(f"after:{start_date} before:{end_date}")
        elif year:
            # Filtro por año completo
            date_filters.append(f"after:{year}-01-01 before:{year}-12-31")
        else:
            # Filtros por períodos recientes
            current_date = datetime.now()
            
            # Último año
            last_year = current_date - timedelta(days=365)
            date_filters.append(f"after:{last_year.strftime('%Y-%m-%d')}")
            
            # Últimos 6 meses
            six_months_ago = current_date - timedelta(days=180)
            date_filters.append(f"after:{six_months_ago.strftime('%Y-%m-%d')}")
        
        return date_filters
    
    def scrape_historico_completo(self):
        """Scraping histórico completo SIN división por semestres"""
        
        period_name = "historico_completo"
        self.session_stats['period_name'] = period_name
        self.session_stats['config_name'] = "zonificado"
        
        logger.info(f"=== SCRAPING HISTÓRICO COMPLETO (SIN FECHAS) ===")
        
        try:
            if not self.setup_driver():
                logger.error("No se pudo configurar el driver")
                return []
            
            # Obtener queries del sistema zonificado (SIN delimitación temporal)
            queries = get_all_queries()
            total_queries = len(queries)
            
            logger.info(f"📊 Total queries: {total_queries:,}")
            
            # Ejecutar queries
            for i, query in enumerate(queries, 1):
                
                # Log de query actual
                logger.info(f"🔍 [{i}/{total_queries}] {query[:70]}...")
                
                if i % 100 == 0:
                    logger.info(f"\n📊 Progreso: {(i/total_queries)*100:.1f}%")
                
                try:
                    articles = self.scrape_google_news_temporal(query, period_name)
                    self.results.extend(articles)
                    self.session_stats['queries_executed'] += 1
                    
                    # Pausa entre queries
                    pause_time = random.uniform(4, 8)
                    time.sleep(pause_time)
                    
                    # Pausa extendida cada 10 queries
                    if self.session_stats['queries_executed'] % 10 == 0:
                        extended_pause = random.uniform(15, 25)
                        logger.info(f"⏸️ Pausa extendida: {extended_pause:.1f}s")
                        time.sleep(extended_pause)
                        self.rotate_user_agent()
                    
                    # Guardado incremental cada 50 queries
                    if i % 50 == 0:
                        self.save_temporal_results(period_name)
                        logger.info(f"💾 Guardado incremental - Total: {len(self.db_manager.unified_data):,}")
                
                except Exception as e:
                    logger.error(f"Error en query {i}: {e}")
                    continue
        
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info("Driver cerrado correctamente")
                except Exception as e:
                    logger.warning(f"Error cerrando driver: {e}")
            
            # Cerrar extractor de contenido si existe
            if self.content_extractor:
                try:
                    self.content_extractor.close()
                    logger.info("Extractor de contenido cerrado")
                except Exception as e:
                    logger.warning(f"Error cerrando extractor: {e}")
        
        # Guardar resultados
        if self.results:
            self.save_temporal_results(period_name)
        
        self.log_temporal_stats()
        return self.results
    
    def scrape_google_news_temporal(self, query, period_name):
        """Scraping con scroll infinito real - SIN límite artificial"""
        articles = []
        
        # Verificar que el driver esté activo
        if not self.driver:
            logger.error("Driver no disponible")
            return articles
        
        try:
            # Verificar que la ventana del driver esté abierta
            try:
                self.driver.current_url
            except Exception as e:
                logger.error(f"Driver inválido, reconfigurar: {e}")
                if not self.setup_driver():
                    return articles
            
            # URL de Google News
            encoded_query = quote_plus(query)
            url = f"https://news.google.com/search?q={encoded_query}&hl=es&gl=CL&ceid=CL:es-419"
            
            # Usar navegación segura con retry y detección de CAPTCHA
            if not self.safe_get_page(url):
                logger.warning(f"No se pudo cargar la página para query: {query[:50]}...")
                return articles
            
            time.sleep(random.uniform(1, 3))  # Pausa adicional después de carga exitosa
            
            # SCROLL INFINITO: Seguir scrolleando hasta que no aparezcan más artículos
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            no_new_content_count = 0
            # SCROLL DINÁMICO: continúa hasta que no haya más contenido nuevo
            # Se detiene después de 5 intentos sin contenido nuevo (más robusto)
            max_scrolls = 200  # Límite de seguridad alto (rara vez se alcanza)
            scroll_count = 0
            
            while scroll_count < max_scrolls and no_new_content_count < 5:
                # Scroll hacia abajo
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
                
                # Calcular nueva altura
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                
                if new_height == last_height:
                    no_new_content_count += 1
                else:
                    no_new_content_count = 0
                
                last_height = new_height
                scroll_count += 1
            
            # Buscar TODOS los artículos después del scroll
            selectors = ["article", "div[jsname]", "div.xrnccd", "div.JheGif"]
            article_elements = []
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        article_elements = elements  # SIN LÍMITE - tomar todos
                        break
                except:
                    continue
            
            logger.info(f"Scroll completado: {scroll_count} scrolls, {len(article_elements)} elementos encontrados")
            
            # Extraer TODOS los artículos encontrados
            for element in article_elements:
                try:
                    # Título
                    title = ""
                    title_selectors = ["h3", "h4", "a[aria-label]", ".JheGif a"]
                    for sel in title_selectors:
                        try:
                            title_elem = element.find_element(By.CSS_SELECTOR, sel)
                            title = title_elem.text.strip() or title_elem.get_attribute('aria-label') or ""
                            if title and len(title) > 10:
                                break
                        except:
                            continue
                    
                    if not title or len(title) < 10:
                        continue
                    
                    # URL
                    link = ""
                    link_selectors = ["a", "h3 a", "h4 a"]
                    for sel in link_selectors:
                        try:
                            link_elem = element.find_element(By.CSS_SELECTOR, sel)
                            link = link_elem.get_attribute('href') or ""
                            if link and 'http' in link:
                                break
                        except:
                            continue
                    
                    if not link or link in self.scraped_urls:
                        continue
                    
                    # Fuente
                    source = ""
                    source_selectors = [".wEwyrc", ".vr1PYe", ".CEMjEf"]
                    for sel in source_selectors:
                        try:
                            source_elem = element.find_element(By.CSS_SELECTOR, sel)
                            source = source_elem.text.strip()
                            if source:
                                break
                        except:
                            continue
                    
                    # Descripción
                    description = ""
                    desc_selectors = [".GI74Re", ".st", ".Y3v8qd"]
                    for sel in desc_selectors:
                        try:
                            desc_elem = element.find_element(By.CSS_SELECTOR, sel)
                            description = desc_elem.text.strip()
                            if description:
                                break
                        except:
                            continue
                    
                    # Extraer contenido completo si está habilitado
                    real_url = link
                    full_content = ""
                    content_length = 0
                    
                    if self.extract_full_content and self.content_extractor:
                        try:
                            logger.info(f"Extrayendo contenido completo: {title[:50]}...")
                            real_url, full_content, content_length = self.content_extractor.process_article(link)
                            logger.info(f"Contenido extraído: {content_length} caracteres")
                        except Exception as e:
                            logger.warning(f"Error extrayendo contenido de {link}: {e}")
                    
                    # Crear artículo temporal
                    article = {
                        'titulo': title,
                        'descripcion': description or title,
                        'enlace': link,  # URL original de Google News
                        'real_url': real_url,  # URL directa del artículo
                        'fuente': source or 'Google News',
                        'fecha_scraping': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'query_original': query,
                        'periodo_scraping': period_name,
                        'configuracion': self.session_stats.get('config_name', 'desconocida'),
                        'tipo_scraping': 'temporal',
                        'full_content': full_content,  # Contenido completo del artículo
                        'content_length': content_length,  # Longitud del contenido
                        'content_hash': hashlib.md5(f"{title}{link}".encode()).hexdigest()
                    }
                    
                    articles.append(article)
                    self.scraped_urls.add(link)
                    self.session_stats['unique_sources'].add(source)
                    
                except Exception as e:
                    logger.debug(f"Error extrayendo artículo: {e}")
                    continue
            
            self.session_stats['articles_found'] += len(articles)
            logger.info(f"Encontrados {len(articles)} artículos")
            
        except Exception as e:
            logger.error(f"Error en scraping temporal: {e}")
        
        return articles
    
    def rotate_user_agent(self):
        """Rotar User-Agent durante la sesión"""
        if self.driver:
            try:
                new_user_agent = random.choice(self.user_agents)
                self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": new_user_agent
                })
                logger.info(f"User-Agent rotado: {new_user_agent[:50]}...")
            except Exception as e:
                logger.debug(f"No se pudo rotar User-Agent: {e}")
    
    def detect_captcha(self) -> bool:
        """
        Detecta si la página actual muestra un CAPTCHA o bloqueo.
        
        Returns:
            True si se detecta CAPTCHA, False en caso contrario
        """
        if not self.driver:
            return False
        
        try:
            # Obtener el HTML de la página
            page_source = self.driver.page_source.lower()
            page_title = self.driver.title.lower()
            
            # Verificar patrones en el contenido
            for pattern in self.captcha_patterns:
                if pattern in page_source or pattern in page_title:
                    logger.warning(f"⚠️ CAPTCHA detectado: patrón '{pattern}' encontrado")
                    self.session_stats['captcha_detected'] += 1
                    return True
            
            # Verificar si la página está vacía o tiene muy poco contenido
            if len(page_source) < 1000:
                logger.warning("⚠️ Página sospechosamente corta, posible bloqueo")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error detectando CAPTCHA: {e}")
            return False
    
    def retry_with_backoff(self, func, *args, **kwargs):
        """
        Ejecuta una función con retry y backoff exponencial.
        
        Args:
            func: Función a ejecutar
            *args, **kwargs: Argumentos para la función
        
        Returns:
            Resultado de la función o None si falla después de todos los reintentos
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                result = func(*args, **kwargs)
                
                # Verificar si hay CAPTCHA después de la ejecución
                if self.detect_captcha():
                    raise Exception("CAPTCHA detectado")
                
                return result
                
            except Exception as e:
                last_exception = e
                self.session_stats['retries_total'] += 1
                
                # Calcular delay con backoff exponencial
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                # Agregar jitter aleatorio para evitar patrones predecibles
                delay = delay + random.uniform(0, delay * 0.3)
                
                logger.warning(f"⚠️ Intento {attempt + 1}/{self.max_retries} falló: {e}")
                logger.info(f"⏳ Esperando {delay:.1f}s antes de reintentar...")
                
                time.sleep(delay)
                
                # Rotar User-Agent después de cada fallo
                self.rotate_user_agent()
                
                # Si es CAPTCHA, esperar más y posiblemente reiniciar driver
                if 'captcha' in str(e).lower():
                    logger.warning("🔄 Reiniciando driver por CAPTCHA...")
                    if self.driver:
                        try:
                            self.driver.quit()
                        except:
                            pass
                    time.sleep(random.uniform(30, 60))  # Espera larga
                    self.setup_driver()
        
        logger.error(f"❌ Todos los reintentos fallaron. Último error: {last_exception}")
        return None
    
    def safe_get_page(self, url: str) -> bool:
        """
        Navega a una URL de forma directa y rápida (sin detección CAPTCHA).
        """
        try:
            self.driver.get(url)
            time.sleep(random.uniform(1.5, 3))
            return True
        except Exception as e:
            logger.warning(f"Error navegando a {url[:50]}: {e}")
            return False
    
    def save_temporal_results(self, period_name):
        """Guardar resultados temporales en base de datos unificada"""
        if not self.results:
            return
        
        # Agregar a base de datos unificada
        new_articles = 0
        for article in self.results:
            content_hash = article['content_hash']
            
            if content_hash not in self.db_manager.existing_hashes:
                article['fecha_agregado'] = datetime.now().isoformat()
                self.db_manager.unified_data.append(article)
                self.db_manager.existing_hashes.add(content_hash)
                new_articles += 1
        
        # Guardar archivos
        # Política: durante la ejecución, solo guardar archivos ORIGINALES
        # (no actualizar copias). Las copias se gestionarán con scripts finales.
        try:
            self.db_manager.save_csv_copy = False
            self.db_manager.save_json_copy = False
            self.db_manager.save_excel_copy = False
        except Exception:
            pass

        saved_files = self.db_manager.save_unified_database()
        
        logger.info(f"=== RESULTADOS TEMPORALES GUARDADOS ===")
        logger.info(f"Período: {period_name}")
        logger.info(f"Nuevos artículos: {new_articles}")
        logger.info(f"Total en base de datos: {saved_files['total_records']}")
        logger.info(f"Archivos actualizados: {', '.join([v for k, v in saved_files.items() if k != 'total_records'])}")
    
    def log_temporal_stats(self):
        """Mostrar estadísticas de la sesión temporal"""
        elapsed = datetime.now() - self.session_stats['start_time']
        
        logger.info(f"=== ESTADÍSTICAS TEMPORALES ===")
        logger.info(f"Período: {self.session_stats['period_name']}")
        logger.info(f"Tiempo total: {elapsed}")
        logger.info(f"Queries ejecutadas: {self.session_stats['queries_executed']}")
        logger.info(f"Artículos encontrados: {self.session_stats['articles_found']}")
        logger.info(f"URLs únicas: {len(self.scraped_urls)}")
        logger.info(f"Fuentes únicas: {len(self.session_stats['unique_sources'])}")
        logger.info(f"CAPTCHAs detectados: {self.session_stats['captcha_detected']}")
        logger.info(f"Reintentos totales: {self.session_stats['retries_total']}")
        

def main():
    """Función principal - SCRAPING HISTÓRICO COMPLETO SIN FECHAS"""
    print("\n" + "="*80)
    print("SCRAPER TRANSICIÓN ENERGÉTICA - HISTÓRICO COMPLETO")
    print("="*80)
    
    # Mostrar estadísticas del sistema
    stats = get_estadisticas()
    print("\nKEYWORDS OPTIMIZADOS:")
    for zona, cantidad in stats.items():
        if zona != "TOTAL":
            print(f"  {zona}: {cantidad}")
    print(f"\n  TOTAL: {stats['TOTAL']} keywords")
    
    # Calcular estimación
    total_queries = stats['TOTAL']
    tiempo_estimado_horas = (total_queries * 10) / 3600  # 10 seg por query
    
    print(f"\n📊 ESTIMACIÓN:")
    print(f"  Modo: HISTÓRICO COMPLETO (SIN delimitación temporal)")
    print(f"  Total queries: {total_queries:,}")
    print(f"  Tiempo estimado: {tiempo_estimado_horas:.1f} horas (~{tiempo_estimado_horas/24:.1f} días)")
    print(f"  Artículos esperados: 25,000-40,000 únicos")
    print(f"  Scroll infinito: SIN límite artificial")
    
    print("\n" + "="*80)
    # Inicio automático sin confirmación interactiva
    print("\n🚀 INICIANDO SCRAPING HISTÓRICO COMPLETO...")
    print("="*80)
    
    # HEADLESS=TRUE (sin abrir Chrome visible)
    scraper = EnhancedTemporalScraper(headless=True)
    
    # Ejecutar scraping histórico completo SIN división por semestres
    scraper.scrape_historico_completo()
    
    print("\n" + "="*80)
    print("🎉 SCRAPING HISTÓRICO COMPLETADO")
    print(f"📊 Total artículos: {len(scraper.db_manager.unified_data):,}")
    print("="*80)


if __name__ == "__main__":
    main()
