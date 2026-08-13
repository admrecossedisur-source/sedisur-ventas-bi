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
    "henry.azofeifa@sedisur.com": {"password": "Hea000", "cargo": "Gerencia", "rol": "Usuario"},
    "diego.barrantes@sedisur.com": {"password": "Dib000", "cargo": "Supervisión", "rol": "Usuario"},
    "harvy.arbustini@sedisur.com": {"password": "Haa000", "cargo": "Supervisión", "rol": "Usuario"},
    "eddy.zuniga@sedisur.com": {"password": "Edz000", "cargo": "Supervisión", "rol": "Usuario"},
    "cristina.nunez@sedisur.com": {"password": "Crn000", "cargo": "Supervisión", "rol": "administrador"},
    "erick.abarca@sedisur.com": {"password": "Era000", "cargo": "Supervisión", "rol": "Usuario"},
    "rafael.romero@sedisur.com": {"password": "Rar000", "cargo": "Supervisión", "rol": "administrador"}
}

def verificar_acceso():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if st.session_state["autenticado"]:
        return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## 🔐 Inicio de Sesión - Sedisur BI")
        st.markdown("Por favor, ingrese sus credenciales corporativas para acceder al sistema.")

        with st.form("form_login"):
            correo = st.text_input("Correo electrónico").strip().lower()
            password = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Ingresar", use_container_width=True)

            if submit:
                if correo in USUARIOS_PERMITIDOS and USUARIOS_PERMITIDOS[correo]["password"] == password:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario_actual"] = correo
                    st.session_state["cargo_actual"] = USUARIOS_PERMITIDOS[correo]["cargo"]
                    st.session_state["rol_actual"] = USUARIOS_PERMITIDOS[correo]["rol"]
                    st.success("¡Acceso concedido!")
                    st.rerun()
                else:
                    st.error("Correo o contraseña incorrectos.")
    
    return False

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

    anios_deseados = [2024, 2025, 2026]
    for a in anios_deseados:
        if a not in pivot.columns:
            pivot[a] = 0.0

    res_df = pd.DataFrame()
    res_df[titulo] = pivot[col_group]

    res_df['2024'] = pivot[2024].apply(lambda x: f"{x:,.2f}")
    res_df['2025'] = pivot[2025].apply(lambda x: f"{x:,.2f}")
    
    var_25_24 = [calcular_variacion(act, ant) for act, ant in zip(pivot[2025], pivot[2024])]
    res_df['Var % (25 vs 24)'] = [f"{v:+.2f}%" if v != 0 else "0.00%" for v in var_25_24]

    res_df['2026'] = pivot[2026].apply(lambda x: f"{x:,.2f}")
    
    var_26_25 = [calcular_variacion(act, ant) for act, ant in zip(pivot[2026], pivot[2025])]
    res_df['Var % (26 vs 25)'] = [f"{v:+.2f}%" if v != 0 else "0.00%" for v in var_26_25]

    totales = {titulo: 'TOTAL'}
    totales['2024'] = f"{pivot[2024].sum():,.2f}"
    totales['2025'] = f"{pivot[2025].sum():,.2f}"
    totales['Var % (25 vs 24)'] = f"{calcular_variacion(pivot[2025].sum(), pivot[2024].sum()):+.2f}%"
    totales['2026'] = f"{pivot[2026].sum():,.2f}"
    totales['Var % (26 vs 25)'] = f"{calcular_variacion(pivot[2026].sum(), pivot[2025].sum()):+.2f}%"

    df_tot = pd.DataFrame([totales])
    res_completo = pd.concat([res_df, df_tot], ignore_index=True)

    cols_ind = [c for c in res_completo.columns if 'Var %' in c]
    styler = res_completo.style.map(resaltar_variaciones, subset=cols_ind)
    
    st.subheader(f"🏷️ {titulo}")
    st.dataframe(
        styler,
        use_container_width=True,
        hide_index=True,
        height=(len(res_completo) + 1) * 35 + 5
    )

