"""Algoritmos heurísticos de roteirização logística (Nearest Neighbor $O(n^2)$ e 2-Opt).

Este módulo implementa a transição da complexidade fatorial $O(n!)$ para heurísticas
polinomiais $O(n^2)$ ponderadas pelo risco climático:

1. **Vizinho Mais Próximo (*Nearest Neighbor*):** Seleção iterativa gulosa que escolhe,
   a partir do vértice atual $u$, o próximo vértice não visitado $v^*$ que minimiza o
   custo ponderado:
   $$v^* = \\arg\\min_{v \\in U} d_{u,v} \\cdot (1 + \\alpha \\cdot R_v)$$
2. **Refinamento Local *2-Opt*:** Operador de busca local que elimina cruzamentos
   geométricos invertendo subsegmentos $[i, k]$ da rota sempre que houver redução
   estrita no custo ponderado acumulado.
"""

from __future__ import annotations

import time

from src.domain.delivery import DeliveryStop, RoutePlan
from src.mathematics.permutations import calculate_factorial
from src.mathematics.risk_matrix import calculate_weighted_edge_cost, evaluate_stops_risk


def calculate_route_distance(
    origin: DeliveryStop,
    ordered_stops: list[DeliveryStop],
) -> float:
    """Calcula a distância geodésica real (Haversine) acumulada ao longo da rota.

    Percorre sequencialmente `origin -> ordered_stops[0] -> ... -> ordered_stops[-1]`
    somando as distâncias em quilômetros entre coordenadas válidas.

    Args:
        origin: Ponto de partida da rota.
        ordered_stops: Sequência ordenada de paradas de entrega.

    Returns:
        Distância total em quilômetros arredondada em 4 casas decimais.
    """
    if not ordered_stops:
        return 0.0

    total_distance = 0.0
    current = origin
    for stop in ordered_stops:
        coords_curr = current.address.coordinates
        coords_next = stop.address.coordinates
        if coords_curr is not None and coords_next is not None:
            total_distance += coords_curr.distance_to(coords_next)
        current = stop

    return round(total_distance, 4)


def _calculate_total_weighted_cost(
    origin: DeliveryStop,
    ordered_stops: list[DeliveryStop],
    alpha: float,
) -> float:
    """Calcula a soma dos custos ponderados das arestas ao longo de toda a sequência."""
    if not ordered_stops:
        return 0.0

    total_cost = calculate_weighted_edge_cost(origin, ordered_stops[0], alpha=alpha)
    for idx in range(len(ordered_stops) - 1):
        total_cost += calculate_weighted_edge_cost(
            ordered_stops[idx],
            ordered_stops[idx + 1],
            alpha=alpha,
        )
    return total_cost


def optimize_route_nearest_neighbor(
    origin: DeliveryStop,
    stops: list[DeliveryStop],
    alpha: float = 0.5,
) -> list[DeliveryStop]:
    """Constrói uma rota usando a Heurística Gulosa do Vizinho Mais Próximo ($O(n^2)$).

    A cada passo, seleciona dentre os pontos ainda não visitados $U$ aquele que minimiza
    o custo de transição ponderado pelo risco climático:

        $$v_{\\text{next}} = \\arg\\min_{v \\in U} C_{\\text{current}, v}(\\alpha)$$

    Args:
        origin: Ponto de partida (Centro de Distribuição).
        stops: Lista de paradas a serem roteirizadas.
        alpha: Coeficiente de penalização por risco climático (padrão `0.5`).

    Returns:
        Nova lista de `DeliveryStop` ordenada pela heurística construtiva.
    """
    if not stops:
        return []

    unvisited: list[DeliveryStop] = list(stops)
    ordered: list[DeliveryStop] = []
    current = origin

    while unvisited:
        best_idx = min(
            range(len(unvisited)),
            key=lambda idx: calculate_weighted_edge_cost(current, unvisited[idx], alpha=alpha),
        )
        next_stop = unvisited.pop(best_idx)
        ordered.append(next_stop)
        current = next_stop

    return ordered


