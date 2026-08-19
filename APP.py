import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime
import io

# Intentar importar ReportLab para la generación del PDF con soporte de gráficos
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    REPORTLAB_DISPONIBLE = True
except ImportError:
    REPORTLAB_DISPONIBLE = False

# ---------------------------------------------------------
# 0. Sistema de Autenticación de Usuarios
# ---------------------------------------------------------
USUARIOS_PERMITIDOS = {
    "kenneth.martinez@sedisur.com": {"password": "Kem000", "cargo": "Gerencia", "rol": "Usuario"},
    "custodio.arias@sedisur.com": {"password": "Cua000", "cargo": "Gerencia", "rol": "Usuario"},
    "henry.azofeifa@sedisur.com": {"password": "Henry1979", "cargo": "Gerencia", "rol": "Usuario"},
    "diego.barrantes@sedisur.com": {"password": "Dib000", "cargo": "Supervisión", "rol": "Usuario"},
    "harvy.arbustini@sedisur.com": {"password": "Haa000", "cargo": "Supervisión", "rol": "Usuario"},
    "eddy.zuniga@sedisur.com": {"password": "Edz000", "cargo": "Supervisión", "rol": "Usuario"},
    "cristina.nunez@sedisur.com": {"password": "Crn000", "cargo": "Supervisión", "rol": "administrador"},
    "erick.abarca@sedisur.com": {"password": "absa1528", "cargo": "Supervisión", "rol": "Usuario"},
    "adm": {"password": "Adm1994", "cargo": "Supervisión", "rol": "administrador"},
    
    # --- Agentes Proveedores ---
    "eliecer_valdez@colpal.com": {"password": "Col123", "cargo": "Agente Proveedor", "rol": "proveedor_marca", "marca_restringida": "COLGATE_PALM"},
    "hugomora@alimer.com": {"password": "Ali123", "cargo": "Agente Proveedor", "rol": "proveedor_marca", "marca_restringida": "ALIMER S.A."},
    "jonathan.romero@sedisur.com": {"password": "Rec123", "cargo": "Agente Proveedor", "rol": "proveedor_marca", "marca_restringida": "RECKITT"},
    "alexander.castro@essity.com": {"password": "Ess123", "cargo": "Agente Proveedor", "rol": "proveedor_marca", "marca_restringida": "ESSITY"},
    "juan.segura@pepsico.com": {"password": "Pep123", "cargo": "Agente Proveedor", "rol": "proveedor_marca", "marca_restringida": "PEPSICO"},
    "juan.campos@kraftheinz.com": {"password": "Hei123", "cargo": "Agente Proveedor", "rol": "proveedor_marca", "marca_restringida": "HEINZ.CR"}
}

def verificar_acceso():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if st.session_state["autenticado"]:
        return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try:
            st.image("Sedisur_logo.png", width=250)
        except Exception:
            pass
            
        st.markdown("## 🔐 Inicio de Sesión - Sedisur BI")
        st.markdown("Por favor, ingrese sus credenciales corporativas para acceder al sistema.")

        with st.form("form_login"):
            correo = st.text_input("Usuario").strip().lower()
            password = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Ingresar", use_container_width=True)

            if submit:
                if correo in USUARIOS_PERMITIDOS and USUARIOS_PERMITIDOS[correo]["password"] == password:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario_actual"] = correo
                    st.session_state["cargo_actual"] = USUARIOS_PERMITIDOS[correo]["cargo"]
                    st.session_state["rol_actual"] = USUARIOS_PERMITIDOS[correo]["rol"]
                    
                    if USUARIOS_PERMITIDOS[correo]["rol"] == "proveedor_marca":
                        st.session_state["marca_restringida"] = USUARIOS_PERMITIDOS[correo]["marca_restringida"]
                    else:
                        st.session_state["marca_restringida"] = None

                    st.success("¡Acceso concedido!")
                    st.rerun()
                else:
                    st.error("Correo o contraseña incorrectos.")
    
    return False

# ---------------------------------------------------------
# 1. Configuración Inicial de la Página e Identidad Sedisur
# ---------------------------------------------------------
st.set_page_config(
    page_title="Sedisur BI - Comparativa y Cobertura",
    page_icon="Sedisur_logo.png",
    layout="wide"
)

