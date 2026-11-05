# 🧮 Fundamentos de Matemática Computacional Aplicada

Este documento detalha os conceitos matemáticos estudados com os professores **Aron** e **Cristiano** aplicados no **ApoioCEP**.

---

## 1. Princípios de Contagem e Análise Combinatória

### 1.1 O Desafio da Roteirização por Força Bruta (Permutação Simples)
Dado um conjunto de $n$ pontos de entrega partindo de uma base de distribuição central, o número de rotas possíveis visitando cada ponto exatamente uma vez corresponde a uma **permutação simples**:

$$P_n = n!$$

| Número de Entregas ($n$) | Rotas Possíveis ($n!$) | Tempo Estimado de Cálculo (Força Bruta) |
| :---: | :---: | :---: |
| 4 | 24 | $< 1$ milissegundo |
| 8 | 40.320 | $\approx 25$ milissegundos |
| 10 | 3.628.800 | $\approx 2,1$ segundos |
| 12 | 479.001.600 | $\approx 5$ minutos |
| 15 | 1.307.674.368.000 | $> 15$ dias |

### 1.2 Transição para Heurísticas Polinomiais
Para resolver a explosão combinatória $O(n!)$, o ApoioCEP implementa:
1. **Heurística do Vizinho Mais Próximo (*Nearest Neighbor*):** Complexidade $O(n^2)$. A partir do ponto de partida, o algoritmo seleciona iterativamente o vértice de menor custo euclidiano ponderado pelo risco climático.
2. **Refinamento *2-Opt*:** Elimina cruzamentos de arestas no grafo da rota, garantindo convergência rápida para um ótimo local de alta qualidade.

---

## 2. Distância Euclidiana e Espaço Métrico

As coordenadas geográficas (Latitude $\phi$, Longitude $\lambda$) são projetadas no plano métrico por aproximação ou cálculo de Haversine:

$$d = 2R \cdot \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)}\right)$$

Onde $R \approx 6.371\text{ km}$ é o raio médio da Terra.

---

## 3. Matriz Probabilística de Risco Climático

Para cada ponto de entrega $i$ na janela horária $t$, calculamos um **Índice de Risco Logístico ($R_{i,t}$)** normalizado no intervalo $[0, 1]$:

$$R_{i,t} = w_1 \cdot f_{\text{chuva}}(p_{i,t}) + w_2 \cdot f_{\text{vento}}(v_{i,t}) + w_3 \cdot f_{\text{prio}}(P_i)$$

Onde:
- $p_{i,t}$: Volume de precipitação previsto (mm/h)
- $v_{i,t}$: Velocidade do vento / rajadas (km/h)
- $P_i$: Prioridade do pacote
- $\sum_{k=1}^3 w_k = 1$ (Pesos ponderados)

O custo da aresta entre a parada $i$ e $j$ na rota torna-se:

$$C_{i,j} = d_{i,j} \cdot (1 + \alpha \cdot R_{j,t})$$

Desta forma, o algoritmo prioriza evitar áreas sob tempestade iminente, antecipando entregas críticas para janelas de tempo seco.
