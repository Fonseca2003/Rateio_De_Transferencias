import streamlit as st
import pandas as pd
import math
import io
import datetime
from PIL import Image

# =============================================================================
# CONFIGURAÇÕES GERAIS
# =============================================================================
icon = Image.open("icon.png")

st.set_page_config(
    page_title="Rateio de Estoque",
    layout="wide",
    page_icon=icon
)

col_logo, col_titulo = st.columns([1, 5])
with col_logo:
    st.image("logo.png", use_container_width=True)
with col_titulo:
    st.title("Rateio de Estoque")

# =============================================================================
# ESTADO DA SESSÃO
# =============================================================================
if "parametros_confirmados" not in st.session_state:
    st.session_state.parametros_confirmados = False
if "minimo_saida" not in st.session_state:
    st.session_state.minimo_saida = 100
if "dias_estoque_entrada" not in st.session_state:
    st.session_state.dias_estoque_entrada = 60
if "minimo_mov" not in st.session_state:
    st.session_state.minimo_mov = 10
if "com_pedido" not in st.session_state:
    st.session_state.com_pedido = True
if "df_base" not in st.session_state:
    st.session_state.df_base = None
if "df_base_tratada" not in st.session_state:
    st.session_state.df_base_tratada = None
if "resultado_rateio" not in st.session_state:
    st.session_state.resultado_rateio = None

# =============================================================================
# MODELO EXCEL
# =============================================================================
def gerar_modelo_excel():
    colunas = [
        "Loja", "Código Produto", "Produto", "Embal",
        "Quantidade Disponível", "Qtd. Pend. Ped.Compra",
        "Média Vda/Dia", "Cto. Bruto Unitário", "Comprador"
    ]
    df_modelo = pd.DataFrame(columns=colunas)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_modelo.to_excel(writer, sheet_name="Base", index=False)
    buffer.seek(0)
    return buffer

