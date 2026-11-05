"""Princípios de contagem, análise combinatória ($P_n = n!$) e busca exata por força bruta.

Este módulo implementa os fundamentos combinatórios para o Problema do Caixeiro Viajante
(TSP) aplicado à logística de entregas:

1. Permutação simples de $n$ paradas distintas:
   $$P_n = n! = n \\times (n - 1) \\times (n - 2) \\times \\dots \\times 1$$
2. Comparação assintótica entre a explosão combinatória $O(n!)$ da força bruta e a
   complexidade polinomial $O(n^2)$ da Heurística do Vizinho Mais Próximo.
3. Solucionador exato por enumeração exaustiva para instâncias didáticas ($n \\le 8$).
"""

from __future__ import annotations

import itertools
import math
import time

from src.domain.delivery import DeliveryStop, RoutePlan
from src.mathematics.risk_matrix import calculate_weighted_edge_cost, evaluate_stops_risk

_MAX_BRUTE_FORCE_STOPS = 8


def calculate_factorial(n: int) -> int:
    """Calcula o número de permutações simples $P_n = n!$ para $n$ pontos de entrega.

    Fórmula matemática:
        $$P_n = n! = \\prod_{k=1}^{n} k, \\quad \\text{com } 0! = 1$$

    Args:
        n: Número inteiro não-negativo de pontos de entrega.

    Returns:
        O fatorial $n!$ representando o total de sequências possíveis de visitação.

    Raises:
        ValueError: Se `n < 0`.
    """
    if n < 0:
        raise ValueError(f"O número de paradas n deve ser não-negativo (recebido: {n}).")
    return math.factorial(n)


def estimate_brute_force_time_ms(n: int, ops_per_ms: float = 1500.0) -> float:
    """Estima o tempo computacional (em milissegundos) para avaliar $n!$ rotas por força bruta.

    Modelo linear de tempo de execução:
        $$T(n) = \\frac{P_n}{\\text{ops\\_per\\_ms}} = \\frac{n!}{\\text{ops\\_per\\_ms}}$$

    Args:
        n: Número de paradas de entrega ($n \\ge 0$).
        ops_per_ms: Quantidade média de permutações avaliadas por milissegundo (padrão `1500.0`).

    Returns:
        Tempo estimado em milissegundos arredondado em 4 casas decimais.

    Raises:
        ValueError: Se `n < 0` ou `ops_per_ms <= 0`.
    """
    if ops_per_ms <= 0.0:
        raise ValueError("A taxa ops_per_ms deve ser estritamente positiva.")
    perms = calculate_factorial(n)
    return round(perms / ops_per_ms, 4)


def generate_complexity_comparison_table(
    max_n: int = 12,
) -> list[dict[str, int | float | str]]:
    """Gera tabela comparativa entre crescimento fatorial $O(n!)$ e heurística polinomial $O(n^2)$.

    Args:
        max_n: Valor máximo de $n$ na tabela (de `1` até `max_n`, inclusive).

    Returns:
        Lista de dicionários contendo `n`, `permutacoes_fatorial`,
        `operacoes_heuristica_n2` e `tempo_forca_bruta_ms`.

    Raises:
        ValueError: Se `max_n < 1`.
    """
    if max_n < 1:
        raise ValueError(f"O parâmetro max_n deve ser pelo menos 1 (recebido: {max_n}).")

    table: list[dict[str, int | float | str]] = []
    for n in range(1, max_n + 1):
        table.append(
            {
                "n": n,
                "permutacoes_fatorial": calculate_factorial(n),
                "operacoes_heuristica_n2": n**2,
                "tempo_forca_bruta_ms": estimate_brute_force_time_ms(n),
            }
        )
    return table


