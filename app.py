import io
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

# ============================================================
# FINANSMART - Prototipo académico de proyección de flujo de caja
# Empresa ficticia: Andina Distribuciones S.R.L. (Argentina)
# ============================================================

st.set_page_config(
    page_title="FinanSmart | Gestión de liquidez",
    page_icon="💰",
    layout="wide",
)

st.title("💰 FinanSmart")
st.caption("Proyección de flujo de caja, alertas de liquidez y simulación de escenarios")
st.info(
    "Prototipo académico con datos ficticios. No constituye asesoramiento financiero, "
    "contable ni tributario. Verificá los datos antes de usarlo en una empresa real."
)

TODAY = date.today()

@st.cache_data
def demo_movements(today: date) -> pd.DataFrame:
    """Genera movimientos ficticios con fechas relativas a la fecha actual."""
    rows = [
        # Fecha relativa, concepto, tipo, importe, estado, categoría, tercero
        (0, "Saldo inicial de caja y bancos", "Saldo inicial", 2_000_000, "Confirmado", "Caja/Bancos", "Andina Distribuciones"),
        (2, "Venta mostrador", "Cobro", 320_000, "Confirmado", "Ventas", "Clientes varios"),
        (4, "Factura cliente A", "Cobro", 1_250_000, "Pendiente", "Ventas", "Comercial Norte"),
        (5, "Compra de mercadería", "Pago", 1_500_000, "Pendiente", "Proveedores", "Mayorista Cuyo"),
        (7, "Alquiler del depósito", "Pago", 420_000, "Pendiente", "Alquileres", "Inmobiliaria Centro"),
        (9, "Sueldos", "Pago", 800_000, "Pendiente", "Sueldos", "Personal"),
        (12, "Factura cliente B", "Cobro", 980_000, "Pendiente", "Ventas", "Mercado Sur"),
        (14, "Servicios e internet", "Pago", 115_000, "Pendiente", "Servicios", "Proveedores varios"),
        (17, "Pago de impuestos", "Pago", 360_000, "Pendiente", "Impuestos", "Organismos fiscales"),
        (20, "Factura cliente C", "Cobro", 760_000, "Pendiente", "Ventas", "Almacenes del Oeste"),
        (22, "Compra de mercadería", "Pago", 690_000, "Pendiente", "Proveedores", "Mayorista Cuyo"),
        (26, "Cuota de préstamo", "Pago", 240_000, "Pendiente", "Financiación", "Banco ficticio"),
        (30, "Factura cliente D", "Cobro", 1_100_000, "Pendiente", "Ventas", "Distribuidora Sol"),
        (32, "Reposición de mercadería", "Pago", 880_000, "Pendiente", "Proveedores", "Mayorista Cuyo"),
        (38, "Sueldos", "Pago", 800_000, "Pendiente", "Sueldos", "Personal"),
        (42, "Factura cliente A - segunda", "Cobro", 950_000, "Pendiente", "Ventas", "Comercial Norte"),
        (45, "Servicios y mantenimiento", "Pago", 190_000, "Pendiente", "Servicios", "Servicios técnicos"),
        (50, "Pago de impuestos", "Pago", 360_000, "Pendiente", "Impuestos", "Organismos fiscales"),
        (55, "Factura cliente B - segunda", "Cobro", 1_200_000, "Pendiente", "Ventas", "Mercado Sur"),
        (60, "Compra de mercadería", "Pago", 1_050_000, "Pendiente", "Proveedores", "Mayorista Cuyo"),
        (68, "Cobro por venta mayorista", "Cobro", 1_450_000, "Pendiente", "Ventas", "Cliente mayorista"),
        (72, "Sueldos", "Pago", 800_000, "Pendiente", "Sueldos", "Personal"),
        (80, "Pago de impuestos", "Pago", 360_000, "Pendiente", "Impuestos", "Organismos fiscales"),
        (88, "Cobro por venta mayorista", "Cobro", 1_300_000, "Pendiente", "Ventas", "Cliente mayorista"),
    ]
    data = []
    for offset, concepto, tipo, importe, estado, categoria, tercero in rows:
        data.append({
            "Fecha": today + timedelta(days=offset),
            "Concepto": concepto,
            "Tipo": tipo,
            "Importe": float(importe),
            "Estado": estado,
            "Categoría": categoria,
            "Cliente/proveedor": tercero,
        })
    return pd.DataFrame(data)