# Estilos corporativos Sedisur (Azul #00174F, Verde #009640)
st.markdown("""
    <style>
        span[data-baseweb="tag"] {
            background-color: #00174F !important;
            border: 1px solid #009640 !important;
            color: #ffffff !important;
        }
        details summary span p {
            color: #009640 !important;
            font-weight: bold !important;
        }
        .stButton>button {
            border: 1px solid #00174F !important;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            border-color: #009640 !important;
            color: #009640 !important;
        }
        div[role="radiogroup"] label[data-baseweb="radio"] span:first-child {
            border-color: #009640 !important;
        }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. Carga de Datos y Agrupaciones Personalizadas
# ---------------------------------------------------------
def clasificar_categoria_heinz_estricta(c4_val):
    c4 = str(c4_val).upper().strip()
    if 'MAYO' in c4:
        return 'MAYONESA'
    elif any(k in c4 for k in ['KETCHUP', 'TOMATE', 'CATSUP', 'K_CHUP']):
        return 'KETCHUP'
    elif any(k in c4 for k in ['COLADO', 'GERBER', 'PAPILLA']):
        return 'COLADOS'
    elif any(k in c4 for k in ['SALSITA', 'SALSA PREPARADA', 'SOFRITO', 'RANCHERA', 'BOLOGNESA', 'MECHADA', 'POMODORO']):
        return 'SALSITAS'
    else:
        return 'OTROS'

def clasificar_segmento_reckitt(c3_val):
    c3 = str(c3_val).upper().strip()
    marcas_core = ['DUREX', 'HARPIC', 'LYSOL', 'VANISH', 'VEET']
    if any(m in c3 for m in marcas_core):
        return 'CORE'
    else:
        return 'VASTACY'

@st.cache_data
def cargar_datos_exactus():
    anios_a_cargar = [2024, 2025, 2026]
    columnas_necesarias = [
        'CLIENTE', 'ALIAS', 'NOMBRE', 'ANIO', 'MES_NUM', 
        'VENTA_NETA', 'CANTIDAD_NETA', 'CLASIFICACION_1', 
        'CLASIFICACION_2', 'CLASIFICACION_3', 'CLASIFICACION_4', 
        'CATEGORIA_CLIENTE', 'VENDEDOR'
    ]
    
    dfs = []
    for anio in anios_a_cargar:
        archivo = f"ventas_{anio}.parquet"
        try:
            df_temp = pd.read_parquet(archivo, columns=[c for c in columnas_necesarias if c != 'MES_NOMBRE'])
            dfs.append(df_temp)
        except FileNotFoundError:
            pass

    if not dfs:
        try:
            df = pd.read_parquet("datos_ventas.parquet")
        except FileNotFoundError:
            return pd.DataFrame()
    else:
        df = pd.concat(dfs, ignore_index=True)

    df = df[df['CLASIFICACION_1'].notna() & (df['CLASIFICACION_1'].astype(str).str.strip() != '') & (df['CLASIFICACION_1'] != 'SIN CLASIFICAR')]

    meses_es = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }
    df['MES_NOMBRE'] = df['MES_NUM'].map(meses_es)
    df['CLIENTE'] = df['CLIENTE'].astype(str).str.strip()
    df['CLIENTE_DISPLAY'] = df['CLIENTE'] + " - " + df['ALIAS'].astype(str)

    mascara_heinz = df['CLASIFICACION_1'].astype(str).str.strip() == 'HEINZ.CR'
    df['HEINZ_CATEGORIA'] = None
    if mascara_heinz.any():
        df.loc[mascara_heinz, 'HEINZ_CATEGORIA'] = df.loc[mascara_heinz, 'CLASIFICACION_4'].apply(clasificar_categoria_heinz_estricta)

    mascara_reckitt = df['CLASIFICACION_1'].astype(str).str.strip() == 'RECKITT'
    df['RECKITT_SEGMENTO'] = None
    if mascara_reckitt.any():
        df.loc[mascara_reckitt, 'RECKITT_SEGMENTO'] = df.loc[mascara_reckitt, 'CLASIFICACION_3'].apply(clasificar_segmento_reckitt)

    cols_cat = ['CLASIFICACION_1', 'CLASIFICACION_2', 'CLASIFICACION_3', 'CLASIFICACION_4', 'CATEGORIA_CLIENTE', 'VENDEDOR']
    for c in cols_cat:
        if c in df.columns:
            df[c] = df[c].astype('category')

    return df

@st.cache_data
def cargar_datos_canales():
    try:
        df_canales = pd.read_excel("CLIENTES POR CANAL.xlsx")
        df_canales.columns = [str(c).strip().upper() for c in df_canales.columns]
        
        col_cliente = next((c for c in df_canales.columns if 'CLIENTE' in c), None)
        col_canal = next((c for c in df_canales.columns if 'CANAL' in c), None)
        
        if col_cliente and col_canal:
            df_canales = df_canales[[col_cliente, col_canal]].copy()
            df_canales.columns = ['CLIENTE', 'CANAL']
            df_canales['CLIENTE'] = df_canales['CLIENTE'].astype(str).str.strip()
            df_canales['CANAL'] = df_canales['CANAL'].astype(str).str.strip()
            return df_canales
    except Exception as e:
        st.warning(f"No se pudo cargar el archivo de canales: {e}")
    
    return pd.DataFrame(columns=['CLIENTE', 'CANAL'])

# ---------------------------------------------------------
# 3. Funciones de Apoyo y Lógica de Tablas Escalonadas
# ---------------------------------------------------------
def calcular_variacion(actual, anterior):
    if anterior == 0 or pd.isna(anterior):
        return 0.0
    return ((actual - anterior) / anterior) * 100

def resaltar_variaciones(val):
    if isinstance(val, str) and '%' in val:
        try:
            num = float(val.replace('%', '').replace('+', '').strip())
            if num > 0:
                return 'color: #00c853; font-weight: bold;'
            elif num < 0:
                return 'color: #f87171; font-weight: bold;'
        except ValueError:
            pass
    return ''

def obtener_datos_comparativa_formateada(df_sub: pd.DataFrame, col_group: str, titulo: str):
    if df_sub.empty:
        return None

    pivot = pd.pivot_table(
        df_sub,
        index=col_group,
        columns='ANIO',
        values='VENTA_NETA',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    anios = sorted([col for col in pivot.columns if col != col_group])
    if len(anios) == 0:
        return None

    res_df = pd.DataFrame()
    res_df[titulo] = pivot[col_group]

    if len(anios) == 1:
        a1 = anios[0]
        res_df[str(a1)] = pivot[a1].apply(lambda x: f"₡{x:,.2f}")
        res_df['IND'] = "0.0%"
    else:
        a1, a2 = anios[0], anios[1]
        res_df[str(a1)] = pivot[a1].apply(lambda x: f"₡{x:,.2f}")
        res_df[str(a2)] = pivot[a2].apply(lambda x: f"₡{x:,.2f}")
        
        vars_a = [calcular_variacion(act, ant) for act, ant in zip(pivot[a2], pivot[a1])]
        res_df['IND'] = [f"{v:+.1f}%" if v != 0 else "0.0%" for v in vars_a]

        if len(anios) >= 3:
            a3 = anios[2]
            meses_a3 = df_sub[df_sub['ANIO'] == a3]['MES_NUM'].unique()
            
            v_a2_periodo = df_sub[(df_sub['ANIO'] == a2) & (df_sub['MES_NUM'].isin(meses_a3))].groupby(col_group)['VENTA_NETA'].sum().reindex(pivot[col_group], fill_value=0).values
            v_a3_periodo = df_sub[(df_sub['ANIO'] == a3) & (df_sub['MES_NUM'].isin(meses_a3))].groupby(col_group)['VENTA_NETA'].sum().reindex(pivot[col_group], fill_value=0).values
            
            res_df[f"{a2} ({a3})"] = [f"₡{x:,.2f}" for x in v_a2_periodo]
            res_df[str(a3)] = [f"₡{x:,.2f}" for x in v_a3_periodo]
            
            vars_p = [calcular_variacion(act, ant) for act, ant in zip(v_a3_periodo, v_a2_periodo)]
            res_df['IND '] = [f"{v:+.1f}%" if v != 0 else "0.0%" for v in vars_p]

    totales = {titulo: 'TOTAL'}
    for anio in anios:
        totales[str(anio)] = f"₡{pivot[anio].sum():,.2f}"
    
    if len(anios) >= 2:
        totales['IND'] = f"{calcular_variacion(pivot[anios[1]].sum(), pivot[anios[0]].sum()):+.1f}%"
    else:
        totales['IND'] = "0.0%"

    if len(anios) >= 3:
        v2_tot = df_sub[(df_sub['ANIO'] == anios[1]) & (df_sub['MES_NUM'].isin(df_sub[df_sub['ANIO'] == anios[2]]['MES_NUM'].unique()))]['VENTA_NETA'].sum()
        v3_tot = df_sub[(df_sub['ANIO'] == anios[2]) & (df_sub['MES_NUM'].isin(df_sub[df_sub['ANIO'] == anios[2]]['MES_NUM'].unique()))]['VENTA_NETA'].sum()
        totales[f"{anios[1]} ({anios[2]})"] = f"₡{v2_tot:,.2f}"
        totales[str(anios[2])] = f"₡{v3_tot:,.2f}"
        totales['IND '] = f"{calcular_variacion(v3_tot, v2_tot):+.1f}%"

    df_tot = pd.DataFrame([totales])
    res_completo = pd.concat([res_df, df_tot], ignore_index=True)
    return res_completo

def generar_tabla_comparativa_formateada(df_sub: pd.DataFrame, col_group: str, titulo: str):
    res_completo = obtener_datos_comparativa_formateada(df_sub, col_group, titulo)
    if res_completo is None or res_completo.empty:
        return

    cols_ind = [c for c in res_completo.columns if 'IND' in c]
    styler = res_completo.style.map(resaltar_variaciones, subset=cols_ind) if cols_ind else res_completo
    
    st.subheader(f"🏷️ {titulo}")
    st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
        height=(len(res_completo) + 1) * 35 + 5
    )

def construir_datos_escalonados_proveedor(df_prov: pd.DataFrame, nombre_prov: str):
    if df_prov.empty:
        return None, []

    anios = sorted(df_prov['ANIO'].unique())
    if not anios:
        return None, []

    meses_a3 = df_prov[df_prov['ANIO'] == anios[2]]['MES_NUM'].unique() if len(anios) >= 3 else []

    filas = []
    tipos_fila = []

    def procesar_agrupacion(df_segmento, etiqueta, tipo):
        datos = {'Concepto': etiqueta}
        ventas_por_anio = df_segmento.groupby('ANIO')['VENTA_NETA'].sum().to_dict()

        for a in anios:
            datos[str(a)] = ventas_por_anio.get(a, 0.0)

        if len(anios) >= 2:
            a1, a2 = anios[0], anios[1]
            datos['IND'] = calcular_variacion(datos[str(a2)], datos[str(a1)])

        if len(anios) >= 3:
            a2, a3 = anios[1], anios[2]
            v_a2_per = df_segmento[(df_segmento['ANIO'] == a2) & (df_segmento['MES_NUM'].isin(meses_a3))]['VENTA_NETA'].sum()
            v_a3_per = df_segmento[(df_segmento['ANIO'] == a3) & (df_segmento['MES_NUM'].isin(meses_a3))]['VENTA_NETA'].sum()
            datos[f"{a2} ({a3})"] = v_a2_per
            datos[str(a3)] = v_a3_per
            datos['IND '] = calcular_variacion(v_a3_per, v_a2_per)

        filas.append(datos)
        tipos_fila.append(tipo)

    # N1: Cabecera
    procesar_agrupacion(df_prov, f"{nombre_prov}", 'N1')

    # 1. COLGATE_PALM: Clasif 1 -> Clasif 2 -> Clasif 4 -> Clasif 3 (Excepto CUIDADO BEBE)
    if nombre_prov == 'COLGATE_PALM':
        c2_unicos = sorted([x for x in df_prov['CLASIFICACION_2'].dropna().unique() if str(x).strip() != ''])
        for val_c2 in c2_unicos:
            df_c2 = df_prov[df_prov['CLASIFICACION_2'] == val_c2]
            procesar_agrupacion(df_c2, f"{val_c2}", 'N2')
            
            val_c2_limpio = str(val_c2).upper().replace('_', ' ').strip()
            if val_c2_limpio == 'CUIDADO BEBE':
                continue

            c4_unicos = sorted([x for x in df_c2['CLASIFICACION_4'].dropna().unique() if str(x).strip() != ''])
            for val_c4 in c4_unicos:
                df_c4 = df_c2[df_c2['CLASIFICACION_4'] == val_c4]
                procesar_agrupacion(df_c4, f"      {val_c4}", 'N3')
                
                c3_unicos = sorted([x for x in df_c4['CLASIFICACION_3'].dropna().unique() if str(x).strip() != ''])
                for val_c3 in c3_unicos:
                    df_c3 = df_c4[df_c4['CLASIFICACION_3'] == val_c3]
                    procesar_agrupacion(df_c3, f"            {val_c3}", 'N4')

    # 2. ESSITY: Clasif 1 -> Clasif 2 -> Clasif 3 -> Clasif 4
    elif nombre_prov == 'ESSITY':
        c2_unicos = sorted([x for x in df_prov['CLASIFICACION_2'].dropna().unique() if str(x).strip() != ''])
        for val_c2 in c2_unicos:
            df_c2 = df_prov[df_prov['CLASIFICACION_2'] == val_c2]
            procesar_agrupacion(df_c2, f"{val_c2}", 'N2')
            
            c3_unicos = sorted([x for x in df_c2['CLASIFICACION_3'].dropna().unique() if str(x).strip() != ''])
            for val_c3 in c3_unicos:
                df_c3 = df_c2[df_c2['CLASIFICACION_3'] == val_c3]
                procesar_agrupacion(df_c3, f"      {val_c3}", 'N3')
                
                c4_unicos = sorted([x for x in df_c3['CLASIFICACION_4'].dropna().unique() if str(x).strip() != ''])
                for val_c4 in c4_unicos:
                    df_c4 = df_c3[df_c3['CLASIFICACION_4'] == val_c4]
                    procesar_agrupacion(df_c4, f"            {val_c4}", 'N4')

    # 3. HEINZ.CR: Clasif 1 -> HEINZ_CATEGORIA -> Clasif 4 -> Clasif 3 (Excepto OTROS)
    elif nombre_prov == 'HEINZ.CR':
        orden_heinz = ['MAYONESA', 'KETCHUP', 'COLADOS', 'SALSITAS', 'OTROS']
        heinz_cats_presentes = [c for c in orden_heinz if c in df_prov['HEINZ_CATEGORIA'].dropna().unique()]
        
        for cat_heinz in heinz_cats_presentes:
            df_cat = df_prov[df_prov['HEINZ_CATEGORIA'] == cat_heinz]
            procesar_agrupacion(df_cat, f"{cat_heinz}", 'N2')
            
            if cat_heinz == 'OTROS':
                continue
            
            c4_unicos = sorted([x for x in df_cat['CLASIFICACION_4'].dropna().unique() if str(x).strip() != ''])
            for val_c4 in c4_unicos:
                df_cat_c4 = df_cat[df_cat['CLASIFICACION_4'] == val_c4]
                procesar_agrupacion(df_cat_c4, f"      {val_c4}", 'N3')
                
                c3_unicos = sorted([x for x in df_cat_c4['CLASIFICACION_3'].dropna().unique() if str(x).strip() != ''])
                for val_c3 in c3_unicos:
                    df_cat_c3 = df_cat_c4[df_cat_c4['CLASIFICACION_3'] == val_c3]
                    procesar_agrupacion(df_cat_c3, f"            {val_c3}", 'N4')

    # 4. RECKITT: Clasif 1 -> CORE / VASTACY -> Clasif 3
    elif nombre_prov == 'RECKITT':
        orden_reckitt = ['CORE', 'VASTACY']
        reckitt_presentes = [r for r in orden_reckitt if r in df_prov['RECKITT_SEGMENTO'].dropna().unique()]
        
        for seg_reckitt in reckitt_presentes:
            df_seg = df_prov[df_prov['RECKITT_SEGMENTO'] == seg_reckitt]
            procesar_agrupacion(df_seg, f"{seg_reckitt}", 'N2')
            
            c3_unicos = sorted([x for x in df_seg['CLASIFICACION_3'].dropna().unique() if str(x).strip() != ''])
            for val_c3 in c3_unicos:
                df_c3 = df_seg[df_seg['CLASIFICACION_3'] == val_c3]
                procesar_agrupacion(df_c3, f"      {val_c3}", 'N3')

    # 5. RESTO DE MARCAS CONFIGURADAS
    else:
        grupo_1_2_3 = ['PEPSICO']
        grupo_1_3_4 = ['ALIMER S.A.', 'BARRAZA']

        if nombre_prov in grupo_1_2_3:
            cols_niveles = ['CLASIFICACION_2', 'CLASIFICACION_3']
        elif nombre_prov in grupo_1_3_4:
            cols_niveles = ['CLASIFICACION_3', 'CLASIFICACION_4']
        else:
            cols_niveles = ['CLASIFICACION_2']

        col_n2 = cols_niveles[0]
        n2_unicos = sorted([x for x in df_prov[col_n2].dropna().unique() if str(x).strip() != ''])

        for val_n2 in n2_unicos:
            df_n2 = df_prov[df_prov[col_n2] == val_n2]
            procesar_agrupacion(df_n2, f"{val_n2}", 'N2')

            if len(cols_niveles) > 1:
                col_n3 = cols_niveles[1]
                if col_n3 in df_n2.columns:
                    n3_unicos = sorted([x for x in df_n2[col_n3].dropna().unique() if str(x).strip() != ''])
                    for val_n3 in n3_unicos:
                        df_n3 = df_n2[df_n2[col_n3] == val_n3]
                        procesar_agrupacion(df_n3, f"      {val_n3}", 'N3')

    df_resultado = pd.DataFrame(filas)

    for c in df_resultado.columns:
        if c in ['Concepto']:
            continue
        elif 'IND' in c:
            df_resultado[c] = df_resultado[c].apply(lambda x: f"{x:+.1f}%" if x != 0 else "0.0%")
        else:
            df_resultado[c] = df_resultado[c].apply(lambda x: f"₡{x:,.2f}")

    return df_resultado, tipos_fila

def generar_tabla_escalonada_proveedor(df_prov: pd.DataFrame, nombre_prov: str):
    df_resultado, tipos_fila = construir_datos_escalonados_proveedor(df_prov, nombre_prov)
    if df_resultado is None or df_resultado.empty:
        return

    def estilo_dark_escalonado(row):
        idx = row.name
        tipo = tipos_fila[idx]
        if tipo == 'N1':
            return ['background-color: #111927; color: #ffffff; font-weight: bold; border-top: 1px solid #374151;'] * len(row)
        elif tipo == 'N2':
            return ['background-color: #1a2332; color: #f3f4f6; font-weight: bold;'] * len(row)
        elif tipo == 'N3':
            return ['background-color: #0e131f; color: #d1d5db; font-weight: normal;'] * len(row)
        elif tipo == 'N4':
            return ['background-color: #080c14; color: #9ca3af; font-style: italic;'] * len(row)
        return [''] * len(row)

    cols_ind = [c for c in df_resultado.columns if 'IND' in c]
    styler = df_resultado.style.apply(estilo_dark_escalonado, axis=1)
    if cols_ind:
        styler = styler.map(resaltar_variaciones, subset=cols_ind)

    st.subheader(f"🏷️ Detalle Escalonado: {nombre_prov}")
    st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
        height=(len(df_resultado) + 1) * 35 + 5
    )

# ---------------------------------------------------------
# 4. Generador de PDF Completo en Base a Vista Actual
# ---------------------------------------------------------
def formatear_dataframe_para_reportlab(df_tabla):
    if df_tabla is None or df_tabla.empty:
        return []
    headers = list(df_tabla.columns)
    filas = [headers]
    for _, row in df_tabla.iterrows():
        fila_str = [str(val) for val in row.values]
        filas.append(fila_str)
    return filas

def generar_pdf_reporte_completo(df_analisis, seleccion_actual, fig_plotly, df_mensual_resultado, marcas_a_mostrar):
    if not REPORTLAB_DISPONIBLE:
        return None
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=12,
        textColor=colors.HexColor("#00174F"),
        spaceAfter=3
    )
    style_section = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        fontSize=9,
        textColor=colors.HexColor("#009640"),
        spaceAfter=3,
        spaceBefore=6,
        keepWithNext=True
    )
    style_subsection = ParagraphStyle(
        'SubSectionStyle',
        parent=styles['Heading3'],
        fontSize=7.5,
        textColor=colors.HexColor("#00174F"),
        spaceAfter=2,
        spaceBefore=4,
        keepWithNext=True
    )

    # 1. Cabecera
    story.append(Paragraph(f"<b>Informe Ejecutivo Sedisur BI - {seleccion_actual}</b>", style_title))
    story.append(Paragraph(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    
    clientes_unicos = df_analisis['CLIENTE'].unique()
    if len(clientes_unicos) == 1:
        story.append(Spacer(1, 2))
        story.append(Paragraph(f"<b>Cliente:</b> {df_analisis['ALIAS'].iloc[0]} | <b>Razón Social:</b> {df_analisis['NOMBRE'].iloc[0]} | <b>Código:</b> {df_analisis['CLIENTE'].iloc[0]}", styles['Normal']))

    vendedores_unicos = df_analisis['VENDEDOR'].unique()
    if len(vendedores_unicos) == 1 and pd.notna(vendedores_unicos[0]):
        story.append(Paragraph(f"<b>Vendedor:</b> {vendedores_unicos[0]}", styles['Normal']))

    story.append(Spacer(1, 4))

    # 2. Tabla Comparativa por Mes y Variación Porcentual
    if df_mensual_resultado is not None and not df_mensual_resultado.empty:
        story.append(Paragraph("<b>1. Tabla Comparativa por Mes y Variación Porcentual</b>", style_section))
        data_mensual = formatear_dataframe_para_reportlab(df_mensual_resultado)
        num_cols = len(data_mensual[0])
        col_w = [65] + [(500 - 65) / (num_cols - 1)] * (num_cols - 1)
        
        t_mensual = Table(data_mensual, colWidths=col_w)
        t_mensual.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#00174F")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('ALIGN', (0,1), (0,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 5.5),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#e2efda")),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
            ('TOPPADDING', (0,0), (-1,-1), 1.5),
        ]))
        story.append(KeepTogether([t_mensual]))
        story.append(Spacer(1, 4))

    # 3. Tendencia Evolutiva Mensual (Gráfico Plotly)
    try:
        img_bytes = fig_plotly.to_image(format="png", width=700, height=200, scale=2)
        img_io = io.BytesIO(img_bytes)
        story.append(Paragraph("<b>2. Tendencia Evolutiva Mensual</b>", style_section))
        story.append(KeepTogether([RLImage(img_io, width=480, height=135)]))
        story.append(Spacer(1, 4))
    except Exception:
        pass

    # 4. Sección: Comparativa por Proveedores y Sub-Marcas Escalonadas
    story.append(Paragraph("<b>3. Comparativa por Proveedores y Sub-Marcas Escalonadas</b>", style_section))

    # Resumen General Proveedores (Solo si está en Consolidado General)
    if seleccion_actual == "📊 Consolidado General (Sedisur)":
        df_resumen_gen = obtener_datos_comparativa_formateada(df_analisis, 'CLASIFICACION_1', 'Resumen General Proveedores')
        if df_resumen_gen is not None and not df_resumen_gen.empty:
            data_res = formatear_dataframe_para_reportlab(df_resumen_gen)
            num_cols_res = len(data_res[0])
            col_w_res = [100] + [(500 - 100) / (num_cols_res - 1)] * (num_cols_res - 1)
            
            t_res = Table(data_res, colWidths=col_w_res)
            t_res.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#00174F")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('ALIGN', (0,1), (0,-1), 'LEFT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 5.5),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#e2efda")),
                ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
                ('TOPPADDING', (0,0), (-1,-1), 1.5),
            ]))
            story.append(KeepTogether([
                Paragraph("<b>Resumen General Proveedores</b>", style_subsection),
                t_res,
                Spacer(1, 4)
            ]))

    # Todos los Detalles Escalonados que se muestran en pantalla
    for prov_marca in marcas_a_mostrar:
        df_prov_filtrado = df_analisis[df_analisis['CLASIFICACION_1'].str.strip() == prov_marca.strip()]
        if not df_prov_filtrado.empty:
            df_esc, tipos_f = construir_datos_escalonados_proveedor(df_prov_filtrado, prov_marca)
            if df_esc is not None and not df_esc.empty:
                data_esc = formatear_dataframe_para_reportlab(df_esc)
                num_cols_esc = len(data_esc[0])
                col_w_esc = [120] + [(500 - 120) / (num_cols_esc - 1)] * (num_cols_esc - 1)
                
                # Definir estilos por jerarquía de filas en el PDF
                estilos_tabla_esc = [
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#00174F")),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('ALIGN', (0,1), (0,-1), 'LEFT'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 5.5),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
                    ('TOPPADDING', (0,0), (-1,-1), 1.5),
                ]

                for row_idx, tipo in enumerate(tipos_f, start=1):
                    if tipo == 'N1':
                        estilos_tabla_esc.extend([
                            ('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#e2efda")),
                            ('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold')
                        ])
                    elif tipo == 'N2':
                        estilos_tabla_esc.extend([
                            ('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#f2f4f7")),
                            ('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold')
                        ])

                t_esc = Table(data_esc, colWidths=col_w_esc)
                t_esc.setStyle(TableStyle(estilos_tabla_esc))
                
                story.append(KeepTogether([
                    Paragraph(f"<b>Detalle Escalonado: {prov_marca}</b>", style_subsection),
                    t_esc,
                    Spacer(1, 4)
                ]))

    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_manual_operaciones():
    try:
        with open("Manual_Operaciones_Sedisur.pdf", "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None

# ---------------------------------------------------------
# 5. Vista Comparativa
# ---------------------------------------------------------
def mostrar_vista_comparativa(df: pd.DataFrame, df_raw_completo: pd.DataFrame):
    st.header("📈 Comparativa de Ventas Año contra Año")

    if df.empty:
        st.warning("No hay datos disponibles con los filtros seleccionados.")
        return None

    marca_restriccion = st.session_state.get("marca_restringida")

    if marca_restriccion:
        lista_vistas = [f"Proveedor: {marca_restriccion}"]
        st.info(f"🔒 **Modo Proveedor Activo:** Visualizando únicamente los datos correspondientes a **{marca_restriccion}**.")
    else:
        orden_personalizado = [
            'COLGATE_PALM', 'ESSITY', 'PEPSICO', 'HEINZ.CR', 'ALIMER S.A.',
            'BAYER', 'RECKITT', 'BARRAZA', 'REYA CR.', 'HEALTH. RB.',
            'GRUPO Q.', 'BEL PREMIUM', 'CODOMI', 'FARMANOVA', 'MUNDOREP', 'PRONUTRE'
        ]

        proveedores_disponibles_df = df['CLASIFICACION_1'].dropna().unique()
        proveedores_ordenados = [p for p in orden_personalizado if p in proveedores_disponibles_df]
        otros_proveedores = sorted([p for p in proveedores_disponibles_df if p not in orden_personalizado])
        
        lista_proveedores_final = proveedores_ordenados + otros_proveedores
        lista_vistas = ["📊 Consolidado General (Sedisur)"] + [f"Proveedor: {p}" for p in lista_proveedores_final]

    if "indice_vista_prov" not in st.session_state:
        st.session_state["indice_vista_prov"] = 0

    if st.session_state["indice_vista_prov"] >= len(lista_vistas):
        st.session_state["indice_vista_prov"] = 0

    if not marca_restriccion:
        col_info, col_btn_izq, col_btn_sedisur, col_btn_der = st.columns([4, 1.2, 1.2, 1.2])

        with col_btn_izq:
            if st.button("◀ Anterior", use_container_width=True):
                st.session_state["indice_vista_prov"] = (st.session_state["indice_vista_prov"] - 1) % len(lista_vistas)
                st.rerun()

        with col_btn_sedisur:
            if st.button("🏢 Sedisur", use_container_width=True):
                st.session_state["indice_vista_prov"] = 0
                st.rerun()

        with col_btn_der:
            if st.button("Siguiente ▶", use_container_width=True):
                st.session_state["indice_vista_prov"] = (st.session_state["indice_vista_prov"] + 1) % len(lista_vistas)
                st.rerun()
    else:
        col_info = st.columns([1])[0]

    seleccion_actual = lista_vistas[st.session_state["indice_vista_prov"]]

    with col_info:
        st.markdown(f"### 🏷️ Analizando: **{seleccion_actual}**")

    st.divider()

    if seleccion_actual != "📊 Consolidado General (Sedisur)":
        proveedor_seleccionado = seleccion_actual.replace("Proveedor: ", "").strip()
        df_analisis = df[df['CLASIFICACION_1'].str.strip() == proveedor_seleccionado]
    else:
        df_analisis = df

    clientes_unicos = df_analisis['CLIENTE'].unique()
    if len(clientes_unicos) == 1:
        st.subheader(f"🏪 Cliente: {df_analisis['ALIAS'].iloc[0]}")
        st.caption(f"**Razón Social:** {df_analisis['NOMBRE'].iloc[0]} | **Código:** {df_analisis['CLIENTE'].iloc[0]}")
    else:
        st.subheader("📊 Tabla Comparativa por Mes y Variación Porcentual")

    pivot_base = pd.pivot_table(
        df_analisis,
        index=['MES_NUM', 'MES_NOMBRE'],
        columns='ANIO',
        values='VENTA_NETA',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    pivot_base = pivot_base.sort_values('MES_NUM').drop(columns=['MES_NUM'])
    pivot_base.rename(columns={'MES_NOMBRE': 'Mes'}, inplace=True)

    anios_presentes = sorted([col for col in pivot_base.columns if col != 'Mes'])

    if len(anios_presentes) < 2:
        st.info("💡 Selecciona al menos dos años en los filtros para ver la variación porcentual interanual.")

    fila_totales = {'Mes': 'TOTAL GENERAL'}
    for anio in anios_presentes:
        fila_totales[anio] = pivot_base[anio].sum()

    pivot_completa = pd.concat([pivot_base, pd.DataFrame([fila_totales])], ignore_index=True)

    df_resultado = pd.DataFrame()
    df_resultado['Mes'] = pivot_completa['Mes']

    if len(anios_presentes) > 0:
        primer_anio = anios_presentes[0]
        df_resultado[str(primer_anio)] = pivot_completa[primer_anio].apply(lambda x: f"₡{x:,.2f}")

    columnas_variacion = []
    for i in range(1, len(anios_presentes)):
        anio_anterior = anios_presentes[i - 1]
        anio_actual = anios_presentes[i]

        col_var_nombre = f"Var % ({str(anio_actual)[-2:]} vs {str(anio_anterior)[-2:]})"
        columnas_variacion.append(col_var_nombre)

        variaciones = [
            calcular_variacion(actual, anterior)
            for actual, anterior in zip(pivot_completa[anio_actual], pivot_completa[anio_anterior])
        ]

        df_resultado[str(anio_actual)] = pivot_completa[anio_actual].apply(lambda x: f"₡{x:,.2f}")
        df_resultado[col_var_nombre] = [f"{v:+.2f}%" for v in variaciones]

    styler = df_resultado.style.map(resaltar_variaciones, subset=columnas_variacion) if columnas_variacion else df_resultado
    
    st.dataframe(
        styler, 
        use_container_width=True, 
        hide_index=True,
        height=(len(df_resultado) + 1) * 35 + 3
    )

    st.divider()

    df_agrupado = df_analisis.groupby(['ANIO', 'MES_NUM', 'MES_NOMBRE'], as_index=False).agg({
        'VENTA_NETA': 'sum',
        'CANTIDAD_NETA': 'sum'
    }).sort_values('MES_NUM')

    df_agrupado['ANIO_STR'] = df_agrupado['ANIO'].astype(str)

    st.subheader("📉 Tendencia Evolutiva Mensual")

    tipo_grafico = st.radio(
        "Métrica a visualizar en el gráfico:",
        options=["Venta Neta (₡)", "Cantidad Neta"],
        horizontal=True,
        key="radio_metrica_grafico_dinamico"
    )

    columna_y = 'VENTA_NETA' if tipo_grafico == "Venta Neta (₡)" else 'CANTIDAD_NETA'

    colores_anios = {
        '2024': '#8A9BA8',
        '2025': '#00174F',
        '2026': '#009640'
    }

    fig = px.line(
        df_agrupado,
        x='MES_NOMBRE',
        y=columna_y,
        color='ANIO_STR',
        color_discrete_map=colores_anios,
        markers=True,
        title=f"Evolución Mensual Comparativa ({seleccion_actual}): {tipo_grafico}",
        labels={
            'MES_NOMBRE': 'Mes',
            columna_y: tipo_grafico,
            'ANIO_STR': 'Año'
        },
        category_orders={'MES_NOMBRE': ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']}
    )

    if tipo_grafico == "Venta Neta (₡)":
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Métrica: ₡%{y:,.2f}<extra></extra>")
    else:
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Métrica: %{y:,.0f}<extra></extra>")

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#E0E0E0',
        height=450, 
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.header("🏢 Comparativa por Proveedores y Sub-Marcas Escalonadas")

    marcas_autorizadas_escalonadas = [
        'COLGATE_PALM', 'ESSITY', 'PEPSICO', 'RECKITT',
        'ALIMER S.A.', 'BARRAZA', 'HEINZ.CR'
    ]

    marcas_renderizadas = []

    if marca_restriccion:
        if marca_restriccion in marcas_autorizadas_escalonadas:
            df_base_proveedor = df_raw_completo[df_raw_completo['CLASIFICACION_1'].str.strip() == marca_restriccion]
            generar_tabla_escalonada_proveedor(df_base_proveedor, marca_restriccion)
            marcas_renderizadas.append(marca_restriccion)
    else:
        if seleccion_actual == "📊 Consolidado General (Sedisur)":
            generar_tabla_comparativa_formateada(df_analisis, 'CLASIFICACION_1', 'Resumen General Proveedores')
            st.markdown("---")

            proveedores_disponibles = sorted(df_analisis['CLASIFICACION_1'].dropna().unique())
            for prov in proveedores_disponibles:
                prov_limpio = prov.strip()
                if prov_limpio in marcas_autorizadas_escalonadas:
                    df_prov = df_analisis[df_analisis['CLASIFICACION_1'].str.strip() == prov_limpio]
                    if not df_prov.empty:
                        generar_tabla_escalonada_proveedor(df_prov, prov_limpio)
                        marcas_renderizadas.append(prov_limpio)
                        st.markdown("<br>", unsafe_allow_html=True)
        else:
            proveedor_seleccionado = seleccion_actual.replace("Proveedor: ", "").strip()
            if proveedor_seleccionado in marcas_autorizadas_escalonadas:
                generar_tabla_escalonada_proveedor(df_analisis, proveedor_seleccionado)
                marcas_renderizadas.append(proveedor_seleccionado)

    # Generar PDF que incluye exactamente las tablas y gráficos renderizados en pantalla
    pdf_buffer_global = None
    if REPORTLAB_DISPONIBLE:
        pdf_buffer_global = generar_pdf_reporte_completo(
            df_analisis=df_analisis,
            seleccion_actual=seleccion_actual,
            fig_plotly=fig,
            df_mensual_resultado=df_resultado,
            marcas_a_mostrar=marcas_renderizadas
        )

    return pdf_buffer_global

# ---------------------------------------------------------
# 6. Vista Cobertura 8020
# ---------------------------------------------------------
def mostrar_vista_cobertura_8020(df_raw: pd.DataFrame, filtro_a, reglas_b: dict, df_filtrado: pd.DataFrame):
    st.header("🎯 Análisis de Cobertura 80/20 y Oportunidades de Alcance")

    marca_restriccion = st.session_state.get("marca_restringida")
    if marca_restriccion:
        filtro_a = marca_restriccion
        st.info(f"🔒 **Modo Proveedor Activo:** Analizando cobertura exclusivamente para **{marca_restriccion}**.")

    if not filtro_a:
        st.info("👆 Por favor, seleccione una opción en el **Filtro A (Referencia 80/20)** en el segundo panel para calcular el Pareto.")
        return

    if df_filtrado.empty:
        st.warning("No hay datos disponibles con los filtros seleccionados.")
        return

    if filtro_a == "TODOS (Consolidado Sedisur)":
        df_ref_a = df_filtrado.copy()
    else:
        df_ref_a = df_filtrado[df_filtrado['CLASIFICACION_1'] == filtro_a]

    if df_ref_a.empty:
        st.warning("No se encontraron registros para la referencia seleccionada en el Filtro A con los filtros actuales.")
        return

    # A. Promedio Mensual
    df_mensual_cliente = df_ref_a.groupby(['CLIENTE', 'ALIAS', 'CATEGORIA_CLIENTE', 'ANIO', 'MES_NUM'], as_index=False).agg(
        VENTA_MES=('VENTA_NETA', 'sum')
    )

    if df_mensual_cliente.empty:
        st.warning("No se encontraron registros para calcular la cobertura con los filtros actuales.")
        return

    df_clientes = df_mensual_cliente.groupby(['CLIENTE', 'ALIAS', 'CATEGORIA_CLIENTE'], as_index=False).agg(
        VENTA_TOTAL_A=('VENTA_MES', 'sum'),
        VENTA_PROMEDIO_A=('VENTA_MES', 'mean')
    ).sort_values(by='VENTA_PROMEDIO_A', ascending=False).reset_index(drop=True)

    if df_clientes.empty:
        st.warning("No se pudieron agrupar los clientes para esta selección.")
        return

    df_clientes['Posición'] = df_clientes.index + 1

    venta_total_promedio_acumulada = df_clientes['VENTA_PROMEDIO_A'].sum()
    df_clientes['PORCENTAJE_INDIVIDUAL'] = 0.0
    df_clientes['PORCENTAJE_ACUMULADO'] = 0.0

    if venta_total_promedio_acumulada > 0:
        df_clientes['PORCENTAJE_INDIVIDUAL'] = (df_clientes['VENTA_PROMEDIO_A'] / venta_total_promedio_acumulada) * 100
        df_clientes['PORCENTAJE_ACUMULADO'] = df_clientes['PORCENTAJE_INDIVIDUAL'].cumsum()

    # B. Venta del Mes Actual
    ahora = datetime.now()
    mes_actual_num = ahora.month
    anio_actual_valor = ahora.year

    if filtro_a == "TODOS (Consolidado Sedisur)":
        df_base_actual = df_raw.copy()
    else:
        df_base_actual = df_raw[df_raw['CLASIFICACION_1'] == filtro_a]

    df_mes_actual_ref = df_base_actual[
        (df_base_actual['ANIO'] == anio_actual_valor) & 
        (df_base_actual['MES_NUM'] == mes_actual_num)
    ]

    if not df_mes_actual_ref.empty:
        df_venta_mes_actual = df_mes_actual_ref.groupby('CLIENTE', as_index=False).agg(
            VENTA_MES_ACTUAL=('VENTA_NETA', 'sum')
        )
    else:
        df_venta_mes_actual = pd.DataFrame(columns=['CLIENTE', 'VENTA_MES_ACTUAL'])

    df_clientes = df_clientes.merge(df_venta_mes_actual, on='CLIENTE', how='left')
    df_clientes['VENTA_MES_ACTUAL'] = df_clientes['VENTA_MES_ACTUAL'].fillna(0)

    # Tabla Base
    df_tabla_final = pd.DataFrame()
    df_tabla_final['Posición'] = df_clientes['Posición']
    df_tabla_final['CLIENTE'] = df_clientes['CLIENTE']
    df_tabla_final['Cód. Cliente'] = df_clientes['CLIENTE']
    df_tabla_final['Alias'] = df_clientes['ALIAS']
    df_tabla_final['Categoría Cliente'] = df_clientes['CATEGORIA_CLIENTE']
    df_tabla_final['% Individual'] = df_clientes['PORCENTAJE_INDIVIDUAL'].apply(lambda x: f"{x:.2f}%")
    df_tabla_final['Venta Promedio Mensual (Filtro A)'] = df_clientes['VENTA_PROMEDIO_A'].apply(lambda x: f"₡{x:,.2f}")
    df_tabla_final['Venta Mes Actual'] = df_clientes['VENTA_MES_ACTUAL'].apply(lambda x: f"₡{x:,.2f}")
    df_tabla_final['% Acumulado'] = df_clientes['PORCENTAJE_ACUMULADO']
    df_tabla_final['Cobertura Filtro A'] = "✅"

    # C. Procesamiento del Filtro B
    filtros_b_prov = reglas_b.get("proveedores", [])
    sel_c2 = reglas_b.get("c2", [])
    sel_c3 = reglas_b.get("c3", [])
    sel_c4 = reglas_b.get("c4", [])

    if filtros_b_prov and not marca_restriccion:
        for prov_b in filtros_b_prov:
            df_prov_b = df_raw[df_raw['CLASIFICACION_1'] == prov_b]

            df_clientes_prov_b = df_prov_b.groupby('CLIENTE', as_index=False).agg(VENTA_CONSOLIDADA=('VENTA_NETA', 'sum'))
            df_tabla_final = df_tabla_final.merge(df_clientes_prov_b, on='CLIENTE', how='left')
            df_tabla_final['VENTA_CONSOLIDADA'] = df_tabla_final['VENTA_CONSOLIDADA'].fillna(0)
            df_tabla_final[f"Colocación: {prov_b} (Consol.)"] = df_tabla_final['VENTA_CONSOLIDADA'].apply(lambda x: "✅" if x > 0 else "❌")
            df_tabla_final = df_tabla_final.drop(columns=['VENTA_CONSOLIDADA'])

            subcats_prov = [c for c in sel_c2 if c in df_prov_b['CLASIFICACION_2'].unique()]
            if subcats_prov:
                for subcat in subcats_prov:
                    df_sub = df_prov_b[df_prov_b['CLASIFICACION_2'] == subcat]
                    
                    if sel_c3 and 'CLASIFICACION_3' in df_sub.columns:
                        df_sub = df_sub[df_sub['CLASIFICACION_3'].isin(sel_c3)]
                    if sel_c4 and 'CLASIFICACION_4' in df_sub.columns:
                        df_sub = df_sub[df_sub['CLASIFICACION_4'].isin(sel_c4)]

                    df_clientes_sub = df_sub.groupby('CLIENTE', as_index=False).agg(VENTA_SUBCAT=('VENTA_NETA', 'sum'))
                    col_nombre = f"Colocación: {prov_b} - {subcat}"
                    df_tabla_final = df_tabla_final.merge(df_clientes_sub, on='CLIENTE', how='left')
                    df_tabla_final['VENTA_SUBCAT'] = df_tabla_final['VENTA_SUBCAT'].fillna(0)
                    df_tabla_final[col_nombre] = df_tabla_final['VENTA_SUBCAT'].apply(lambda x: "✅" if x > 0 else "❌")
                    df_tabla_final = df_tabla_final.drop(columns=['VENTA_SUBCAT'])

    def resaltar_8020(row):
        styles = [''] * len(row)
        try:
            idx_porc = row.index.get_loc('% Individual')
            if df_clientes.loc[row.name, 'PORCENTAJE_ACUMULADO'] <= 80.0:
                styles[idx_porc] = 'color: #00c853; font-weight: bold;'
        except Exception:
            pass
        return styles

    df_mostrar = df_tabla_final.drop(columns=['CLIENTE', '% Acumulado'])
    styler_8020 = df_mostrar.style.apply(resaltar_8020, axis=1)

    titulo_b_str = f" vs ({', '.join(filtros_b_prov)})" if (filtros_b_prov and not marca_restriccion) else ""
    st.subheader(f"📊 Matriz de Cobertura para: {filtro_a}{titulo_b_str}")
    st.dataframe(styler_8020, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# 7. Flujo Principal de Ejecución
# ---------------------------------------------------------
if verificar_acceso():
    with st.spinner("Cargando datos del reporte..."):
        df_raw = cargar_datos_exactus()
        df_canales = cargar_datos_canales()

    df_raw['CLIENTE'] = df_raw['CLIENTE'].astype(str).str.strip()
    if not df_canales.empty:
        df_canales['CLIENTE'] = df_canales['CLIENTE'].astype(str).str.strip()
        df_raw = df_raw.merge(df_canales[['CLIENTE', 'CANAL']], on='CLIENTE', how='left')
        df_raw['CANAL'] = df_raw['CANAL'].fillna('OTROS')
    else:
        df_raw['CANAL'] = 'OTROS'

    df_raw_completo = df_raw.copy()

    marca_restriccion = st.session_state.get("marca_restringida")
    if marca_restriccion:
        df_raw = df_raw[df_raw['CLASIFICACION_1'].str.strip() == marca_restriccion]

    if "vista_activa" not in st.session_state:
        st.session_state["vista_activa"] = "comparativa"

    with st.sidebar:
        try:
            st.image("Sedisur_logo.png", use_container_width=True)
        except Exception:
            st.markdown("### **Sedisur S.A.**")

        st.markdown(f"👤 **Usuario:** {st.session_state.get('usuario_actual', '')}")
        st.markdown(f"💼 **Cargo:** {st.session_state.get('cargo_actual', '')}")
        st.markdown(f"🛡️ **Rol:** {st.session_state.get('rol_actual', '')}")
        
        if marca_restriccion:
            st.markdown(f"🏷️ **Marca Asignada:** `{marca_restriccion}`")

        st.markdown("---")
        
        if st.button("🔄 Recargar Datos", use_container_width=True, help="Limpia la caché y recarga los datos"):
            cargar_datos_exactus.clear()
            cargar_datos_canales.clear()
            st.toast("¡Datos recargados correctamente!", icon="✅")
            st.rerun()

        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state["autenticado"] = False
            st.rerun()
        st.divider()

        st.markdown("### 🧭 Menú Principal")
        if st.button("📈 Comparativa de ventas", use_container_width=True):
            st.session_state["vista_activa"] = "comparativa"
            st.rerun()

        if st.button("🎯 Cobertura 8020", use_container_width=True):
            st.session_state["vista_activa"] = "cobertura"
            st.rerun()

        st.divider()

        pdf_manual_bytes = generar_pdf_manual_operaciones()
        if pdf_manual_bytes:
            st.download_button(
                label="📖 Descargar Manual BI",
                data=pdf_manual_bytes,
                file_name="Manual_Operaciones_Sedisur.pdf",
                mime="application/pdf",
                use_container_width=True,
                help="Descargar tu manual de operaciones en PDF"
            )
        else:
            st.warning("⚠️ No se encontró 'Manual_Operaciones_Sedisur.pdf' en el directorio.")

        st.markdown("---")
        st.markdown(
            "<div style='text-align: center; font-size: 11px; color: gray; padding-bottom: 10px;'>"
            "Creado por RM Studio para Sedisur Central K.C.M.A."
            "</div>",
            unsafe_allow_html=True
        )

    lista_canales = ['TODOS'] + sorted([c for c in df_raw['CANAL'].dropna().unique().tolist() if c != 'OTROS']) + ['OTROS']
    
    df_clientes_unicos = df_raw[['CLIENTE', 'ALIAS']].drop_duplicates().sort_values('CLIENTE')
    opciones_clientes = df_clientes_unicos['CLIENTE'].tolist()
    format_func_cliente = lambda x: f"{x} - {df_clientes_unicos[df_clientes_unicos['CLIENTE'] == x]['ALIAS'].values[0]}" if x in df_clientes_unicos['CLIENTE'].values else str(x)

    if st.session_state["vista_activa"] == "comparativa":
        with st.expander("🔍 **Panel de Filtros Comerciales (Comparativa)**", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                anios_disponibles = sorted(df_raw['ANIO'].unique(), reverse=True)
                sel_anios = st.multiselect("Año", anios_disponibles, key="filtro_anios")
                
                meses_disponibles = [m for m in ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                                                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'] if m in df_raw['MES_NOMBRE'].unique()]
                sel_meses = st.multiselect("Mes", meses_disponibles, key="filtro_meses")

            with col2:
                filtro_canal_sel = st.selectbox("Canal", lista_canales, key="filtro_canal_comp")
                categorias = sorted(df_raw['CATEGORIA_CLIENTE'].dropna().unique())
                sel_cats = st.multiselect("Categoría Cliente", categorias, key="filtro_cats")

            with col3:
                vendedores = sorted(df_raw['VENDEDOR'].dropna().unique())
                sel_vendedores = st.multiselect("Vendedor", vendedores, key="filtro_vendedores")
                sel_clientes = st.multiselect("Cliente (Código y Alias)", options=opciones_clientes, format_func=format_func_cliente, key="filtro_clientes_comp")

            with col4:
                if marca_restriccion:
                    st.selectbox("Proveedor (Clasif. 1)", options=[marca_restriccion], disabled=True, key="filtro_proveedor_bloqueado")
                    sel_proveedores = [marca_restriccion]
                else:
                    proveedores = sorted(df_raw['CLASIFICACION_1'].dropna().unique())
                    sel_proveedores = st.multiselect("Proveedor (Clasif. 1)", proveedores, key="filtro_proveedores")
                
                df_cascada_c2 = df_raw if not sel_proveedores else df_raw[df_raw['CLASIFICACION_1'].isin(sel_proveedores)]
                clasificaciones = sorted(df_cascada_c2['CLASIFICACION_2'].dropna().unique())
                sel_clasificaciones = st.multiselect("Clasificación (Clasif. 2)", clasificaciones, key="filtro_clasificaciones")

                df_cascada_c3 = df_cascada_c2
                if sel_clasificaciones:
                    df_cascada_c3 = df_cascada_c3[df_cascada_c3['CLASIFICACION_2'].isin(sel_clasificaciones)]
                
                marcas = sorted(df_cascada_c3['CLASIFICACION_3'].dropna().unique()) if 'CLASIFICACION_3' in df_cascada_c3.columns else []
                sel_marcas_prod = st.multiselect("Marca (Clasif. 3)", marcas, key="filtro_marcas_prod")

                df_cascada_c4 = df_cascada_c3
                if sel_marcas_prod and 'CLASIFICACION_3' in df_cascada_c4.columns:
                    df_cascada_c4 = df_cascada_c4[df_cascada_c4['CLASIFICACION_3'].isin(sel_marcas_prod)]

                tipos_producto = sorted(df_cascada_c4['CLASIFICACION_4'].dropna().unique()) if 'CLASIFICACION_4' in df_cascada_c4.columns else []
                sel_tipos_prod = st.multiselect("Tipo de producto (Clasif. 4)", tipos_producto, key="filtro_tipos_prod")

        df_raw_global = df_raw.copy()
        if filtro_canal_sel != 'TODOS':
            df_raw_global = df_raw_global[df_raw_global['CANAL'] == filtro_canal_sel]

        df_filt = df_raw_global.copy()
        if sel_anios:
            df_filt = df_filt[df_filt['ANIO'].isin(sel_anios)]

        # Lógica de Meses Cerrados por Defecto (Enero a Mes Anterior al Actual)
        ahora_actual = datetime.now()
        mes_actual_sistema = ahora_actual.month

        if sel_meses:
            df_filt = df_filt[df_filt['MES_NOMBRE'].isin(sel_meses)]
        else:
            limite_mes = max(1, mes_actual_sistema - 1)
            df_filt = df_filt[df_filt['MES_NUM'] <= limite_mes]

        if sel_proveedores and not marca_restriccion:
            df_filt = df_filt[df_filt['CLASIFICACION_1'].isin(sel_proveedores)]
        if sel_clasificaciones:
            df_filt = df_filt[df_filt['CLASIFICACION_2'].isin(sel_clasificaciones)]
        if sel_marcas_prod and 'CLASIFICACION_3' in df_filt.columns:
            df_filt = df_filt[df_filt['CLASIFICACION_3'].isin(sel_marcas_prod)]
        if sel_tipos_prod and 'CLASIFICACION_4' in df_filt.columns:
            df_filt = df_filt[df_filt['CLASIFICACION_4'].isin(sel_tipos_prod)]
        if sel_cats:
            df_filt = df_filt[df_filt['CATEGORIA_CLIENTE'].isin(sel_cats)]
        if sel_vendedores:
            df_filt = df_filt[df_filt['VENDEDOR'].isin(sel_vendedores)]
        if sel_clientes:
            df_filt = df_filt[df_filt['CLIENTE'].isin(sel_clientes)]

        pdf_buffer_generado = mostrar_vista_comparativa(df_filt, df_raw_completo)

        # Botón de Descarga del PDF
        if REPORTLAB_DISPONIBLE and pdf_buffer_generado:
            st.download_button(
                label="📥 Descargar Informe Ejecutivo en PDF",
                data=pdf_buffer_generado,
                file_name="Informe_Sedisur_Ejecutivo.pdf",
                mime="application/pdf",
                use_container_width=True,
                help="Descargar informe PDF completo con tablas y gráficos"
            )

    elif st.session_state["vista_activa"] == "cobertura":
        # --- PANEL 1: Filtros Generales ---
        with st.expander("🔍 **Panel 1: Filtros Generales (Año, Mes, Vendedor y Categoría Cliente)**", expanded=True):
            col_g1, col_g2, col_g3, col_g4 = st.columns(4)
            
            with col_g1:
                anios_disponibles = sorted(df_raw['ANIO'].unique(), reverse=True)
                sel_anios_cob = st.multiselect("Año", anios_disponibles, key="filtro_anios_cob")
                
            with col_g2:
                meses_disponibles = [m for m in ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                                                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'] if m in df_raw['MES_NOMBRE'].unique()]
                sel_meses_cob = st.multiselect("Mes", meses_disponibles, key="filtro_meses_cob")

            with col_g3:
                vendedores_disponibles = sorted(df_raw['VENDEDOR'].dropna().unique())
                sel_vendedores_cob = st.multiselect("Vendedor", vendedores_disponibles, key="filtro_vendedores_cob")

            with col_g4:
                categorias = sorted(df_raw['CATEGORIA_CLIENTE'].dropna().unique())
                sel_cats_cob = st.multiselect("Categoría Cliente", categorias, key="filtro_cats_cob")

        # --- PANEL 2: Filtros Comerciales (A y B) ---
        with st.expander("🔍 **Panel 2: Filtros Comerciales (Filtro A y Filtro B Escalonados)**", expanded=False):
            marcas_disponibles = sorted(df_raw['CLASIFICACION_1'].dropna().unique())
            
            if marca_restriccion:
                opciones_filtro_a = [marca_restriccion]
            else:
                opciones_filtro_a = ["TODOS (Consolidado Sedisur)"] + list(marcas_disponibles)

            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("### 📌 Filtro A (Referencia 80/20)")
                if marca_restriccion:
                    st.selectbox("Proveedor Principal (Clasif. 1)", options=[marca_restriccion], disabled=True, key="filtro_a_cob_bloq")
                    filtro_a = marca_restriccion
                else:
                    filtro_a = st.selectbox("Proveedor Principal (Clasif. 1)", options=opciones_filtro_a, key="filtro_a_cob")

                df_cascada_a = df_raw if (filtro_a == "TODOS (Consolidado Sedisur)" or not filtro_a) else df_raw[df_raw['CLASIFICACION_1'] == filtro_a]
                
                clasificaciones_a = sorted(df_cascada_a['CLASIFICACION_2'].dropna().unique())
                sel_clasificaciones_a = st.multiselect("Clasificación (Clasif. 2) - A", clasificaciones_a, key="filtro_clasificaciones_a")

                df_cascada_a_c3 = df_cascada_a
                if sel_clasificaciones_a:
                    df_cascada_a_c3 = df_cascada_a_c3[df_cascada_a_c3['CLASIFICACION_2'].isin(sel_clasificaciones_a)]

                marcas_a = sorted(df_cascada_a_c3['CLASIFICACION_3'].dropna().unique()) if 'CLASIFICACION_3' in df_cascada_a_c3.columns else []
                sel_marcas_a = st.multiselect("Marca (Clasif. 3) - A", marcas_a, key="filtro_marcas_a")

                df_cascada_a_c4 = df_cascada_a_c3
                if sel_marcas_a and 'CLASIFICACION_3' in df_cascada_a_c4.columns:
                    df_cascada_a_c4 = df_cascada_a_c4[df_cascada_a_c4['CLASIFICACION_3'].isin(sel_marcas_a)]

                tipos_prod_a = sorted(df_cascada_a_c4['CLASIFICACION_4'].dropna().unique()) if 'CLASIFICACION_4' in df_cascada_a_c4.columns else []
                sel_tipos_prod_a = st.multiselect("Tipo de producto (Clasif. 4) - A", tipos_prod_a, key="filtro_tipos_prod_a")

            with col_b:
                st.markdown("### 🔍 Filtro B (Comparativo de Colocación)")
                if marca_restriccion:
                    st.info("🔒 Bloque B no disponible en modo proveedor restringido.")
                    filtros_b = []
                    sel_clasificaciones_b, sel_marcas_b, sel_tipos_prod_b = [], [], []
                else:
                    filtros_b = st.multiselect("Proveedores a Comparar (Clasif. 1)", options=marcas_disponibles, key="filtro_b_cob")

                    df_cascada_b = df_raw if not filtros_b else df_raw[df_raw['CLASIFICACION_1'].isin(filtros_b)]

                    clasificaciones_b = sorted(df_cascada_b['CLASIFICACION_2'].dropna().unique())
                    sel_clasificaciones_b = st.multiselect("Clasificación (Clasif. 2) - B", clasificaciones_b, key="filtro_clasificaciones_b")

                    df_cascada_b_c3 = df_cascada_b
                    if sel_clasificaciones_b:
                        df_cascada_b_c3 = df_cascada_b_c3[df_cascada_b_c3['CLASIFICACION_2'].isin(sel_clasificaciones_b)]

                    marcas_b = sorted(df_cascada_b_c3['CLASIFICACION_3'].dropna().unique()) if 'CLASIFICACION_3' in df_cascada_b_c3.columns else []
                    sel_marcas_b = st.multiselect("Marca (Clasif. 3) - B", marcas_b, key="filtro_marcas_b")

                    df_cascada_b_c4 = df_cascada_b_c3
                    if sel_marcas_b and 'CLASIFICACION_3' in df_cascada_b_c4.columns:
                        df_cascada_b_c4 = df_cascada_b_c4[df_cascada_b_c4['CLASIFICACION_3'].isin(sel_marcas_b)]

                    tipos_prod_b = sorted(df_cascada_b_c4['CLASIFICACION_4'].dropna().unique()) if 'CLASIFICACION_4' in df_cascada_b_c4.columns else []
                    sel_tipos_prod_b = st.multiselect("Tipo de producto (Clasif. 4) - B", tipos_prod_b, key="filtro_tipos_prod_b")

        reglas_b = {
            "proveedores": filtros_b,
            "c2": sel_clasificaciones_b,
            "c3": sel_marcas_b,
            "c4": sel_tipos_prod_b
        }

        df_filt_cob = df_raw.copy()
        if sel_anios_cob:
            df_filt_cob = df_filt_cob[df_filt_cob['ANIO'].isin(sel_anios_cob)]
        if sel_meses_cob:
            df_filt_cob = df_filt_cob[df_filt_cob['MES_NOMBRE'].isin(sel_meses_cob)]
        if sel_vendedores_cob:
            df_filt_cob = df_filt_cob[df_filt_cob['VENDEDOR'].isin(sel_vendedores_cob)]
        if sel_cats_cob:
            df_filt_cob = df_filt_cob[df_filt_cob['CATEGORIA_CLIENTE'].isin(sel_cats_cob)]

        if sel_clasificaciones_a:
            df_filt_cob = df_filt_cob[df_filt_cob['CLASIFICACION_2'].isin(sel_clasificaciones_a)]
        if sel_marcas_a and 'CLASIFICACION_3' in df_filt_cob.columns:
            df_filt_cob = df_filt_cob[df_filt_cob['CLASIFICACION_3'].isin(sel_marcas_a)]
        if sel_tipos_prod_a and 'CLASIFICACION_4' in df_filt_cob.columns:
            df_filt_cob = df_filt_cob[df_filt_cob['CLASIFICACION_4'].isin(sel_tipos_prod_a)]

        mostrar_vista_cobertura_8020(df_raw, filtro_a, reglas_b, df_filt_cob)
