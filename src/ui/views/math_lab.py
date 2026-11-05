"""Laboratório interativo de Matemática Computacional Aplicada (Projeto A3)."""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from src.domain.delivery import DeliveryStop
from src.mathematics.permutations import (
    calculate_factorial,
    generate_complexity_comparison_table,
    solve_tsp_brute_force,
)
from src.mathematics.risk_matrix import (
    calculate_weighted_edge_cost,
    evaluate_stops_risk,
)
from src.mathematics.routing import build_optimized_route
from src.ui.components.charts import render_complexity_chart


def render_math_lab_view(
    origin: DeliveryStop,
    stops: list[DeliveryStop],
    alpha: float,
) -> None:
    """Renderiza o laboratório didático interativo de Matemática Computacional Aplicada.

    Demonstra na prática os fundamentos estudados na disciplina com os professores
    Aron e Cristiano:
    1. Princípios de Contagem e Permutação Simples ($P_n = n!$) vs Complexidade $O(n^2)$.
    2. Benchmark ao vivo entre Busca Exata por Força Bruta ($O(n!)$) e Heurística *2-Opt*.
    3. Geometria no Espaço Métrico Esférico (Haversine) e Custo de Aresta Ponderado pelo Clima.

    Args:
        origin: Ponto de partida (Centro de Distribuição).
        stops: Lista de paradas de entrega cadastradas.
        alpha: Coeficiente de aversão ao risco climático ($\\alpha$).
    """
    st.markdown("### Análise Matemática Aplicada (Amostra A3)")
    st.caption(
        "Demonstração formal e experimental dos modelos matemáticos implementados no motor do "
        "ApoioCEP — Disciplina dos Professores Aron e Cristiano (UniCuritiba)."
    )

    # =========================================================================
    # SEÇÃO 1 — Princípios de Contagem e Permutação Fatorial (P_n = n!)
    # =========================================================================
    st.markdown("#### 1. Princípios de Contagem e Explosão Combinatória ($P_n = n!$)")
    st.latex(
        r"P_n = n! = \prod_{k=1}^{n} k = n \times (n - 1) \times (n - 2) \times \dots \times 1"
    )
    st.markdown(
        "Em um roteiro com $n$ entregas distintas partindo de um Centro de Distribuição fixo, "
        "o espaço amostral $\\mathcal{S}_n$ de sequências possíveis possui cardinalidade "
        "$|\\mathcal{S}_n| = n!$. Compare abaixo o crescimento fatorial $O(n!)$ da enumeração "
        "exaustiva frente à complexidade polinomial $O(n^2)$ da Heurística do Vizinho Mais Próximo."
    )

    max_n = st.slider(
        "Simular tamanho máximo do roteiro (n paradas) para análise assintótica:",
        min_value=4,
        max_value=12,
        value=10,
        step=1,
        key="math_lab_max_n_slider",
    )

    comp_col1, comp_col2 = st.columns([3, 2], gap="large")
    with comp_col1:
        render_complexity_chart(max_n=max_n)
    with comp_col2:
        table_records = generate_complexity_comparison_table(max_n=max_n)
        comp_df = pd.DataFrame(table_records).rename(
            columns={
                "n": "Paradas (n)",
                "permutacoes_fatorial": "Permutações (n!)",
                "operacoes_heuristica_n2": "Operações O(n²)",
                "tempo_forca_bruta_ms": "Tempo Força Bruta (ms)",
            }
        )
        st.dataframe(comp_df, use_container_width=True, hide_index=True, height=380)

    st.divider()

    # =========================================================================
    # SEÇÃO 2 — Benchmark Ao Vivo: Força Bruta O(n!) vs Heurística 2-Opt O(n²)
    # =========================================================================
    st.markdown(
        "#### 2. Benchmark Ao Vivo: Força Bruta Exata ($O(n!)$) vs Heurística *Nearest Neighbor + 2-Opt* ($O(n^2)$)"
    )
    st.latex(
        r"\pi^* = \arg\min_{\pi \in \mathcal{S}_n} \left( C_{\text{origem}, \pi(1)} + \sum_{k=1}^{n-1} C_{\pi(k), \pi(k+1)} \right)"
    )

    n_current = len(stops)
    if n_current == 0:
        st.info("Cadastre ao menos 1 parada no Planejador para executar o benchmark comparativo.")
    elif n_current <= 8:
        exact_plan = solve_tsp_brute_force(origin, stops, alpha=alpha)
        heuristic_plan = build_optimized_route(origin, stops, alpha=alpha, use_2opt=True)

        exact_dist = exact_plan.total_distance_km
        heur_dist = heuristic_plan.total_distance_km
        gap_pct = (
            ((heur_dist - exact_dist) / exact_dist * 100.0)
            if exact_dist > 0.0
            else 0.0
        )

        b_col1, b_col2, b_col3, b_col4 = st.columns(4)
        with b_col1:
            st.metric(
                label="Distância Ótima Exata (Força Bruta)",
                value=f"{exact_dist:.2f} km",
                delta=f"{exact_plan.total_permutations_possible:,} rotas testadas",
                delta_color="off",
            )
        with b_col2:
            st.metric(
                label="Distância Heurística (NN + 2-Opt)",
                value=f"{heur_dist:.2f} km",
                delta=f"Gap de otimalidade: {gap_pct:+.2f}%",
                delta_color="off" if abs(gap_pct) < 1e-4 else "inverse",
            )
        with b_col3:
            st.metric(
                label="Espaço Combinatório vs Polinomial",
                value=f"{calculate_factorial(n_current):,} vs {n_current**2}",
                delta=f"n = {n_current} paradas (n! vs n²)",
                delta_color="off",
            )
        with b_col4:
            st.metric(
                label="Tempo de Execução (Exato vs 2-Opt)",
                value=f"{heuristic_plan.computation_time_ms:.2f} ms",
                delta=f"Força Bruta: {exact_plan.computation_time_ms:.2f} ms",
                delta_color="off",
            )

        seq_col1, seq_col2 = st.columns(2)
        with seq_col1:
            exact_seq_str = " -> ".join(
                ["Origem", *[f"{s.id} ({s.address.bairro})" for s in exact_plan.ordered_stops]]
            )
            st.markdown(f"**Sequência Ótima Global ($O(n!)$):**  \n`{exact_seq_str}`")
        with seq_col2:
            heur_seq_str = " -> ".join(
                ["Origem", *[f"{s.id} ({s.address.bairro})" for s in heuristic_plan.ordered_stops]]
            )
            st.markdown(f"**Sequência Heurística (*NN + 2-Opt*):**  \n`{heur_seq_str}`")
    else:
        st.warning(
            f"O roteiro atual possui **{n_current} paradas** "
            f"($P_{{{n_current}}} = {calculate_factorial(n_current):,}$ permutações). "
            "Por governança de segurança computacional, a enumeração exaustiva por Força Bruta "
            "é bloqueada para $n > 8$, operando exclusivamente com a Heurística Polinomial *2-Opt*."
        )

    st.divider()

    # =========================================================================
    # SEÇÃO 3 — Espaço Métrico (Haversine) e Custo de Aresta Ponderado
    # =========================================================================
    st.markdown(
        "#### 3. Espaço Métrico Geodésico (Haversine) e Custo de Aresta Ponderado pelo Clima"
    )
    st.latex(
        r"d_{a,b} = 2R \cdot \arctan2\left(\sqrt{a}, \sqrt{1 - a}\right), \quad "
        r"a = \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_a)\cos(\phi_b)\sin^2\left(\frac{\Delta \lambda}{2}\right)"
    )
    st.latex(
        r"C_{a,b}(\alpha) = d_{a,b} \cdot (1 + \alpha \cdot R_b), \quad "
        r"R_b = 0{,}50 \cdot f_{\text{rain}} + 0{,}30 \cdot f_{\text{wind}} + 0{,}20 \cdot f_{\text{prio}}"
    )

    evaluated_all: list[DeliveryStop] = evaluate_stops_risk([origin, *stops])
    node_map: dict[str, DeliveryStop] = {
        f"{node.id} — {node.recipient_name} ({node.address.bairro})": node
        for node in evaluated_all
    }
    node_keys = list(node_map.keys())

    sel_col1, sel_col2 = st.columns(2)
    with sel_col1:
        key_a = st.selectbox(
            "Vértice de Partida (Ponto A):",
            options=node_keys,
            index=0,
            key="math_lab_node_a",
        )
    with sel_col2:
        key_b = st.selectbox(
            "Vértice de Destino (Ponto B):",
            options=node_keys,
            index=min(1, len(node_keys) - 1),
            key="math_lab_node_b",
        )

    resolved_key_a = key_a if key_a is not None else node_keys[0]
    resolved_key_b = key_b if key_b is not None else node_keys[min(1, len(node_keys) - 1)]
    stop_a = node_map[resolved_key_a]
    stop_b = node_map[resolved_key_b]
    coords_a = stop_a.address.coordinates
    coords_b = stop_b.address.coordinates

    if coords_a is not None and coords_b is not None:
        phi1 = math.radians(coords_a.latitude)
        phi2 = math.radians(coords_b.latitude)
        delta_phi = math.radians(coords_b.latitude - coords_a.latitude)
        delta_lambda = math.radians(coords_b.longitude - coords_a.longitude)

        distance_km = coords_a.distance_to(coords_b)
        risk_b = stop_b.risk_score
        penalty_multiplier = round(1.0 + alpha * risk_b, 4)
        edge_cost = calculate_weighted_edge_cost(stop_a, stop_b, alpha=alpha)

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.metric(
                label="Distância Geodésica (d_a,b)",
                value=f"{distance_km:.4f} km",
                delta=f"Δφ={delta_phi:.4f} rad | Δλ={delta_lambda:.4f} rad",
                delta_color="off",
            )
        with m_col2:
            st.metric(
                label="Score de Risco no Destino (R_b)",
                value=f"{risk_b:.4f}",
                delta=f"Nível: {stop_b.risk_level.value}",
                delta_color="off",
            )
        with m_col3:
            st.metric(
                label=f"Fator de Penalização (1 + α·R_b, α={alpha:.1f})",
                value=f"{penalty_multiplier:.4f}×",
                delta=f"+{(penalty_multiplier - 1.0) * 100.0:.1f}% sobre a distância",
                delta_color="off",
            )
        with m_col4:
            st.metric(
                label="Custo Final da Aresta (C_a,b)",
                value=f"{edge_cost:.4f}",
                delta="Unidades equivalentes de km",
                delta_color="off",
            )

        with st.container(border=True):
            st.markdown(
                f"**Memória de Cálculo Passo a Passo ({stop_a.id} $\\to$ {stop_b.id}):**\n"
                f"- **Coordenada A ({stop_a.address.bairro}):** "
                f"$\\phi_a = {coords_a.latitude:.4f}^\\circ$ (`{phi1:.4f} rad`), "
                f"$\\lambda_a = {coords_a.longitude:.4f}^\\circ$\n"
                f"- **Coordenada B ({stop_b.address.bairro}):** "
                f"$\\phi_b = {coords_b.latitude:.4f}^\\circ$ (`{phi2:.4f} rad`), "
                f"$\\lambda_b = {coords_b.longitude:.4f}^\\circ$\n"
                f"- **Distância Haversine ($R = 6371\\text{{ km}}$):** "
                f"$d_{{a,b}} = {distance_km:.4f}\\text{{ km}}$\n"
                f"- **Custo Ponderado da Aresta:** "
                f"$C_{{a,b}} = {distance_km:.4f} \\times (1 + {alpha:.2f} \\times {risk_b:.4f}) "
                f"= \\mathbf{{{edge_cost:.4f}}}$"
            )
    else:
        st.warning("Coordenadas ausentes em um dos pontos selecionados.")