def refine_route_2opt(
    origin: DeliveryStop,
    stops: list[DeliveryStop],
    alpha: float = 0.5,
    max_iterations: int = 100,
) -> list[DeliveryStop]:
    """Refina uma rota existente aplicando o operador de busca local *2-Opt*.

    Testa iterativamente a inversão de todos os subsegmentos contíguos `route[i : k + 1]`
    ($0 \\le i < k < n$). Se a rota resultante apresentar menor custo ponderado total,
    a troca de arestas é aceita, eliminando cruzamentos geométricos e convergindo para
    um ótimo local.

    Args:
        origin: Ponto de partida fixo da rota.
        stops: Sequência inicial de paradas de entrega.
        alpha: Coeficiente de penalização por risco climático (padrão `0.5`).
        max_iterations: Limite máximo de varreduras completas de melhoria (padrão `100`).

    Returns:
        Lista de `DeliveryStop` refinada pelo algoritmo *2-Opt*.
    """
    n = len(stops)
    if n < 2 or max_iterations <= 0:
        return list(stops)

    best_route = list(stops)
    best_cost = _calculate_total_weighted_cost(origin, best_route, alpha=alpha)

    iteration = 0
    improved = True

    while improved and iteration < max_iterations:
        improved = False
        iteration += 1

        for i in range(n - 1):
            for k in range(i + 1, n):
                candidate = (
                    best_route[:i]
                    + list(reversed(best_route[i : k + 1]))
                    + best_route[k + 1 :]
                )
                candidate_cost = _calculate_total_weighted_cost(origin, candidate, alpha=alpha)
                if candidate_cost + 1e-9 < best_cost:
                    best_route = candidate
                    best_cost = candidate_cost
                    improved = True

    return best_route


def build_optimized_route(
    origin: DeliveryStop,
    stops: list[DeliveryStop],
    alpha: float = 0.5,
    use_2opt: bool = True,
) -> RoutePlan:
    """Executa o pipeline completo de avaliação de risco e otimização heurística da rota.

    Etapas do pipeline:
    1. Avalia e atualiza o índice de risco climático (`risk_score` e `risk_level`) da
       origem e de todas as paradas via `evaluate_stops_risk`.
    2. Constrói a rota inicial com `optimize_route_nearest_neighbor` ($O(n^2)$).
    3. Caso `use_2opt=True` e `len(stops) >= 3`, aplica o refinamento `refine_route_2opt`.
    4. Consolida distância real Haversine, risco médio, cardinalidade fatorial $n!$ e
       tempo de computação em um objeto `RoutePlan`.

    Args:
        origin: Ponto de partida (Centro de Distribuição).
        stops: Lista de paradas de entrega.
        alpha: Coeficiente de aversão ao risco climático (padrão `0.5`).
        use_2opt: Define se o refinamento local *2-Opt* deve ser aplicado (padrão `True`).

    Returns:
        Objeto `RoutePlan` completo e validado.
    """
    start_time = time.perf_counter()

    evaluated_origin = evaluate_stops_risk([origin])[0]
    evaluated_stops = evaluate_stops_risk(stops)

    ordered = optimize_route_nearest_neighbor(evaluated_origin, evaluated_stops, alpha=alpha)
    if use_2opt and len(ordered) >= 3:
        ordered = refine_route_2opt(evaluated_origin, ordered, alpha=alpha)

    total_distance = calculate_route_distance(evaluated_origin, ordered)
    avg_risk = (
        round(sum(stop.risk_score for stop in ordered) / len(ordered), 4)
        if ordered
        else 0.0
    )
    total_perms = max(1, calculate_factorial(len(ordered)))
    algorithm_name = "nearest_neighbor_2opt" if use_2opt else "nearest_neighbor"
    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 4)

    return RoutePlan(
        origin=evaluated_origin,
        ordered_stops=ordered,
        total_distance_km=total_distance,
        average_risk_score=avg_risk,
        algorithm_used=algorithm_name,
        total_permutations_possible=total_perms,
        computation_time_ms=elapsed_ms,
    )
