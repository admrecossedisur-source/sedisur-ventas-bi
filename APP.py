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
# 2. Carga de Datos Segura
# ---------------------------------------------------------
@st.cache_data
def cargar_datos_exactus():
    # Asumiendo que el archivo parquet está en el mismo directorio
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
# 3. Funciones de Apoyo
# ---------------------------------------------------------
def calcular_variacion(actual, anterior):
    if anterior == 0 or pd.isna(anterior):
        return 0.0
    return ((actual - anterior) / anterior) * 100

def resaltar_variaciones(val):
    if isinstance(val, str) and '%' in val:
        try:
            num = float(val.replace('%', '').replace('+', '').strip())
            if num > 0: return 'color: #2e7d32; font-weight: bold;'
            elif num < 0: return 'color: #c62828; font-weight: bold;'
        except ValueError: pass
    return ''

def mostrar_vista_comparativa(df: pd.DataFrame):
    st.header("📈 Comparativa de Ventas Año contra Año")

    if df.empty:
        st.warning("No hay datos disponibles con los filtros seleccionados.")
        return

    # --- CONTROL DE NAVEGACIÓN POR PROVEEDOR ---
    proveedores_disponibles = sorted(df['CLASIFICACION_1'].dropna().unique())
    opciones_vista = ["📊 Consolidado General (Sedisur)"] + [f"Proveedor: {p}" for p in proveedores_disponibles]
    
    seleccion_actual = st.radio(
        "Navegar vista por proveedor:",
        options=opciones_vista,
        horizontal=True
    )
    
    # Filtramos el DataFrame según la selección
    if seleccion_actual != "📊 Consolidado General (Sedisur)":
         proveedor_seleccionado = seleccion_actual.replace("Proveedor: ", "").strip()
         df_analisis = df[df['CLASIFICACION_1'].str.strip() == proveedor_seleccionado]
         st.subheader(f"🏷️ Proveedor: {proveedor_seleccionado}")
    else:
         df_analisis = df
         st.subheader("📊 Consolidado General (Todos los Proveedores Seleccionados)")

    st.divider()

    # Tabla Comparativa Principal
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
        variaciones = [calcular_variacion(act, ant) for act, ant in zip(pivot_completa[anio_actual], pivot_completa[anio_anterior])]
        df_resultado[str(anio_actual)] = pivot_completa[anio_actual].apply(lambda x: f"₡{x:,.2f}")
        df_resultado[col_var_nombre] = [f"{v:+.2f}%" for v in variaciones]

    st.dataframe(df_resultado.style.map(resaltar_variaciones, subset=columnas_variacion), use_container_width=True, hide_index=True)

    # Gráfico
    df_agrupado = df_analisis.groupby(['ANIO', 'MES_NUM', 'MES_NOMBRE'], as_index=False).agg({'VENTA_NETA': 'sum', 'CANTIDAD_NETA': 'sum'}).sort_values('MES_NUM')
    df_agrupado['ANIO_STR'] = df_agrupado['ANIO'].astype(str)
    tipo_grafico = st.radio("Métrica:", ["Venta Neta (₡)", "Cantidad Neta"], horizontal=True)
    columna_y = 'VENTA_NETA' if tipo_grafico == "Venta Neta (₡)" else 'CANTIDAD_NETA'
    fig = px.line(df_agrupado, x='MES_NOMBRE', y=columna_y, color='ANIO_STR', markers=True)
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# 4. Flujo Principal
# ---------------------------------------------------------
df_raw = cargar_datos_exactus()

# Inicialización estados
for key in ["filtro_anios", "filtro_meses", "filtro_marcas", "filtro_cats", "filtro_clientes", "filtro_vendedores"]:
    if key not in st.session_state: st.session_state[key] = []

with st.expander("🔍 **Panel de Filtros Comerciales**", expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        sel_anios = st.multiselect("Año", sorted(df_raw['ANIO'].unique(), reverse=True), key="filtro_anios")
        sel_meses = st.multiselect("Mes", df_raw['MES_NOMBRE'].unique(), key="filtro_meses")
    with col2:
        sel_marcas = st.multiselect("Marca", sorted(df_raw['CLASIFICACION_1'].dropna().unique()), key="filtro_marcas")
        sel_cats = st.multiselect("Categoría", sorted(df_raw['CATEGORIA_CLIENTE'].dropna().unique()), key="filtro_cats")
    with col3:
        sel_clientes = st.multiselect("Cliente", sorted(df_raw['CLIENTE_DISPLAY'].dropna().unique()), key="filtro_clientes")
    with col4:
        sel_vendedores = st.multiselect("Vendedor", sorted(df_raw['VENDEDOR'].dropna().unique()), key="filtro_vendedores")

# Filtrado
df_filt = df_raw.copy()
if sel_anios: df_filt = df_filt[df_filt['ANIO'].isin(sel_anios)]
if sel_meses: df_filt = df_filt[df_filt['MES_NOMBRE'].isin(sel_meses)]
if sel_marcas: df_filt = df_filt[df_filt['CLASIFICACION_1'].isin(sel_marcas)]
if sel_cats: df_filt = df_filt[df_filt['CATEGORIA_CLIENTE'].isin(sel_cats)]
if sel_clientes: df_filt = df_filt[df_filt['CLIENTE_DISPLAY'].isin(sel_clientes)]
if sel_vendedores: df_filt = df_filt[df_filt['VENDEDOR'].isin(sel_vendedores)]

mostrar_vista_comparativa(df_filt)