def money(value):
    return f"${value:,.0f}".replace(",", ".")


def normalise_movements(df: pd.DataFrame) -> pd.DataFrame:
    required = ["Fecha", "Concepto", "Tipo", "Importe", "Estado", "Categoría", "Cliente/proveedor"]
    for col in required:
        if col not in df.columns:
            df[col] = ""
    df = df[required].copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date
    df["Importe"] = pd.to_numeric(df["Importe"], errors="coerce").fillna(0.0).abs()
    df["Tipo"] = df["Tipo"].astype(str)
    df["Estado"] = df["Estado"].astype(str)
    df["Concepto"] = df["Concepto"].astype(str)
    df["Categoría"] = df["Categoría"].astype(str)
    df["Cliente/proveedor"] = df["Cliente/proveedor"].astype(str)
    df = df[df["Fecha"].notna()]
    df = df[df["Tipo"].isin(["Saldo inicial", "Cobro", "Pago"])]
    df = df[df["Estado"].isin(["Confirmado", "Pendiente"])]
    return df.sort_values(["Fecha", "Tipo", "Concepto"]).reset_index(drop=True)


def simulate(df, start_date, horizon, initial_balance, minimum_cash,
             delay_collections, collection_reduction, payment_increase,
             delay_payments, one_off_inflow, one_off_outflow):
    end_date = start_date + timedelta(days=horizon - 1)
    work = df.copy()
    work = work[work["Tipo"].isin(["Cobro", "Pago"])].copy()
    work = work[(work["Fecha"] >= start_date) & (work["Fecha"] <= end_date)].copy()

    # Se consideran tanto movimientos confirmados como pendientes para construir el plan.
    # El usuario puede filtrar o cambiar el estado en la tabla.
    adjusted_dates = []
    adjusted_amounts = []
    for _, row in work.iterrows():
        kind = row["Tipo"]
        movement_date = row["Fecha"]
        amount = float(row["Importe"])
        if kind == "Cobro":
            movement_date = movement_date + timedelta(days=int(delay_collections))
            amount *= (1 - collection_reduction / 100)
        elif kind == "Pago":
            movement_date = movement_date + timedelta(days=int(delay_payments))
            amount *= (1 + payment_increase / 100)
        adjusted_dates.append(movement_date)
        adjusted_amounts.append(amount)
    work["Fecha ajustada"] = adjusted_dates
    work["Importe ajustado"] = adjusted_amounts
    work = work[(work["Fecha ajustada"] >= start_date) & (work["Fecha ajustada"] <= end_date)]

    calendar = pd.DataFrame({"Fecha": [start_date + timedelta(days=i) for i in range(horizon)]})
    calendar["Cobros"] = 0.0
    calendar["Pagos"] = 0.0
    for _, row in work.iterrows():
        idx = row["Fecha ajustada"]
        if row["Tipo"] == "Cobro":
            calendar.loc[calendar["Fecha"] == idx, "Cobros"] += row["Importe ajustado"]
        else:
            calendar.loc[calendar["Fecha"] == idx, "Pagos"] += row["Importe ajustado"]

    # Movimientos extraordinarios del escenario, ubicados en el primer día.
    calendar.loc[calendar.index == 0, "Cobros"] += float(one_off_inflow)
    calendar.loc[calendar.index == 0, "Pagos"] += float(one_off_outflow)
    calendar["Flujo neto"] = calendar["Cobros"] - calendar["Pagos"]
    balance = float(initial_balance)
    balances = []
    for net in calendar["Flujo neto"]:
        balance += float(net)
        balances.append(balance)
    calendar["Saldo proyectado"] = balances
    calendar["Saldo mínimo requerido"] = float(minimum_cash)
    calendar["Estado de liquidez"] = calendar["Saldo proyectado"].apply(
        lambda x: "Riesgo" if x < minimum_cash else "Adecuado"
    )
    return calendar, work


def to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")


