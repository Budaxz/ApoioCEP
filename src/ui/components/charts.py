"""Componentes de visualização gráfica interativa com Plotly para clima, risco e complexidade."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.mathematics.permutations import generate_complexity_comparison_table
from src.ui.theme import RISK_COLORS_HEX

_LEVEL_COLOR_BY_STR: dict[str, str] = {
    level.value: hex_color for level, hex_color in RISK_COLORS_HEX.items()
}


def build_weather_timeline_figure(
    weather_df: pd.DataFrame,
    title: str = "Previsão Horária: Precipitação, Média Móvel (3h) e Temperatura",
) -> go.Figure:
    """Constrói figura Plotly com precipitação horária, média móvel de 3h e temperatura.

    Args:
        weather_df: DataFrame gerado por `weather_to_dataframe`.
        title: Título exibido no topo do gráfico.

    Returns:
        Instância de `go.Figure` pronta para renderização ou inspeção em testes.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if weather_df.empty:
        fig.update_layout(
            title=title,
            template="plotly_white",
            height=380,
            annotations=[
                {
                    "text": "Sem dados meteorológicos horários disponíveis.",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 14, "color": "#64748B"},
                }
            ],
        )
        return fig

    x_axis = weather_df["Hora"] if "Hora" in weather_df.columns else weather_df.index

    fig.add_trace(
        go.Bar(
            x=x_axis,
            y=weather_df["Precipitacao_mm"],
            name="Precipitação (mm/h)",
            marker_color="rgba(59, 130, 246, 0.55)",
            customdata=weather_df["Prob_Chuva_Pct"]
            if "Prob_Chuva_Pct" in weather_df.columns
            else None,
            hovertemplate=(
                "<b>Hora:</b> %{x}<br>"
                "<b>Chuva:</b> %{y:.1f} mm<br>"
                "<b>Probabilidade:</b> %{customdata:.0f}%<extra></extra>"
            ),
        ),
        secondary_y=False,
    )

    if "Precipitacao_Media_Movel_3h" in weather_df.columns:
        fig.add_trace(
            go.Scatter(
                x=x_axis,
                y=weather_df["Precipitacao_Media_Movel_3h"],
                name="Média Móvel Chuva (3h)",
                mode="lines+markers",
                line={"color": "#1D4ED8", "width": 2.5, "dash": "dash"},
                hovertemplate="<b>Hora:</b> %{x}<br><b>Média Móvel (3h):</b> %{y:.2f} mm<extra></extra>",
            ),
            secondary_y=False,
        )

    if "Temperatura_C" in weather_df.columns:
        fig.add_trace(
            go.Scatter(
                x=x_axis,
                y=weather_df["Temperatura_C"],
                name="Temperatura (°C)",
                mode="lines+markers",
                line={"color": "#F97316", "width": 2.5},
                hovertemplate="<b>Hora:</b> %{x}<br><b>Temperatura:</b> %{y:.1f} °C<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_layout(
        title={"text": title, "font": {"size": 16}},
        template="plotly_white",
        height=400,
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1.0,
        },
        margin={"l": 40, "r": 40, "t": 70, "b": 40},
    )
    fig.update_xaxes(title_text="Horário Previsto")
    fig.update_yaxes(title_text="Precipitação (mm)", secondary_y=False, rangemode="tozero")
    fig.update_yaxes(title_text="Temperatura (°C)", secondary_y=True)

    return fig


