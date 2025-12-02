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

# TÍTULO COM LOGO
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
# FUNÇÃO PARA GERAR EXCEL PADRÃO (VAZIO) COM ABA "Base"
# =============================================================================
def gerar_modelo_excel():
    colunas = [
        "Loja",
        "Código Produto",
        "Produto",
        "Embal",
        "Quantidade Disponível",
        "Qtd. Pend. Ped.Compra",
        "Média Vda/Dia",
        "Cto. Bruto Unitário",
        "Comprador"
    ]

    df_modelo = pd.DataFrame(columns=colunas)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_modelo.to_excel(writer, sheet_name="Base", index=False)
    buffer.seek(0)
    return buffer

# =============================================================================
# ETAPA 1 – BAIXAR EXCEL PADRÃO
# =============================================================================
st.header("1️⃣ Baixar Planilha Padrão")

st.write("Exporte abaixo um modelo vazio de Excel.")
st.write("É necessário preencher todas as colunas com os dados de estoque das lojas que irão receber e enviar os produtos.")
st.write("Os dados devem estar em embalagem de compra (CX, FD, PC etc).")
st.write("Não altere o título das colunas.")

buffer_modelo = gerar_modelo_excel()
st.download_button(
    label="📥 Baixar modelo",
    data=buffer_modelo,
    file_name="Modelo_Base_Transferencias.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.markdown("---")

# =============================================================================
# ETAPA 2 – PARÂMETROS DE SIMULAÇÃO
# =============================================================================
st.header("2️⃣ Definir Parâmetros")

col1, col2, col3 = st.columns(3)
with col1:
    minimo_saida = st.number_input(
        "Dias de estoque mínimo (lojas de saída):",
        min_value=0,
        value=st.session_state.minimo_saida,
        step=1
    )
with col2:
    dias_estoque_entrada = st.number_input(
        "Dias de estoque alvo (lojas de entrada):",
        min_value=0,
        value=st.session_state.dias_estoque_entrada,
        step=1
    )
with col3:
    minimo_mov = st.number_input(
        "Qtd mínima para movimentar:",
        min_value=0,
        value=st.session_state.minimo_mov,
        step=1
    )

col4, _ = st.columns(2)
with col4:
    com_pedido = st.checkbox("Considerar pedido pendente", value=st.session_state.com_pedido)

# botão de confirmação dos parâmetros
if st.button("✅ Confirmar Parâmetros"):
    st.session_state.minimo_saida = minimo_saida
    st.session_state.dias_estoque_entrada = dias_estoque_entrada
    st.session_state.minimo_mov = minimo_mov
    st.session_state.com_pedido = com_pedido
    st.session_state.parametros_confirmados = True
    st.success("Parâmetros confirmados!")

if not st.session_state.parametros_confirmados:
    st.warning("⚠️ Confirme os parâmetros acima antes de prosseguir.")
    st.stop()

st.markdown("---")

# =============================================================================
# ETAPA 3 – IMPORTAR BASE
# =============================================================================
st.header("3️⃣ Importar Planilha Padrão")

arquivo = st.file_uploader("Selecione o arquivo base (.xlsx):", type=["xlsx"])

if arquivo is not None and st.button("📥 Salvar"):
    try:
        with st.spinner("Importando base, aguarde..."):
            df_base = pd.read_excel(arquivo, sheet_name="Base", header=0)

            # Tratamento da base
            colunas_para_numerico = ['Quantidade Disponível', 'Qtd. Pend. Ped.Compra', 'Média Vda/Dia']
            for col in colunas_para_numerico:
                if col in df_base.columns:
                    df_base[col] = pd.to_numeric(df_base[col], errors='coerce').fillna(0)
                else:
                    df_base[col] = 0.0

            if 'Loja' not in df_base.columns:
                st.error("Coluna 'Loja' não encontrada na base de dados.")
                st.stop()

            df_base['Loja'] = df_base['Loja'].astype(str)

            if 'Comprador' not in df_base.columns:
                df_base['Comprador'] = 'N/A'
            if 'Cto. Bruto Unitário' not in df_base.columns:
                df_base['Cto. Bruto Unitário'] = 0.0

            st.session_state.df_base = df_base
            st.session_state.df_base_tratada = df_base.copy()

        st.success("Base importada com sucesso!")
    except Exception as e:
        st.error(f"Erro ao ler a aba 'Base': {e}")
        st.stop()
else:
    if st.session_state.df_base_tratada is None:
        st.info("Faça o upload do arquivo e clique em **📥 Salvar**.")
        st.stop()
    else:
        st.success("Base já carregada. Se precisar trocar o arquivo, faça upload e clique em **📥 Salvar** novamente.")

df_base = st.session_state.df_base_tratada.copy()
st.markdown("---")

# =============================================================================
# ETAPA 4 – SELECIONAR LOJAS (APENAS LOJA A LOJA)
# =============================================================================
st.header("4️⃣ Escolher Lojas de Saída e Entrada")

todas_lojas = sorted(df_base['Loja'].dropna().unique().tolist())

col_saida, col_entrada = st.columns(2)

# Lojas de saída
with col_saida:
    st.subheader("Lojas de Saída")
    if "lojas_ll_saida" in st.session_state:
        default_ll_saida = st.session_state.lojas_ll_saida
    else:
        default_ll_saida = todas_lojas

    lojas_saida = st.multiselect(
        "Selecione as lojas que irão enviar os produtos:",
        options=todas_lojas,
        default=default_ll_saida,
        key="lojas_ll_saida"
    )

# Lojas de entrada
with col_entrada:
    st.subheader("Lojas de Entrada")
    lojas_possiveis_entrada = [l for l in todas_lojas if l not in lojas_saida]

    if "lojas_ll_entrada" in st.session_state:
        default_ll_entrada = [
            l for l in st.session_state.lojas_ll_entrada if l in lojas_possiveis_entrada
        ] or lojas_possiveis_entrada
    else:
        default_ll_entrada = lojas_possiveis_entrada

    lojas_entrada = st.multiselect(
        "Selecione as lojas que irão receber os produtos:",
        options=lojas_possiveis_entrada,
        default=default_ll_entrada,
        key="lojas_ll_entrada"
    )

if not lojas_saida:
    st.error("Selecione pelo menos uma loja de **saída**.")
    st.stop()

if not lojas_entrada:
    st.error("Selecione pelo menos uma loja de **entrada**.")
    st.stop()

df_saida = df_base[df_base["Loja"].isin(lojas_saida)].copy().reset_index(drop=True)
df_entrada = df_base[df_base["Loja"].isin(lojas_entrada)].copy().reset_index(drop=True)

st.markdown("---")

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================
def calcular_liberado_para_transferir(df_saida, minimo_saida, minimo_mov, com_pedido):
    base_estoque_saida = df_saida['Quantidade Disponível'] - (df_saida['Média Vda/Dia'] * minimo_saida)
    if com_pedido:
        liberado_transf = base_estoque_saida + df_saida['Qtd. Pend. Ped.Compra']
    else:
        liberado_transf = base_estoque_saida

    df_saida['Liberado Para Transferir'] = liberado_transf.apply(
        lambda x: int(round(x, 0)) if x >= minimo_mov else 0
    ).astype(int)
    df_saida = df_saida[df_saida['Liberado Para Transferir'] > 0].reset_index(drop=True)
    return df_saida

def calcular_liberado_para_receber(df_entrada, dias_estoque_entrada, minimo_mov, com_pedido):
    estoque_alvo_desejado = (df_entrada['Média Vda/Dia'] * dias_estoque_entrada)
    necessidade_bruta = estoque_alvo_desejado - df_entrada['Quantidade Disponível']

    if com_pedido:
        liberado_receber_float = necessidade_bruta - df_entrada['Qtd. Pend. Ped.Compra']
    else:
        liberado_receber_float = necessidade_bruta

    def calcular_necessidade_minima(x):
        if x <= 0:
            return 0
        necessidade_liquida = int(math.ceil(x))
        if necessidade_liquida >= minimo_mov:
            return necessidade_liquida
        else:
            return 0

    df_entrada['Liberado Para Receber'] = liberado_receber_float.apply(calcular_necessidade_minima)
    df_entrada['Estoque Alvo Desejado'] = estoque_alvo_desejado.round(4)
    df_entrada = df_entrada[df_entrada['Liberado Para Receber'] > 0].reset_index(drop=True)
    return df_entrada

# =============================================================================
# ETAPA 5 – BOTÃO PARA PROCESSAR RATEIO
# =============================================================================
st.header("5️⃣ Calcular Transferências")

if st.button("🚀 Calcular Transferências"):
    with st.spinner("Processando rateio, isso pode levar alguns instantes..."):
        df_saida_proc = df_saida.copy()
        df_entrada_proc = df_entrada.copy()

        minimo_saida = st.session_state.minimo_saida
        dias_estoque_entrada = st.session_state.dias_estoque_entrada
        minimo_mov = st.session_state.minimo_mov
        com_pedido = st.session_state.com_pedido

        # 1) Cálculo liberado para transferir
        df_saida_proc = calcular_liberado_para_transferir(
            df_saida_proc,
            minimo_saida=minimo_saida,
            minimo_mov=minimo_mov,
            com_pedido=com_pedido
        )

        # 2) Cálculo liberado para receber
        df_entrada_proc = calcular_liberado_para_receber(
            df_entrada_proc,
            dias_estoque_entrada=dias_estoque_entrada,
            minimo_mov=minimo_mov,
            com_pedido=com_pedido
        )

        if df_saida_proc.empty:
            st.error("Nenhuma loja de saída com 'Liberado Para Transferir' > 0 após os parâmetros definidos.")
            st.stop()

        if df_entrada_proc.empty:
            st.error("Nenhuma loja de entrada com 'Liberado Para Receber' > 0 após os parâmetros definidos.")
            st.stop()

        # DataFrame de resultado (apenas Loja a Loja)
        rateio_ll = pd.DataFrame(columns=[
            'Código Produto', 'Produto', 'Embal', 'Quantidade Para Transferir',
            'Loja Saída', 'Loja Entrada', 'Estoque Atual Loja Entrada',
            'Estoque Alvo Loja Entrada'
        ])

        # Mapa de produto
        df_base_local = st.session_state.df_base_tratada.copy()
        info_produto_map = df_base_local.drop_duplicates(subset=['Código Produto']).set_index('Código Produto')[['Produto', 'Embal']]
        info_produto_map = info_produto_map.to_dict('index')

        # Mapa de diagnóstico
        df_diag = df_base_local[['Loja', 'Código Produto', 'Quantidade Disponível', 'Média Vda/Dia']].copy()
        df_diag['Estoque Alvo Desejado'] = (df_diag['Média Vda/Dia'] * dias_estoque_entrada).round(4)
        df_diag.set_index(['Loja', 'Código Produto'], inplace=True)
        diag_map = df_diag.to_dict('index')

        # =======================
        # MÓDULO: Rateio Loja a Loja
        # =======================
        df_saida_ll_temp = df_saida_proc.copy()
        produtos_ll = df_saida_ll_temp['Código Produto'].unique()
        resultados_ll = []

        for produto in produtos_ll:
            lojas_saida_prod = df_saida_ll_temp[df_saida_ll_temp['Código Produto'] == produto].copy()
            lojas_entrada_prod = df_entrada_proc[df_entrada_proc['Código Produto'] == produto].copy()

            if lojas_saida_prod.empty or lojas_entrada_prod.empty:
                continue

            lojas_saida_prod.sort_values(by='Liberado Para Transferir', ascending=False, inplace=True)
            lojas_entrada_prod.sort_values(by='Liberado Para Receber', ascending=False, inplace=True)

            prod_info = info_produto_map.get(produto, {'Produto': '', 'Embal': ''})

            for _, loja_ent in lojas_entrada_prod.iterrows():
                loja_ent_nome = loja_ent['Loja']
                qtd_restante = int(loja_ent['Liberado Para Receber'])

                if qtd_restante <= 0:
                    continue

                lojas_saida_ativas = lojas_saida_prod[lojas_saida_prod['Liberado Para Transferir'] > 0].copy()

                for sai_idx, loja_sai in lojas_saida_ativas.iterrows():
                    loja_sai_nome = loja_sai['Loja']
                    qtd_disp_saida = loja_sai['Liberado Para Transferir']

                    if qtd_restante <= 0:
                        break

                    qtd_transferir = min(qtd_disp_saida, qtd_restante)

                    if qtd_transferir < minimo_mov:
                        continue

                    chave_diag = (loja_ent_nome, produto)
                    info_diag = diag_map.get(chave_diag, {})

                    resultados_ll.append({
                        'Código Produto': produto,
                        'Produto': prod_info.get('Produto', ''),
                        'Embal': prod_info.get('Embal', ''),
                        'Quantidade Para Transferir': int(qtd_transferir),
                        'Loja Saída': loja_sai_nome,
                        'Loja Entrada': loja_ent_nome,
                        'Estoque Atual Loja Entrada': info_diag.get('Quantidade Disponível', 0),
                        'Estoque Alvo Loja Entrada': info_diag.get('Estoque Alvo Desejado', 0)
                    })

                    qtd_restante -= qtd_transferir
                    df_saida_ll_temp.loc[sai_idx, 'Liberado Para Transferir'] -= qtd_transferir
                    lojas_saida_prod.loc[sai_idx, 'Liberado Para Transferir'] -= qtd_transferir

        if resultados_ll:
            rateio_ll = pd.DataFrame(resultados_ll)
            colunas_finais = [
                'Código Produto', 'Produto', 'Embal',
                'Quantidade Para Transferir', 'Loja Saída', 'Loja Entrada',
                'Estoque Atual Loja Entrada', 'Estoque Alvo Loja Entrada'
            ]
            rateio_ll = rateio_ll[colunas_finais]

        # =======================
        # PÓS-FILTRO: VERIFICA ATENDIMENTO TOTAL DA NECESSIDADE
        # =======================
        df_recebimento_total = pd.DataFrame()
        if not rateio_ll.empty:
            df_temp_ll = rateio_ll.groupby(['Loja Entrada', 'Código Produto'])[
                'Quantidade Para Transferir'
            ].sum().reset_index().rename(columns={'Quantidade Para Transferir': 'Qtd Recebida'})
            df_recebimento_total = pd.concat([df_recebimento_total, df_temp_ll])

        df_entrada_total_proc = df_entrada_proc.copy()

        if not df_recebimento_total.empty and not df_entrada_total_proc.empty:
            df_recebimento_total = df_recebimento_total.groupby(
                ['Loja Entrada', 'Código Produto']
            )['Qtd Recebida'].sum().reset_index()

            df_verificacao = pd.merge(
                df_entrada_total_proc[['Loja', 'Código Produto', 'Liberado Para Receber']],
                df_recebimento_total,
                left_on=['Loja', 'Código Produto'],
                right_on=['Loja Entrada', 'Código Produto'],
                how='left'
            ).fillna(0)

            df_verificacao['Diferenca'] = df_verificacao['Liberado Para Receber'] - df_verificacao['Qtd Recebida']
            lojas_para_remover = df_verificacao[df_verificacao['Diferenca'] > 0][['Loja', 'Código Produto']]
            chaves_remover = set(tuple(row) for row in lojas_para_remover.values)

            def filtro_final(df, coluna_loja):
                if df.empty:
                    return df
                df = df.copy()
                df['chave'] = list(zip(df[coluna_loja], df['Código Produto']))
                df_filtrado = df[~df['chave'].isin(chaves_remover)].drop(columns=['chave'])
                return df_filtrado

            rateio_ll = filtro_final(rateio_ll, 'Loja Entrada')

        # =======================
        # CÁLCULO DOS VALORES TOTAIS POR LOJA, COMPRADOR E LOJA ENTRADA
        # =======================
        map_custo = df_base_local.set_index(['Loja', 'Código Produto'])['Cto. Bruto Unitário'].to_dict()
        map_comprador = df_base_local.set_index(['Loja', 'Código Produto'])['Comprador'].to_dict()

        def adicionar_valores(df, campo_qtd='Quantidade Para Transferir'):
            if df.empty:
                return df.copy()
            df = df.copy()
            custos = []
            compradores = []
            valores = []

            for _, row in df.iterrows():
                loja_sai = row['Loja Saída']
                cod = row['Código Produto']
                qtd = row[campo_qtd]
                custo_unit = map_custo.get((loja_sai, cod), 0.0)
                comprador = map_comprador.get((loja_sai, cod), 'N/A')
                custos.append(custo_unit)
                compradores.append(comprador)
                valores.append(custo_unit * qtd)

            df['Cto. Bruto Unitário'] = custos
            df['Comprador'] = compradores
            df['Valor Transferência'] = valores
            return df

        if not rateio_ll.empty:
            rateio_ll = adicionar_valores(rateio_ll, campo_qtd='Quantidade Para Transferir')

        df_todas_saidas = pd.DataFrame()
        df_todas_entradas = pd.DataFrame()

        if not rateio_ll.empty:
            # Base para loja de saída + comprador
            df_todas_saidas = pd.concat([
                df_todas_saidas,
                rateio_ll[['Loja Saída', 'Comprador', 'Valor Transferência']]
            ])

            # Base para loja de entrada
            df_todas_entradas = pd.concat([
                df_todas_entradas,
                rateio_ll[['Loja Entrada', 'Valor Transferência']]
            ])

        if not df_todas_saidas.empty:
            df_todas_saidas['Valor Transferência'] = df_todas_saidas['Valor Transferência'].fillna(0.0)
        if not df_todas_entradas.empty:
            df_todas_entradas['Valor Transferência'] = df_todas_entradas['Valor Transferência'].fillna(0.0)

        # Total por comprador
        if not df_todas_saidas.empty:
            df_valor_por_comprador = (
                df_todas_saidas
                .groupby('Comprador', as_index=False)['Valor Transferência']
                .sum()
                .rename(columns={'Valor Transferência': 'Valor Total Transferência'})
            )
        else:
            df_valor_por_comprador = pd.DataFrame(columns=['Comprador', 'Valor Total Transferência'])

        # Total por loja de saída
        if not df_todas_saidas.empty:
            df_valor_por_loja_saida = (
                df_todas_saidas
                .groupby('Loja Saída', as_index=False)['Valor Transferência']
                .sum()
                .rename(columns={'Valor Transferência': 'Valor Total Transferência'})
            )
        else:
            df_valor_por_loja_saida = pd.DataFrame(columns=['Loja Saída', 'Valor Total Transferência'])

        # Total por loja de entrada
        if not df_todas_entradas.empty:
            df_valor_por_loja_entrada = (
                df_todas_entradas
                .groupby('Loja Entrada', as_index=False)['Valor Transferência']
                .sum()
                .rename(columns={'Valor Transferência': 'Valor Total Transferência'})
            )
        else:
            df_valor_por_loja_entrada = pd.DataFrame(columns=['Loja Entrada', 'Valor Total Transferência'])

        df_parametros = pd.DataFrame({
            'Parâmetro': [
                'Dias Estoque Mínimo (Saída)',
                'Dias Estoque Alvo (Entrada)',
                'Qtd Mínima para Movimentar',
                'Considera Pedido Pendente',
                'Modalidade'
            ],
            'Valor': [
                minimo_saida,
                dias_estoque_entrada,
                minimo_mov,
                com_pedido,
                'Loja a Loja'
            ]
        })

        st.session_state.resultado_rateio = {
            "df_saida": df_saida_proc,
            "rateio_ll": rateio_ll,
            "df_entrada": df_entrada_total_proc,
            "df_valor_por_comprador": df_valor_por_comprador,
            "df_valor_por_loja_saida": df_valor_por_loja_saida,
            "df_valor_por_loja_entrada": df_valor_por_loja_entrada,
            "df_parametros": df_parametros
        }

    st.success("Rateio Loja a Loja processado com sucesso! Veja abaixo os resultados e faça o download do Excel.")

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