with st.sidebar:
    st.header("⚙️ Configuración")
    st.write("Empresa ficticia")
    company = st.text_input("Nombre de la empresa", "Andina Distribuciones S.R.L.")
    start_date = st.date_input("Inicio de la proyección", TODAY)
    horizon = st.selectbox("Horizonte de proyección", [30, 60, 90], index=2)
    initial_balance = st.number_input("Saldo inicial disponible ($)", min_value=0.0, value=2_000_000.0, step=100_000.0)
    minimum_cash = st.number_input("Saldo mínimo de seguridad ($)", min_value=0.0, value=500_000.0, step=50_000.0)
    st.divider()
    st.subheader("🧪 Simulación de escenarios")
    delay_collections = st.slider("Demora adicional de cobros (días)", 0, 60, 0, 1)
    collection_reduction = st.slider("Reducción de cobros previstos (%)", 0, 100, 0, 5)
    payment_increase = st.slider("Aumento de pagos previstos (%)", 0, 100, 0, 5)
    delay_payments = st.slider("Reprogramación de pagos (días)", 0, 30, 0, 1)
    one_off_inflow = st.number_input("Cobro extraordinario al inicio ($)", min_value=0.0, value=0.0, step=50_000.0)
    one_off_outflow = st.number_input("Pago extraordinario al inicio ($)", min_value=0.0, value=0.0, step=50_000.0)
    st.caption("Los supuestos se aplican a todos los cobros o pagos alcanzados por la proyección. No cambian los datos originales.")

st.subheader(f"🏢 {company}")
st.write(
    "Empresa ficticia dedicada a la distribución mayorista de productos de consumo. "
    "Los movimientos precargados son ejemplos inventados para demostrar el funcionamiento."
)

if "movements" not in st.session_state:
    st.session_state.movements = demo_movements(TODAY)

left, right = st.columns([1, 1])
with left:
    uploaded = st.file_uploader("Importar movimientos desde CSV", type=["csv"])
    if uploaded is not None:
        try:
            incoming = pd.read_csv(uploaded)
            st.session_state.movements = normalise_movements(incoming)
            st.success("Archivo importado. Revisá los datos en la tabla antes de continuar.")
        except Exception as exc:
            st.error(f"No se pudo leer el archivo: {exc}")
with right:
    if st.button("↩️ Restaurar datos ficticios"):
        st.session_state.movements = demo_movements(TODAY)
        st.rerun()

st.caption(
    "Columnas del CSV: Fecha, Concepto, Tipo, Importe, Estado, Categoría, Cliente/proveedor. "
    "Fecha en formato AAAA-MM-DD; Tipo: Saldo inicial/Cobro/Pago; Estado: Confirmado/Pendiente."
)

st.subheader("1. Registro de movimientos")
edited = st.data_editor(
    st.session_state.movements,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY", required=True),
        "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Saldo inicial", "Cobro", "Pago"], required=True),
        "Importe": st.column_config.NumberColumn("Importe ($)", min_value=0, step=1000, format="%.2f"),
        "Estado": st.column_config.SelectboxColumn("Estado", options=["Confirmado", "Pendiente"], required=True),
    },
    key="movement_editor",
)
clean = normalise_movements(edited)
st.session_state.movements = clean

# Saldo inicial se ingresa en configuración, por lo que se excluye de los movimientos
# para evitar contar dos veces el saldo inicial.
forecast, adjusted_movements = simulate(
    clean, start_date, int(horizon), float(initial_balance), float(minimum_cash),
    int(delay_collections), float(collection_reduction), float(payment_increase),
    int(delay_payments), float(one_off_inflow), float(one_off_outflow)
)

# Se considera saldo al inicio del día antes de los flujos de ese día para localizar
# el saldo intradiario mínimo de forma simple y conservadora.
forecast["Saldo anterior al flujo"] = forecast["Saldo proyectado"] - forecast["Flujo neto"]
forecast["Fecha"] = pd.to_datetime(forecast["Fecha"])

risk_days = forecast[forecast["Saldo proyectado"] < minimum_cash]
negative_days = forecast[forecast["Saldo proyectado"] < 0]
min_row = forecast.loc[forecast["Saldo proyectado"].idxmin()]
total_in = forecast["Cobros"].sum()
total_out = forecast["Pagos"].sum()
final_balance = forecast["Saldo proyectado"].iloc[-1]
net_flow = total_in - total_out

