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
    # Lee el archivo de datos procesados (sin tocar SQL Server)
    df = pd.read_parquet("datos_ventas.parquet")
    
    df = df[df['CLASIFICACION_1'].notna() & (df['CLASIFICACION_1'].astype(str).str.strip() != '') & (df['CLASIFICACION_1'] != 'SIN CLASIFICAR')]

    meses_es = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }
    df['MES_NOMBRE'] = df['MES_NUM'].map(meses_es)
    df['CLIENTE_DISPLAY'] = df['CLIENTE'] + " - " + df['ALIAS']
    
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

def generar_tabla_comparativa_formateada(df_sub: pd.DataFrame, col_group: str, titulo: str):
    if df_sub.empty:
        return

    pivot = pd.pivot_table(
        df_sub,
        index=col_group,
        columns='ANIO',
        values='VENTA_NETA',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    anios = sorted([col for col in pivot.columns if col != col_group])
    if len(anios) < 2:
        return

    res_df = pd.DataFrame()
    res_df[titulo] = pivot[col_group]

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
    totales[str(a1)] = f"₡{pivot[a1].sum():,.2f}"
    totales[str(a2)] = f"₡{pivot[a2].sum():,.2f}"
    totales['IND'] = f"{calcular_variacion(pivot[a2].sum(), pivot[a1].sum()):+.1f}%"

    if len(anios) >= 3:
        v2_tot = df_sub[(df_sub['ANIO'] == a2) & (df_sub['MES_NUM'].isin(meses_a3))]['VENTA_NETA'].sum()
        v3_tot = df_sub[(df_sub['ANIO'] == a3) & (df_sub['MES_NUM'].isin(meses_a3))]['VENTA_NETA'].sum()
        totales[f"{a2} ({a3})"] = f"₡{v2_tot:,.2f}"
        totales[str(a3)] = f"₡{v3_tot:,.2f}"
        totales['IND '] = f"{calcular_variacion(v3_tot, v2_tot):+.1f}%"

    df_tot = pd.DataFrame([totales])
    res_completo = pd.concat([res_df, df_tot], ignore_index=True)

    cols_ind = [c for c in res_completo.columns if 'IND' in c]
    styler = res_completo.style.map(resaltar_variaciones, subset=cols_ind)
    
    st.subheader(f"🏷️ {titulo}")
    st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
        height=(len(res_completo) + 1) * 35 + 5
    )

def mostrar_vista_comparativa(df: pd.DataFrame):
    st.header("📈 Comparativa de Ventas Año contra Año")

    if df.empty:
        st.warning("No hay datos disponibles con los filtros seleccionados.")
        return

    clientes_unicos = df['CLIENTE'].unique()
    if len(clientes_unicos) == 1:
        st.subheader(f"🏪 Cliente: {df['ALIAS'].iloc[0]}")
        st.caption(f"**Razón Social:** {df['NOMBRE'].iloc[0]} | **Código:** {df['CLIENTE'].iloc[0]}")
    else:
        st.subheader("📊 Tabla Comparativa por Mes y Variación Porcentual")

    pivot_base = pd.pivot_table(
        df,
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

    df_agrupado = df.groupby(['ANIO', 'MES_NUM', 'MES_NOMBRE'], as_index=False).agg({
        'VENTA_NETA': 'sum',
        'CANTIDAD_NETA': 'sum'
    }).sort_values('MES_NUM')

    df_agrupado['ANIO_STR'] = df_agrupado['ANIO'].astype(str)

    st.subheader("📉 Tendencia Evolutiva Mensual")

    tipo_grafico = st.radio(
        "Métrica a visualizar en el gráfico:",
        options=["Venta Neta (₡)", "Cantidad Neta"],
        horizontal=True
    )

    columna_y = 'VENTA_NETA' if tipo_grafico == "Venta Neta (₡)" else 'CANTIDAD_NETA'

    fig = px.line(
        df_agrupado,
        x='MES_NOMBRE',
        y=columna_y,
        color='ANIO_STR',
        markers=True,
        title=f"Evolución Mensual Comparativa: {tipo_grafico}",
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

    st.divider()

    st.header("🏢 Comparativa por Proveedores y Categorías")

    generar_tabla_comparativa_formateada(df, 'CLASIFICACION_1', 'Sedisur (Consolidado por Proveedor)')

    st.markdown("---")

    proveedores_excluidos = [
        'AB-INBEV', 'BAYER', 'BEL PREMIUM', 'CODOMI',  
        'FARMANOVA', 'GRUPO Q.', 'HEALTH. RB.', 'HEALTH',  
        'REYA CR.', 'RECKITT'
    ]

    orden_proveedores = [
        'COLGATE_PALM',
        'ESSITY',
        'HEINZ.CR',
        'ALIMER S.A.',
        'PEPSICO',
        'BARRAZA'
    ]

    proveedores_disponibles = df['CLASIFICACION_1'].dropna().unique()
    proveedores_a_mostrar = [p for p in orden_proveedores if p in proveedores_disponibles]
    otros_proveedores = sorted([p for p in proveedores_disponibles if p not in orden_proveedores])
    proveedores_finales = proveedores_a_mostrar + otros_proveedores

    for prov in proveedores_finales:
        prov_limpio = prov.strip()
        if prov_limpio not in proveedores_excluidos:
            df_prov = df[df['CLASIFICACION_1'].str.strip() == prov_limpio]
            if not df_prov.empty:
                generar_tabla_comparativa_formateada(df_prov, 'CLASIFICACION_2', f"Proveedor: {prov}")

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

# --- FILTROS EN PANEL EXPANDIBLE SUPERIOR ---
with st.expander("🔍 **Panel de Filtros Comerciales**", expanded=True):
    
    # --- BOTÓN DE SINCRONIZACIÓN (Actualiza el archivo local) ---
    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        if st.button("🔄 Recargar Datos", help="Limpia la caché y vuelve a leer el archivo de datos"):
            cargar_datos_exactus.clear()
            st.toast("¡Datos recargados correctamente!", icon="✅")
            st.rerun()

    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    
    with col1:
        anios_disponibles = sorted(df_raw['ANIO'].unique(), reverse=True)
        sel_anios = st.multiselect("Año", anios_disponibles, key="filtro_anios")
        
        meses_en_datos = [m for m in ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                                      'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'] if m in df_raw['MES_NOMBRE'].unique()]
        sel_meses = st.multiselect("Mes", meses_en_data, key="filtro_meses" if 'meses_en_datos' in locals() else "filtro_meses") # Corregido por seguridad

    with col2:
        marcas = sorted(df_raw['CLASIFICACION_1'].dropna().unique())
        sel_marcas = st.multiselect("Clasificación 1 (Marca)", marcas, key="filtro_marcas")
        
        categorias = sorted(df_raw['CATEGORIA_CLIENTE'].dropna().unique())
        sel_cats = st.multiselect("Categoría Cliente", categorias, key="filtro_cats")

    with col3:
        clientes = sorted(df_raw['CLIENTE_DISPLAY'].dropna().unique())
        sel_clientes = st.multiselect("Cliente", clientes, key="filtro_clientes")

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

# Invocación de la Vista Comparativa Completa
mostrar_vista_comparativa(df_filt)