def build_stop_risk_bar_figure(stops_df: pd.DataFrame) -> go.Figure:
    """Constrói gráfico de barras do score de risco climático por parada na ordem otimizada.

    Args:
        stops_df: DataFrame gerado por `stops_to_dataframe`.

    Returns:
        Instância de `go.Figure` com barras coloridas conforme `Nivel_Risco`.
    """
    fig = go.Figure()

    if stops_df.empty:
        fig.update_layout(
            title="Score de Risco Climático por Parada da Rota",
            template="plotly_white",
            height=360,
        )
        return fig

    labels = [
        f"{row['Ordem']}. {row['Destinatario']}"
        for _, row in stops_df.iterrows()
    ]
    colors = [
        _LEVEL_COLOR_BY_STR.get(str(row["Nivel_Risco"]), "#64748B")
        for _, row in stops_df.iterrows()
    ]
    custom_data = list(
        zip(
            stops_df["CEP"],
            stops_df["Bairro"],
            stops_df["Distancia_Acumulada_km"],
            stops_df["Chuva_Max_mm"],
            stops_df["Nivel_Risco"],
            strict=False,
        )
    )

    fig.add_trace(
        go.Bar(
            x=labels,
            y=stops_df["Score_Risco"],
            marker_color=colors,
            text=[f"{val:.2f}" for val in stops_df["Score_Risco"]],
            textposition="outside",
            customdata=custom_data,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Score de Risco: %{y:.2f} (%{customdata[4]})<br>"
                "CEP: %{customdata[0]} — %{customdata[1]}<br>"
                "Distância Acumulada: %{customdata[2]:.2f} km<br>"
                "Chuva Máx Prevista: %{customdata[3]:.1f} mm/h<extra></extra>"
            ),
            name="Score de Risco",
        )
    )

    fig.update_layout(
        title={"text": "Score de Risco Climático por Parada na Sequência Otimizada", "font": {"size": 16}},
        template="plotly_white",
        height=380,
        xaxis_title="Ordem de Visitação e Destinatário",
        yaxis={"title": "Score de Risco (0.0 a 1.0)", "range": [0.0, 1.12]},
        margin={"l": 40, "r": 30, "t": 60, "b": 60},
        showlegend=False,
    )

    return fig


def build_complexity_comparison_figure(max_n: int = 10) -> go.Figure:
    """Constrói gráfico comparativo em escala logarítmica entre $O(n!)$ e $O(n^2)$.

    Args:
        max_n: Número máximo de paradas $n$ para simulação combinatória.

    Returns:
        Instância de `go.Figure` comparando permutações exatas e operações heurísticas.
    """
    records = generate_complexity_comparison_table(max_n=max_n)
    n_values = [int(r["n"]) for r in records]
    factorial_ops = [int(r["permutacoes_fatorial"]) for r in records]
    quadratic_ops = [int(r["operacoes_heuristica_n2"]) for r in records]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=n_values,
            y=factorial_ops,
            mode="lines+markers",
            name="Força Bruta Exata: P_n = n! (O(n!))",
            line={"color": "#EF4444", "width": 3},
            marker={"size": 8},
            hovertemplate="<b>n = %{x} paradas</b><br>Permutações (n!): %{y:,}<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=n_values,
            y=quadratic_ops,
            mode="lines+markers",
            name="Heurística Vizinho Mais Próximo: O(n²)",
            line={"color": "#10B981", "width": 3, "dash": "dot"},
            marker={"size": 8},
            hovertemplate="<b>n = %{x} paradas</b><br>Operações Heurísticas (n²): %{y:,}<extra></extra>",
        )
    )

    fig.update_layout(
        title={
            "text": "Explosão Combinatória O(n!) vs Heurística Polinomial O(n²) (Escala Log)",
            "font": {"size": 16},
        },
        template="plotly_white",
        height=400,
        xaxis={"title": "Número de Paradas de Entrega (n)", "dtick": 1},
        yaxis={"title": "Operações / Sequências Avaliadas (Escala Log₁₀)", "type": "log"},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1.0,
        },
        margin={"l": 50, "r": 30, "t": 70, "b": 45},
    )

    return fig


def render_weather_timeline_chart(
    weather_df: pd.DataFrame,
    title: str = "Previsão Horária: Precipitação, Média Móvel (3h) e Temperatura",
) -> None:
    """Renderiza o gráfico de linha do tempo meteorológica no Streamlit."""
    st.plotly_chart(build_weather_timeline_figure(weather_df, title=title), use_container_width=True)


def render_stop_risk_chart(stops_df: pd.DataFrame) -> None:
    """Renderiza o gráfico de barras de risco climático por parada no Streamlit."""
    st.plotly_chart(build_stop_risk_bar_figure(stops_df), use_container_width=True)


def render_complexity_chart(max_n: int = 10) -> None:
    """Renderiza o gráfico de crescimento fatorial vs polinomial no Streamlit."""
    st.plotly_chart(build_complexity_comparison_figure(max_n=max_n), use_container_width=True)