st.subheader("2. Indicadores principales")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Saldo final proyectado", money(final_balance))
c2.metric("Cobros proyectados", money(total_in))
c3.metric("Pagos proyectados", money(total_out))
c4.metric("Flujo neto", money(net_flow), delta=None)

c5, c6, c7 = st.columns(3)
c5.metric("Saldo mínimo del período", money(min_row["Saldo proyectado"]))
c6.metric("Días bajo el mínimo de seguridad", f"{len(risk_days)}")
c7.metric("Días con saldo negativo", f"{len(negative_days)}")

if len(negative_days) > 0:
    st.error(
        f"Alerta: la proyección muestra saldo negativo en {len(negative_days)} día(s). "
        f"El punto más bajo es {money(min_row['Saldo proyectado'])} el {min_row['Fecha'].strftime('%d/%m/%Y')}."
    )
elif len(risk_days) > 0:
    st.warning(
        f"Atención: el saldo proyectado cae por debajo del mínimo de seguridad de "
        f"{money(minimum_cash)} en {len(risk_days)} día(s). Revisá las fechas de cobro y pago."
    )
else:
    st.success("Según los supuestos actuales, el saldo proyectado se mantiene en o por encima del mínimo de seguridad.")

st.subheader("3. Evolución proyectada del efectivo")
chart = px.line(
    forecast, x="Fecha", y="Saldo proyectado", markers=True,
    title="Saldo de caja proyectado por día",
    labels={"Fecha": "Fecha", "Saldo proyectado": "Saldo ($)"},
)
chart.add_hline(y=minimum_cash, line_dash="dash", annotation_text="Mínimo de seguridad")
chart.add_hline(y=0, line_dash="dot", annotation_text="Saldo cero")
st.plotly_chart(chart, use_container_width=True)

flow_chart = px.bar(
    forecast, x="Fecha", y=["Cobros", "Pagos"],
    title="Cobros y pagos por día",
    labels={"value": "Importe ($)", "Fecha": "Fecha", "variable": "Movimiento"},
    barmode="group",
)
st.plotly_chart(flow_chart, use_container_width=True)

