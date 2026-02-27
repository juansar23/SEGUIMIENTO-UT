import streamlit as st
import pandas as pd
import io
from datetime import datetime

# Configuración de la página
st.set_page_config(page_title="Sistema de Gestión UT", layout="wide")

# ==================================================
# 1. PERSISTENCIA DE DATOS (Session State)
# ==================================================
if 'db_materiales_operarios' not in st.session_state:
    # Movimientos: INICIAL, BODEGA (Suma) y ACTA (Resta)
    st.session_state.db_materiales_operarios = pd.DataFrame(
        columns=["Fecha", "Tipo_Movimiento", "Operario", "Material", "Cantidad", "Referencia/Acta"]
    )

if 'db_materiales_bodega' not in st.session_state:
    st.session_state.db_materiales_bodega = pd.DataFrame(columns=["Fecha", "Material", "Cantidad", "Origen"])

if 'db_herramientas_operarios' not in st.session_state:
    st.session_state.db_herramientas_operarios = pd.DataFrame(columns=["Fecha", "Operario", "Herramienta", "Cantidad", "ID_Serie"])

# Catálogos
if 'cat_materiales' not in st.session_state: st.session_state.cat_materiales = []
if 'cat_herramientas' not in st.session_state: st.session_state.cat_herramientas = []
if 'cat_operarios' not in st.session_state: st.session_state.cat_operarios = []

# ==================================================
# 2. FUNCIONES DE CÁLCULO
# ==================================================
def convertir_a_csv(df):
    return df.to_csv(index=False).encode('utf-8')

def obtener_stock_real_operarios():
    if st.session_state.db_materiales_operarios.empty:
        return pd.DataFrame(columns=["Operario", "Material", "Stock Actual"])
    
    df = st.session_state.db_materiales_operarios.copy()
    # Los movimientos tipo ACTA restan, los demás suman
    df['Cantidad_Neta'] = df.apply(lambda x: -x['Cantidad'] if x['Tipo_Movimiento'] == "ACTA" else x['Cantidad'], axis=1)
    
    resumen = df.groupby(["Operario", "Material"])["Cantidad_Neta"].sum().reset_index()
    resumen.rename(columns={"Cantidad_Neta": "Stock Actual"}, inplace=True)
    return resumen

# ==================================================
# 3. BARRA LATERAL (CONFIGURACIÓN)
# ==================================================
with st.sidebar:
    st.header("⚙️ Configuración")
    
    op_input = st.text_input("Añadir Operario")
    if st.button("Registrar Operario") and op_input:
        nombre = op_input.strip().upper()
        if nombre not in st.session_state.cat_operarios:
            st.session_state.cat_operarios.append(nombre)
            st.rerun()

    mat_input = st.text_input("Añadir Material")
    if st.button("Registrar Material") and mat_input:
        nombre = mat_input.strip().upper()
        if nombre not in st.session_state.cat_materiales:
            st.session_state.cat_materiales.append(nombre)
            st.rerun()

    herr_input = st.text_input("Añadir Herramienta")
    if st.button("Registrar Herramienta") and herr_input:
        nombre = herr_input.strip().upper()
        if nombre not in st.session_state.cat_herramientas:
            st.session_state.cat_herramientas.append(nombre)
            st.rerun()

    st.divider()
    if st.button("🚨 Reiniciar Sistema"):
        st.session_state.clear()
        st.rerun()

# ==================================================
# 4. CUERPO PRINCIPAL
# ==================================================
st.title("🛡️ Control de Inventario y Actas de Operarios")

tab_resumen, tab_inicial, tab_actas, tab_bodega, tab_herr = st.tabs([
    "📊 Resumen de Stock", 
    "📥 Carga Inicial", 
    "📄 Consumo (Actas)", 
    "🏢 Bodega", 
    "🛠️ Herramientas"
])

# --- TAB: RESUMEN (STOCK ACTUAL EN CALLE) ---
with tab_resumen:
    st.subheader("Estado Actual de Materiales por Operario")
    df_resumen = obtener_stock_real_operarios()
    if not df_resumen.empty:
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)
        st.download_button("📥 Descargar Inventario Calle (CSV)", convertir_a_csv(df_resumen), "stock_operarios.csv")
    else:
        st.info("No hay materiales asignados.")

# --- TAB: CARGA INICIAL ---
with tab_inicial:
    st.subheader("Registrar Inventario Inicial del Operario")
    with st.form("form_inicial", clear_on_submit=True):
        col1, col2 = st.columns(2)
        op_i = col1.selectbox("Operario", st.session_state.cat_operarios, key="op_i")
        mat_i = col1.selectbox("Material", st.session_state.cat_materiales, key="mat_i")
        cant_i = col2.number_input("Cantidad Inicial", min_value=1, step=1)
        ref_i = col2.text_input("Referencia (Opcional)", "Inventario Inicial")
        
        if st.form_submit_button("Cargar Stock Inicial"):
            nueva_fila = pd.DataFrame([[datetime.now().date(), "INICIAL", op_i, mat_i, cant_i, ref_i]], 
                                     columns=st.session_state.db_materiales_operarios.columns)
            st.session_state.db_materiales_operarios = pd.concat([st.session_state.db_materiales_operarios, nueva_fila], ignore_index=True)
            st.success("Cargado con éxito")
            st.rerun()