def _sequence_weighted_cost(
    origin: DeliveryStop,
    sequence: tuple[DeliveryStop, ...] | list[DeliveryStop],
    alpha: float,
) -> float:
    """Calcula o custo ponderado acumulado ao longo de uma sequência de paradas."""
    if not sequence:
        return 0.0

    total_cost = calculate_weighted_edge_cost(origin, sequence[0], alpha=alpha)
    for idx in range(len(sequence) - 1):
        total_cost += calculate_weighted_edge_cost(sequence[idx], sequence[idx + 1], alpha=alpha)
    return total_cost


def _sequence_real_distance_km(
    origin: DeliveryStop,
    sequence: list[DeliveryStop],
) -> float:
    """Calcula a distância geodésica real (Haversine) total da sequência em km."""
    if not sequence:
        return 0.0

    total_km = 0.0
    current = origin
    for stop in sequence:
        if current.address.coordinates is not None and stop.address.coordinates is not None:
            total_km += current.address.coordinates.distance_to(stop.address.coordinates)
        current = stop
    return round(total_km, 4)


def solve_tsp_brute_force(
    origin: DeliveryStop,
    stops: list[DeliveryStop],
    alpha: float = 0.5,
) -> RoutePlan:
    """Resolve o roteamento de entregas de forma exata por enumeração de todas as permutações $n!$.

    Avalia exaustivamente o espaço de busca $\\mathcal{S}_n$ de cardinalidade $|\\mathcal{S}_n| = n!$,
    encontrando a permutação $\\pi^* \\in \\mathcal{S}_n$ que minimiza a função objetivo ponderada:

        $$\\pi^* = \\arg\\min_{\\pi \\in \\mathcal{S}_n} \\left( C_{\\text{origin}, \\pi(1)} + \\sum_{k=1}^{n-1} C_{\\pi(k), \\pi(k+1)} \\right)$$

    Por segurança computacional contra explosão combinatória, este método é restrito a
    instâncias com $n \\le 8$ paradas ($8! = 40.320$ permutações).

    Args:
        origin: Ponto de partida (Centro de Distribuição).
        stops: Lista de paradas de entrega ($n \\le 8$).
        alpha: Coeficiente de aversão ao risco climático nas arestas (padrão `0.5`).

    Returns:
        Instância de `RoutePlan` contendo a rota ótima global exata e métricas associadas.

    Raises:
        ValueError: Se `len(stops) > 8`.
    """
    n_stops = len(stops)
    if n_stops > _MAX_BRUTE_FORCE_STOPS:
        raise ValueError(
            f"Busca por força bruta limitada a {_MAX_BRUTE_FORCE_STOPS} paradas para evitar "
            f"explosão combinatória O(n!). Recebido: {n_stops} paradas ({calculate_factorial(n_stops)} permutações)."
        )

    start_time = time.perf_counter()

    evaluated_origin = evaluate_stops_risk([origin])[0]
    evaluated_stops = evaluate_stops_risk(stops)

    if not evaluated_stops:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 4)
        return RoutePlan(
            origin=evaluated_origin,
            ordered_stops=[],
            total_distance_km=0.0,
            average_risk_score=0.0,
            algorithm_used="brute_force_exact",
            total_permutations_possible=1,
            computation_time_ms=elapsed_ms,
        )

    best_sequence: list[DeliveryStop] = list(evaluated_stops)
    best_cost = float("inf")

    for perm in itertools.permutations(evaluated_stops):
        cost = _sequence_weighted_cost(evaluated_origin, perm, alpha=alpha)
        if cost < best_cost:
            best_cost = cost
            best_sequence = list(perm)

    total_distance = _sequence_real_distance_km(evaluated_origin, best_sequence)
    avg_risk = round(
        sum(stop.risk_score for stop in best_sequence) / len(best_sequence),
        4,
    )
    total_perms = max(1, calculate_factorial(len(best_sequence)))
    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 4)

    return RoutePlan(
        origin=evaluated_origin,
        ordered_stops=best_sequence,
        total_distance_km=total_distance,
        average_risk_score=avg_risk,
        algorithm_used="brute_force_exact",
        total_permutations_possible=total_perms,
        computation_time_ms=elapsed_ms,
    )
