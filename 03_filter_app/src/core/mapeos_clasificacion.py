"""
MAPEOS CENTRALIZADOS DE CLASIFICACIÓN
======================================

Centraliza TODOS los mapeos de normalización de tipos para facilitar
mantenimiento y actualización. Los mapeos normalizan variaciones de la IA
a las categorías oficiales definidas en filtrador_config.py

Versión: 2.1 (Diciembre 2024) - Agregado MapeoRegion
"""

import unicodedata
from typing import Optional


class MapeoRegion:
    """
    Centraliza normalización de nombres de regiones chilenas.
    Movido desde filtrador_analisis.py para separar lógica de negocio.
    """
    
    # Diccionario de variaciones sincronizado con generador_mapas.py
    VARIACIONES = {
        # O'Higgins
        'libertador bernardo ohiggins': "Región del Libertador General Bernardo O'Higgins",
        'libertador gral. bernardo ohiggins': "Región del Libertador General Bernardo O'Higgins",
        'libertador general bernardo ohiggins': "Región del Libertador General Bernardo O'Higgins",
        'ohiggins': "Región del Libertador General Bernardo O'Higgins",
        "o'higgins": "Región del Libertador General Bernardo O'Higgins",
        'vi region': "Región del Libertador General Bernardo O'Higgins",
        
        # Biobío
        'biobio': 'Región del Biobío',
        'bio bio': 'Región del Biobío',
        'bio-bio': 'Región del Biobío',
        'bío bío': 'Región del Biobío',
        'viii region': 'Región del Biobío',
        
        # Aysén
        'aysen': 'Región de Aysén del Gral.Ibañez del Campo',
        'aysen del gral. carlos ibanez del campo': 'Región de Aysén del Gral.Ibañez del Campo',
        'aysen del general carlos ibanez del campo': 'Región de Aysén del Gral.Ibañez del Campo',
        'aysen del gral.ibanez del campo': 'Región de Aysén del Gral.Ibañez del Campo',
        'aysen del general carlos ibañez del campo': 'Región de Aysén del Gral.Ibañez del Campo',
        'xi region': 'Región de Aysén del Gral.Ibañez del Campo',
        
        # Magallanes
        'magallanes': 'Región de Magallanes y Antártica Chilena',
        'magallanes y antartica chilena': 'Región de Magallanes y Antártica Chilena',
        'magallanes y la antartica': 'Región de Magallanes y Antártica Chilena',
        'magallanes y de la antartica chilena': 'Región de Magallanes y Antártica Chilena',
        'xii region': 'Región de Magallanes y Antártica Chilena',
        
        # Arica y Parinacota
        'arica y parinacota': 'Región de Arica y Parinacota',
        'arica parinacota': 'Región de Arica y Parinacota',
        'xv region': 'Región de Arica y Parinacota',
        
        # Tarapacá
        'tarapaca': 'Región de Tarapacá',
        'i region': 'Región de Tarapacá',
        
        # Antofagasta
        'antofagasta': 'Región de Antofagasta',
        'ii region': 'Región de Antofagasta',
        
        # Atacama
        'atacama': 'Región de Atacama',
        'iii region': 'Región de Atacama',
        
        # Coquimbo
        'coquimbo': 'Región de Coquimbo',
        'iv region': 'Región de Coquimbo',
        
        # Valparaíso
        'valparaiso': 'Región de Valparaíso',
        'v region': 'Región de Valparaíso',
        
        # Metropolitana
        'metropolitana': 'Región Metropolitana',
        'metropolitana de santiago': 'Región Metropolitana',
        'santiago': 'Región Metropolitana',
        'rm': 'Región Metropolitana',
        
        # Maule
        'maule': 'Región del Maule',
        'vii region': 'Región del Maule',
        
        # Ñuble
        'nuble': 'Región de Ñuble',
        'ñuble': 'Región de Ñuble',
        'xvi region': 'Región de Ñuble',
        
        # Araucanía
        'araucania': 'Región de La Araucanía',
        'la araucania': 'Región de La Araucanía',
        'ix region': 'Región de La Araucanía',
        
        # Los Ríos
        'los rios': 'Región de Los Ríos',
        'xiv region': 'Región de Los Ríos',
        
        # Los Lagos
        'los lagos': 'Región de Los Lagos',
        'x region': 'Región de Los Lagos',
    }
    
    PREFIJOS = ['region de ', 'region del ', 'region de la ', 'region de los ']
    
    @classmethod
    def normalizar(cls, region_texto: str, regiones_oficiales: dict = None) -> Optional[str]:
        """
        Normaliza nombre de región con diccionario de variaciones robusto.
        
        Args:
            region_texto: Texto de región a normalizar
            regiones_oficiales: Dict opcional de regiones oficiales para fallback
            
        Returns:
            Nombre normalizado de la región o None si no se encuentra
        """
        if not region_texto:
            return None
        
        # Normalizar texto de entrada (quitar tildes, lowercase)
        region_norm = region_texto.strip().lower()
        region_norm = ''.join(
            c for c in unicodedata.normalize('NFD', region_norm)
            if unicodedata.category(c) != 'Mn'
        )
        
        # Eliminar prefijos comunes
        for prefijo in cls.PREFIJOS:
            if region_norm.startswith(prefijo):
                region_norm = region_norm[len(prefijo):]
                break
        
        # Buscar en diccionario de variaciones
        if region_norm in cls.VARIACIONES:
            return cls.VARIACIONES[region_norm]
        
        # Fallback: buscar en regiones oficiales si se proporcionan
        if regiones_oficiales:
            for region_oficial in regiones_oficiales.keys():
                region_oficial_norm = region_oficial.lower()
                region_oficial_norm = ''.join(
                    c for c in unicodedata.normalize('NFD', region_oficial_norm)
                    if unicodedata.category(c) != 'Mn'
                )
                
                # Eliminar prefijos
                for prefijo in cls.PREFIJOS:
                    if region_oficial_norm.startswith(prefijo):
                        region_oficial_norm = region_oficial_norm[len(prefijo):]
                        break
                
                if region_norm == region_oficial_norm:
                    return region_oficial
                
                # Matching parcial solo si hay suficiente similitud
                if len(region_norm) > 5 and (region_norm in region_oficial_norm or region_oficial_norm in region_norm):
                    return region_oficial
        
        return None


