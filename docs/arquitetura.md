# 📐 Arquitetura do ApoioCEP

Este documento descreve as decisões arquiteturais, padrões de projeto e o fluxo de dados do sistema **ApoioCEP** (*Painel de apoio a entregas com CEP e clima*).

---

## 1. Visão Geral da Arquitetura

O sistema adota os princípios de **Clean Architecture** (Arquitetura Limpa) e **Domain-Driven Design (DDD)** simplificado para Python, garantindo desacoplamento entre regras de negócio, serviços de infraestrutura e a camada de interface gráfica.

```mermaid
flowchart TD
    subgraph UI ["Camada de Apresentação (Streamlit)"]
        DASH["Dashboard & Métricas"]
        MAP["Mapa Geoespacial (PyDeck)"]
        CHART["Gráficos de Clima (Plotly)"]
        LAB["Math Lab (Permutações/Grafos)"]
    end

    subgraph AGENT ["Camada Agêntica / Decisão"]
        DISPATCHER["Dispatcher Copilot Agent<br/>(Regras de Inferência e Otimização)"]
    end

    subgraph DOMAIN ["Camada de Domínio (Pydantic v2)"]
        ADDR["Address & Coordinates"]
        WEATHER["WeatherForecast & RiskLevel"]
        DELIVERY["DeliveryStop & RoutePlan"]
    end

    subgraph MATH ["Motor Matemático Computacional"]
        PERM["Permutação & Fatorial"]
        ROUTING["Nearest Neighbor & 2-Opt"]
        RISK["Matriz de Risco Climático"]
    end

    subgraph SERVICES ["Camada de Serviços & Infraestrutura"]
        CEP_SRV["CEP Service (BrasilAPI / ViaCEP)"]
        METEO_SRV["Weather Service (Open-Meteo)"]
        CACHE["Cache Local (TTL / SQLite)"]
    end

    UI --> AGENT
    AGENT --> MATH
    AGENT --> DOMAIN
    MATH --> DOMAIN
    UI --> SERVICES
    SERVICES --> CACHE
    SERVICES --> DOMAIN
```

---

## 2. Descrição das Camadas e Regras de Cada Pasta

| Diretório | Responsabilidade | Regra de Governança |
| :--- | :--- | :--- |
| `config/` | Configurações globais e leitura de variáveis de ambiente. | Utilizar `pydantic-settings`. Proibido `hardcode` de URLs ou timeouts no código de serviço. |
| `src/domain/` | Modelos de dados puros e invariantes de negócio. | Devem herdar de `pydantic.BaseModel`. Proibido conter lógica de IO ou chamadas de rede. |
| `src/services/` | Comunicação com APIs externas e persistência de cache. | Devem implementar retries (`tenacity`), tratamento de falhas e fallback entre provedores. |
| `src/mathematics/` | Implementação formal dos tópicos de Matemática Computacional. | Funções puras e sem efeitos colaterais. Devem possuir anotações de complexidade $O(f(n))$. |
| `src/agent/` | Inteligência agêntica e regras de despacho inteligente. | Cruza as restrições de entregas com os vetores climáticos para emitir alertas e reordenar rotas. |
| `src/ui/` | Componentes visuais e visualizações analíticas em Streamlit. | Proibido chamar APIs externas diretamente; deve sempre consumir `services` e `agent`. |
| `tests/` | Suíte de testes unitários e de integração com `pytest`. | Cobertura mínima nas camadas `domain`, `mathematics` e `services`. |
| `data/` | Massas de dados fictícios para demonstração e mockups. | Arquivos JSON estáticos e dados em conformidade com a LGPD. |

---

## 3. Fluxo de Dados e Resiliência

```mermaid
sequenceDiagram
    autonumber
    actor Operador as Operador Logístico
    participant UI as Interface Web (Streamlit)
    participant Agent as Dispatcher Copilot
    participant CEPSrv as Serviço de CEP
    participant MeteoSrv as Serviço de Clima
    participant Math as Motor Matemático

    Operador->>UI: Insere lista de CEPs de entrega
    UI->>CEPSrv: Consulta endereço e coordenadas
    alt Cache presente
        CEPSrv-->>UI: Retorna dados cacheados
    else Cache ausente
        CEPSrv->>CEPSrv: Consulta BrasilAPI (com fallback ViaCEP)
        CEPSrv-->>UI: Retorna coordenadas (Lat/Long)
    end

    UI->>MeteoSrv: Consulta previsão do tempo para as coordenadas
    MeteoSrv-->>UI: Retorna curvas de chuva, temperatura e vento
    
    UI->>Agent: Solicita análise e otimização da rota
    Agent->>Math: Executa Heurística de Roteamento + Matriz de Risco
    Math-->>Agent: Retorna rota ótima ponderada pelo clima
    Agent-->>UI: Exibe recomendações, mapas interativos e alertas proativos
```

---

## 4. Governança e Performance

1. **Validação Estrita:** Nenhum dado não validado transita entre camadas.
2. **Resiliência:** Tolerância a falhas transitórias com backoff exponencial.
3. **Cache Inteligente:** Reduz em até 95% o número de requisições externas para consultas recorrentes na mesma região.
