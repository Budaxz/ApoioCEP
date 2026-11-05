"""Camada de Matemática Computacional Aplicada do projeto ApoioCEP.

Reúne os módulos de Análise Combinatória ($P_n = n!$), Matriz Probabilística de
Risco Climático ($R_{i,t}$) e Otimização Heurística de Rotas (*Nearest Neighbor* + *2-Opt*).
"""

from src.mathematics.permutations import (
    calculate_factorial,
    estimate_brute_force_time_ms,
    generate_complexity_comparison_table,
    solve_tsp_brute_force,
)
from src.mathematics.risk_matrix import (
    calculate_weighted_edge_cost,
    compute_stop_risk_score,
    evaluate_stops_risk,
    parse_delivery_window_hours,
)
from src.mathematics.routing import (
    build_optimized_route,
    calculate_route_distance,
    optimize_route_nearest_neighbor,
    refine_route_2opt,
)

__all__ = [
    "build_optimized_route",
    "calculate_factorial",
    "calculate_route_distance",
    "calculate_weighted_edge_cost",
    "compute_stop_risk_score",
    "estimate_brute_force_time_ms",
    "evaluate_stops_risk",
    "generate_complexity_comparison_table",
    "optimize_route_nearest_neighbor",
    "parse_delivery_window_hours",
    "refine_route_2opt",
    "solve_tsp_brute_force",
]