st.subheader("4. Calendario de flujo de caja")
view = forecast.copy()
view["Fecha"] = view["Fecha"].dt.strftime("%d/%m/%Y")
st.dataframe(
    view[["Fecha", "Cobros", "Pagos", "Flujo neto", "Saldo proyectado", "Estado de liquidez"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Cobros": st.column_config.NumberColumn(format="$ %.2f"),
        "Pagos": st.column_config.NumberColumn(format="$ %.2f"),
        "Flujo neto": st.column_config.NumberColumn(format="$ %.2f"),
        "Saldo proyectado": st.column_config.NumberColumn(format="$ %.2f"),
    },
)

st.subheader("5. Movimientos ajustados por el escenario")
if adjusted_movements.empty:
    st.write("No hay movimientos dentro del horizonte elegido.")
else:
    adjusted_view = adjusted_movements.copy()
    adjusted_view["Fecha original"] = adjusted_view["Fecha"].astype(str)
    adjusted_view["Fecha ajustada"] = adjusted_view["Fecha ajustada"].astype(str)
    st.dataframe(
        adjusted_view[["Fecha original", "Fecha ajustada", "Concepto", "Tipo", "Importe", "Importe ajustado", "Estado", "Categoría", "Cliente/proveedor"]],
        use_container_width=True,
        hide_index=True,
    )

st.subheader("6. Recomendaciones automáticas")
recommendations = []
if len(negative_days) > 0:
    recommendations.append("Priorizar el análisis de las fechas con saldo negativo: verificar cobros esperados, vencimientos y alternativas de financiación.")
if len(risk_days) > 0:
    recommendations.append("Revisar si es posible negociar fechas de pago o acelerar cobros sin asumir costos desproporcionados.")
if delay_collections > 0:
    recommendations.append("El escenario incluye demoras de cobro: confirmar con clientes las fechas probables y revisar la concentración de cuentas por cobrar.")
if payment_increase > 0:
    recommendations.append("El escenario incluye un aumento de pagos: comparar precios, revisar gastos y analizar el efecto sobre los márgenes.")
if collection_reduction > 0:
    recommendations.append("La reducción de cobros representa un supuesto de estrés; revisar la capacidad de pago si este escenario se materializa.")
if delay_payments > 0:
    recommendations.append("Se reprogramaron pagos en el escenario. Antes de aplicarlo, verificar contratos, intereses, penalidades y obligaciones legales.")
if one_off_inflow > 0:
    recommendations.append("Se incorporó un cobro extraordinario. Confirmar que exista evidencia suficiente de su fecha e importe.")
if one_off_outflow > 0:
    recommendations.append("Se incorporó un pago extraordinario. Revisar si corresponde provisionarlo y si puede financiarse con recursos disponibles.")
if not recommendations:
    recommendations.append("Con los supuestos seleccionados no se activaron alertas especiales. Compará el escenario base con situaciones adversas antes de tomar decisiones.")
for item in recommendations:
    st.markdown(f"- {item}")

st.subheader("7. Comparar escenario base con escenario actual")
base_forecast, _ = simulate(
    clean, start_date, int(horizon), float(initial_balance), float(minimum_cash),
    0, 0, 0, 0, 0, 0
)
comparison = pd.DataFrame({
    "Fecha": pd.to_datetime(forecast["Fecha"]),
    "Escenario actual": forecast["Saldo proyectado"],
    "Escenario base": base_forecast["Saldo proyectado"],
})
comparison_long = comparison.melt("Fecha", var_name="Escenario", value_name="Saldo")
comp_chart = px.line(
    comparison_long, x="Fecha", y="Saldo", color="Escenario",
    title="Comparación de saldos proyectados",
    labels={"Saldo": "Saldo ($)", "Fecha": "Fecha"},
)
comp_chart.add_hline(y=minimum_cash, line_dash="dash", annotation_text="Mínimo de seguridad")
st.plotly_chart(comp_chart, use_container_width=True)

st.subheader("8. Exportar resultados")
col_a, col_b, col_c = st.columns(3)
with col_a:
    st.download_button(
        "⬇️ Descargar movimientos (CSV)",
        data=to_csv_bytes(clean),
        file_name="finansmart_movimientos.csv",
        mime="text/csv",
        use_container_width=True,
    )
with col_b:
    export_forecast = forecast.copy()
    export_forecast["Fecha"] = export_forecast["Fecha"].dt.strftime("%Y-%m-%d")
    st.download_button(
        "⬇️ Descargar proyección (CSV)",
        data=to_csv_bytes(export_forecast),
        file_name="finansmart_proyeccion.csv",
        mime="text/csv",
        use_container_width=True,
    )
with col_c:
    report = pd.DataFrame([{
        "Empresa": company,
        "Fecha de inicio": str(start_date),
        "Horizonte (días)": horizon,
        "Saldo inicial": initial_balance,
        "Cobros proyectados": total_in,
        "Pagos proyectados": total_out,
        "Flujo neto": net_flow,
        "Saldo final": final_balance,
        "Saldo mínimo del período": float(min_row["Saldo proyectado"]),
        "Días bajo mínimo": len(risk_days),
        "Días con saldo negativo": len(negative_days),
    }])
    st.download_button(
        "⬇️ Descargar resumen (CSV)",
        data=to_csv_bytes(report),
        file_name="finansmart_resumen.csv",
        mime="text/csv",
        use_container_width=True,
    )

with st.expander("📘 Supuestos y limitaciones del prototipo"):
    st.markdown("""
    - Los datos iniciales corresponden a una empresa ficticia y deben reemplazarse o editarse para un caso real.
    - La aplicación suma movimientos por fecha y calcula saldos acumulados; no es un sistema contable completo.
    - En esta versión, los cambios de escenario se aplican de forma general a todos los cobros o pagos del período.
    - Los movimientos confirmados y pendientes se incluyen en la proyección para representar el plan esperado; el estado se muestra para su revisión.
    - La reprogramación de pagos no determina si el cambio es legal o contractualmente admisible.
    - No se conecta con bancos, AFIP/ARCA ni sistemas de facturación.
    - No calcula rentabilidad, impuestos, intereses financieros ni inflación de manera automática.
    - No incorpora autenticación multiusuario ni cifrado de datos; no cargues información sensible o real en una instancia pública.
    - Para un uso profesional serían necesarios controles de acceso, copias de seguridad, validaciones, pruebas y revisión por un profesional.
    """)
