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

# ---------------------------------------------------------
# 4. Generador de PDF Completo (A4, Márgenes Estrechos, Azul Claro)
# ---------------------------------------------------------
def construir_datos_tabla_pdf(df_sub, col_group, titulo_col):
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
        return None, None

    res_df = pd.DataFrame()
    res_df[titulo_col] = pivot[col_group]
    a1, a2 = anios[0], anios[1]
    res_df[str(a1)] = pivot[a1].apply(lambda x: f"₡{x:,.2f}")
    res_df[str(a2)] = pivot[a2].apply(lambda x: f"₡{x:,.2f}")
    vars_a = [calcular_variacion(act, ant) for act, ant in zip(pivot[a2], pivot[a1])]
    res_df['Var %'] = [f"{v:+.1f}%" for v in vars_a]

    totales = {titulo_col: 'TOTAL'}
    totales[str(a1)] = f"₡{pivot[a1].sum():,.2f}"
    totales[str(a2)] = f"₡{pivot[a2].sum():,.2f}"
    totales['Var %'] = f"{calcular_variacion(pivot[a2].sum(), pivot[a1].sum()):+.1f}%"

    df_tot = pd.DataFrame([totales])
    res_completo = pd.concat([res_df, df_tot], ignore_index=True)
    
    headers = list(res_completo.columns)
    data = [headers]
    for _, row in res_completo.iterrows():
        data.append([str(row[h]) for h in headers])
        
    return data, headers

def generar_pdf_reporte_completo(df_analisis, seleccion_actual, fig_plotly):
    if not REPORTLAB_DISPONIBLE:
        return None
    
    buffer = io.BytesIO()
    # A4 en horizontal (landscape) con márgenes estrechos (20 puntos ~ 0.7 cm)
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20
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
        spaceBefore=6
    )

    # Encabezado principal del reporte
    story.append(Paragraph(f"<b>Informe Ejecutivo Sedisur BI - {seleccion_actual}</b>", style_title))
    story.append(Paragraph(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    
    # Contexto de cliente o vendedor en la primera hoja si aplica
    clientes_unicos = df_analisis['CLIENTE'].unique()
    if len(clientes_unicos) == 1:
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Cliente:</b> {df_analisis['ALIAS'].iloc[0]} | <b>Razón Social:</b> {df_analisis['NOMBRE'].iloc[0]} | <b>Código:</b> {df_analisis['CLIENTE'].iloc[0]}", styles['Normal']))

    vendedores_unicos = df_analisis['VENDEDOR'].unique()
    if len(vendedores_unicos) == 1 and pd.notna(vendedores_unicos[0]):
        story.append(Paragraph(f"<b>Vendedor:</b> {vendedores_unicos[0]}", styles['Normal']))

    story.append(Spacer(1, 8))

    # 1. Tabla Principal Mensual (Total Sedisur o Proveedor analizado)
    story.append(Paragraph("<b>Tabla Comparativa por Mes y Variación Porcentual</b>", style_subtitle))
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

    if len(anios_presentes) >= 2:
        fila_totales = {'Mes': 'TOTAL GENERAL'}
        for anio in anios_presentes:
            fila_totales[anio] = pivot_base[anio].sum()
        
        pivot_completa = pd.concat([pivot_base, pd.DataFrame([fila_totales])], ignore_index=True)
        headers_pdf = ['Mes'] + [str(a) for a in anios_presentes]
        data_pdf = [headers_pdf]
        
        for _, row in pivot_completa.iterrows():
            fila_vals = [str(row['Mes'])]
            for anio in anios_presentes:
                fila_vals.append(f"₡{row[anio]:,.2f}")
            data_pdf.append(fila_vals)
            
        t = Table(data_pdf, colWidths=[65] + [90]*len(anios_presentes))
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4a90e2")), # Azul claro elegante
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 7),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#e2efda")),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTSIZE', (0,1), (-1,-1), 7),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

    # 2. Gráfico en Imagen (Tendencia Evolutiva Mensual)
    try:
        img_bytes = fig_plotly.to_image(format="png", width=650, height=240, scale=2)
        img_io = io.BytesIO(img_bytes)
        story.append(Paragraph("<b>Tendencia Evolutiva Mensual</b>", style_subtitle))
        story.append(RLImage(img_io, width=420, height=155))
        story.append(Spacer(1, 8))
    except Exception:
        pass

    # 3. Tablas Inferiores (Resumen y Proveedores)
    story.append(Paragraph("<b>Comparativa por Proveedores y Categorías</b>", style_subtitle))
    
    data_res, headers_res = construir_datos_tabla_pdf(df_analisis, 'CLASIFICACION_1', f'Resumen ({seleccion_actual})')
    if data_res:
        t_res = Table(data_res, colWidths=[160, 95, 95, 85])
        t_res.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4a90e2")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 7),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#e2efda")),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTSIZE', (0,1), (-1,-1), 7),
        ]))
        story.append(t_res)
        story.append(Spacer(1, 6))

    # Iterar proveedores secundarios
    orden_personalizado = [
        'COLGATE_PALM', 'ESSITY', 'PEPSICO', 'HEINZ.CR', 'ALIMER S.A.',
        'BAYER', 'RECKITT', 'BARRAZA', 'REYA CR.', 'HEALTH. RB.',
        'GRUPO Q.', 'BEL PREMIUM', 'CODOMI', 'FARMANOVA', 'MUNDOREP', 'PRONUTRE'
    ]
    proveedores_excluidos = ['AB-INBEV', 'BAYER', 'BEL PREMIUM', 'CODOMI', 'FARMANOVA', 'GRUPO Q.', 'HEALTH. RB.', 'HEALTH', 'REYA CR.', 'RECKITT']
    
    proveedores_disponibles_sub = df_analisis['CLASIFICACION_1'].dropna().unique()
    proveedores_a_mostrar = [p for p in orden_personalizado if p in proveedores_disponibles_sub]
    otros_proveedores_sub = sorted([p for p in proveedores_disponibles_sub if p not in orden_personalizado])
    proveedores_finales_sub = proveedores_a_mostrar + otros_proveedores_sub

    for prov in proveedores_finales_sub:
        prov_limpio = prov.strip()
        if prov_limpio not in proveedores_excluidos:
            df_prov = df_analisis[df_analisis['CLASIFICACION_1'].str.strip() == prov_limpio]
            if not df_prov.empty:
                data_prov, _ = construir_datos_tabla_pdf(df_prov, 'CLASIFICACION_2', f"Proveedor: {prov}")
                if data_prov:
                    t_p = Table(data_prov, colWidths=[160, 95, 95, 85])
                    t_p.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#5b9bd5")), # Azul claro secundario
                        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0,0), (-1,0), 6.5),
                        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#f2f2f2")),
                        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
                        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                        ('FONTSIZE', (0,1), (-1,-1), 6.5),
                    ]))
                    # Usamos KeepTogether para evitar que una tabla de proveedor se rompa a la mitad entre páginas
                    story.append(KeepTogether([Spacer(1, 4), t_p]))

    doc.build(story)
    buffer.seek(0)
    return buffer

