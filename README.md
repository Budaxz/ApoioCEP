# 📦 ApoioCEP - Painel de Apoio a Entregas com CEP e Clima

> **Projeto Prático da A3** — Disciplina de **Matemática Computacional Aplicada**  
> **Professores:** Aron e Cristiano | **Instituição:** UniCuritiba (Expounicuritiba)  
> **Repositório Oficial:** [github.com/Budaxz/ApoioCEP](https://github.com/Budaxz/ApoioCEP.git)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/ui-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked: Mypy](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](https://mypy-lang.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 📌 1. Visão Geral e Problema Real

### O Problema
Empresas de delivery urbano, entregadores autônomos e pequenos centros de distribuição enfrentam atrasos severos, avarias em mercadorias e riscos de acidentes causados por variações meteorológicas abruptas (tempestades repentinas, rajadas de vento e alagamentos). Planejar rotas considerando apenas a distância geográfica costuma direcionar entregadores para áreas críticas sob forte chuva.

### O Público-Alvo
* Entregadores autônomos e motoboys;
* Pequenos e médios comércios com logística própria de entrega rápida;
* Despachantes e operadores logísticos urbanos.

### A Solução: ApoioCEP
O **ApoioCEP** é um painel inteligente que integra **consulta geocodificada de CEPs brasileiros** à **previsão meteorológica hiperlocal em tempo real**. Através de modelos matemáticos de análise combinatória e um **Copiloto Agêntico de Despacho**, o sistema calcula rotas otimizadas, antecipa janelas de tempestade e sugere o sequenciamento mais seguro e eficiente para as entregas.

---

## 🧮 2. Conteúdos da Disciplina Aplicados

Conforme os requisitos da disciplina, o software implementa integralmente os seguintes tópicos:

| Tópico Estudado | Aplicação no ApoioCEP | Localização no Código |
| :--- | :--- | :--- |
| **Princípios de Contagem e Permutações ($n!$)** | Demonstração do limite da busca exata de rotas e cálculo do espaço amostral fatorial de itinerários. | [`src/mathematics/permutations.py`](src/mathematics/permutations.py) |
| **Grafos e Otimização Combinatória** | Algoritmo de roteirização Heurística Gulosa (*Nearest Neighbor*) com refinamento *2-Opt*. | [`src/mathematics/routing.py`](src/mathematics/routing.py) |
| **Álgebra e Espaço Métrico** | Cálculo de distâncias geodésicas (Haversine) entre coordenadas de latitude e longitude. | [`src/domain/address.py`](src/domain/address.py) |
| **Tratamento de Dados com Pandas** | Modelagem de DataFrames para agregação de rotas, janelas de entrega e relatórios analíticos. | [`src/services/route_analytics.py`](src/services/) |
| **Visualização com Plotly e PyDeck** | Gráficos de previsão de chuva/vento por horário e mapa geoespacial interativo de rotas. | [`src/ui/components/`](src/ui/components/) |
| **Consumo Resiliente de APIs Públicas** | Integração com as APIs abertas da **BrasilAPI**, **ViaCEP** e **Open-Meteo**. | [`src/services/`](src/services/) |

---

## 🏛️ 3. Arquitetura do Projeto e Regras de Pastas

A estrutura adota princípios de **Arquitetura Limpa (Clean Architecture)** e **Domain-Driven Design (DDD)** simplificado:

```
ApoioCEP/
│
├── config/             # Governança e configurações centrais (pydantic-settings)
│   └── settings.py     # Variáveis tipadas, URLs de APIs, tempos de timeout e cache
│
├── docs/               # Documentação técnica e material da Amostra A3
│   ├── arquitetura.md  # Diagramas de arquitetura, classes e fluxos C4
│   └── matematica_aplicada.md  # Formalização matemática de grafos, fatorial e probabilidade
│
├── data/               # Conjuntos de dados e mockups para testes e demonstração
│   └── mock_deliveries.json
│
├── src/                # Código-fonte principal da aplicação
│   ├── domain/         # Entidades puras de negócio com Pydantic v2 (Address, Stop, Forecast)
│   ├── services/       # Clientes HTTP assíncronos/síncronos com Tenacity e cache local
│   ├── mathematics/    # Módulos matemáticos de contagem, grafos e cálculo de risco
│   ├── agent/          # Copiloto Agêntico: motor de regras e recomendações proativas
│   └── ui/             # Camada de apresentação Streamlit (componentes e visualizações)
│
├── tests/              # Testes automatizados unitários e de integração (Pytest)
├── pyproject.toml      # Configuração de linters (Ruff) e checagem estática (Mypy)
├── requirements.txt    # Dependências do projeto
└── README.md           # Documentação oficial do projeto
```

### Regras de Governança
1. **Tipagem Estrita:** 100% das funções possuem anotações de tipo validadas pelo `mypy`.
2. **Governança de Dados:** Não trafegam dicionários puros (`dict`) entre serviços; todo dado é validado por modelos `Pydantic`.
3. **Resiliência:** Requisições a APIs públicas utilizam retries com *backoff exponencial* e camada de cache local para evitar bloqueios por *rate limiting*.
4. **Desacoplamento de UI:** A camada de UI em `src/ui/` não consome diretamente serviços externos; consome apenas o motor de domínio e o agente despachante.

---

## 🚀 4. Instalação e Execução

### Pré-requisitos
* **Python 3.10** ou superior instalado.
* Conexão com a internet (para consulta das APIs do Open-Meteo e BrasilAPI).

### Passo a Passo

1. **Clonar o Repositório:**
   ```bash
   git clone https://github.com/Budaxz/ApoioCEP.git
   cd ApoioCEP
   ```

2. **Criar e Ativar o Ambiente Virtual:**
   ```bash
   # Windows (PowerShell):
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Linux / macOS:
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instalar as Dependências:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Executar a Aplicação:**
   ```bash
   streamlit run src/app.py
   ```
   A interface abrirá automaticamente no navegador em `http://localhost:8501`.

---

## 🧪 5. Qualidade de Código e Testes

Para executar os testes automatizados e linters de governança:

```bash
# Executar a suíte de testes com Pytest:
pytest

# Verificar conformidade de estilo e boas práticas com Ruff:
ruff check .

# Executar checagem estática de tipos com Mypy:
mypy src/
```

---

## 📅 6. Cronograma de Entregas (A3 2026)

| Etapa | Data Limite | Status |
| :--- | :---: | :---: |
| **Proposta Formal** | 28/10/2026 | Concluída ✅ |
| **Protótipo Funcional** | 11/11/2026 | Em Andamento ⏳ |
| **Versão Final do Software** | 18/11/2026 | Planejada 📅 |
| **Apresentação do Pôster (Expounicuritiba)** | 01/12/2026 | Planejada 📅 |

---

## 👥 Equipe do Projeto
* Projeto desenvolvido para a Amostra da A3 — UniCuritiba.
* Disciplina: **Matemática Computacional Aplicada**.
* Cristian A. Tavares
* Pedro H. P. Moreira
* Pedro V. Budasz