# ---------------------------------------------------------
# 4. Generador de PDF Completo
# ---------------------------------------------------------
def construir_datos_tabla_mensual_pdf(df_filtrado):
    pivot_base = pd.pivot_table(
        df_filtrado,
        index=['MES_NUM', 'MES_NOMBRE'],
        columns='ANIO',
        values='VENTA_NETA',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    for a in [2024, 2025, 2026]:
        if a not in pivot_base.columns:
            pivot_base[a] = 0.0

    pivot_base = pivot_base.sort_values('MES_NUM').drop(columns=['MES_NUM'])
    pivot_base.rename(columns={'MES_NOMBRE': 'Mes'}, inplace=True)

    fila_totales = {'Mes': 'TOTAL GENERAL', 2024: pivot_base[2024].sum(), 2025: pivot_base[2025].sum(), 2026: pivot_base[2026].sum()}
    pivot_completa = pd.concat([pivot_base, pd.DataFrame([fila_totales])], ignore_index=True)

    headers_pdf = ['Mes', '2024', '2025', 'Var % (25/24)', '2026', 'Var % (26/25)']
    data_pdf = [headers_pdf]
    
    for _, row in pivot_completa.iterrows():
        v25_24 = calcular_variacion(row[2025], row[2024])
        v26_25 = calcular_variacion(row[2026], row[2025])
        
        fila_vals = [
            str(row['Mes']),
            f"{row[2024]:,.2f}",
            f"{row[2025]:,.2f}",
            f"{v25_24:+.1f}%",
            f"{row[2026]:,.2f}",
            f"{v26_25:+.1f}%"
        ]
        data_pdf.append(fila_vals)
        
    return data_pdf

def generar_pdf_reporte_completo(df_analisis, seleccion_actual, fig_plotly):
    if not REPORTLAB_DISPONIBLE:
        return None
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=15, leftMargin=15, topMargin=20, bottomMargin=20
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=13,
        textColor=colors.HexColor("#2f5597"),
        spaceAfter=4
    )
    style_subtitle = ParagraphStyle(
        'SubTitleStyle',
        parent=styles['Heading2'],
        fontSize=10,
        textColor=colors.HexColor("#333333"),
        spaceAfter=4,
        spaceBefore=6,
        keepWithNext=True
    )

    story.append(Paragraph(f"<b>Informe Ejecutivo Sedisur BI - {seleccion_actual}</b>", style_title))
    story.append(Paragraph(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    
    clientes_unicos = df_analisis['CLIENTE'].unique()
    if len(clientes_unicos) == 1:
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Cliente:</b> {df_analisis['ALIAS'].iloc[0]} | <b>Razón Social:</b> {df_analisis['NOMBRE'].iloc[0]} | <b>Código:</b> {df_analisis['CLIENTE'].iloc[0]}", styles['Normal']))

    vendedores_unicos = df_analisis['VENDEDOR'].unique()
    if len(vendedores_unicos) == 1 and pd.notna(vendedores_unicos[0]):
        story.append(Paragraph(f"<b>Vendedor:</b> {vendedores_unicos[0]}", styles['Normal']))

    story.append(Spacer(1, 8))

    proveedores_principales = ['COLGATE_PALM', 'ESSITY', 'HEINZ.CR', 'ALIMER S.A.', 'PEPSICO']

    titulo_gen = Paragraph("<b>Tabla Comparativa por Mes y Variaciones (2024 - 2025 - 2026) - Consolidado General</b>", style_subtitle)
    data_gen = construir_datos_tabla_mensual_pdf(df_analisis)
    t_gen = Table(data_gen, colWidths=[65, 75, 75, 75, 75, 75])
    t_gen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4a90e2")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 6.5),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#e2efda")),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,1), (-1,-1), 6.5),
    ]))
    story.append(KeepTogether([titulo_gen, t_gen]))
    story.append(Spacer(1, 8))

    for prov_esp in proveedores_principales:
        df_prov_esp = df_analisis[df_analisis['CLASIFICACION_1'].str.strip() == prov_esp]
        if not df_prov_esp.empty:
            titulo_esp = Paragraph(f"<b>Tabla Comparativa por Mes y Variaciones (2024 - 2025 - 2026) - Proveedor: {prov_esp}</b>", style_subtitle)
            data_esp = construir_datos_tabla_mensual_pdf(df_prov_esp)
            t_esp = Table(data_esp, colWidths=[65, 75, 75, 75, 75, 75])
            t_esp.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#5b9bd5")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 6.5),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#f2f2f2")),
                ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('FONTSIZE', (0,1), (-1,-1), 6.5),
            ]))
            story.append(KeepTogether([titulo_esp, t_esp]))
            story.append(Spacer(1, 8))

    try:
        img_bytes = fig_plotly.to_image(format="png", width=650, height=240, scale=2)
        img_io = io.BytesIO(img_bytes)
        titulo_img = Paragraph("<b>Tendencia Evolutiva Mensual</b>", style_subtitle)
        story.append(KeepTogether([titulo_img, RLImage(img_io, width=420, height=155)]))
        story.append(Spacer(1, 8))
    except Exception:
        pass

    doc.build(story)
    buffer.seek(0)
    return buffer