class MapeoTipos:
    """Centraliza TODOS los mapeos de normalización"""
    
    # ========================================
    # MAPEOS DE TIPOS DE CONFLICTO (17 tipos oficiales)
    # ========================================
    CONFLICTOS = {
        # --- Zonas de sacrificio ---
        'Zonas de sacrificio': 'Zonas de sacrificio',
        'Justicia ambiental en zonas de sacrificio': 'Zonas de sacrificio',
        'Zona de sacrificio': 'Zonas de sacrificio',
        'Contaminación industrial': 'Zonas de sacrificio',
        
        # --- Territorial/Indígena ---
        'Conflicto territorial': 'Conflicto territorial/indígena',
        'Conflicto por derechos indígenas': 'Conflicto territorial/indígena',
        'Conflicto indígena': 'Conflicto territorial/indígena',
        'Territorio ancestral': 'Conflicto territorial/indígena',
        'Consulta indígena': 'Conflicto territorial/indígena',
        
        # --- Uso del suelo (NUEVO) ---
        'Uso del suelo': 'Conflicto por uso del suelo',
        'Competencia por suelo': 'Conflicto por uso del suelo',
        'Agricultura vs energía': 'Conflicto por uso del suelo',
        
        # --- Biodiversidad (NUEVO) ---
        'Biodiversidad': 'Conflicto por biodiversidad/ecosistemas',
        'Ecosistemas': 'Conflicto por biodiversidad/ecosistemas',
        'Flora y fauna': 'Conflicto por biodiversidad/ecosistemas',
        'Impacto ambiental': 'Conflicto por biodiversidad/ecosistemas',
        
        # --- Hídrico ---
        'Conflicto por agua': 'Conflicto hídrico vinculado a energía',
        'Conflicto hídrico': 'Conflicto hídrico vinculado a energía',
        'Recursos hídricos': 'Conflicto hídrico vinculado a energía',
        'Escasez hídrica': 'Conflicto hídrico vinculado a energía',
        
        # --- Minerales críticos ---
        'Litio': 'Conflicto por minerales críticos',
        'Cobre': 'Conflicto por minerales críticos',
        'Minerales críticos': 'Conflicto por minerales críticos',
        'Minería de litio': 'Conflicto por minerales críticos',
        'Minería de cobre': 'Conflicto por minerales críticos',
        
        # --- Líneas de transmisión ---
        'Líneas de transmisión': 'Conflicto por líneas de transmisión',
        'Transmisión eléctrica': 'Conflicto por líneas de transmisión',
        'Torres de alta tensión': 'Conflicto por líneas de transmisión',
        'Subestación': 'Conflicto por líneas de transmisión',
        
        # --- Hidrógeno verde ---
        'Hidrógeno verde': 'Conflicto por hidrógeno verde',
        'H2V': 'Conflicto por hidrógeno verde',
        'Amoníaco verde': 'Conflicto por hidrógeno verde',
        
        # --- Cierre energético ---
        'Cierre energético': 'Cierre de proyecto energético',
        'Descarbonización': 'Cierre de proyecto energético',
        'Cierre de termoeléctrica': 'Cierre de proyecto energético',
        
        # --- Transición justa (NUEVO) ---
        'Transición justa': 'Transición justa/Reconversión laboral',
        'Reconversión laboral': 'Transición justa/Reconversión laboral',
        'Pérdida de empleos': 'Transición justa/Reconversión laboral',
        
        # --- Justicia energética (NUEVO) ---
        'Justicia energética': 'Justicia energética/Acceso a energía',
        'Acceso a energía': 'Justicia energética/Acceso a energía',
        'Pobreza energética': 'Justicia energética/Acceso a energía',
        'Tarifas eléctricas': 'Justicia energética/Acceso a energía',
        
        # --- Residuos (NUEVO) ---
        'Residuos tecnológicos': 'Residuos de tecnología limpia',
        'Reciclaje de baterías': 'Residuos de tecnología limpia',
        'Paneles en desuso': 'Residuos de tecnología limpia',
    }
    
    # ========================================
    # MAPEOS DE TIPOS DE ACCIÓN (16 tipos oficiales)
    # ========================================
    ACCIONES = {
        # --- Declaración ---
        'Carta pública, declaración y/o opinión': 'Declaración pública/Carta',
        'Declaración pública': 'Declaración pública/Carta',
        'Carta pública': 'Declaración pública/Carta',
        'Opinión': 'Declaración pública/Carta',
        'Comunicado': 'Declaración pública/Carta',
        'Pronunciamiento': 'Declaración pública/Carta',
        
        # --- Campaña mediática (NUEVO) ---
        'Campaña': 'Campaña mediática/Sensibilización',
        'Campaña en redes': 'Campaña mediática/Sensibilización',
        'Conferencia de prensa': 'Campaña mediática/Sensibilización',
        'Denuncia de greenwashing': 'Campaña mediática/Sensibilización',
        
        # --- Denuncia ---
        'Denuncia a autoridades políticas': 'Denuncia a autoridades',
        'Denuncia': 'Denuncia a autoridades',
        'Queja': 'Denuncia a autoridades',
        'Solicitud de fiscalización': 'Denuncia a autoridades',
        
        # --- Participación ambiental (NUEVO) ---
        'Observaciones a EIA': 'Participación en proceso ambiental',
        'Observaciones ciudadanas': 'Participación en proceso ambiental',
        'Consulta indígena': 'Participación en proceso ambiental',
        'Reclamación administrativa': 'Participación en proceso ambiental',
        
        # --- Recurso judicial ---
        'Interponer recurso y/o gestión en la justicia': 'Recurso judicial',
        'Recurso de protección': 'Recurso judicial',
        'Demanda': 'Recurso judicial',
        'Acción legal': 'Recurso judicial',
        'Querella': 'Recurso judicial',
        
        # --- Boicot (NUEVO) ---
        'Boicot': 'Boicot/Desinversión',
        'Desinversión': 'Boicot/Desinversión',
        'Presión a financistas': 'Boicot/Desinversión',
        
        # --- Protesta ---
        'Protestas': 'Protesta/Manifestación',
        'Manifestación': 'Protesta/Manifestación',
        'Movilización': 'Protesta/Manifestación',
        'Movilización social': 'Protesta/Manifestación',
        'Marcha': 'Protesta/Manifestación',
        'Concentración': 'Protesta/Manifestación',
        'Vigilia': 'Protesta/Manifestación',
        'Cacerolazo': 'Protesta/Manifestación',
        
        # --- Huelga de hambre (NUEVO) ---
        'Huelga de hambre': 'Huelga de hambre',
        'Ayuno': 'Huelga de hambre',
        
        # --- Desobediencia civil (NUEVO) ---
        'Desobediencia civil': 'Desobediencia civil',
        'Encadenamiento': 'Desobediencia civil',
        'Sentada': 'Desobediencia civil',
        'Ocupación simbólica': 'Desobediencia civil',
        
        # --- Cierre de rutas ---
        'Cierre de rutas': 'Cierre de rutas/Bloqueo',
        'Bloqueo': 'Cierre de rutas/Bloqueo',
        'Corte de ruta': 'Cierre de rutas/Bloqueo',
        'Barricada': 'Cierre de rutas/Bloqueo',
        
        # --- Toma ---
        'Toma de infraestructura/terreno': 'Toma de terreno/infraestructura',
        'Toma de acceso': 'Toma de terreno/infraestructura',
        'Ocupación': 'Toma de terreno/infraestructura',
        'Toma': 'Toma de terreno/infraestructura',
        
        # --- Huelga ---
        'Huelga': 'Huelga/Paralización',
        'Paro': 'Huelga/Paralización',
        'Paro de actividades': 'Huelga/Paralización',
        'Paralización': 'Huelga/Paralización',
        'Paralización de obras': 'Huelga/Paralización',
        
        # --- Diálogo (NUEVO) ---
        'Diálogo': 'Diálogo/Mesa de trabajo',
        'Mesa de diálogo': 'Diálogo/Mesa de trabajo',
        'Mesa técnica': 'Diálogo/Mesa de trabajo',
        'Negociación': 'Diálogo/Mesa de trabajo',
        'Mediación': 'Diálogo/Mesa de trabajo',
        
        # --- Sanción ---
        'Fiscalización': 'Sanción administrativa',
        'Multa': 'Sanción administrativa',
        'Clausura': 'Sanción administrativa',
        'Suspensión': 'Sanción administrativa',
        
        # --- Consulta ciudadana ---
        'Plebiscito': 'Consulta ciudadana',
        'Cabildo': 'Consulta ciudadana',
        'Votación': 'Consulta ciudadana',
        
        # --- Acción violenta ---
        'Quema de vehículos y/o maquinaria': 'Acción violenta',
        'Sabotaje': 'Acción violenta',
        'Atentado': 'Acción violenta',
        'Incendio provocado': 'Acción violenta',
        
        # --- EXCLUSIONES ---
        'Malestar social sin acción contenciosa': None,  # Exclusión Motivo 7
        'Malestar sin acción': None,
    }
    
    # ========================================
    # MAPEOS DE ACTORES DEMANDANTES (11 tipos oficiales)
    # ========================================
    DEMANDANTES = {
        # --- Comunidades indígenas ---
        'Organización de pueblo originario': 'Comunidades indígenas',
        'Pueblo originario': 'Comunidades indígenas',
        'Comunidad indígena': 'Comunidades indígenas',
        'Comunidades atacameñas': 'Comunidades indígenas',
        'Comunidades mapuche': 'Comunidades indígenas',
        'Comunidades diaguitas': 'Comunidades indígenas',
        'Consejo de pueblos': 'Comunidades indígenas',
        
        # --- Organizaciones territoriales ---
        'Organizaciones vecinales y comunitarias': 'Organizaciones territoriales',
        'Organizaciones vecinales': 'Organizaciones territoriales',
        'Comunidad': 'Organizaciones territoriales',
        'Comunidades': 'Organizaciones territoriales',
        'Comunidades locales': 'Organizaciones territoriales',
        'Vecinos': 'Organizaciones territoriales',
        'Junta de vecinos': 'Organizaciones territoriales',
        'Comité de defensa': 'Organizaciones territoriales',
        'Coordinadora': 'Organizaciones territoriales',
        
        # --- ONGs ---
        'ONGs, fundaciones y/o organizaciones ambientalistas': 'ONGs ambientalistas',
        'ONG ambiental': 'ONGs ambientalistas',
        'Organizaciones ambientalistas': 'ONGs ambientalistas',
        'Fundación ambiental': 'ONGs ambientalistas',
        
        # --- Academia ---
        'Academia y/o grupo de investigación': 'Academia/Expertos',
        'Academia': 'Academia/Expertos',
        'Universidades': 'Academia/Expertos',
        'Investigadores': 'Academia/Expertos',
        'Científicos': 'Academia/Expertos',
        'Colegio profesional': 'Academia/Expertos',
        
        # --- Estado como demandante ---
        'Organismos del estado': 'Organismos del Estado',
        'Municipalidad': 'Organismos del Estado',
        'Gobierno regional': 'Organismos del Estado',
        'Servicio público': 'Organismos del Estado',
        
        # --- Sindicatos ---
        'Organización sindical': 'Sindicatos/Trabajadores',
        'Sindicato': 'Sindicatos/Trabajadores',
        'Trabajadores o Sindicato de Trabajadores': 'Sindicatos/Trabajadores',
        'Trabajadores': 'Sindicatos/Trabajadores',
        'Federación sindical': 'Sindicatos/Trabajadores',
        
        # --- Empresas ---
        'Empresa': 'Empresas',
        'Empresa privada': 'Empresas',
        'Empresa energética': 'Empresas',
        'Empresa minera': 'Empresas',
        'Empresa afectada': 'Empresas',
        
        # --- Gremios ---
        'Gremios y asociaciones empresariales': 'Gremios empresariales',
        'Asociación gremial': 'Gremios empresariales',
        'Cámara de comercio': 'Gremios empresariales',
        
        # --- Ciudadanos ---
        'Persona natural': 'Ciudadanos individuales',
        'Ciudadano/a': 'Ciudadanos individuales',
        'Ciudadanos': 'Ciudadanos individuales',
        'Particular individual': 'Ciudadanos individuales',
        'Propietario': 'Ciudadanos individuales',
        
        # --- Coalición ---
        'Coalición': 'Coalición de actores',
        'Alianza': 'Coalición de actores',
        'Múltiple': 'Coalición de actores',
    }
    
    # ========================================
    # MAPEOS DE ACTORES DEMANDADOS (9 tipos oficiales)
    # ========================================
    DEMANDADOS = {
        # --- Empresa energética ---
        'Empresa energética': 'Empresa energética',
        'Empresa renovable': 'Empresa energética',
        'Empresa termoeléctrica': 'Empresa energética',
        'Empresa de transmisión': 'Empresa energética',
        'Generadora': 'Empresa energética',
        'Distribuidora': 'Empresa energética',
        
        # --- Empresa minera ---
        'Empresa minera': 'Empresa minera',
        'Minera': 'Empresa minera',
        'SQM': 'Empresa minera',
        'Albemarle': 'Empresa minera',
        
        # --- Empresa pública ---
        'Empresa pública': 'Empresa pública (estatal)',
        'Empresa estatal': 'Empresa pública (estatal)',
        'Codelco': 'Empresa pública (estatal)',
        'ENAP': 'Empresa pública (estatal)',
        'ENAMI': 'Empresa pública (estatal)',
        
        # --- Empresa privada otra ---
        'Empresa privada': 'Empresa privada (otra)',
        'Empresa': 'Empresa privada (otra)',
        'Empresas': 'Empresa privada (otra)',  # ✅ AGREGADO: Plural que la IA usa
        'Constructora': 'Empresa privada (otra)',
        'Contratista': 'Empresa privada (otra)',
        
        # --- Estado como demandado ---
        'Organismos del estado': 'Organismos del Estado',
        'Gobierno': 'Organismos del Estado',
        'Autoridades políticas o estatales': 'Organismos del Estado',
        'Autoridades locales': 'Organismos del Estado',
        'Ministerio': 'Organismos del Estado',
        'SEA': 'Organismos del Estado',
        'SMA': 'Organismos del Estado',
        'Municipalidad': 'Organismos del Estado',
        
        # --- Empresa industrial ---
        'Empresa industrial': 'Empresa industrial',
        'Empresa petrolífera': 'Empresa industrial',
        'Empresa de fundición': 'Empresa industrial',
        'Empresa química': 'Empresa industrial',
        'Industria': 'Empresa industrial',
        
        # --- Financiadores (NUEVO) ---
        'Banco': 'Financiadores/Inversionistas',
        'Fondo de inversión': 'Financiadores/Inversionistas',
        'Inversionista': 'Financiadores/Inversionistas',
        'Financista': 'Financiadores/Inversionistas',
        
        # --- Comunidades como demandadas ---
        'Organizaciones vecinales y comunitarias': 'Comunidades',
        'Organización de pueblo originario': 'Comunidades',
        'Comunidad': 'Comunidades',
    }
    
    # ========================================
    # MAPEOS DE SECTORES ECONÓMICOS
    # ========================================
    SECTORES = {
        # Mapeos para normalizar sectores que la IA puede generar
        'Energía': 'Energía renovable',
        'Energia': 'Energía renovable',
        'Renovable': 'Energía renovable',
        'Solar': 'Energía renovable',
        'Eólica': 'Energía renovable',
        'Eólico': 'Energía renovable',
        'Hidroeléctrica': 'Energía renovable',
        'Geotérmica': 'Energía renovable',
        'Fotovoltaica': 'Energía renovable',
        
        'Convencional': 'Energía convencional',
        'Termoeléctrica': 'Energía convencional',
        'Carbón': 'Energía convencional',
        'Gas natural': 'Energía convencional',
        
        'Minería de litio': 'Minería',
        'Minería de cobre': 'Minería',
        'Litio': 'Minería',
        'Cobre': 'Minería',
        'Minero': 'Minería',
        
        'Petróleo': 'Hidrocarburos',
        'Gas': 'Hidrocarburos',
        'GNL': 'Hidrocarburos',
        
        'Transmisión': 'Infraestructura energética',
        'Infraestructura': 'Infraestructura energética',
        'Líneas de transmisión': 'Infraestructura energética',
        'Subestación': 'Infraestructura energética',
        
        'Recursos hídricos': 'Agua/Recursos hídricos',
        'Agua': 'Agua/Recursos hídricos',
        'Hídrico': 'Agua/Recursos hídricos',
        
        'Transporte': 'Transporte/Electromovilidad',
        'Electromovilidad': 'Transporte/Electromovilidad',
        'Movilidad eléctrica': 'Transporte/Electromovilidad',
        
        'Industria': 'Industrial',
        'Manufactura': 'Industrial',
        
        'Indígena': 'Territorial/Indígena',
        'Territorial': 'Territorial/Indígena',
        'Territorio': 'Territorial/Indígena',
        
        'Varios': 'Múltiple',
        'Mixto': 'Múltiple',
    }
    
    @classmethod
    def mapear_conflicto(cls, tipo: str) -> tuple[str, bool]:
        """
        Mapea un tipo de conflicto a su equivalente válido
        
        Args:
            tipo: Tipo de conflicto generado por la IA
            
        Returns:
            (tipo_mapeado, fue_mapeado)
        """
        if tipo in cls.CONFLICTOS:
            return cls.CONFLICTOS[tipo], True
        return tipo, False
    
    @classmethod
    def mapear_accion(cls, tipo: str) -> tuple[str | None, bool, bool]:
        """
        Mapea un tipo de acción a su equivalente válido
        
        Args:
            tipo: Tipo de acción generado por la IA
            
        Returns:
            (tipo_mapeado, fue_mapeado, es_exclusion)
        """
        if tipo in cls.ACCIONES:
            mapeado = cls.ACCIONES[tipo]
            if mapeado is None:
                # Caso especial: "Malestar sin acción" → Exclusión
                return None, True, True
            return mapeado, True, False
        return tipo, False, False
    
    @classmethod
    def mapear_demandante(cls, tipo: str) -> tuple[str, bool]:
        """
        Mapea un actor demandante a su equivalente válido
        
        Args:
            tipo: Actor demandante generado por la IA
            
        Returns:
            (tipo_mapeado, fue_mapeado)
        """
        if tipo in cls.DEMANDANTES:
            return cls.DEMANDANTES[tipo], True
        return tipo, False
    
    @classmethod
    def mapear_demandado(cls, tipo: str) -> tuple[str | None, bool, bool]:
        """
        Mapea un actor demandado a su equivalente válido
        
        Args:
            tipo: Actor demandado generado por la IA
            
        Returns:
            (tipo_mapeado, fue_mapeado, requiere_revision)
        """
        if tipo in cls.DEMANDADOS:
            mapeado = cls.DEMANDADOS[tipo]
            if mapeado is None:
                # Caso especial: "Múltiple" → Revisión manual
                return None, True, True
            return mapeado, True, False
        return tipo, False, False
    
    @classmethod
    def mapear_sector(cls, sector: str) -> tuple[str, bool]:
        """
        Mapea un sector económico a su equivalente válido
        
        Args:
            sector: Sector generado por la IA
            
        Returns:
            (sector_mapeado, fue_mapeado)
        """
        if sector in cls.SECTORES:
            return cls.SECTORES[sector], True
        return sector, False
    
    @classmethod
    def agregar_mapeo_conflicto(cls, original: str, mapeado: str):
        """Agrega un nuevo mapeo de conflicto dinámicamente"""
        cls.CONFLICTOS[original] = mapeado
    
    @classmethod
    def agregar_mapeo_accion(cls, original: str, mapeado: str | None):
        """Agrega un nuevo mapeo de acción dinámicamente"""
        cls.ACCIONES[original] = mapeado
    
    @classmethod
    def agregar_mapeo_demandante(cls, original: str, mapeado: str):
        """Agrega un nuevo mapeo de demandante dinámicamente"""
        cls.DEMANDANTES[original] = mapeado
    
    @classmethod
    def agregar_mapeo_demandado(cls, original: str, mapeado: str | None):
        """Agrega un nuevo mapeo de demandado dinámicamente"""
        cls.DEMANDADOS[original] = mapeado
    
    @classmethod
    def obtener_todos_mapeos(cls) -> dict:
        """Retorna todos los mapeos para exportación"""
        return {
            'conflictos': cls.CONFLICTOS,
            'acciones': cls.ACCIONES,
            'demandantes': cls.DEMANDANTES,
            'demandados': cls.DEMANDADOS
        }
    
    @classmethod
    def exportar_a_yaml(cls, filepath: str):
        """Exporta mapeos a archivo YAML para fácil edición"""
        import yaml
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(cls.obtener_todos_mapeos(), f, allow_unicode=True, default_flow_style=False)
    
    @classmethod
    def cargar_desde_yaml(cls, filepath: str):
        """Carga mapeos desde archivo YAML"""
        import yaml
        with open(filepath, 'r', encoding='utf-8') as f:
            mapeos = yaml.safe_load(f)
            cls.CONFLICTOS = mapeos.get('conflictos', {})
            cls.ACCIONES = mapeos.get('acciones', {})
            cls.DEMANDANTES = mapeos.get('demandantes', {})
            cls.DEMANDADOS = mapeos.get('demandados', {})