def mostrar_vista_comparativa(df: pd.DataFrame):
    # --- BARRA SUPERIOR DISCRETA CON TÍTULO Y BOTÓN DE DESCARGA ---
    col_top_title, col_top_pdf = st.columns([6, 1])
    with col_top_title:
        st.header("📈 Comparativa de Ventas Año contra Año")

    if df.empty:
        st.warning("No hay datos disponibles con los filtros seleccionados.")
        return

    # --- ORDEN PERSONALIZADO DE PROVEEDORES ---
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

    # --- FILTRAR DATOS SEGÚN LA SELECCIÓN DE LOS BOTONES ---
    seleccion_actual = lista_vistas[st.session_state["indice_vista_prov"]]
    if seleccion_actual != "📊 Consolidado General (Sedisur)":
        proveedor_seleccionado = seleccion_actual.replace("Proveedor: ", "").strip()
        df_analisis = df[df['CLASIFICACION_1'].str.strip() == proveedor_seleccionado]
    else:
        df_analisis = df

    # Generar gráfico preliminar para la vista y el PDF
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
        labels={'MES_NOMBRE': 'Mes', 'VENTA_NETA': 'Venta Neta (₡)', 'ANIO_STR': 'Año'},
        category_orders={'MES_NOMBRE': ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']}
    )
    fig.update_traces(hovertemplate="<b>%{x}</b><br>Métrica: ₡%{y:,.2f}<extra></extra>")
    fig.update_layout(height=450, hovermode="x unified")

    with col_top_pdf:
        if REPORTLAB_DISPONIBLE:
            pdf_buffer = generar_pdf_reporte_completo(df_analisis, seleccion_actual, fig)
            if pdf_buffer:
                st.download_button(
                    label="📥 Descargar",
                    data=pdf_buffer,
                    file_name=f"Informe_Sedisur_{seleccion_actual.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    help="Descargar informe PDF completo con tablas y gráficos"
                )
        else:
            st.caption("Instale `reportlab`.")

    # --- BARRA DE CONTROL CON TRES BOTONES (ANTERIOR, SEDISUR, SIGUIENTE) ---
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
    st.subheader("📉 Tendencia Evolutiva Mensual")
    st.plotly_chart(fig, use_container_width=True)

    # --- RESTAURACIÓN DE LAS TABLAS INFERIORES ---
    st.divider()
    st.header("🏢 Comparativa por Proveedores y Categorías")

    generar_tabla_comparativa_formateada(df_analisis, 'CLASIFICACION_1', f'Resumen ({seleccion_actual})')

    st.markdown("---")

    proveedores_excluidos = [
        'AB-INBEV', 'BAYER', 'BEL PREMIUM', 'CODOMI',  
        'FARMANOVA', 'GRUPO Q.', 'HEALTH. RB.', 'HEALTH',  
        'REYA CR.', 'RECKITT'
    ]

    proveedores_disponibles_sub = df_analisis['CLASIFICACION_1'].dropna().unique()
    proveedores_a_mostrar = [p for p in lista_proveedores_final if p in proveedores_disponibles_sub]
    otros_proveedores_sub = sorted([p for p in proveedores_disponibles_sub if p not in lista_proveedores_final])
    proveedores_finales_sub = proveedores_a_mostrar + otros_proveedores_sub

    for prov in proveedores_finales_sub:
        prov_limpio = prov.strip()
        if prov_limpio not in proveedores_excluidos:
            df_prov = df_analisis[df_analisis['CLASIFICACION_1'].str.strip() == prov_limpio]
            if not df_prov.empty:
                generar_tabla_comparativa_formateada(df_prov, 'CLASIFICACION_2', f"Proveedor: {prov}")

# ---------------------------------------------------------
# 5. Flujo Principal de Ejecución de la App Web
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

# Invocación de la Vista Comparativa Completa
mostrar_vista_comparativa(df_filt)