def mostrar_vista_comparativa(df: pd.DataFrame):
    col_top_title, col_top_pdf = st.columns([6, 1])
    with col_top_title:
        st.header("📈 Comparativa de Ventas Año contra Año")

    if df.empty:
        st.warning("No hay datos disponibles con los filtros seleccionados.")
        return

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

    seleccion_actual = lista_vistas[st.session_state["indice_vista_prov"]]
    if seleccion_actual != "📊 Consolidado General (Sedisur)":
        proveedor_seleccionado = seleccion_actual.replace("Proveedor: ", "").strip()
        df_analisis = df[df['CLASIFICACION_1'].str.strip() == proveedor_seleccionado]
    else:
        df_analisis = df

    df_agrupado = df_analisis.groupby(['ANIO', 'MES_NUM', 'MES_NOMBRE'], as_index=False).agg({
        'VENTA_NETA': 'sum',
        'CANTIDAD_NETA': 'sum'
    }).sort_values('MES_NUM')
    df_agrupado['ANIO_STR'] = df_agrupado['ANIO'].astype(str)

    fig = px.line(
        df_agrupado,
        x='MES_NOMBRE',
        y='VENTA_NETA',
        color='ANIO_STR',
        markers=True,
        title=f"Evolución Mensual Comparativa ({seleccion_actual})",
        labels={'MES_NOMBRE': 'Mes', 'VENTA_NETA': 'Venta Neta', 'ANIO_STR': 'Año'},
        category_orders={'MES_NOMBRE': ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']}
    )
    fig.update_traces(hovertemplate="<b>%{x}</b><br>Métrica: %{y:,.2f}<extra></extra>")
    fig.update_layout(height=450, hovermode="x unified")

    pdf_buffer_global = None
    if REPORTLAB_DISPONIBLE:
        pdf_buffer_global = generar_pdf_reporte_completo(df_analisis, seleccion_actual, fig)

    col_info, col_btn_izq, col_btn_sedisur, col_btn_der = st.columns([3.5, 1.1, 1.1, 1.1])

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

    with col_info:
        st.markdown(f"### 🏷️ Analizando: **{seleccion_actual}**")

    st.divider()

    pivot_base = pd.pivot_table(
        df_analisis,
        index=['MES_NUM', 'MES_NOMBRE'],
        columns='ANIO',
        values='VENTA_NETA',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    for a in [2024, 2025, 2026]:
        if a not in pivot_base.columns:
            pivot_base[a] = 0.0

    pivot_base = pivot_base.sort_values('MES_NUM').drop(columns=['MES_NUM'])
    pivot_base.rename(columns={'MES_NOMBRE': 'Mes'}, inplace=True)

    fila_totales = {'Mes': 'TOTAL GENERAL', 2024: pivot_base[2024].sum(), 2025: pivot_base[2025].sum(), 2026: pivot_base[2026].sum()}
    pivot_completa = pd.concat([pivot_base, pd.DataFrame([fila_totales])], ignore_index=True)

    df_resultado = pd.DataFrame()
    df_resultado['Mes'] = pivot_completa['Mes']
    df_resultado['2024'] = pivot_completa[2024].apply(lambda x: f"{x:,.2f}")
    df_resultado['2025'] = pivot_completa[2025].apply(lambda x: f"{x:,.2f}")

    var_25_24 = [calcular_variacion(act, ant) for act, ant in zip(pivot_completa[2025], pivot_completa[2024])]
    df_resultado['Var % (25 vs 24)'] = [f"{v:+.2f}%" if v != 0 else "0.00%" for v in var_25_24]

    df_resultado['2026'] = pivot_completa[2026].apply(lambda x: f"{x:,.2f}")

    var_26_25 = [calcular_variacion(act, ant) for act, ant in zip(pivot_completa[2026], pivot_completa[2025])]
    df_resultado['Var % (26 vs 25)'] = [f"{v:+.2f}%" if v != 0 else "0.00%" for v in var_26_25]

    columnas_variacion = ['Var % (25 vs 24)', 'Var % (26 vs 25)']
    styler = df_resultado.style.map(resaltar_variaciones, subset=columnas_variacion)
    
    st.dataframe(
        styler, 
        use_container_width=True, 
        hide_index=True,
        height=(len(df_resultado) + 1) * 35 + 3
    )

    st.divider()
    st.subheader("📉 Tendencia Evolutiva Mensual")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.header("🏢 Comparativa por Proveedores y Categorías")
    generar_tabla_comparativa_formateada(df_analisis, 'CLASIFICACION_1', f'Resumen ({seleccion_actual})')

    return pdf_buffer_global

# ---------------------------------------------------------
# 6. Vista Cobertura 8020 (Con Promedio Mensual en Colones ₡)
# ---------------------------------------------------------
def mostrar_vista_cobertura_8020(df_raw: pd.DataFrame, filtro_a, filtros_b: list, df_filtrado: pd.DataFrame):
    st.header("🎯 Análisis de Cobertura 80/20 y Oportunidades de Alcance")
    st.markdown("Utiliza el panel superior para configurar el **Filtro A** y múltiples marcas en el **Filtro B** para evaluar la cobertura y brechas.")

    if not filtro_a:
        st.info("👆 Por favor, seleccione una opción en el **Filtro A (Referencia 80/20)** en el panel superior para calcular el Pareto.")
        return

    if df_filtrado.empty:
        st.warning("No hay datos disponibles con los filtros seleccionados en el panel.")
        return

    if filtro_a == "TODOS (Consolidado Sedisur)":
        df_ref_a = df_filtrado.copy()
    else:
        df_ref_a = df_filtrado[df_filtrado['CLASIFICACION_1'] == filtro_a]

    if df_ref_a.empty:
        st.warning("No se encontraron registros para la referencia seleccionada en el Filtro A con los filtros actuales.")
        return

    df_mensual_cliente = df_ref_a.groupby(['CLIENTE', 'ALIAS', 'CATEGORIA_CLIENTE', 'ANIO', 'MES_NUM'], as_index=False).agg(
        VENTA_MES=('VENTA_NETA', 'sum')
    )

    df_clientes = df_mensual_cliente.groupby(['CLIENTE', 'ALIAS', 'CATEGORIA_CLIENTE'], as_index=False).agg(
        VENTA_TOTAL_A=('VENTA_MES', 'sum'),
        VENTA_PROMEDIO_A=('VENTA_MES', 'mean')
    ).sort_values(by='VENTA_PROMEDIO_A', ascending=False)

    if df_clientes.empty:
        return

    venta_total_promedio_acumulada = df_clientes['VENTA_PROMEDIO_A'].sum()
    if venta_total_promedio_acumulada > 0:
        df_clientes['PORCENTAJE_INDIVIDUAL'] = (df_clientes['VENTA_PROMEDIO_A'] / venta_total_promedio_acumulada) * 100
        df_clientes['PORCENTAJE_ACUMULADO'] = df_clientes['PORCENTAJE_INDIVIDUAL'].cumsum()
    else:
        df_clientes['PORCENTAJE_INDIVIDUAL'] = 0.0
        df_clientes['PORCENTAJE_ACUMULADO'] = 0.0

    df_tabla_final = pd.DataFrame()
    df_tabla_final['CLIENTE'] = df_clientes['CLIENTE']
    df_tabla_final['Cód. Cliente'] = df_clientes['CLIENTE']
    df_tabla_final['Alias'] = df_clientes['ALIAS']
    df_tabla_final['Categoría Cliente'] = df_clientes['CATEGORIA_CLIENTE']
    df_tabla_final['Venta Promedio Mensual (Filtro A)'] = df_clientes['VENTA_PROMEDIO_A'].apply(lambda x: f"₡{x:,.2f}")
    df_tabla_final['% Individual'] = df_clientes['PORCENTAJE_INDIVIDUAL'].apply(lambda x: f"{x:.2f}%")
    df_tabla_final['Cobertura Filtro A'] = "✅"

    if filtros_b:
        for prov_b in filtros_b:
            df_ref_b = df_filtrado[df_filtrado['CLASIFICACION_1'] == prov_b]
            df_clientes_b = df_ref_b.groupby('CLIENTE', as_index=False).agg(
                VENTA_TOTAL_B=('VENTA_NETA', 'sum')
            )

            df_tabla_final = df_tabla_final.merge(df_clientes_b, on='CLIENTE', how='left')
            df_tabla_final['VENTA_TOTAL_B'] = df_tabla_final['VENTA_TOTAL_B'].fillna(0)
            
            nombre_col_colocacion = f"Colocación: {prov_b}"
            df_tabla_final[nombre_col_colocacion] = df_tabla_final['VENTA_TOTAL_B'].apply(lambda x: "✅" if x > 0 else "❌")
            df_tabla_final = df_tabla_final.drop(columns=['VENTA_TOTAL_B'])

    df_mostrar = df_tabla_final.drop(columns=['CLIENTE'])

    titulo_b_str = f" vs ({', '.join(filtros_b)})" if filtros_b else ""
    st.subheader(f"📊 Matriz de Cobertura para: {filtro_a}{titulo_b_str}")
    st.dataframe(df_mostrar, use_container_width=True, hide_index=True)


# ---------------------------------------------------------
# 7. Flujo Principal de Ejecución con Autenticación
# ---------------------------------------------------------
if verificar_acceso():
    with st.spinner("Cargando datos del reporte..."):
        df_raw = cargar_datos_exactus()

    if "vista_activa" not in st.session_state:
        st.session_state["vista_activa"] = "comparativa"

    with st.sidebar:
        st.markdown(f"👤 **Usuario:** {st.session_state.get('usuario_actual', '')}")
        st.markdown(f"💼 **Cargo:** {st.session_state.get('cargo_actual', '')}")
        st.markdown(f"🛡️ **Rol:** {st.session_state.get('rol_actual', '')}")
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

    if st.session_state["vista_activa"] == "comparativa":
        with st.expander("🔍 **Panel de Filtros Comerciales (Comparativa)**", expanded=True):
            col_btn1, col_btn_desc, col_space = st.columns([1.2, 1.2, 4.6])
            with col_btn1:
                if st.button("🔄 Recargar Datos", help="Limpia la caché y vuelve a leer el archivo de datos", use_container_width=True, key="btn_recargar_comp"):
                    cargar_datos_exactus.clear()
                    st.toast("¡Datos recargados correctamente!", icon="✅")
                    st.rerun()

            st.markdown("---")

            col1, col2, col3 = st.columns(3)
            
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

                vendedores = sorted(df_raw['VENDEDOR'].dropna().unique())
                sel_vendedores = st.multiselect("Vendedor", vendedores, key="filtro_vendedores")

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

        pdf_buffer_generado = mostrar_vista_comparativa(df_filt)

        with col_btn_desc:
            if REPORTLAB_DISPONIBLE and pdf_buffer_generado:
                st.download_button(
                    label="📥 Descargar PDF",
                    data=pdf_buffer_generado,
                    file_name="Informe_Sedisur_Ejecutivo.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    help="Descargar informe PDF completo con tablas y gráficos"
                )

    elif st.session_state["vista_activa"] == "cobertura":
        with st.expander("🔍 **Panel de Filtros Comerciales (Cobertura 80/20)**", expanded=True):
            col_btn1, col_space = st.columns([1.2, 5.8])
            with col_btn1:
                if st.button("🔄 Recargar Datos", help="Limpia la caché y vuelve a leer el archivo de datos", use_container_width=True, key="btn_recargar_cob"):
                    cargar_datos_exactus.clear()
                    st.toast("¡Datos recargados correctamente!", icon="✅")
                    st.rerun()

            st.markdown("---")

            marcas_disponibles = sorted(df_raw['CLASIFICACION_1'].dropna().unique())
            opciones_filtro_a = ["TODOS (Consolidado Sedisur)"] + list(marcas_disponibles)

            col1, col2, col3 = st.columns(3)
            
            with col1:
                anios_disponibles = sorted(df_raw['ANIO'].unique(), reverse=True)
                sel_anios_cob = st.multiselect("Año", anios_disponibles, key="filtro_anios_cob")
                
                meses_disponibles = [m for m in ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                                                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'] if m in df_raw['MES_NOMBRE'].unique()]
                sel_meses_cob = st.multiselect("Mes", meses_disponibles, key="filtro_meses_cob")

            with col2:
                filtro_a = st.selectbox("📌 Filtro A (Referencia 80/20)", options=opciones_filtro_a, key="filtro_a_cob")
                
                categorias = sorted(df_raw['CATEGORIA_CLIENTE'].dropna().unique())
                sel_cats_cob = st.multiselect("Categoría Cliente", categorias, key="filtro_cats_cob")

            with col3:
                filtros_b = st.multiselect("🔍 Filtro B (Comparativo de Colocación)", options=marcas_disponibles, key="filtro_b_cob")

                vendedores = sorted(df_raw['VENDEDOR'].dropna().unique())
                sel_vendedores_cob = st.multiselect("Vendedor", vendedores, key="filtro_vendedores_cob")

        df_filt_cob = df_raw.copy()
        if sel_anios_cob:
            df_filt_cob = df_filt_cob[df_filt_cob['ANIO'].isin(sel_anios_cob)]
        if sel_meses_cob:
            df_filt_cob = df_filt_cob[df_filt_cob['MES_NOMBRE'].isin(sel_meses_cob)]
        if sel_cats_cob:
            df_filt_cob = df_filt_cob[df_filt_cob['CATEGORIA_CLIENTE'].isin(sel_cats_cob)]
        if sel_vendedores_cob:
            df_filt_cob = df_filt_cob[df_filt_cob['VENDEDOR'].isin(sel_vendedores_cob)]

        mostrar_vista_cobertura_8020(df_raw, filtro_a, filtros_b, df_filt_cob)
