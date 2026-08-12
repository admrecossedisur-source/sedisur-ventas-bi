import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime

# ---------------------------------------------------------
# 1. Configuración Inicial de la Página
# ---------------------------------------------------------
st.set_page_config(
    page_title="Sedisur BI - Comparativa de Ventas",
    page_icon="📈",
    layout="wide"
)

# ---------------------------------------------------------
# 2. Carga de Datos Segura (Desde el archivo local/nube)
# ---------------------------------------------------------
@st.cache_data
def cargar_datos_exactus():
    df = pd.read_parquet("datos_ventas.parquet")
    
    df = df[df['CLASIFICACION_1'].notna() & (df['CLASIFICACION_1'].astype(str).str.strip() != '') & (df['CLASIFICACION_1'] != 'SIN CLASIFICAR')]

    meses_es = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }
    df['MES_NOMBRE'] = df['MES_NUM'].map(meses_es)
    df['CLIENTE_DISPLAY'] = df['CLIENTE'].astype(str) + " - " + df['ALIAS'].astype(str)
    
    return df

# ---------------------------------------------------------
# 3. Funciones de Apoyo (Cálculos y Tablas)
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
                return 'color: #2e7d32; font-weight: bold;'
            elif num < 0:
                return 'color: #c62828; font-weight: bold;'
        except ValueError:
            pass
    return ''

def mostrar_vista_comparativa(df: pd.DataFrame):
    st.header("📈 Comparativa de Ventas Año contra Año")

    if df.empty:
        st.warning("No hay datos disponibles con los filtros seleccionados.")
        return

    # --- LISTA ORDENADA DE PROVEEDORES PARA NAVEGACIÓN ---
    proveedores_disponibles = sorted(df['CLASIFICACION_1'].dropna().unique())
    lista_vistas = ["📊 Consolidado General (Sedisur)"] + [f"Proveedor: {p}" for p in proveedores_disponibles]

    # Inicializar el índice de navegación en session_state si no existe
    if "indice_vista_prov" not in st.session_state:
        st.session_state["indice_vista_prov"] = 0

    if st.session_state["indice_vista_prov"] >= len(lista_vistas):
        st.session_state["indice_vista_prov"] = 0

    # --- BARRA DE CONTROL CON BOTONES (ESTILO ANTERIOR / SIGUIENTE) ---
    col_info, col_btn_izq, col_btn_der = st.columns([6, 1, 1])

    with col_btn_izq:
        if st.button("◀ Anterior", use_container_width=True):
            st.session_state["indice_vista_prov"] = (st.session_state["indice_vista_prov"] - 1) % len(lista_vistas)
            st.rerun()

    with col_btn_der:
        if st.button("Siguiente ▶", use_container_width=True):
            st.session_state["indice_vista_prov"] = (st.session_state["indice_vista_prov"] + 1) % len(lista_vistas)
            st.rerun()

    seleccion_actual = lista_vistas[st.session_state["indice_vista_prov"]]

    with col_info:
        st.markdown(f"### 🏷️ Analizando: **{seleccion_actual}**")

    st.divider()

    # --- FILTRAR DATOS SEGÚN LA SELECCIÓN DE LOS BOTONES ---
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

    # --- CONSTRUCCIÓN DE LA TABLA PRINCIPAL ---
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

    styler = df_resultado.style.map(resaltar_variaciones, subset=columnas_variacion)
    
    st.dataframe(
        styler, 
        use_container_width=True, 
        hide_index=True,
        height=(len(df_resultado) + 1) * 35 + 3
    )

    st.divider()

    # --- GRÁFICO DE TENDENCIA EVOLUTIVA MENSUAL ---
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

    fig = px.line(
        df_agrupado,
        x='MES_NOMBRE',
        y=columna_y,
        color='ANIO_STR',
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

    fig.update_layout(height=450, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# 4. Flujo Principal de Ejecución de la App Web
# ---------------------------------------------------------
with st.spinner("Cargando datos del reporte..."):
    df_raw = cargar_datos_exactus()

# --- INICIALIZACIÓN SEGURA DE ESTADOS EN SESSION_STATE ---
if "filtro_anios" not in st.session_state:
    st.session_state["filtro_anios"] = sorted(df_raw['ANIO'].unique(), reverse=True)

if "filtro_meses" not in st.session_state:
    mes_actual = datetime.now().month
    mes_limite = mes_actual - 1 if mes_actual > 1 else 12
    orden_meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                   'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    st.session_state["filtro_meses"] = [m for i, m in enumerate(orden_meses[:mes_limite]) if m in df_raw['MES_NOMBRE'].unique()]

if "filtro_marcas" not in st.session_state:
    st.session_state["filtro_marcas"] = []

if "filtro_cats" not in st.session_state:
    st.session_state["filtro_cats"] = []

if "filtro_clientes" not in st.session_state:
    st.session_state["filtro_clientes"] = []

if "filtro_vendedores" not in st.session_state:
    st.session_state["filtro_vendedores"] = []

# --- FILTROS EN PANEL EXPANDIBLE SUPERIOR ---
with st.expander("🔍 **Panel de Filtros Comerciales**", expanded=True):
    
    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        if st.button("🔄 Recargar Datos", help="Limpia la caché y vuelve a leer el archivo de datos"):
            cargar_datos_exactus.clear()
            st.toast("¡Datos recargados correctamente!", icon="✅")
            st.rerun()

    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        anios_disponibles = sorted(df_raw['ANIO'].unique(), reverse=True)
        sel_anios = st.multiselect("Año", anios_disponibles, key="filtro_anios")
        
        meses_disponibles = [m for m in ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                                        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'] if m in df_raw['MES_NOMBRE'].unique()]
        sel_meses = st.multiselect("Mes", meses_disponibles, key="filtro_meses")

    with col2:
        marcas = sorted(df_raw['CLASIFICACION_1'].dropna().unique())
        sel_marcas = st.multiselect("Clasificación 1 (Marca)", marcas, key="filtro_marcas")
        
        categorias = sorted(df_raw['CATEGORIA_CLIENTE'].dropna().unique())
        sel_cats = st.multiselect("Categoría Cliente", categorias, key="filtro_cats")

    with col3:
        clientes = sorted(df_raw['CLIENTE_DISPLAY'].dropna().unique())
        sel_clientes = st.multiselect("Cliente", clientes, key="filtro_clientes")

    with col4:
        vendedores = sorted(df_raw['VENDEDOR'].dropna().unique())
        sel_vendedores = st.multiselect("Vendedor", vendedores, key="filtro_vendedores")

# Filtrado de DataFrame
df_filt = df_raw.copy()

if sel_anios:
    df_filt = df_filt[df_filt['ANIO'].isin(sel_anios)]
if sel_meses:
    df_filt = df_filt[df_filt['MES_NOMBRE'].isin(sel_meses)]
if sel_marcas:
    df_filt = df_filt[df_filt['CLASIFICACION_1'].isin(sel_marcas)]
if sel_cats:
    df_filt = df_filt[df_filt['CATEGORIA_CLIENTE'].isin(sel_cats)]
if sel_clientes:
    df_filt = df_filt[df_filt['CLIENTE_DISPLAY'].isin(sel_clientes)]
if sel_vendedores:
    df_filt = df_filt[df_filt['VENDEDOR'].isin(sel_vendedores)]

# Invocación de la Vista Comparativa Interactiva
mostrar_vista_comparativa(df_filt)