# =============================================================================
# ETAPA 1
# =============================================================================
st.header("1️⃣ Baixar Planilha Padrão")
st.download_button(
    "📥 Baixar modelo",
    gerar_modelo_excel(),
    "Modelo_Base_Transferencias.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.markdown("---")

# =============================================================================
# ETAPA 2 – PARÂMETROS
# =============================================================================
st.header("2️⃣ Definir Parâmetros")

c1, c2, c3 = st.columns(3)
with c1:
    minimo_saida = st.number_input(
        "Dias de estoque mínimo (lojas de saída):",
        min_value=0,
        value=st.session_state.minimo_saida,
        step=1
    )
with c2:
    dias_estoque_entrada = st.number_input(
        "Dias de estoque alvo (lojas de entrada):",
        min_value=0,
        value=st.session_state.dias_estoque_entrada,
        step=1
    )
with c3:
    minimo_mov = st.number_input(
        "Qtd mínima para movimentar:",
        min_value=0,
        value=st.session_state.minimo_mov,
        step=1
    )

com_pedido = st.checkbox(
    "Considerar pedido pendente",
    value=st.session_state.com_pedido
)

if st.button("✅ Confirmar Parâmetros"):
    st.session_state.minimo_saida = minimo_saida
    st.session_state.dias_estoque_entrada = dias_estoque_entrada
    st.session_state.minimo_mov = minimo_mov
    st.session_state.com_pedido = com_pedido
    st.session_state.parametros_confirmados = True
    st.success("Parâmetros confirmados!")

if not st.session_state.parametros_confirmados:
    st.stop()

st.markdown("---")

# =============================================================================
# ETAPA 3 – IMPORTAÇÃO
# =============================================================================
st.header("3️⃣ Importar Planilha")

arquivo = st.file_uploader("Selecione o arquivo base (.xlsx):", type=["xlsx"])

if arquivo is not None and st.button("📥 Salvar"):
    try:
        with st.spinner("Importando base, aguarde..."):
            df_base = pd.read_excel(arquivo, sheet_name="Base")

            for col in ['Quantidade Disponível', 'Qtd. Pend. Ped.Compra', 'Média Vda/Dia']:
                df_base[col] = pd.to_numeric(df_base[col], errors='coerce').fillna(0)

            df_base['Loja'] = df_base['Loja'].astype(str)

            if 'Comprador' not in df_base.columns:
                df_base['Comprador'] = 'N/A'
            if 'Cto. Bruto Unitário' not in df_base.columns:
                df_base['Cto. Bruto Unitário'] = 0.0

            st.session_state.df_base = df_base
            st.session_state.df_base_tratada = df_base.copy()

        st.success("Base importada com sucesso!")
    except Exception as e:
        st.error(f"Erro ao ler a base: {e}")
        st.stop()

if st.session_state.df_base_tratada is None:
    st.stop()

df_base = st.session_state.df_base_tratada.copy()
st.markdown("---")

# =============================================================================
# ETAPA 4 – SELECIONAR LOJAS
# =============================================================================
st.header("4️⃣ Modalidade e Escolha de Lojas")

modalidade = st.radio(
    "Modalidade de Transferência:",
    ["Loja a Loja", "De Todas Para Todas"],
    horizontal=True
)

todas_lojas = sorted(df_base['Loja'].dropna().unique().tolist())

col_saida, col_entrada = st.columns(2)

# -------- SAÍDA --------
with col_saida:
    st.subheader("Lojas de Saída")
    lojas_saida = st.multiselect(
        "Selecione as lojas que irão enviar os produtos:",
        options=todas_lojas,
        default=todas_lojas
    )

# -------- ENTRADA --------
with col_entrada:
    st.subheader("Lojas de Entrada")

    if modalidade == "De Todas Para Todas":
        lojas_entrada = st.multiselect(
            "Selecione as lojas que irão receber os produtos:",
            options=todas_lojas,
            default=todas_lojas
        )
    else:
        lojas_entrada = st.multiselect(
            "Selecione as lojas que irão receber os produtos:",
            options=[l for l in todas_lojas if l not in lojas_saida],
            default=[l for l in todas_lojas if l not in lojas_saida]
        )

df_saida = df_base[df_base["Loja"].isin(lojas_saida)].copy().reset_index(drop=True)
df_entrada = df_base[df_base["Loja"].isin(lojas_entrada)].copy().reset_index(drop=True)

# =============================================================================
# FUNÇÕES AUXILIARES (ORIGINAIS)
# =============================================================================
def calcular_liberado_para_transferir(df_saida, minimo_saida, minimo_mov, com_pedido):
    base_estoque_saida = df_saida['Quantidade Disponível'] - (df_saida['Média Vda/Dia'] * minimo_saida)
    if com_pedido:
        base_estoque_saida += df_saida['Qtd. Pend. Ped.Compra']

    df_saida['Liberado Para Transferir'] = base_estoque_saida.apply(
        lambda x: int(round(x, 0)) if x >= minimo_mov else 0
    )
    return df_saida[df_saida['Liberado Para Transferir'] > 0].reset_index(drop=True)

def calcular_liberado_para_receber(df_entrada, dias_estoque_entrada, minimo_mov, com_pedido):
    alvo = df_entrada['Média Vda/Dia'] * dias_estoque_entrada
    necessidade = alvo - df_entrada['Quantidade Disponível']
    if com_pedido:
        necessidade -= df_entrada['Qtd. Pend. Ped.Compra']

    df_entrada['Liberado Para Receber'] = necessidade.apply(
        lambda x: math.ceil(x) if x >= minimo_mov else 0
    )
    df_entrada['Estoque Alvo Desejado'] = alvo
    return df_entrada[df_entrada['Liberado Para Receber'] > 0].reset_index(drop=True)

# =============================================================================
# ETAPA 5 – RATEIO (ORIGINAL + BLOQUEIO AUTO)
# =============================================================================
st.header("5️⃣ Calcular Transferências")

if st.button("🚀 Calcular Transferências"):
    with st.spinner("Processando rateio, isso pode levar alguns instantes..."):
        df_saida_proc = calcular_liberado_para_transferir(
            df_saida,
            st.session_state.minimo_saida,
            st.session_state.minimo_mov,
            st.session_state.com_pedido
        )

        df_entrada_proc = calcular_liberado_para_receber(
            df_entrada,
            st.session_state.dias_estoque_entrada,
            st.session_state.minimo_mov,
            st.session_state.com_pedido
        )

        resultados = []

        for produto in df_saida_proc['Código Produto'].unique():
            lojas_saida_prod = df_saida_proc[
                df_saida_proc['Código Produto'] == produto
            ].copy()

            lojas_entrada_prod = df_entrada_proc[
                df_entrada_proc['Código Produto'] == produto
            ].copy()

            if lojas_saida_prod.empty or lojas_entrada_prod.empty:
                continue

            for _, ent in lojas_entrada_prod.iterrows():
                loja_ent_nome = ent['Loja']
                qtd_restante = int(ent['Liberado Para Receber'])

                if qtd_restante <= 0:
                    continue

                lojas_saida_ativas = lojas_saida_prod[
                    lojas_saida_prod['Liberado Para Transferir'] > 0
                ].copy()

                for sai_idx, sai in lojas_saida_ativas.iterrows():
                    loja_sai_nome = sai['Loja']

                    # 🔒 BLOQUEIO DE AUTO-TRANSFERÊNCIA
                    if loja_sai_nome == loja_ent_nome:
                        continue

                    qtd_disp_saida = int(sai['Liberado Para Transferir'])

                    if qtd_restante <= 0:
                        break

                    qtd = min(qtd_disp_saida, qtd_restante)

                    if qtd < st.session_state.minimo_mov:
                        continue

                    resultados.append({
                        'Código Produto': produto,
                        'Produto': sai['Produto'],
                        'Embal': sai['Embal'],
                        'Quantidade Para Transferir': qtd,
                        'Loja Saída': loja_sai_nome,
                        'Loja Entrada': loja_ent_nome
                    })

                    qtd_restante -= qtd
                    lojas_saida_prod.loc[sai_idx, 'Liberado Para Transferir'] -= qtd

        rateio_ll = pd.DataFrame(resultados)

        # =======================
        # CÁLCULO DOS VALORES
        # =======================
        df_base_local = st.session_state.df_base_tratada.copy()

        map_custo = df_base_local.set_index(
            ['Loja', 'Código Produto']
        )['Cto. Bruto Unitário'].to_dict()

        map_comprador = df_base_local.set_index(
            ['Loja', 'Código Produto']
        )['Comprador'].to_dict()

        if not rateio_ll.empty:
            custos = []
            compradores = []
            valores = []

            for _, row in rateio_ll.iterrows():
                loja_sai = row['Loja Saída']
                cod = row['Código Produto']
                qtd = row['Quantidade Para Transferir']

                custo_unit = map_custo.get((loja_sai, cod), 0.0)
                comprador = map_comprador.get((loja_sai, cod), 'N/A')

                custos.append(custo_unit)
                compradores.append(comprador)
                valores.append(custo_unit * qtd)

            rateio_ll['Cto. Bruto Unitário'] = custos
            rateio_ll['Comprador'] = compradores
            rateio_ll['Valor Transferência'] = valores

        # =======================
        # RESUMOS GERENCIAIS
        # =======================
        df_valor_por_comprador = (
        rateio_ll.groupby('Comprador', as_index=False)['Valor Transferência']
            .sum()
            .rename(columns={'Valor Transferência': 'Valor Total Transferência'})
        )

        df_valor_por_loja_saida = (
            rateio_ll.groupby('Loja Saída', as_index=False)['Valor Transferência']
            .sum()
            .rename(columns={'Valor Transferência': 'Valor Total Transferência'})
        )

        df_valor_por_loja_entrada = (
            rateio_ll.groupby('Loja Entrada', as_index=False)['Valor Transferência']
            .sum()
            .rename(columns={'Valor Transferência': 'Valor Total Transferência'})        )


        # =======================
        # PARÂMETROS
        # =======================
        df_parametros = pd.DataFrame({
            'Parâmetro': [
                'Dias Estoque Mínimo (Saída)',
                'Dias Estoque Alvo (Entrada)',
                'Qtd Mínima para Movimentar',
                'Considera Pedido Pendente',
                'Modalidade'
            ],
            'Valor': [
                st.session_state.minimo_saida,
                st.session_state.dias_estoque_entrada,
                st.session_state.minimo_mov,
                st.session_state.com_pedido,
                modalidade
            ]
        })

        # =======================
        # SALVAR RESULTADO FINAL
        # =======================
        st.session_state.resultado_rateio = {
            "df_saida": df_saida_proc,
            "rateio_ll": rateio_ll,
            "df_entrada": df_entrada_proc,
            "df_valor_por_comprador": df_valor_por_comprador,
            "df_valor_por_loja_saida": df_valor_por_loja_saida,
            "df_valor_por_loja_entrada": df_valor_por_loja_entrada,
            "df_parametros": df_parametros
        }



# =============================================================================
# EXIBIÇÃO DE RESULTADOS E EXPORTAÇÃO
# =============================================================================
if st.session_state.resultado_rateio is not None:
    res = st.session_state.resultado_rateio

    st.header("📝 Resumo")

    if res["rateio_ll"] is not None and not res["rateio_ll"].empty:
        st.subheader("Rateio Loja a Loja")
        st.dataframe(res["rateio_ll"].head(100), use_container_width=True, hide_index=True)

    # ============================
    # Resumos Gerenciais em 3 colunas
    # ============================
    df_comp = res["df_valor_por_comprador"].copy()
    df_loja_saida = res["df_valor_por_loja_saida"].copy()
    df_loja_entrada = res["df_valor_por_loja_entrada"].copy()

    # --------- Função para adicionar total e formatar moeda ----------
    def preparar_resumo(df, col_valor, label_total="TOTAL"):
        if df is None or df.empty:
            return df

        df = df.copy()

        # calcula total
        total_valor = df[col_valor].sum()

        # adiciona linha TOTAL
        linha_total = {}
        for col in df.columns:
            if col == col_valor:
                linha_total[col] = total_valor
            else:
                linha_total[col] = label_total
        df = pd.concat([df, pd.DataFrame([linha_total])], ignore_index=True)

        # formata como moeda
        df_styled = df.style.format({
            col_valor: "R$ {:,.2f}".format
        })

        return df_styled

    df_comp_styled = preparar_resumo(df_comp, "Valor Total Transferência", label_total="TOTAL")
    df_loja_saida_styled = preparar_resumo(df_loja_saida, "Valor Total Transferência", label_total="TOTAL")
    df_loja_entrada_styled = preparar_resumo(df_loja_entrada, "Valor Total Transferência", label_total="TOTAL")

    col_res1, col_res2, col_res3 = st.columns(3)

    with col_res1:
        st.subheader("Resumo por Comprador")
        if df_comp is not None and not df_comp.empty:
            st.dataframe(df_comp_styled, use_container_width=True, hide_index=True)
        else:
            st.info("Sem dados para compradores.")

    with col_res2:
        st.subheader("Resumo Saída")
        if df_loja_saida is not None and not df_loja_saida.empty:
            st.dataframe(df_loja_saida_styled, use_container_width=True, hide_index=True)
        else:
            st.info("Sem dados para lojas de saída.")

    with col_res3:
        st.subheader("Resumo Entrada")
        if df_loja_entrada is not None and not df_loja_entrada.empty:
            st.dataframe(df_loja_entrada_styled, use_container_width=True, hide_index=True)
        else:
            st.info("Sem dados para lojas de entrada.")


    # Função para exportar Excel final
    def gerar_excel_saida():
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book

            header_format = workbook.add_format({
                'bold': True,
                'font_color': 'white',
                'bg_color': '#00B050',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })

            moeda_format = workbook.add_format({'num_format': 'R$ #,##0.00'})
            total_format = workbook.add_format({'bold': True, 'border': 1})
            total_moeda_format = workbook.add_format({'bold': True, 'border': 1, 'num_format': 'R$ #,##0.00'})

            def ajustar_largura_colunas(ws, df):
                for idx, col in enumerate(df.columns):
                    serie = df[col].astype(str)
                    max_len = max(
                        serie.map(len).max() if not serie.empty else 0,
                        len(str(col)),
                        len("TOTAL")
                    ) + 2
                    ws.set_column(idx, idx, max_len)

            # ---- Gerencial ----
            df_valor_por_comprador = res["df_valor_por_comprador"]
            df_valor_por_loja_saida = res["df_valor_por_loja_saida"]
            df_valor_por_loja_entrada = res["df_valor_por_loja_entrada"]
            df_parametros = res["df_parametros"]

            ws_resumo = workbook.add_worksheet('Gerencial')
            linha_atual = 0

            # =========================
            # Resumo por comprador
            # =========================
            ws_resumo.write(linha_atual, 0, "Resumo por Comprador", header_format)
            ws_resumo.merge_range(linha_atual, 0, linha_atual, 1, "Resumo por Comprador", header_format)
            linha_atual += 1

            if df_valor_por_comprador is not None and not df_valor_por_comprador.empty:
                for col_num, col_name in enumerate(df_valor_por_comprador.columns):
                    ws_resumo.write(linha_atual, col_num, col_name, header_format)
                linha_atual += 1

                for _, row in df_valor_por_comprador.iterrows():
                    ws_resumo.write(linha_atual, 0, row['Comprador'])
                    ws_resumo.write_number(linha_atual, 1, row['Valor Total Transferência'], moeda_format)
                    linha_atual += 1

                ws_resumo.write(linha_atual, 0, "TOTAL", total_format)
                total_val_comprador = df_valor_por_comprador['Valor Total Transferência'].sum()
                ws_resumo.write_number(linha_atual, 1, total_val_comprador, total_moeda_format)
                linha_atual += 2
            else:
                linha_atual += 2

            # =========================
            # Resumo por loja de saída
            # =========================
            ws_resumo.write(linha_atual, 0, "Resumo por Loja de Saída", header_format)
            ws_resumo.merge_range(linha_atual, 0, linha_atual, 1, "Resumo por Loja de Saída", header_format)
            linha_atual += 1

            if df_valor_por_loja_saida is not None and not df_valor_por_loja_saida.empty:
                for col_num, col_name in enumerate(df_valor_por_loja_saida.columns):
                    ws_resumo.write(linha_atual, col_num, col_name, header_format)
                linha_atual += 1

                for _, row in df_valor_por_loja_saida.iterrows():
                    ws_resumo.write(linha_atual, 0, row['Loja Saída'])
                    ws_resumo.write_number(linha_atual, 1, row['Valor Total Transferência'], moeda_format)
                    linha_atual += 1

                ws_resumo.write(linha_atual, 0, "TOTAL", total_format)
                total_val_loja_saida = df_valor_por_loja_saida['Valor Total Transferência'].sum()
                ws_resumo.write_number(linha_atual, 1, total_val_loja_saida, total_moeda_format)
                linha_atual += 2
            else:
                linha_atual += 2

            # =========================
            # Resumo por loja de entrada
            # =========================
            ws_resumo.write(linha_atual, 0, "Resumo por Loja de Entrada", header_format)
            ws_resumo.merge_range(linha_atual, 0, linha_atual, 1, "Resumo por Loja de Entrada", header_format)
            linha_atual += 1

            if df_valor_por_loja_entrada is not None and not df_valor_por_loja_entrada.empty:
                for col_num, col_name in enumerate(df_valor_por_loja_entrada.columns):
                    ws_resumo.write(linha_atual, col_num, col_name, header_format)
                linha_atual += 1

                for _, row in df_valor_por_loja_entrada.iterrows():
                    ws_resumo.write(linha_atual, 0, row['Loja Entrada'])
                    ws_resumo.write_number(linha_atual, 1, row['Valor Total Transferência'], moeda_format)
                    linha_atual += 1

                ws_resumo.write(linha_atual, 0, "TOTAL", total_format)
                total_val_loja_entrada = df_valor_por_loja_entrada['Valor Total Transferência'].sum()
                ws_resumo.write_number(linha_atual, 1, total_val_loja_entrada, total_moeda_format)
                linha_atual += 2
            else:
                linha_atual += 2

            # =========================
            # Parâmetros
            # =========================
            ws_resumo.write(linha_atual, 0, "Parâmetros Utilizados", header_format)
            ws_resumo.merge_range(linha_atual, 0, linha_atual, 1, "Parâmetros Utilizados", header_format)
            linha_atual += 1

            for col_num, col_name in enumerate(df_parametros.columns):
                ws_resumo.write(linha_atual, col_num, col_name, header_format)
            linha_atual += 1

            for _, row in df_parametros.iterrows():
                ws_resumo.write(linha_atual, 0, str(row['Parâmetro']))
                ws_resumo.write(linha_atual, 1, str(row['Valor']))
                linha_atual += 1

            for idx in range(3):
                ws_resumo.set_column(idx, idx, 30)

            # ---- Rateio Loja a Loja ----
            rateio_ll = res["rateio_ll"]
            if rateio_ll is not None and not rateio_ll.empty:
                rateio_ll.to_excel(writer, sheet_name='Rateio Loja a Loja', index=False)
                ws_ll = writer.sheets['Rateio Loja a Loja']

                for col_num, value in enumerate(rateio_ll.columns.values):
                    ws_ll.write(0, col_num, value, header_format)

                if 'Valor Transferência' in rateio_ll.columns:
                    col_idx_valor = rateio_ll.columns.get_loc('Valor Transferência')
                    ws_ll.set_column(col_idx_valor, col_idx_valor, 18, moeda_format)

                ajustar_largura_colunas(ws_ll, rateio_ll)

            # ---- Lojas De Saída ----
            df_saida_diag = res["df_saida"].rename(
                columns={'Quantidade Disponível': 'Estoque Atual',
                         'Liberado Para Transferir': 'Liberado Saída (Caixas)'}
            ).copy()

            # Qtd Transferida por loja/produto (Loja a Loja)
            df_transferencias_sint = pd.DataFrame()
            if res["rateio_ll"] is not None and not res["rateio_ll"].empty:
                tmp_ll = res["rateio_ll"][['Loja Saída', 'Código Produto', 'Quantidade Para Transferir']].copy()
                tmp_ll = tmp_ll.rename(columns={'Loja Saída': 'Loja'})
                df_transferencias_sint = pd.concat([df_transferencias_sint, tmp_ll])

            if not df_transferencias_sint.empty:
                df_transferencias_sint = df_transferencias_sint.groupby(
                    ['Loja', 'Código Produto'], as_index=False
                )['Quantidade Para Transferir'].sum()
                df_transferencias_sint = df_transferencias_sint.rename(columns={'Quantidade Para Transferir': 'Qtd Transferida'})
                df_saida_diag = pd.merge(
                    df_saida_diag,
                    df_transferencias_sint,
                    on=['Loja', 'Código Produto'],
                    how='left'
                )
            else:
                df_saida_diag['Qtd Transferida'] = 0

            df_saida_diag['Qtd Transferida'] = df_saida_diag['Qtd Transferida'].fillna(0)
            df_saida_diag['Estoque Após Transferência'] = df_saida_diag['Estoque Atual'] - df_saida_diag['Qtd Transferida']

            # Dias de estoque atual (antes da transferência)
            df_saida_diag['Dias Estoque Atual'] = df_saida_diag.apply(
                lambda row: row['Estoque Atual'] / row['Média Vda/Dia']
                if row['Média Vda/Dia'] > 0 else None,
                axis=1
            )

            # Dias de estoque após transferência
            df_saida_diag['Dias Estoque Após Transferência'] = df_saida_diag.apply(
                lambda row: row['Estoque Após Transferência'] / row['Média Vda/Dia']
                if row['Média Vda/Dia'] > 0 else None,
                axis=1
            )

            if 'Produto' in df_saida_diag.columns:
                df_saida_diag = df_saida_diag[
                    ['Loja', 'Código Produto', 'Produto', 'Média Vda/Dia',
                     'Estoque Atual', 'Dias Estoque Atual',
                     'Qtd. Pend. Ped.Compra',
                     'Liberado Saída (Caixas)', 'Qtd Transferida',
                     'Estoque Após Transferência', 'Dias Estoque Após Transferência']
                ]
            else:
                df_saida_diag = df_saida_diag[
                    ['Loja', 'Código Produto',
                     'Média Vda/Dia',
                     'Estoque Atual', 'Dias Estoque Atual',
                     'Qtd. Pend. Ped.Compra',
                     'Liberado Saída (Caixas)', 'Qtd Transferida',
                     'Estoque Após Transferência', 'Dias Estoque Após Transferência']
                ]

            df_saida_diag.to_excel(writer, sheet_name='Lojas De Saída', index=False)
            ws_saida_diag = writer.sheets['Lojas De Saída']

            for col_num, value in enumerate(df_saida_diag.columns.values):
                ws_saida_diag.write(0, col_num, value, header_format)

            ajustar_largura_colunas(ws_saida_diag, df_saida_diag)

            # ---- Lojas De Entrada ----
            df_entrada_diag = res["df_entrada"]
            if df_entrada_diag is not None and not df_entrada_diag.empty:
                df_entrada_diag = df_entrada_diag[['Loja', 'Código Produto', 'Produto',
                                                   'Média Vda/Dia', 'Quantidade Disponível',
                                                   'Estoque Alvo Desejado', 'Liberado Para Receber']].copy()
                df_entrada_diag = df_entrada_diag.rename(
                    columns={'Quantidade Disponível': 'Estoque Atual',
                             'Liberado Para Receber': 'Necessidade Líquida (Caixas)'}
                )
                df_entrada_diag = df_entrada_diag[
                    ['Loja', 'Código Produto', 'Produto',
                     'Média Vda/Dia', 'Estoque Alvo Desejado',
                     'Estoque Atual', 'Necessidade Líquida (Caixas)']
                ]

                df_entrada_diag.to_excel(writer, sheet_name='Lojas De Entrada', index=False)
                ws_ent_diag = writer.sheets['Lojas De Entrada']

                for col_num, value in enumerate(df_entrada_diag.columns.values):
                    ws_ent_diag.write(0, col_num, value, header_format)

                ajustar_largura_colunas(ws_ent_diag, df_entrada_diag)

        output.seek(0)
        return output

    excel_saida = gerar_excel_saida()
    data_atual = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = f"Rateio_Loja_a_Loja_{data_atual}.xlsx"

    st.download_button(
        label="📤 Baixar resultado em Excel",
        data=excel_saida,
        file_name=nome_arquivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