# --- TAB: ACTAS (RESTAR MATERIAL) ---
with tab_actas:
    st.subheader("📄 Registro de Consumo por Acta")
    st.write("Utilice esta sección para restar el material que el operario ya instaló o utilizó.")
    
    df_val = obtener_stock_real_operarios()
    
    with st.form("form_acta", clear_on_submit=True):
        c1, c2 = st.columns(2)
        op_a = c1.selectbox("Operario que reporta", st.session_state.cat_operarios)
        
        # Filtrar materiales que realmente tiene el operario
        mats_op = df_val[df_val["Operario"] == op_a]["Material"].unique()
        mat_a = c1.selectbox("Material utilizado", mats_op if len(mats_op)>0 else ["Sin stock"])
        
        # Mostrar cuánto tiene antes de restar
        if len(mats_op) > 0:
            actual = df_val[(df_val["Operario"] == op_a) & (df_val["Material"] == mat_a)]["Stock Actual"].values[0]
            c1.info(f"Stock actual del operario: {int(actual)}")
        
        cant_a = c2.number_input("Cantidad utilizada (A restar)", min_value=1, step=1)
        num_acta = c2.text_input("Número de Acta / Orden")
        
        if st.form_submit_button("🔥 Registrar Consumo (Restar)"):
            if len(mats_op) == 0:
                st.error("El operario no tiene materiales asignados.")
            elif cant_a > actual:
                st.error(f"Error: El operario solo tiene {int(actual)} unidades.")
            else:
                nueva_acta = pd.DataFrame([[datetime.now().date(), "ACTA", op_a, mat_a, cant_a, num_acta]], 
                                         columns=st.session_state.db_materiales_operarios.columns)
                st.session_state.db_materiales_operarios = pd.concat([st.session_state.db_materiales_operarios, nueva_acta], ignore_index=True)
                st.success(f"Se restaron {cant_a} unidades a {op_a} por el acta {num_acta}")
                st.rerun()

# --- TAB: BODEGA ---
with tab_bodega:
    st.subheader("Movimientos de Bodega Central")
    col_b1, col_b2 = st.columns(2)
    
    with col_b1:
        st.write("**Entrada a Bodega**")
        with st.form("b_ent"):
            m_b = st.selectbox("Material", st.session_state.cat_materiales)
            c_b = st.number_input("Cantidad", min_value=1)
            if st.form_submit_button("Ingresar"):
                st.session_state.db_materiales_bodega = pd.concat([st.session_state.db_materiales_bodega, 
                    pd.DataFrame([[datetime.now().date(), m_b, c_b, "Compra/Ingreso"]], columns=st.session_state.db_materiales_bodega.columns)], ignore_index=True)
                st.rerun()

    with col_b2:
        st.write("**Entrega Bodega -> Operario**")
        with st.form("b_sal"):
            op_d = st.selectbox("Operario Destino", st.session_state.cat_operarios)
            mat_d = st.selectbox("Material", st.session_state.cat_materiales)
            cant_d = st.number_input("Cantidad", min_value=1)
            if st.form_submit_button("Entregar"):
                # Sumar al operario
                nueva_ent = pd.DataFrame([[datetime.now().date(), "BODEGA", op_d, mat_d, cant_d, "Entrega Bodega"]], 
                                         columns=st.session_state.db_materiales_operarios.columns)
                st.session_state.db_materiales_operarios = pd.concat([st.session_state.db_materiales_operarios, nueva_ent], ignore_index=True)
                # Restar de bodega
                nueva_rest = pd.DataFrame([[datetime.now().date(), mat_d, -cant_d, f"Salida a {op_d}"]], 
                                          columns=st.session_state.db_materiales_bodega.columns)
                st.session_state.db_materiales_bodega = pd.concat([st.session_state.db_materiales_bodega, nueva_rest], ignore_index=True)
                st.success("Entrega registrada")
                st.rerun()

# --- TAB: HERRAMIENTAS ---
with tab_herr:
    st.subheader("Asignación de Herramientas")
    with st.form("f_herr"):
        op_h = st.selectbox("Operario", st.session_state.cat_operarios)
        her_h = st.selectbox("Herramienta", st.session_state.cat_herramientas)
        can_h = st.number_input("Cantidad", min_value=1, value=1)
        ser_h = st.text_input("Número de Serie")
        if st.form_submit_button("🛠️ Asignar Herramienta"):
            st.session_state.db_herramientas_operarios = pd.concat([st.session_state.db_herramientas_operarios, 
                pd.DataFrame([[datetime.now().date(), op_h, her_h, can_h, ser_h]], columns=st.session_state.db_herramientas_operarios.columns)], ignore_index=True)
            st.success("Asignada")
            st.rerun()
    
    st.dataframe(st.session_state.db_herramientas_operarios, use_container_width=True)
